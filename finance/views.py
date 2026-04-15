import csv
import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from accounts.decorators import role_required
from accounts.mixins import AdminOrCoachRequiredMixin, AdminRequiredMixin
from accounts.utils import ROLE_ADMIN, ROLE_COACH, has_role
from finance.forms import (
    BillingConfigurationForm,
    ExpenseEntryForm,
    ForecastScenarioForm,
    HistoricalLockForm,
    InvoiceForm,
    PaymentPlanForm,
    PayrollRecordForm,
    ProductForm,
)
from finance.models import (
    BillingConfiguration,
    ExpenseEntry,
    ForecastScenario,
    HistoricalLock,
    Invoice,
    PaymentPlan,
    PayrollRecord,
    Product,
)
from finance.services import billing_context_data, build_branch_choices, build_finance_snapshot, format_ringgit
from members.models import Member
from payments.models import Payment


def visible_invoices_for_user(user):
    queryset = (
        Invoice.objects.select_related("member", "member__assigned_coach", "member__parent_user", "member__payment_plan", "payment_plan")
        .prefetch_related("payments", "member__admission_applications")
        .order_by("-period", "member__full_name")
    )
    if has_role(user, ROLE_COACH) and not has_role(user, ROLE_ADMIN):
        return queryset.filter(member__assigned_coach=user)
    return queryset


def visible_products_for_user(user):
    queryset = Product.objects.select_related("created_by", "updated_by")
    if has_role(user, ROLE_ADMIN):
        return queryset
    return queryset.filter(is_active=True)


def visible_payroll_for_user(user):
    queryset = PayrollRecord.objects.select_related("coach", "created_by", "updated_by").order_by("-period", "coach__username")
    if has_role(user, ROLE_COACH) and not has_role(user, ROLE_ADMIN):
        return queryset.filter(coach=user)
    return queryset


def chart_payload(labels, datasets):
    return json.dumps({"labels": labels, "datasets": datasets})


class FinanceOverviewView(AdminRequiredMixin, TemplateView):
    template_name = "finance/overview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        snapshot = build_finance_snapshot()
        chart = snapshot["chart"]
        context.update(snapshot)
        context.update(billing_context_data())
        context["quick_sections"] = [
            ("revenue", "Revenue"),
            ("collections", "Payment & Collection"),
            ("expenses", "Expenses"),
            ("payroll", "Payroll"),
            ("profit-loss", "Profit & Loss"),
            ("cashflow", "Cashflow"),
            ("forecasting", "Forecasting"),
            ("compliance", "Report & Compliance"),
        ]
        context["revenue_chart_data"] = chart_payload(
            chart["labels"],
            [
                {
                    "label": "Revenue Trend",
                    "data": chart["revenue"],
                    "borderColor": "#4f6ef7",
                    "backgroundColor": "rgba(79,110,247,0.16)",
                    "borderWidth": 3,
                    "fill": True,
                    "tension": 0.35,
                }
            ],
        )
        context["cashflow_chart_data"] = chart_payload(
            chart["labels"],
            [
                {
                    "label": "Cash In",
                    "data": chart["cash_in"],
                    "borderColor": "#22c55e",
                    "backgroundColor": "rgba(34,197,94,0.12)",
                    "borderWidth": 3,
                    "fill": False,
                    "tension": 0.35,
                },
                {
                    "label": "Cash Out",
                    "data": chart["cash_out"],
                    "borderColor": "#ef4444",
                    "backgroundColor": "rgba(239,68,68,0.12)",
                    "borderWidth": 3,
                    "fill": False,
                    "tension": 0.35,
                },
                {
                    "label": "Net Cashflow",
                    "data": chart["net_cashflow"],
                    "borderColor": "#f59e0b",
                    "backgroundColor": "rgba(245,158,11,0.12)",
                    "borderWidth": 3,
                    "fill": False,
                    "tension": 0.35,
                },
            ],
        )
        context["payment_method_chart_data"] = chart_payload(
            [label for label, _ in snapshot["payment_method_totals"]],
            [
                {
                    "data": [float(amount) for _, amount in snapshot["payment_method_totals"]],
                    "backgroundColor": ["#4f6ef7", "#22c55e", "#f59e0b", "#06b6d4", "#a855f7"],
                    "borderWidth": 0,
                }
            ],
        )
        return context


