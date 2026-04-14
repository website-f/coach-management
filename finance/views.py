import csv
import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncMonth
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from accounts.decorators import role_required
from accounts.mixins import AdminOrCoachRequiredMixin, AdminRequiredMixin
from accounts.utils import ROLE_ADMIN, ROLE_COACH, has_role
from finance.forms import BillingConfigurationForm, InvoiceForm, PaymentPlanForm, ProductForm
from finance.models import BillingConfiguration, Invoice, PaymentPlan, Product
from finance.services import billing_context_data
from members.models import Member
from payments.models import Payment


def visible_invoices_for_user(user):
    queryset = Invoice.objects.select_related(
        "member",
        "member__assigned_coach",
        "member__parent_user",
        "member__payment_plan",
        "payment_plan",
    )
    if has_role(user, ROLE_COACH) and not has_role(user, ROLE_ADMIN):
        return queryset.filter(member__assigned_coach=user)
    return queryset


def visible_products_for_user(user):
    queryset = Product.objects.select_related("created_by", "updated_by")
    if has_role(user, ROLE_ADMIN):
        return queryset
    return queryset.filter(is_active=True)


def shift_month(source_date, delta):
    month_index = source_date.month - 1 + delta
    year = source_date.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def build_cashflow_labels(month_count=6):
    current = timezone.localdate().replace(day=1)
    return [shift_month(current, offset) for offset in range(-(month_count - 1), 1)]


def normalize_month_key(value):
    if hasattr(value, "date"):
        value = value.date()
    return value.replace(day=1)


