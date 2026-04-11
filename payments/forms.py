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
    class Meta:
        model = Payment
        fields = ["proof_image"]


class PaymentReviewForm(forms.Form):
    rejection_reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))
