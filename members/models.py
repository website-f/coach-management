from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

DEFAULT_SKILLS = [
    "Service",
    "Lobbing",
    "Smashing",
    "Drop Shot",
    "Netting",
    "Footwork",
    "Defense",
]


class Member(models.Model):
    LEVEL_BASIC = "basic"
    LEVEL_INTERMEDIATE = "intermediate"
    LEVEL_ADVANCED = "advanced"
    LEVEL_CHOICES = [
        (LEVEL_BASIC, "Basic"),
        (LEVEL_INTERMEDIATE, "Intermediate"),
        (LEVEL_ADVANCED, "Advanced"),
    ]

    MEMBERSHIP_PACKAGE_4 = "monthly_4"
    MEMBERSHIP_PACKAGE_8 = "monthly_8"
    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_SUSPENDED = "suspended"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_INACTIVE, "Inactive"),
        (STATUS_SUSPENDED, "Suspended"),
    ]

    full_name = models.CharField(max_length=255)
    date_of_birth = models.DateField()
    contact_number = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    emergency_contact_name = models.CharField(max_length=255)
    emergency_contact_phone = models.CharField(max_length=30)
    membership_type = models.CharField(max_length=50, blank=True, default=MEMBERSHIP_PACKAGE_4)
    payment_plan = models.ForeignKey(
        "finance.PaymentPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members",
    )
    skill_level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default=LEVEL_BASIC)
    assigned_coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_members",
    )
    parent_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="child_members",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    joined_at = models.DateField(default=timezone.localdate)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_members",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name

    def save(self, *args, **kwargs):
        if self.payment_plan_id and self.membership_type != self.payment_plan.code:
            self.membership_type = self.payment_plan.code
        super().save(*args, **kwargs)

    @property
    def active_payment_plan(self):
        return self.payment_plan

    @property
    def package_label(self):
        if self.payment_plan_id and self.payment_plan:
            return self.payment_plan.name
        if self.membership_type == self.MEMBERSHIP_PACKAGE_8:
            return "Monthly Package - 8 Sessions"
        return "Monthly Package - 4 Sessions"

    @property
    def package_sessions(self):
        if self.payment_plan_id and self.payment_plan:
            return self.payment_plan.sessions_per_month
        if self.membership_type == self.MEMBERSHIP_PACKAGE_8:
            return 8
        return 4

    @property
    def package_amount(self):
        if self.payment_plan_id and self.payment_plan:
            return self.payment_plan.monthly_fee
        if self.membership_type == self.MEMBERSHIP_PACKAGE_8:
            return Decimal("160.00")
        return Decimal("100.00")

    @property
    def package_summary(self):
        if self.payment_plan_id and self.payment_plan:
            return self.payment_plan.summary
        if self.membership_type == self.MEMBERSHIP_PACKAGE_8:
            return "RM160 per month for 8 sessions"
        return "RM100 per month for 4 sessions"


