from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView

from accounts.mixins import AdminOrCoachRequiredMixin, ParentRequiredMixin
from accounts.utils import ROLE_ADMIN, ROLE_COACH, has_role
from finance.models import Invoice
from members.models import Member
from payments.forms import PaymentReviewForm, PaymentSubmissionForm, QRCodeForm
from payments.models import Payment, QRCode


def visible_payments_for_user(user):
    queryset = Payment.objects.select_related("invoice", "invoice__member", "paid_by", "reviewed_by")
    if has_role(user, ROLE_COACH) and not has_role(user, ROLE_ADMIN):
        return queryset.filter(invoice__member__assigned_coach=user)
    return queryset


def visible_qr_codes_for_user(user):
    queryset = QRCode.objects.select_related("invoice", "invoice__member", "uploaded_by")
    if has_role(user, ROLE_COACH) and not has_role(user, ROLE_ADMIN):
        return queryset.filter(invoice__member__assigned_coach=user) | queryset.filter(uploaded_by=user)
    return queryset


class QRCodeListView(AdminOrCoachRequiredMixin, ListView):
    model = QRCode
    template_name = "payments/qrcode_list.html"
    context_object_name = "qr_codes"
    paginate_by = 10

    def get_queryset(self):
        return visible_qr_codes_for_user(self.request.user).distinct()


class QRCodeCreateView(AdminOrCoachRequiredMixin, CreateView):
    model = QRCode
    form_class = QRCodeForm
    template_name = "payments/qrcode_form.html"
    success_url = reverse_lazy("payments:qrcode_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["current_user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "QR code uploaded successfully.")
        return response


class MyPaymentsView(ParentRequiredMixin, ListView):
    model = Invoice
    template_name = "payments/my_payments.html"
    context_object_name = "invoices"
    paginate_by = 10

    def get_queryset(self):
        return Invoice.objects.select_related("member").filter(member__parent_user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["children"] = Member.objects.filter(parent_user=self.request.user).order_by("full_name")
        return context


class SubmitPaymentView(ParentRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        invoice = get_object_or_404(Invoice, pk=kwargs["pk"], member__parent_user=request.user)
        if invoice.status == Invoice.STATUS_PAID:
            messages.warning(request, "This invoice has already been paid.")
            return redirect("payments:my_payments")
        if invoice.payments.filter(status=Payment.STATUS_PENDING).exists():
            messages.warning(request, "A payment proof is already waiting for review.")
            return redirect("payments:my_payments")

        form = PaymentSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.invoice = invoice
            payment.paid_by = request.user
            payment.status = Payment.STATUS_PENDING
            payment.save()
            invoice.status = Invoice.STATUS_PENDING
            invoice.save(update_fields=["status", "updated_at"])
            messages.success(request, "Payment proof submitted. The team will verify it soon.")
        else:
            messages.error(request, "Please upload a valid payment proof image.")
        return redirect("payments:my_payments")


class PendingPaymentListView(AdminOrCoachRequiredMixin, ListView):
    model = Payment
    template_name = "payments/pending_review_list.html"
    context_object_name = "payments"
    paginate_by = 10

    def get_queryset(self):
        return visible_payments_for_user(self.request.user).filter(status=Payment.STATUS_PENDING)


class PaymentReviewView(AdminOrCoachRequiredMixin, DetailView):
    model = Payment
    template_name = "payments/payment_review.html"
    context_object_name = "payment"

    def get_queryset(self):
        return visible_payments_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["review_form"] = PaymentReviewForm()
        return context

    def post(self, request, *args, **kwargs):
        payment = self.get_object()
        action = request.POST.get("action")
        rejection_reason = request.POST.get("rejection_reason", "").strip()

        if action == "approve":
            payment.status = Payment.STATUS_APPROVED
            payment.reviewed_by = request.user
            payment.reviewed_at = timezone.now()
            payment.rejection_reason = ""
            payment.save(update_fields=["status", "reviewed_by", "reviewed_at", "rejection_reason"])
            invoice = payment.invoice
            invoice.status = Invoice.STATUS_PAID
            invoice.member.status = Member.STATUS_ACTIVE
            invoice.save(update_fields=["status", "updated_at"])
            invoice.member.save(update_fields=["status", "updated_at"])
            messages.success(request, "Payment approved and invoice marked as paid.")
        elif action == "reject":
            if not rejection_reason:
                messages.error(request, "Please provide a rejection reason.")
                return render(request, self.template_name, {"payment": payment, "review_form": PaymentReviewForm(request.POST)})
            payment.status = Payment.STATUS_REJECTED
            payment.reviewed_by = request.user
            payment.reviewed_at = timezone.now()
            payment.rejection_reason = rejection_reason
            payment.save(update_fields=["status", "reviewed_by", "reviewed_at", "rejection_reason"])
            invoice = payment.invoice
            invoice.status = Invoice.STATUS_REJECTED
            invoice.save(update_fields=["status", "updated_at"])
            messages.warning(request, "Payment rejected and the parent can resubmit proof.")
        return redirect("payments:pending_reviews")

# Create your views here.
