from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    ROLE_ADMIN = "admin"
    ROLE_COACH = "coach"
    ROLE_HEADCOUNT = "headcount"
    ROLE_PARENT = "parent"

    ROLE_CHOICES = [
        (ROLE_ADMIN, "Admin"),
        (ROLE_COACH, "Coach"),
        (ROLE_HEADCOUNT, "Sales/Admin"),
        (ROLE_PARENT, "Parent"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_PARENT)
    phone_number = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__username"]

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


class SystemFlag(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return self.key


class LandingPageContent(models.Model):
    hero_title = models.CharField(max_length=255, default="NYO Admin Dashboard")
    hero_subtitle = models.TextField(
        default="Manage badminton club operations, parent billing, sessions, and role-based workflows from one connected system."
    )
    announcement_text = models.CharField(max_length=255, default="Role-based club operations")
    contact_email = models.EmailField(blank=True, default="support@nyo.local")
    instagram_link = models.URLField(blank=True)
    tiktok_link = models.URLField(blank=True)
    primary_cta_text = models.CharField(max_length=100, default="Enter Parent Portal")
    secondary_cta_text = models.CharField(max_length=100, default="Explore Role Flows")
    available_programs = models.JSONField(default=list, blank=True)
    available_locations = models.JSONField(default=list, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_landing_content",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Landing page content"
        verbose_name_plural = "Landing page content"

    def __str__(self):
        return "Landing Page Content"

    @classmethod
    def get_solo(cls):
        defaults = {
            "available_programs": [
                "Junior Development",
                "Competitive Squad",
                "Private Coaching",
            ],
            "available_locations": [
                "Court 1",
                "Court 2",
                "Weekend Hall",
            ],
        }
        obj = cls.objects.order_by("pk").first()
        if obj:
            return obj
        return cls.objects.create(**defaults)


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username}: {self.title}"