class BillingSettingsView(AdminRequiredMixin, UpdateView):
    model = BillingConfiguration
    form_class = BillingConfigurationForm
    template_name = "finance/billing_settings.html"
    success_url = reverse_lazy("finance:billing_settings")

    def get_object(self, queryset=None):
        return BillingConfiguration.get_solo()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["payment_plans"] = PaymentPlan.objects.order_by("sort_order", "sessions_per_month", "monthly_fee", "name")
        context.update(billing_context_data())
        return context

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Billing settings updated successfully.")
        return response


class PaymentPlanCreateView(AdminRequiredMixin, CreateView):
    model = PaymentPlan
    form_class = PaymentPlanForm
    template_name = "finance/payment_plan_form.html"
    success_url = reverse_lazy("finance:billing_settings")

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Payment plan created successfully.")
        return response


class PaymentPlanUpdateView(AdminRequiredMixin, UpdateView):
    model = PaymentPlan
    form_class = PaymentPlanForm
    template_name = "finance/payment_plan_form.html"
    success_url = reverse_lazy("finance:billing_settings")

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Payment plan updated successfully.")
        return response


class InvoiceListView(AdminOrCoachRequiredMixin, ListView):
    model = Invoice
    template_name = "finance/invoice_list.html"
    context_object_name = "invoices"
    paginate_by = 12

    def get_queryset(self):
        queryset = visible_invoices_for_user(self.request.user)
        status = self.request.GET.get("status", "").strip()
        member = self.request.GET.get("member", "").strip()
        branch = self.request.GET.get("branch", "").strip()
        if status:
            queryset = queryset.filter(status=status)
        if member:
            queryset = queryset.filter(member_id=member)
        if branch:
            queryset = [invoice for invoice in queryset if invoice.branch_label == branch]
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invoice_rows = list(context["invoices"])
        context["statuses"] = Invoice.STATUS_CHOICES
        context["is_admin"] = has_role(self.request.user, ROLE_ADMIN)
        context["can_manage"] = has_role(self.request.user, ROLE_ADMIN)
        context["members"] = visible_invoices_for_user(self.request.user).values_list("member_id", "member__full_name").distinct()
        context["branches"] = build_branch_choices()
        context["approved_total"] = sum(Decimal(invoice.approved_amount or 0) for invoice in invoice_rows)
        context["outstanding_total"] = sum(Decimal(invoice.outstanding_amount or 0) for invoice in invoice_rows)
        return context


