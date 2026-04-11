from django.contrib import admin

from sessions.models import AttendanceRecord, TrainingSession


class AttendanceInline(admin.TabularInline):
    model = AttendanceRecord
    extra = 0


@admin.register(TrainingSession)
class TrainingSessionAdmin(admin.ModelAdmin):
    list_display = ("title", "session_date", "court", "coach")
    list_filter = ("session_date", "coach")
    search_fields = ("title", "court")
    inlines = [AttendanceInline]


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("training_session", "member", "status", "marked_by", "marked_at")
    list_filter = ("status",)

# Register your models here.
