from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView

from accounts.mixins import AdminOrCoachRequiredMixin, AdminRequiredMixin, ParentRequiredMixin
from accounts.models import UserProfile
from accounts.notifications import notify_users
from accounts.utils import ROLE_ADMIN, ROLE_COACH, has_role
from finance.models import Invoice
from finance.services import billing_context_data, is_period_locked
from members.models import CommunicationLog, Member
from payments.forms import PaymentReviewForm, PaymentSubmissionForm, QRCodeForm
from payments.models import Payment, QRCode


User = get_user_model()


def admin_users():
    return User.objects.filter(profile__role=UserProfile.ROLE_ADMIN, is_active=True)


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


class QRCodeListView(AdminRequiredMixin, ListView):
    model = QRCode
    template_name = "payments/qrcode_list.html"
    context_object_name = "qr_codes"
    paginate_by = 10

    def get_queryset(self):
        return visible_qr_codes_for_user(self.request.user).distinct()


class QRCodeCreateView(AdminRequiredMixin, CreateView):
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
        queryset = (
            Invoice.objects.select_related("member", "member__payment_plan", "payment_plan")
            .prefetch_related("payments", "member__admission_applications")
            .filter(member__parent_user=self.request.user)
        )
        for invoice in queryset:
            invoice.refresh_status_from_payments(save=False)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        children = Member.objects.filter(parent_user=self.request.user).order_by("full_name")
        invoice_queryset = list(self.get_queryset())
        today = timezone.localdate()
        current_month_invoices = [
            invoice
            for invoice in invoice_queryset
            if invoice.period.year == today.year and invoice.period.month == today.month and invoice.status != Invoice.STATUS_PAID
        ]
        child_summaries = []
        for child in children:
            child_invoices = [invoice for invoice in invoice_queryset if invoice.member_id == child.pk]
            attendance_records = child.attendance_records.exclude(status="scheduled")
            total_records = attendance_records.count()
            attended = attendance_records.filter(status__in=["present", "late"]).count()
            child_summaries.append(
                {
                    "member": child,
                    "attendance_rate": round((attended / total_records) * 100, 1) if total_records else 0,
                    "latest_invoice": child_invoices[0] if child_invoices else None,
                    "outstanding_total": sum(invoice.outstanding_amount for invoice in child_invoices),
                }
            )
        context.update(
            {
                "children": children,
                "outstanding_total": sum(invoice.outstanding_amount for invoice in invoice_queryset),
                "pending_invoice_count": sum(1 for invoice in invoice_queryset if invoice.status == Invoice.STATUS_PENDING),
                "partial_invoice_count": sum(1 for invoice in invoice_queryset if invoice.status == Invoice.STATUS_PARTIAL),
                "overdue_invoice_count": sum(1 for invoice in invoice_queryset if invoice.status == Invoice.STATUS_OVERDUE),
                "paid_invoice_count": sum(1 for invoice in invoice_queryset if invoice.status == Invoice.STATUS_PAID),
                "current_month_unpaid_count": len(current_month_invoices),
                "featured_invoice": current_month_invoices[0] if current_month_invoices else next(
                    (invoice for invoice in invoice_queryset if invoice.status != Invoice.STATUS_PAID),
                    None,
                ),
                "onboarding_invoices": [
                    invoice for invoice in invoice_queryset if invoice.is_onboarding_fee and invoice.status != Invoice.STATUS_PAID
                ][:3],
                "show_onboarding_prompt": self.request.GET.get("onboarding") == "1",
                "child_summaries": child_summaries,
            }
        )
        context.update(billing_context_data())
        return context