class InvoiceCreateView(AdminRequiredMixin, CreateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = "finance/invoice_form.html"
    success_url = reverse_lazy("finance:invoice_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["current_user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        self.object.refresh_status_from_payments()
        messages.success(self.request, "Invoice generated successfully.")
        return response


class InvoiceUpdateView(AdminRequiredMixin, UpdateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = "finance/invoice_form.html"
    success_url = reverse_lazy("finance:invoice_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["current_user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        self.object.refresh_status_from_payments()
        messages.success(self.request, "Invoice updated successfully.")
        return response


class ExpenseListView(AdminRequiredMixin, ListView):
    model = ExpenseEntry
    template_name = "finance/expense_list.html"
    context_object_name = "expenses"
    paginate_by = 12

    def get_queryset(self):
        queryset = ExpenseEntry.objects.order_by("-expense_date", "-created_at")
        expense_type = self.request.GET.get("expense_type", "").strip()
        category = self.request.GET.get("category", "").strip()
        branch = self.request.GET.get("branch", "").strip()
        search = self.request.GET.get("q", "").strip()
        if expense_type:
            queryset = queryset.filter(expense_type=expense_type)
        if category:
            queryset = queryset.filter(category_tag=category)
        if branch:
            queryset = queryset.filter(branch_tag=branch)
        if search:
            queryset = queryset.filter(Q(title__icontains=search) | Q(vendor_name__icontains=search) | Q(notes__icontains=search))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        expense_rows = list(context["expenses"])
        context["expense_types"] = ExpenseEntry.TYPE_CHOICES
        context["categories"] = ExpenseEntry.CATEGORY_CHOICES
        context["branches"] = build_branch_choices()
        context["total_expenses"] = sum(Decimal(expense.amount or 0) for expense in expense_rows)
        context["fixed_total"] = sum(Decimal(expense.amount or 0) for expense in expense_rows if expense.expense_type == ExpenseEntry.TYPE_FIXED)
        context["variable_total"] = sum(Decimal(expense.amount or 0) for expense in expense_rows if expense.expense_type == ExpenseEntry.TYPE_VARIABLE)
        return context


class ExpenseCreateView(AdminRequiredMixin, CreateView):
    model = ExpenseEntry
    form_class = ExpenseEntryForm
    template_name = "finance/expense_form.html"
    success_url = reverse_lazy("finance:expense_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Expense recorded successfully.")
        return response


class ExpenseUpdateView(AdminRequiredMixin, UpdateView):
    model = ExpenseEntry
    form_class = ExpenseEntryForm
    template_name = "finance/expense_form.html"
    success_url = reverse_lazy("finance:expense_list")

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Expense updated successfully.")
        return response


class PayrollListView(AdminOrCoachRequiredMixin, ListView):
    model = PayrollRecord
    template_name = "finance/payroll_list.html"
    context_object_name = "payroll_records"
    paginate_by = 12

    def get_queryset(self):
        queryset = visible_payroll_for_user(self.request.user)
        coach = self.request.GET.get("coach", "").strip()
        status = self.request.GET.get("status", "").strip()
        if coach and has_role(self.request.user, ROLE_ADMIN):
            queryset = queryset.filter(coach_id=coach)
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payroll_rows = list(context["payroll_records"])
        context["statuses"] = PayrollRecord.STATUS_CHOICES
        context["coaches"] = Member.objects.filter(assigned_coach__isnull=False).values_list(
            "assigned_coach_id", "assigned_coach__username"
        ).distinct()
        context["can_manage"] = has_role(self.request.user, ROLE_ADMIN)
        context["is_coach_view"] = has_role(self.request.user, ROLE_COACH) and not has_role(self.request.user, ROLE_ADMIN)
        context["total_payroll"] = sum(Decimal(record.total_pay or 0) for record in payroll_rows)
        context["paid_total"] = sum(
            Decimal(record.total_pay or 0) for record in payroll_rows if record.status == PayrollRecord.STATUS_PAID
        )
        return context


class PayrollCreateView(AdminRequiredMixin, CreateView):
    model = PayrollRecord
    form_class = PayrollRecordForm
    template_name = "finance/payroll_form.html"
    success_url = reverse_lazy("finance:payroll")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["current_user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Payroll record created successfully.")
        return response


class PayrollUpdateView(AdminRequiredMixin, UpdateView):
    model = PayrollRecord
    form_class = PayrollRecordForm
    template_name = "finance/payroll_form.html"
    success_url = reverse_lazy("finance:payroll")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["current_user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Payroll record updated successfully.")
        return response


class ForecastScenarioListView(AdminRequiredMixin, TemplateView):
    template_name = "finance/forecast_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        scenarios = list(ForecastScenario.objects.order_by("-is_primary", "title"))
        scenario_rows = []
        for scenario in scenarios:
            forecast = build_finance_snapshot(today=today, scenario=scenario)["forecast"]
            scenario_rows.append({"scenario": scenario, "forecast": forecast})
        context["scenario_rows"] = scenario_rows
        context["primary_snapshot"] = build_finance_snapshot(today=today)
        return context


class ForecastScenarioCreateView(AdminRequiredMixin, CreateView):
    model = ForecastScenario
    form_class = ForecastScenarioForm
    template_name = "finance/forecast_form.html"
    success_url = reverse_lazy("finance:forecasting")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Forecast scenario created successfully.")
        return response


class ForecastScenarioUpdateView(AdminRequiredMixin, UpdateView):
    model = ForecastScenario
    form_class = ForecastScenarioForm
    template_name = "finance/forecast_form.html"
    success_url = reverse_lazy("finance:forecasting")

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Forecast scenario updated successfully.")
        return response


class ComplianceView(AdminRequiredMixin, TemplateView):
    template_name = "finance/compliance.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        snapshot = build_finance_snapshot()
        context.update(snapshot)
        context["historical_lock_form"] = HistoricalLockForm()
        return context


class HistoricalLockCreateView(AdminRequiredMixin, CreateView):
    model = HistoricalLock
    form_class = HistoricalLockForm
    template_name = "finance/historical_lock_form.html"
    success_url = reverse_lazy("finance:compliance")

    def form_valid(self, form):
        form.instance.locked_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Historical lock updated successfully.")
        return response


class HistoricalLockUpdateView(AdminRequiredMixin, UpdateView):
    model = HistoricalLock
    form_class = HistoricalLockForm
    template_name = "finance/historical_lock_form.html"
    success_url = reverse_lazy("finance:compliance")

    def form_valid(self, form):
        form.instance.locked_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Historical lock updated successfully.")
        return response


class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = "finance/product_list.html"
    context_object_name = "products"
    paginate_by = 12

    def get_queryset(self):
        queryset = visible_products_for_user(self.request.user)
        availability = self.request.GET.get("availability", "").strip()
        search = self.request.GET.get("q", "").strip()
        if availability:
            queryset = queryset.filter(availability=availability)
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        visible_products = visible_products_for_user(self.request.user)
        context["availability_choices"] = Product.AVAILABILITY_CHOICES
        context["can_manage"] = has_role(self.request.user, ROLE_ADMIN)
        context["total_products"] = visible_products.count()
        context["ready_products"] = visible_products.filter(availability=Product.AVAILABILITY_READY).count()
        context["preorder_products"] = visible_products.filter(availability=Product.AVAILABILITY_PREORDER).count()
        context["search_query"] = self.request.GET.get("q", "").strip()
        context["selected_availability"] = self.request.GET.get("availability", "").strip()
        return context


class ProductDetailView(LoginRequiredMixin, DetailView):
    model = Product
    template_name = "finance/product_detail.html"
    context_object_name = "product"

    def get_queryset(self):
        return visible_products_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_manage"] = has_role(self.request.user, ROLE_ADMIN)
        context["related_products"] = visible_products_for_user(self.request.user).exclude(pk=self.object.pk).order_by("name")[:4]
        return context


class ProductCreateView(AdminRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = "finance/product_form.html"
    success_url = reverse_lazy("finance:product_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Product created successfully.")
        return response


class ProductUpdateView(AdminRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = "finance/product_form.html"
    success_url = reverse_lazy("finance:product_list")

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Product updated successfully.")
        return response


class ProductDeleteView(AdminRequiredMixin, DeleteView):
    model = Product
    template_name = "finance/product_confirm_delete.html"
    success_url = reverse_lazy("finance:product_list")

    def form_valid(self, form):
        messages.success(self.request, "Product deleted successfully.")
        return super().form_valid(form)


@role_required(ROLE_ADMIN)
def export_finance_csv(request):
    snapshot = build_finance_snapshot()
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="finance-export.csv"'
    writer = csv.writer(response)

    writer.writerow(["Finance Report Export", timezone.localdate()])
    writer.writerow([])
    writer.writerow(["Summary"])
    writer.writerow(["Monthly recurring revenue", snapshot["monthly_recurring_revenue"]])
    writer.writerow(["Revenue this month", snapshot["revenue_this_month"]])
    writer.writerow(["Total expenses", snapshot["total_expenses"]])
    writer.writerow(["Net profit", snapshot["net_profit"]])
    writer.writerow(["Cash balance", snapshot["cash_balance"]])
    writer.writerow([])

    writer.writerow(["Invoices"])
    writer.writerow(["Student", "Type", "Period", "Branch", "Amount", "Approved", "Outstanding", "Status", "Due date"])
    for invoice in snapshot["invoice_rows"]:
        writer.writerow(
            [
                invoice.student_label,
                invoice.get_invoice_type_display(),
                invoice.period,
                invoice.branch_label,
                invoice.amount,
                invoice.approved_amount,
                invoice.outstanding_amount,
                invoice.get_status_display(),
                invoice.due_date,
            ]
        )

    writer.writerow([])
    writer.writerow(["Expenses"])
    writer.writerow(["Date", "Title", "Type", "Category", "Branch", "Amount", "Payment Method"])
    for expense in snapshot["expenses"][:200]:
        writer.writerow(
            [
                expense.expense_date,
                expense.title,
                expense.get_expense_type_display(),
                expense.get_category_tag_display(),
                expense.branch_label,
                expense.amount,
                expense.get_payment_method_display(),
            ]
        )

    writer.writerow([])
    writer.writerow(["Payroll"])
    writer.writerow(["Coach", "Period", "Branch", "Status", "Sessions", "Total Pay"])
    for payroll in snapshot["all_payroll_rows"][:200]:
        writer.writerow(
            [
                payroll.coach.get_full_name() or payroll.coach.username,
                payroll.period,
                payroll.branch_label,
                payroll.get_status_display(),
                payroll.session_count,
                payroll.total_pay,
            ]
        )
    return response
