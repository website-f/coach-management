from django.contrib import admin

from sessions.models import AttendanceRecord, CoachAvailability, SessionChecklistReport, SessionPlannerEntry, SyllabusStandard, SyllabusTemplate, TrainingSession, WeeklySyllabus


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


@admin.register(SyllabusTemplate)
class SyllabusTemplateAdmin(admin.ModelAdmin):
    list_display = ("track", "name", "curriculum_year_label", "is_active", "updated_at")
    list_filter = ("track", "is_active")
    search_fields = ("name", "annual_goal", "source_document_name")


@admin.register(SyllabusStandard)
class SyllabusStandardAdmin(admin.ModelAdmin):
    list_display = ("template", "code", "title", "is_active", "updated_at")
    list_filter = ("template__track", "is_active")
    search_fields = ("code", "title", "focus", "learning_standard_items")


@admin.register(WeeklySyllabus)
class WeeklySyllabusAdmin(admin.ModelAdmin):
    list_display = ("track", "month_number", "week_number", "title", "standard", "is_active", "updated_at")
    list_filter = ("track", "is_active")
    search_fields = ("title", "objective", "technical_focus", "tactical_focus", "phase_name")


@admin.register(SessionPlannerEntry)
class SessionPlannerEntryAdmin(admin.ModelAdmin):
    list_display = ("training_session", "title", "source", "model_name", "saved_by", "created_at")
    list_filter = ("source", "created_at")
    search_fields = ("title", "user_prompt", "assistant_response", "training_session__title")

@admin.register(CoachAvailability)
class CoachAvailabilityAdmin(admin.ModelAdmin):
    list_display = ("coach", "weekday", "start_time", "end_time", "level", "court", "is_active")
    list_filter = ("weekday", "level", "is_active")
    search_fields = ("coach__username", "coach__first_name", "coach__last_name", "court")


@admin.register(SessionChecklistReport)
class SessionChecklistReportAdmin(admin.ModelAdmin):
    list_display = ("training_session", "coach", "updated_at")
    list_filter = ("coach", "updated_at")
    search_fields = ("training_session__title", "feedback_text")


# Register your models here.
