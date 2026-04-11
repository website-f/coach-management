from django.contrib import admin

from payments.models import Payment, QRCode


@admin.register(QRCode)
class QRCodeAdmin(admin.ModelAdmin):
    list_display = ("label", "invoice", "payment_period", "is_active", "uploaded_by", "created_at")
    list_filter = ("is_active", "payment_period")
    search_fields = ("label",)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("invoice", "paid_by", "status", "submitted_at", "reviewed_by")
    list_filter = ("status",)
    search_fields = ("invoice__member__full_name", "paid_by__username")

# Register your models here.
