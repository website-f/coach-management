from django import forms

from accounts.utils import ROLE_ADMIN, ROLE_COACH, has_role
from finance.models import BillingConfiguration, Invoice, PaymentPlan, Product
from members.models import Member


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ["member", "invoice_type", "description", "amount", "due_date", "period", "status"]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "period": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = Member.objects.select_related("assigned_coach").order_by("full_name")
        if current_user and has_role(current_user, ROLE_COACH) and not has_role(current_user, ROLE_ADMIN):
            queryset = queryset.filter(assigned_coach=current_user)
        self.fields["member"].queryset = queryset


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "description", "price", "stock", "availability", "image", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "price": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "stock": forms.NumberInput(attrs={"min": "0"}),
        }


class BillingConfigurationForm(forms.ModelForm):
    class Meta:
        model = BillingConfiguration
        fields = [
            "registration_fee_name",
            "registration_fee_amount",
            "registration_bonus_text",
            "registration_description",
            "payment_portal_note",
        ]
        widgets = {
            "registration_fee_amount": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "registration_description": forms.Textarea(attrs={"rows": 3}),
            "payment_portal_note": forms.Textarea(attrs={"rows": 3}),
        }


class PaymentPlanForm(forms.ModelForm):
    class Meta:
        model = PaymentPlan
        fields = [
            "name",
            "code",
            "sessions_per_month",
            "monthly_fee",
            "description",
            "is_active",
            "is_default",
            "sort_order",
        ]
        widgets = {
            "monthly_fee": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "sessions_per_month": forms.NumberInput(attrs={"min": "1"}),
            "sort_order": forms.NumberInput(attrs={"min": "0"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip().replace("-", "_")
        return code

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("is_default") and not cleaned_data.get("is_active"):
            self.add_error("is_active", "The default package must stay active.")
        return cleaned_data