class FinanceOverviewView(AdminRequiredMixin, TemplateView):
    template_name = "finance/overview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        week_ahead = today + timedelta(days=7)
        months = build_cashflow_labels()
        month_labels = [month.strftime("%b %Y") for month in months]
        zero_money = Value(Decimal("0.00"), output_field=DecimalField(max_digits=10, decimal_places=2))

        invoices = Invoice.objects.select_related("member", "member__assigned_coach", "payment_plan")
        payments = Payment.objects.select_related("invoice", "invoice__member", "paid_by", "reviewed_by")
        approved_payments = payments.filter(status=Payment.STATUS_APPROVED)
        current_month_invoices = invoices.filter(period__year=today.year, period__month=today.month)
        outstanding_invoices = invoices.exclude(status=Invoice.STATUS_PAID)
        overdue_invoices = outstanding_invoices.filter(due_date__lt=today)

        total_billed = current_month_invoices.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        total_collected = (
            approved_payments.filter(reviewed_at__year=today.year, reviewed_at__month=today.month).aggregate(
                total=Sum("invoice__amount")
            )["total"]
            or Decimal("0.00")
        )
        pending_verification_total = (
            invoices.filter(status=Invoice.STATUS_PENDING).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        )
        outstanding_balances = outstanding_invoices.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        overdue_total = overdue_invoices.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        collection_rate = round((total_collected / total_billed) * 100, 1) if total_billed else 0
        projected_mrr = (
            Member.objects.filter(status=Member.STATUS_ACTIVE).aggregate(total=Sum("payment_plan__monthly_fee"))["total"]
            or Decimal("0.00")
        )

        billed_map = {
            normalize_month_key(item["month"]): item["total"] or Decimal("0.00")
            for item in invoices.annotate(month=TruncMonth("period")).values("month").annotate(total=Sum("amount"))
            if item["month"]
        }
        collected_map = {
            normalize_month_key(item["month"]): item["total"] or Decimal("0.00")
            for item in approved_payments.annotate(month=TruncMonth("reviewed_at")).values("month").annotate(
                total=Sum("invoice__amount")
            )
            if item["month"]
        }
        overdue_map = {
            normalize_month_key(item["month"]): item["total"] or Decimal("0.00")
            for item in overdue_invoices.annotate(month=TruncMonth("due_date")).values("month").annotate(total=Sum("amount"))
            if item["month"]
        }

        billed_values = [float(billed_map.get(month, Decimal("0.00"))) for month in months]
        collected_values = [float(collected_map.get(month, Decimal("0.00"))) for month in months]
        overdue_values = [float(overdue_map.get(month, Decimal("0.00"))) for month in months]

        aging_buckets = {
            "current": Decimal("0.00"),
            "days_1_30": Decimal("0.00"),
            "days_31_60": Decimal("0.00"),
            "days_61_plus": Decimal("0.00"),
        }
        for invoice in outstanding_invoices:
            days_overdue = (today - invoice.due_date).days
            if days_overdue <= 0:
                aging_buckets["current"] += invoice.amount
            elif days_overdue <= 30:
                aging_buckets["days_1_30"] += invoice.amount
            elif days_overdue <= 60:
                aging_buckets["days_31_60"] += invoice.amount
            else:
                aging_buckets["days_61_plus"] += invoice.amount

        plan_rows = list(
            PaymentPlan.objects.annotate(
                active_members=Count("members", filter=Q(members__status=Member.STATUS_ACTIVE), distinct=True)
            ).order_by("sort_order", "sessions_per_month", "monthly_fee", "name")
        )
        for plan in plan_rows:
            plan.projected_revenue = plan.monthly_fee * plan.active_members

        coach_rows = []
        coach_queryset = (
            Member.objects.filter(assigned_coach__isnull=False)
            .values("assigned_coach__first_name", "assigned_coach__last_name", "assigned_coach__username")
            .annotate(
                active_students=Count("id", filter=Q(status=Member.STATUS_ACTIVE), distinct=True),
                outstanding_total=Coalesce(
                    Sum("invoices__amount", filter=~Q(invoices__status=Invoice.STATUS_PAID)),
                    zero_money,
                ),
                collected_this_month=Coalesce(
                    Sum(
                        "invoices__amount",
                        filter=Q(
                            invoices__payments__status=Payment.STATUS_APPROVED,
                            invoices__payments__reviewed_at__year=today.year,
                            invoices__payments__reviewed_at__month=today.month,
                        ),
                    ),
                    zero_money,
                ),
            )
            .order_by("-collected_this_month", "-active_students")
        )
        for item in coach_queryset:
            coach_name = (
                f"{item['assigned_coach__first_name']} {item['assigned_coach__last_name']}".strip()
                or item["assigned_coach__username"]
            )
            coach_rows.append(
                {
                    "coach_name": coach_name,
                    "active_students": item["active_students"],
                    "outstanding_total": item["outstanding_total"],
                    "collected_this_month": item["collected_this_month"],
                }
            )

        due_soon_rows = outstanding_invoices.filter(due_date__range=(today, week_ahead)).order_by("due_date", "member__full_name")[:8]
        recent_payments = payments.order_by("-submitted_at")[:10]
        invoice_rows = current_month_invoices.order_by("member__full_name")[:10]

        context.update(
            {
                "total_billed": total_billed,
                "total_collected": total_collected,
                "outstanding_balances": outstanding_balances,
                "pending_verification_total": pending_verification_total,
                "overdue_total": overdue_total,
                "collection_rate": collection_rate,
                "projected_mrr": projected_mrr,
                "recent_payments": recent_payments,
                "invoice_rows": invoice_rows,
                "payment_plan_count": PaymentPlan.objects.count(),
                "active_payment_plan_count": PaymentPlan.objects.filter(is_active=True).count(),
                "due_soon_rows": due_soon_rows,
                "aging_buckets": aging_buckets,
                "plan_rows": plan_rows,
                "coach_rows": coach_rows[:8],
                "cashflow_chart_data": json.dumps(
                    {
                        "labels": month_labels,
                        "datasets": [
                            {
                                "label": "Billed",
                                "data": billed_values,
                                "borderColor": "#4f6ef7",
                                "backgroundColor": "rgba(79, 110, 247, 0.18)",
                                "borderWidth": 3,
                                "fill": False,
                                "tension": 0.3,
                            },
                            {
                                "label": "Collected",
                                "data": collected_values,
                                "borderColor": "#22c55e",
                                "backgroundColor": "rgba(34, 197, 94, 0.14)",
                                "borderWidth": 3,
                                "fill": False,
                                "tension": 0.3,
                            },
                            {
                                "label": "Overdue",
                                "data": overdue_values,
                                "borderColor": "#ef4444",
                                "backgroundColor": "rgba(239, 68, 68, 0.12)",
                                "borderWidth": 2,
                                "fill": False,
                                "tension": 0.25,
                            },
                        ],
                    }
                ),
                "receivable_chart_data": json.dumps(
                    {
                        "labels": ["Current", "1-30 Days", "31-60 Days", "61+ Days"],
                        "datasets": [
                            {
                                "data": [
                                    float(aging_buckets["current"]),
                                    float(aging_buckets["days_1_30"]),
                                    float(aging_buckets["days_31_60"]),
                                    float(aging_buckets["days_61_plus"]),
                                ],
                                "backgroundColor": ["#4f6ef7", "#f59e0b", "#fb7185", "#ef4444"],
                                "borderWidth": 0,
                            }
                        ],
                    }
                ),
            }
        )
        context.update(billing_context_data())
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
    paginate_by = 10

    def get_queryset(self):
        queryset = visible_invoices_for_user(self.request.user)
        status = self.request.GET.get("status", "").strip()
        member = self.request.GET.get("member", "").strip()
        if status:
            queryset = queryset.filter(status=status)
        if member:
            queryset = queryset.filter(member_id=member)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["statuses"] = Invoice.STATUS_CHOICES
        context["is_admin"] = has_role(self.request.user, ROLE_ADMIN)
        context["can_manage"] = has_role(self.request.user, ROLE_ADMIN)
        context["members"] = visible_invoices_for_user(self.request.user).values_list("member_id", "member__full_name").distinct()
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
        messages.success(self.request, "Invoice updated successfully.")
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
        context["related_products"] = (
            visible_products_for_user(self.request.user)
            .exclude(pk=self.object.pk)
            .order_by("name")[:4]
        )
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
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="finance-report.csv"'
    writer = csv.writer(response)
    writer.writerow(["Member", "Type", "Period", "Amount", "Status", "Due Date"])
    for invoice in Invoice.objects.select_related("member").order_by("-period"):
        writer.writerow(
            [
                invoice.member.full_name,
                invoice.get_invoice_type_display(),
                invoice.period,
                invoice.amount,
                invoice.status,
                invoice.due_date,
            ]
        )
    return response

# Create your views here.
