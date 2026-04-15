from django.contrib import admin

from finance.models import (
    BillingConfiguration,
    ExpenseEntry,
    FinanceAuditLog,
    ForecastScenario,
    HistoricalLock,
    Invoice,
    PaymentPlan,
    PayrollRecord,
    Product,
)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("member", "invoice_type", "payment_plan", "branch_tag", "period", "amount", "status", "due_date")
    list_filter = ("status", "period", "invoice_type", "branch_tag")
    search_fields = ("member__full_name", "description", "branch_tag")


@admin.register(PaymentPlan)
class PaymentPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "monthly_fee", "sessions_per_month", "is_active", "is_default")
    list_filter = ("is_active", "is_default")
    search_fields = ("name", "code", "description")


@admin.register(BillingConfiguration)
class BillingConfigurationAdmin(admin.ModelAdmin):
    list_display = ("registration_fee_name", "registration_fee_amount", "opening_cash_balance", "updated_at")


@admin.register(ExpenseEntry)
class ExpenseEntryAdmin(admin.ModelAdmin):
    list_display = ("expense_date", "title", "expense_type", "category_tag", "branch_tag", "amount")
    list_filter = ("expense_type", "category_tag", "branch_tag", "payment_method", "is_tax_deductible")
    search_fields = ("title", "vendor_name", "notes")


@admin.register(PayrollRecord)
class PayrollRecordAdmin(admin.ModelAdmin):
    list_display = ("coach", "period", "branch_tag", "status", "session_count", "total_pay")
    list_filter = ("status", "period", "branch_tag")
    search_fields = ("coach__username", "coach__first_name", "coach__last_name", "notes")


@admin.register(ForecastScenario)
class ForecastScenarioAdmin(admin.ModelAdmin):
    list_display = ("title", "is_primary", "revenue_drop_percent", "salary_increase_percent", "updated_at")
    list_filter = ("is_primary",)
    search_fields = ("title", "notes")


@admin.register(HistoricalLock)
class HistoricalLockAdmin(admin.ModelAdmin):
    list_display = ("period", "is_closed", "locked_by", "locked_at")
    list_filter = ("is_closed",)


@admin.register(FinanceAuditLog)
class FinanceAuditLogAdmin(admin.ModelAdmin):
    list_display = ("happened_at", "source_model", "action", "object_repr", "actor")
    list_filter = ("source_model", "action")
    search_fields = ("object_repr", "notes")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "stock", "availability", "is_active", "updated_at")
    list_filter = ("availability", "is_active")
    search_fields = ("name", "description")
