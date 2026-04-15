from decimal import Decimal

from django import forms

from finance.models import Invoice
from payments.models import Payment, QRCode


class QRCodeForm(forms.ModelForm):
    class Meta:
        model = QRCode
        fields = ["label", "invoice", "payment_period", "image", "is_active"]
        widgets = {
            "payment_period": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = Invoice.objects.select_related("member").order_by("-period")
        if current_user and getattr(current_user, "profile", None) and current_user.profile.role == "coach":
            queryset = queryset.filter(member__assigned_coach=current_user)
        self.fields["invoice"].queryset = queryset


class PaymentSubmissionForm(forms.ModelForm):
    def __init__(self, *args, invoice=None, **kwargs):
        self.invoice = invoice
        super().__init__(*args, **kwargs)
        self.fields["proof_image"].widget.attrs.update({"accept": "image/*"})
        self.fields["receipt_reference"].widget.attrs.update(
            {"placeholder": "Bank ref, DuitNow ID, or cashier note"}
        )
        self.fields["notes"].widget.attrs.update(
            {"placeholder": "Optional note for admin, for example split payment or transfer details."}
        )
        if invoice is not None:
            outstanding_amount = Decimal(invoice.outstanding_amount or invoice.amount or "0")
            self.fields["amount_received"].initial = outstanding_amount
            self.fields["amount_received"].widget.attrs["max"] = f"{outstanding_amount:.2f}"

    class Meta:
        model = Payment
        fields = ["payment_method", "amount_received", "receipt_reference", "proof_image", "notes"]
        widgets = {
            "amount_received": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_amount_received(self):
        amount_received = Decimal(self.cleaned_data.get("amount_received") or "0")
        if amount_received <= Decimal("0.00"):
            raise forms.ValidationError("Payment amount must be more than zero.")
        if self.invoice is not None:
            outstanding_amount = Decimal(self.invoice.outstanding_amount or self.invoice.amount or "0")
            if outstanding_amount <= Decimal("0.00"):
                raise forms.ValidationError("This invoice is already settled.")
            if amount_received > outstanding_amount:
                raise forms.ValidationError(
                    f"Submitted amount cannot exceed the outstanding balance of RM {outstanding_amount:.2f}."
                )
        return amount_received

    def clean_receipt_reference(self):
        return (self.cleaned_data.get("receipt_reference") or "").strip()


class PaymentReviewForm(forms.Form):
    rejection_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "Tell the parent what needs to be fixed before they resubmit.",
            }
        ),
    )
