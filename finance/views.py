import csv
from decimal import Decimal

from django.contrib import messages
from django.db.models import Sum
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from accounts.decorators import role_required
from accounts.mixins import AdminOrCoachRequiredMixin, AdminRequiredMixin
from accounts.utils import ROLE_ADMIN, ROLE_COACH, has_role
from finance.forms import InvoiceForm
from finance.models import Invoice
from payments.models import Payment


def visible_invoices_for_user(user):
    queryset = Invoice.objects.select_related("member", "member__assigned_coach", "member__parent_user")
    if has_role(user, ROLE_COACH) and not has_role(user, ROLE_ADMIN):
        return queryset.filter(member__assigned_coach=user)
    return queryset


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
            }
        )
        return context


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
        context["members"] = visible_invoices_for_user(self.request.user).values_list("member_id", "member__full_name").distinct()
        return context


class InvoiceCreateView(AdminOrCoachRequiredMixin, CreateView):
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


class InvoiceUpdateView(AdminOrCoachRequiredMixin, UpdateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = "finance/invoice_form.html"
    success_url = reverse_lazy("finance:invoice_list")

    def get_queryset(self):
        return visible_invoices_for_user(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["current_user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Invoice updated successfully.")
        return response


@role_required(ROLE_ADMIN)
def export_finance_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="finance-report.csv"'
    writer = csv.writer(response)
    writer.writerow(["Member", "Period", "Amount", "Status", "Due Date"])
    for invoice in Invoice.objects.select_related("member").order_by("-period"):
        writer.writerow([invoice.member.full_name, invoice.period, invoice.amount, invoice.status, invoice.due_date])
    return response

# Create your views here.
