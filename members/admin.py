from django.contrib import admin

from members.models import AdmissionApplication, Member, ProgressReport


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("full_name", "skill_level", "payment_plan", "assigned_coach", "status", "joined_at")
    list_filter = ("skill_level", "payment_plan", "status")
    search_fields = ("full_name", "contact_number", "email")


@admin.register(AdmissionApplication)
class AdmissionApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "student_name",
        "guardian_name",
        "preferred_program",
        "preferred_location",
        "status",
        "submitted_at",
    )
    list_filter = ("status", "preferred_location", "preferred_program")
    search_fields = ("student_name", "guardian_name", "guardian_email", "contact_number")


@admin.register(ProgressReport)
class ProgressReportAdmin(admin.ModelAdmin):
    list_display = (
        "member",
        "coach",
        "period_start",
        "period_end",
        "overall_status",
        "is_published",
    )
    list_filter = ("overall_status", "is_published", "coach")
    search_fields = ("member__full_name", "coach__username")

# Register your models here.
