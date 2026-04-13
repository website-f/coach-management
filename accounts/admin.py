from django.contrib import admin

from accounts.models import LandingPageContent, Notification, SystemFlag, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "phone_number", "updated_at")
    list_filter = ("role",)
    search_fields = ("user__username", "user__first_name", "user__last_name")


@admin.register(SystemFlag)
class SystemFlagAdmin(admin.ModelAdmin):
    list_display = ("key", "value", "updated_at")
    search_fields = ("key", "value")


@admin.register(LandingPageContent)
class LandingPageContentAdmin(admin.ModelAdmin):
    list_display = ("hero_title", "contact_email", "updated_by", "updated_at")
    search_fields = ("hero_title", "announcement_text", "contact_email")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "is_read", "created_at")
    list_filter = ("is_read", "created_at")
    search_fields = ("user__username", "title", "message")
