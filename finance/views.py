import csv
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
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


class FinanceOverviewView(AdminRequiredMixin, TemplateView):
    template_name = "finance/overview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        current_month_invoices = Invoice.objects.filter(period__year=today.year, period__month=today.month)
        approved_payments = Payment.objects.filter(status=Payment.STATUS_APPROVED)
        context.update(
            {
                "total_collected": approved_payments.filter(
                    reviewed_at__year=today.year,
                    reviewed_at__month=today.month,
                ).aggregate(total=Sum("invoice__amount"))["total"]
                or Decimal("0.00"),
                "outstanding_balances": Invoice.objects.exclude(status=Invoice.STATUS_PAID).aggregate(total=Sum("amount"))[
                    "total"
                ]
                or Decimal("0.00"),
                "recent_payments": Payment.objects.select_related("invoice", "invoice__member", "paid_by", "reviewed_by")
                .order_by("-submitted_at")[:10],
                "invoice_rows": current_month_invoices.order_by("member__full_name")[:10],
                "payment_plan_count": PaymentPlan.objects.count(),
                "active_payment_plan_count": PaymentPlan.objects.filter(is_active=True).count(),
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