class AdmissionApplication(models.Model):
    EXPERIENCE_NONE = "none"
    EXPERIENCE_SCHOOL = "school"
    EXPERIENCE_COMPETITIVE = "competitive"
    EXPERIENCE_CHOICES = [
        (EXPERIENCE_NONE, "New to badminton"),
        (EXPERIENCE_SCHOOL, "School / recreational experience"),
        (EXPERIENCE_COMPETITIVE, "Competitive / tournament experience"),
    ]

    TRAINING_OCCASIONAL = "occasional"
    TRAINING_WEEKLY = "weekly"
    TRAINING_INTENSIVE = "intensive"
    TRAINING_FREQUENCY_CHOICES = [
        (TRAINING_OCCASIONAL, "Just starting or occasional play"),
        (TRAINING_WEEKLY, "Training 1-2 times per week"),
        (TRAINING_INTENSIVE, "Training 3+ times per week"),
    ]

    GOAL_FUNDAMENTALS = "fundamentals"
    GOAL_TEAM = "team"
    GOAL_COMPETITION = "competition"
    GOAL_CHOICES = [
        (GOAL_FUNDAMENTALS, "Build strong basics"),
        (GOAL_TEAM, "Prepare for school/team play"),
        (GOAL_COMPETITION, "Train for competition"),
    ]

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    student_name = models.CharField(max_length=255)
    date_of_birth = models.DateField(null=True, blank=True)
    guardian_name = models.CharField(max_length=255)
    guardian_email = models.EmailField(blank=True)
    contact_number = models.CharField(max_length=30)
    preferred_program = models.CharField(max_length=255)
    preferred_location = models.CharField(max_length=255)
    playing_experience = models.CharField(max_length=20, choices=EXPERIENCE_CHOICES, default=EXPERIENCE_NONE)
    training_frequency = models.CharField(max_length=20, choices=TRAINING_FREQUENCY_CHOICES, default=TRAINING_OCCASIONAL)
    primary_goal = models.CharField(max_length=20, choices=GOAL_CHOICES, default=GOAL_FUNDAMENTALS)
    recommended_level = models.CharField(max_length=20, choices=Member.LEVEL_CHOICES, default=Member.LEVEL_BASIC)
    desired_username = models.CharField(max_length=150, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    rejection_reason = models.TextField(blank=True)
    linked_member = models.ForeignKey(
        "members.Member",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admission_applications",
    )
    linked_parent_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_applications",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_admission_applications",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.student_name} ({self.get_status_display()})"

    def refresh_recommended_level(self):
        score = 0
        if self.playing_experience == self.EXPERIENCE_SCHOOL:
            score += 1
        elif self.playing_experience == self.EXPERIENCE_COMPETITIVE:
            score += 2
        if self.training_frequency == self.TRAINING_WEEKLY:
            score += 1
        elif self.training_frequency == self.TRAINING_INTENSIVE:
            score += 2
        if self.primary_goal == self.GOAL_TEAM:
            score += 1
        elif self.primary_goal == self.GOAL_COMPETITION:
            score += 2

        if score >= 5:
            self.recommended_level = Member.LEVEL_ADVANCED
        elif score >= 2:
            self.recommended_level = Member.LEVEL_INTERMEDIATE
        else:
            self.recommended_level = Member.LEVEL_BASIC


class ProgressReport(models.Model):
    STATUS_ELITE = "elite"
    STATUS_ADVANCED = "advanced"
    STATUS_DEVELOPING = "developing"
    STATUS_FOUNDATION = "foundation"
    STATUS_CHOICES = [
        (STATUS_ELITE, "Elite"),
        (STATUS_ADVANCED, "Advanced"),
        (STATUS_DEVELOPING, "Developing"),
        (STATUS_FOUNDATION, "Foundation"),
    ]

    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="progress_reports")
    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="progress_reports",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    attendance_rate = models.FloatField(default=0)
    total_sessions = models.PositiveIntegerField(default=0)
    overall_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DEVELOPING)
    skill_snapshot = models.JSONField(default=dict, blank=True)
    skill_notes = models.JSONField(default=dict, blank=True)
    coach_reflection = models.TextField(blank=True)
    is_published = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_progress_reports",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period_end", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["member", "period_start", "period_end"],
                name="unique_progress_report_period_per_member",
            )
        ]

    def __str__(self):
        return f"{self.member.full_name} report ({self.period_start} - {self.period_end})"

    @property
    def period_label(self):
        return f"{self.period_start:%b %Y} - {self.period_end:%b %Y}"

    def refresh_metrics(self):
        from sessions.models import AttendanceRecord

        queryset = AttendanceRecord.objects.filter(
            member=self.member,
            training_session__session_date__range=(self.period_start, self.period_end),
        ).exclude(status=AttendanceRecord.STATUS_SCHEDULED)
        total = queryset.count()
        attended = queryset.filter(
            status__in=[AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE]
        ).count()
        self.total_sessions = total
        self.attendance_rate = round((attended / total) * 100, 1) if total else 0

# Create your models here.
