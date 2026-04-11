from django.contrib import admin

from finance.models import Invoice


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("member", "period", "amount", "status", "due_date")
    list_filter = ("status", "period")
    search_fields = ("member__full_name",)

# Register your models here.
