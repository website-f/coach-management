from django.contrib import messages
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Sum
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView

from accounts.mixins import AdminOrCoachRequiredMixin, AdminRequiredMixin, ParentRequiredMixin
from accounts.notifications import notify_users
from accounts.utils import ROLE_ADMIN, ROLE_COACH, has_role
from accounts.models import UserProfile
from finance.models import Invoice
from members.models import Member
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
        return Invoice.objects.select_related("member").filter(member__parent_user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        children = Member.objects.filter(parent_user=self.request.user).order_by("full_name")
        invoice_queryset = self.get_queryset()
        today = timezone.localdate()
        current_month_invoices = invoice_queryset.filter(
            period__year=today.year,
            period__month=today.month,
        ).exclude(status=Invoice.STATUS_PAID)
        child_summaries = []
        for child in children:
            child_invoices = invoice_queryset.filter(member=child)
            attendance_records = child.attendance_records.exclude(status="scheduled")
            total_records = attendance_records.count()
            attended = attendance_records.filter(status__in=["present", "late"]).count()
            child_summaries.append(
                {
                    "member": child,
                    "attendance_rate": round((attended / total_records) * 100, 1) if total_records else 0,
                    "latest_invoice": child_invoices.order_by("-period", "-due_date").first(),
                    "outstanding_total": child_invoices.exclude(status=Invoice.STATUS_PAID).aggregate(total=Sum("amount"))[
                        "total"
                    ]
                    or 0,
                }
            )
        context.update(
            {
                "children": children,
                "outstanding_total": invoice_queryset.exclude(status=Invoice.STATUS_PAID).aggregate(total=Sum("amount"))[
                    "total"
                ]
                or 0,
                "pending_invoice_count": invoice_queryset.filter(status=Invoice.STATUS_PENDING).count(),
                "paid_invoice_count": invoice_queryset.filter(status=Invoice.STATUS_PAID).count(),
                "current_month_unpaid_count": current_month_invoices.count(),
                "featured_invoice": current_month_invoices.order_by("due_date", "period").first()
                or invoice_queryset.exclude(status=Invoice.STATUS_PAID).order_by("due_date", "period").first(),
                "onboarding_invoices": invoice_queryset.filter(is_onboarding_fee=True).exclude(
                    status=Invoice.STATUS_PAID
                ).order_by("due_date", "period")[:3],
                "show_onboarding_prompt": self.request.GET.get("onboarding") == "1",
                "child_summaries": child_summaries,
            }
        )
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
            notify_users(
                admin_users(),
                title="New payment proof submitted",
                message=(
                    f"{invoice.member.full_name} submitted proof for {invoice.period:%B %Y}. "
                    f"Review RM {invoice.amount} from the admin payment queue."
                ),
                url=reverse_lazy("payments:review", kwargs={"pk": payment.pk}),
                email_subject=f"Payment proof submitted for {invoice.member.full_name}",
                email_message=(
                    f"A payment proof has been submitted for {invoice.member.full_name}.\n"
                    f"Billing period: {invoice.period:%B %Y}\n"
                    f"Amount: RM {invoice.amount}\n"
                    "Please review it in the admin dashboard."
                ),
            )
            messages.success(request, "Payment proof submitted. The team will verify it soon.")
        else:
            messages.error(request, "Please upload a valid payment proof image.")
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
            total=Sum("invoice__amount")
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
            notify_users(
                [payment.paid_by, invoice.member.parent_user],
                title="Payment approved",
                message=(
                    f"The payment for {invoice.member.full_name} ({invoice.period:%B %Y}) has been approved."
                ),
                url=reverse_lazy("payments:my_payments"),
                email_subject=f"Payment approved for {invoice.member.full_name}",
                email_message=(
                    f"The payment for {invoice.member.full_name} has been approved.\n"
                    f"Billing period: {invoice.period:%B %Y}\n"
                    f"Amount: RM {invoice.amount}"
                ),
            )
            notify_users(
                [invoice.member.assigned_coach],
                title="Student payment approved",
                message=(
                    f"{invoice.member.full_name}'s payment for {invoice.period:%B %Y} has been approved by admin."
                ),
                url=reverse_lazy("payments:payment_history"),
            )
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
            notify_users(
                [invoice.member.assigned_coach],
                title="Student payment rejected",
                message=(
                    f"{invoice.member.full_name}'s payment proof was rejected by admin. "
                    f"Reason: {rejection_reason}"
                ),
                url=reverse_lazy("payments:payment_history"),
            )
            messages.warning(request, "Payment rejected and the parent can resubmit proof.")
        return redirect("payments:pending_reviews")

# Create your views here.
