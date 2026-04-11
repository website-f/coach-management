from django.contrib import admin

from members.models import Member


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("full_name", "membership_type", "assigned_coach", "status", "joined_at")
    list_filter = ("membership_type", "status")
    search_fields = ("full_name", "contact_number", "email")

# Register your models here.
