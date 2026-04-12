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
        (ROLE_HEADCOUNT, "Headcount"),
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
