from django.contrib import admin

from finance.models import Invoice, Product


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("member", "period", "amount", "status", "due_date")
    list_filter = ("status", "period")
    search_fields = ("member__full_name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "stock", "availability", "is_active", "updated_at")
    list_filter = ("availability", "is_active")
    search_fields = ("name", "description")

# Register your models here.