class SubmitPaymentView(ParentRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        invoice = get_object_or_404(
            Invoice.objects.select_related("member", "member__assigned_coach", "member__parent_user").prefetch_related("payments"),
            pk=kwargs["pk"],
            member__parent_user=request.user,
        )
        invoice.refresh_status_from_payments(save=False)
        if invoice.status == Invoice.STATUS_PAID:
            messages.warning(request, "This invoice has already been fully paid.")
            return redirect("payments:my_payments")
        if invoice.payments.filter(status=Payment.STATUS_PENDING).exists():
            messages.warning(request, "A payment proof is already waiting for review.")
            return redirect("payments:my_payments")
        if is_period_locked(invoice.period):
            messages.error(request, "This financial month is locked. Please contact admin for adjustments.")
            return redirect("payments:my_payments")

        form = PaymentSubmissionForm(request.POST, request.FILES, invoice=invoice)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.invoice = invoice
            payment.paid_by = request.user
            payment.status = Payment.STATUS_PENDING
            payment.save()
            invoice.refresh_status_from_payments()
            notify_users(
                admin_users(),
                title="New payment proof submitted",
                message=(
                    f"{invoice.member.full_name} submitted {payment.get_payment_method_display()} proof for "
                    f"{invoice.period:%B %Y}. Review RM {payment.amount_received} from the admin payment queue."
                ),
                url=reverse_lazy("payments:review", kwargs={"pk": payment.pk}),
                email_subject=f"Payment proof submitted for {invoice.member.full_name}",
                email_message=(
                    f"A payment proof has been submitted for {invoice.member.full_name}.\n"
                    f"Billing period: {invoice.period:%B %Y}\n"
                    f"Payment method: {payment.get_payment_method_display()}\n"
                    f"Amount: RM {payment.amount_received}\n"
                    "Please review it in the admin dashboard."
                ),
            )
            messages.success(
                request,
                f"Payment proof for RM {payment.amount_received} submitted. The team will verify it soon.",
            )
        else:
            messages.error(
                request,
                " ".join(error for errors in form.errors.values() for error in errors)
                or "Please check the payment amount, method, and proof image.",
            )
        return redirect("payments:my_payments")


class PendingPaymentListView(AdminRequiredMixin, ListView):
    model = Payment
    template_name = "payments/pending_review_list.html"
    context_object_name = "payments"
    paginate_by = 10

    def get_queryset(self):
        return visible_payments_for_user(self.request.user).filter(status=Payment.STATUS_PENDING)


class PaymentHistoryView(AdminOrCoachRequiredMixin, ListView):
    model = Payment
    template_name = "payments/payment_history.html"
    context_object_name = "payments"
    paginate_by = 12

    def get_queryset(self):
        queryset = visible_payments_for_user(self.request.user)
        status = self.request.GET.get("status", "").strip()
        member = self.request.GET.get("member", "").strip()
        if status:
            queryset = queryset.filter(status=status)
        if member:
            queryset = queryset.filter(invoice__member_id=member)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        context["statuses"] = Payment.STATUS_CHOICES
        context["members"] = visible_payments_for_user(self.request.user).values_list(
            "invoice__member_id", "invoice__member__full_name"
        ).distinct()
        context["can_review"] = has_role(self.request.user, ROLE_ADMIN)
        context["pending_count"] = queryset.filter(status=Payment.STATUS_PENDING).count()
        context["approved_total"] = queryset.filter(status=Payment.STATUS_APPROVED).aggregate(
            total=Sum("amount_received")
        )["total"] or 0
        return context


class PaymentReviewView(AdminRequiredMixin, DetailView):
    model = Payment
    template_name = "payments/payment_review.html"
    context_object_name = "payment"

    def get_queryset(self):
        return visible_payments_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        projected_outstanding = self.object.invoice.outstanding_amount - self.object.amount_received
        if projected_outstanding < 0:
            projected_outstanding = 0
        context["review_form"] = PaymentReviewForm()
        context["projected_outstanding_after_approval"] = projected_outstanding
        return context

    def post(self, request, *args, **kwargs):
        payment = self.get_object()
        action = request.POST.get("action")
        rejection_reason = request.POST.get("rejection_reason", "").strip()
        invoice = payment.invoice

        if payment.status != Payment.STATUS_PENDING:
            messages.warning(request, "This payment proof has already been reviewed.")
            return redirect("payments:payment_history")
        if is_period_locked(invoice.period):
            messages.error(request, "This financial month is locked. Unlock it before reviewing payments.")
            return redirect("payments:pending_reviews")

        if action == "approve":
            payment.status = Payment.STATUS_APPROVED
            payment.reviewed_by = request.user
            payment.reviewed_at = timezone.now()
            payment.rejection_reason = ""
            payment.save(update_fields=["status", "reviewed_by", "reviewed_at", "rejection_reason"])

            invoice.refresh_status_from_payments()
            member = invoice.member
            member_update_fields = []
            if invoice.invoice_type == Invoice.TYPE_MONTHLY and invoice.status == Invoice.STATUS_PAID:
                if member.status != Member.STATUS_ACTIVE:
                    member.status = Member.STATUS_ACTIVE
                    member_update_fields.append("status")
                if not member.subscription_started_at:
                    member.subscription_started_at = timezone.localdate()
                    member_update_fields.append("subscription_started_at")
                if member.trial_outcome != Member.TRIAL_OUTCOME_CONVERTED:
                    member.trial_outcome = Member.TRIAL_OUTCOME_CONVERTED
                    member_update_fields.append("trial_outcome")
            if member_update_fields:
                member.save(update_fields=member_update_fields + ["updated_at"])

            CommunicationLog.objects.create(
                member=member,
                channel=CommunicationLog.CHANNEL_INTERNAL,
                message_type=CommunicationLog.TYPE_PAYMENT,
                staff=request.user,
                outcome=(
                    f"Payment approved for {invoice.get_invoice_type_display()} ({invoice.period:%b %Y}) "
                    f"via {payment.get_payment_method_display()} for RM {payment.amount_received}."
                ),
                next_step=member.next_action,
            )
            notify_users(
                [payment.paid_by, invoice.member.parent_user],
                title="Payment approved",
                message=(
                    f"The payment for {invoice.member.full_name} ({invoice.period:%B %Y}) "
                    f"was approved for RM {payment.amount_received}. Invoice status is now "
                    f"{invoice.get_status_display().lower()}."
                ),
                url=reverse_lazy("payments:my_payments"),
                email_subject=f"Payment approved for {invoice.member.full_name}",
                email_message=(
                    f"The payment for {invoice.member.full_name} has been approved.\n"
                    f"Billing period: {invoice.period:%B %Y}\n"
                    f"Payment method: {payment.get_payment_method_display()}\n"
                    f"Amount approved: RM {payment.amount_received}\n"
                    f"Invoice status: {invoice.get_status_display()}"
                ),
            )
            if invoice.member.assigned_coach:
                notify_users(
                    [invoice.member.assigned_coach],
                    title="Student payment approved",
                    message=(
                        f"{invoice.member.full_name}'s payment for {invoice.period:%B %Y} "
                        f"was approved and the invoice is now {invoice.get_status_display().lower()}."
                    ),
                    url=reverse_lazy("payments:payment_history"),
                )
            messages.success(request, f"Payment approved. Invoice is now {invoice.get_status_display().lower()}.")
        elif action == "reject":
            if not rejection_reason:
                messages.error(request, "Please provide a rejection reason.")
                return render(
                    request,
                    self.template_name,
                    {
                        "payment": payment,
                        "review_form": PaymentReviewForm(request.POST),
                        "projected_outstanding_after_approval": invoice.outstanding_amount,
                    },
                )

            payment.status = Payment.STATUS_REJECTED
            payment.reviewed_by = request.user
            payment.reviewed_at = timezone.now()
            payment.rejection_reason = rejection_reason
            payment.save(update_fields=["status", "reviewed_by", "reviewed_at", "rejection_reason"])

            invoice.refresh_status_from_payments()
            CommunicationLog.objects.create(
                member=invoice.member,
                channel=CommunicationLog.CHANNEL_INTERNAL,
                message_type=CommunicationLog.TYPE_PAYMENT,
                staff=request.user,
                outcome=(
                    f"Payment rejected for {invoice.get_invoice_type_display()} ({invoice.period:%b %Y}). "
                    f"{rejection_reason}"
                ),
                next_step="Parent needs to resubmit payment proof.",
            )
            notify_users(
                [payment.paid_by, invoice.member.parent_user],
                title="Payment rejected",
                message=(
                    f"The proof for {invoice.member.full_name} was rejected. "
                    f"Reason: {rejection_reason}"
                ),
                url=reverse_lazy("payments:my_payments"),
                email_subject=f"Payment rejected for {invoice.member.full_name}",
                email_message=(
                    f"The payment proof for {invoice.member.full_name} was rejected.\n"
                    f"Reason: {rejection_reason}\n"
                    "Please upload a new proof in the parent portal."
                ),
            )
            if invoice.member.assigned_coach:
                notify_users(
                    [invoice.member.assigned_coach],
                    title="Student payment rejected",
                    message=(
                        f"{invoice.member.full_name}'s payment proof was rejected by admin. "
                        f"Reason: {rejection_reason}"
                    ),
                    url=reverse_lazy("payments:payment_history"),
                )
            messages.warning(request, f"Payment rejected. Invoice is now {invoice.get_status_display().lower()}.")
        return redirect("payments:pending_reviews")
