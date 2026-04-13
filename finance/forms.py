from django import forms

from accounts.utils import ROLE_ADMIN, ROLE_COACH, has_role
from finance.models import Invoice, Product
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
