from django.contrib import admin

from finance.models import BillingConfiguration, Invoice, PaymentPlan, Product


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("member", "invoice_type", "payment_plan", "period", "amount", "status", "due_date")
    list_filter = ("status", "period", "invoice_type")
    search_fields = ("member__full_name", "description")


@admin.register(PaymentPlan)
class PaymentPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "monthly_fee", "sessions_per_month", "is_active", "is_default")
    list_filter = ("is_active", "is_default")
    search_fields = ("name", "code", "description")


@admin.register(BillingConfiguration)
class BillingConfigurationAdmin(admin.ModelAdmin):
    list_display = ("registration_fee_name", "registration_fee_amount", "updated_at")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "stock", "availability", "is_active", "updated_at")
    list_filter = ("availability", "is_active")
    search_fields = ("name", "description")

# Register your models here.
