from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import UserProfile
from accounts.utils import ROLE_ADMIN, ROLE_COACH, has_role
from finance.models import (
    BillingConfiguration,
    ExpenseEntry,
    ForecastScenario,
    HistoricalLock,
    Invoice,
    PaymentPlan,
    PayrollRecord,
    Product,
)
from finance.services import build_branch_choices, is_period_locked
from members.models import Member


User = get_user_model()


def branch_field_choices():
    choices = [("", "Unassigned / Shared")]
    choices.extend((label, label) for label in build_branch_choices())
    return choices


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ["member", "invoice_type", "description", "branch_tag", "amount", "due_date", "period", "status"]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "period": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = Member.objects.select_related("assigned_coach", "payment_plan").order_by("full_name")
        if current_user and has_role(current_user, ROLE_COACH) and not has_role(current_user, ROLE_ADMIN):
            queryset = queryset.filter(assigned_coach=current_user)
        self.fields["member"].queryset = queryset
        self.fields["branch_tag"].required = False
        self.fields["branch_tag"].widget = forms.Select(choices=branch_field_choices())

    def clean_period(self):
        period = self.cleaned_data["period"].replace(day=1)
        if self.instance.pk and self.instance.period == period:
            return period
        if is_period_locked(period):
            raise forms.ValidationError("This financial month is locked. Unlock it before changing invoices.")
        return period


class ExpenseEntryForm(forms.ModelForm):
    class Meta:
        model = ExpenseEntry
        fields = [
            "title",
            "expense_type",
            "category_tag",
            "branch_tag",
            "vendor_name",
            "expense_date",
            "amount",
            "payment_method",
            "receipt_upload",
            "is_tax_deductible",
            "notes",
        ]
        widgets = {
            "expense_date": forms.DateInput(attrs={"type": "date"}),
            "amount": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["branch_tag"].required = False
        self.fields["branch_tag"].widget = forms.Select(choices=branch_field_choices())

    def clean_expense_date(self):
        expense_date = self.cleaned_data["expense_date"]
        if self.instance.pk and self.instance.expense_date == expense_date:
            return expense_date
        if is_period_locked(expense_date):
            raise forms.ValidationError("This financial month is locked. Unlock it before changing expenses.")
        return expense_date


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
            "trial_session_limit",
            "opening_cash_balance",
            "registration_description",
            "payment_portal_note",
        ]
        widgets = {
            "registration_fee_amount": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "trial_session_limit": forms.NumberInput(attrs={"min": "1"}),
            "opening_cash_balance": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
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


class PayrollRecordForm(forms.ModelForm):
    class Meta:
        model = PayrollRecord
        fields = [
            "coach",
            "period",
            "branch_tag",
            "base_pay",
            "per_session_rate",
            "session_count",
            "attendance_adjustment",
            "bonus_amount",
            "deduction_amount",
            "status",
            "paid_at",
            "notes",
        ]
        widgets = {
            "period": forms.DateInput(attrs={"type": "date"}),
            "paid_at": forms.DateInput(attrs={"type": "date"}),
            "base_pay": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "per_session_rate": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "session_count": forms.NumberInput(attrs={"min": "0"}),
            "attendance_adjustment": forms.NumberInput(attrs={"step": "0.01"}),
            "bonus_amount": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "deduction_amount": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        coach_queryset = User.objects.filter(profile__role=UserProfile.ROLE_COACH).order_by("first_name", "username")
        if current_user and has_role(current_user, ROLE_COACH) and not has_role(current_user, ROLE_ADMIN):
            coach_queryset = coach_queryset.filter(pk=current_user.pk)
            self.fields["coach"].initial = current_user
        self.fields["coach"].queryset = coach_queryset
        self.fields["branch_tag"].required = False
        self.fields["branch_tag"].widget = forms.Select(choices=branch_field_choices())

    def clean_period(self):
        period = self.cleaned_data["period"].replace(day=1)
        if self.instance.pk and self.instance.period == period:
            return period
        if is_period_locked(period):
            raise forms.ValidationError("This payroll month is locked. Unlock it before changing payroll.")
        return period

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get("status")
        paid_at = cleaned_data.get("paid_at")
        if status == PayrollRecord.STATUS_PAID and not paid_at:
            cleaned_data["paid_at"] = timezone.localdate()
        return cleaned_data


class ForecastScenarioForm(forms.ModelForm):
    class Meta:
        model = ForecastScenario
        fields = [
            "title",
            "student_count_change_percent",
            "revenue_drop_percent",
            "salary_increase_percent",
            "additional_coach_hires",
            "average_new_coach_monthly_cost",
            "new_branch_student_count",
            "new_branch_monthly_overhead",
            "one_time_expansion_cost",
            "risk_buffer_percent",
            "is_primary",
            "notes",
        ]
        widgets = {
            "student_count_change_percent": forms.NumberInput(attrs={"step": "0.01"}),
            "revenue_drop_percent": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "salary_increase_percent": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "additional_coach_hires": forms.NumberInput(attrs={"min": "0"}),
            "average_new_coach_monthly_cost": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "new_branch_student_count": forms.NumberInput(attrs={"min": "0"}),
            "new_branch_monthly_overhead": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "one_time_expansion_cost": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "risk_buffer_percent": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }


class HistoricalLockForm(forms.ModelForm):
    class Meta:
        model = HistoricalLock
        fields = ["period", "notes", "is_closed"]
        widgets = {
            "period": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_period(self):
        return self.cleaned_data["period"].replace(day=1)
