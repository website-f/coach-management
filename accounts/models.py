from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    ROLE_SUPERADMIN = "superadmin"
    ROLE_ADMIN = "admin"
    ROLE_COACH = "coach"
    ROLE_PARENT = "parent"

    ROLE_CHOICES = [
        (ROLE_SUPERADMIN, "Superadmin"),
        (ROLE_ADMIN, "Admin"),
        (ROLE_COACH, "Coach"),
        (ROLE_PARENT, "Parent"),
    ]

    # Deprecated alias (headcount merged into admin). Kept for legacy refs.
    ROLE_HEADCOUNT = ROLE_ADMIN

    # Mirrors members.Member.LEVEL_CHOICES so a coach's class level lines up
    # with the student class levels used everywhere else (filters, reports,
    # national-team eligibility queries).
    CLASS_LEVEL_BASIC = "basic"
    CLASS_LEVEL_INTERMEDIATE = "intermediate"
    CLASS_LEVEL_ADVANCED = "advanced"
    CLASS_LEVEL_CHOICES = [
        (CLASS_LEVEL_BASIC, "Basic"),
        (CLASS_LEVEL_INTERMEDIATE, "Intermediate"),
        (CLASS_LEVEL_ADVANCED, "Advanced"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_PARENT)
    phone_number = models.CharField(max_length=30, blank=True)
    class_level = models.CharField(
        max_length=20,
        choices=CLASS_LEVEL_CHOICES,
        blank=True,
        default="",
        help_text="Class level this coach handles. Empty for non-coach roles.",
    )
    must_change_password = models.BooleanField(default=False)
    # Plaintext temp password for admin reference (cleared once the coach sets their own).
    temporary_password = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__username"]

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


class Branch(models.Model):
    """A physical location / venue the organization operates from.

    Today it's a flat list under one club. When the multi-tenant revamp lands,
    each Branch will hang off an Organization and pick up a Region FK.
    """

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=30, blank=True, help_text="Short identifier, e.g. RSBE-KL.")
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=120, blank=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_branches",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Branches"

    def __str__(self):
        return self.name


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
