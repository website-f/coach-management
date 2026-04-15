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
    STATUS_TRIAL = "trial"
    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_CHURNED = "churned"
    STATUS_CHOICES = [
        (STATUS_TRIAL, "Trial"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_INACTIVE, "Inactive"),
        (STATUS_CHURNED, "Churned"),
    ]

    TRIAL_OUTCOME_PENDING = "pending"
    TRIAL_OUTCOME_CONVERTED = "converted"
    TRIAL_OUTCOME_NO_SHOW = "no_show"
    TRIAL_OUTCOME_NOT_READY = "not_ready"
    TRIAL_OUTCOME_DECLINED = "declined"
    TRIAL_OUTCOME_CHOICES = [
        (TRIAL_OUTCOME_PENDING, "Pending"),
        (TRIAL_OUTCOME_CONVERTED, "Converted"),
        (TRIAL_OUTCOME_NO_SHOW, "No Show"),
        (TRIAL_OUTCOME_NOT_READY, "Not Ready"),
        (TRIAL_OUTCOME_DECLINED, "Declined"),
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
    program_enrolled = models.CharField(max_length=255, blank=True)
    syllabus_root = models.ForeignKey(
        "club_sessions.SyllabusRoot",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members",
    )
    assigned_coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_members",
    )
    assigned_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_students",
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
    trial_linked_date = models.DateField(null=True, blank=True)
    trial_date = models.DateField(null=True, blank=True)
    trial_outcome = models.CharField(
        max_length=20,
        choices=TRIAL_OUTCOME_CHOICES,
        default=TRIAL_OUTCOME_PENDING,
    )
    parent_feedback = models.TextField(blank=True)
    conversion_reason = models.TextField(blank=True)
    subscription_started_at = models.DateField(null=True, blank=True)
    retention_risk_score = models.PositiveSmallIntegerField(default=0)
    churn_reason = models.TextField(blank=True)
    next_action = models.TextField(blank=True)
    last_contacted_at = models.DateField(null=True, blank=True)
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
    def start_date(self):
        return self.subscription_started_at or self.joined_at

    @property
    def latest_application(self):
        return self.admission_applications.order_by("-submitted_at").first()

    @property
    def lead_source(self):
        application = self.latest_application
        return application.source if application else ""

    @property
    def interest_level(self):
        application = self.latest_application
        return application.interest_level if application else ""

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
    SOURCE_WEBSITE = "website"
    SOURCE_WHATSAPP = "whatsapp"
    SOURCE_REFERRAL = "referral"
    SOURCE_INSTAGRAM = "instagram"
    SOURCE_TIKTOK = "tiktok"
    SOURCE_WALK_IN = "walk_in"
    SOURCE_OTHER = "other"
    SOURCE_CHOICES = [
        (SOURCE_WEBSITE, "Website"),
        (SOURCE_WHATSAPP, "WhatsApp"),
        (SOURCE_REFERRAL, "Referral"),
        (SOURCE_INSTAGRAM, "Instagram"),
        (SOURCE_TIKTOK, "TikTok"),
        (SOURCE_WALK_IN, "Walk-in"),
        (SOURCE_OTHER, "Other"),
    ]

    INTEREST_COLD = "cold"
    INTEREST_WARM = "warm"
    INTEREST_HOT = "hot"
    INTEREST_LEVEL_CHOICES = [
        (INTEREST_COLD, "Cold"),
        (INTEREST_WARM, "Warm"),
        (INTEREST_HOT, "Hot"),
    ]

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
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES, default=SOURCE_WEBSITE)
    interest_level = models.CharField(max_length=20, choices=INTEREST_LEVEL_CHOICES, default=INTEREST_WARM)
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
    assigned_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_admission_applications",
    )
    last_followed_up_at = models.DateField(null=True, blank=True)
    next_action = models.TextField(blank=True)
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


class CommunicationLog(models.Model):
    CHANNEL_WHATSAPP = "whatsapp"
    CHANNEL_CALL = "call"
    CHANNEL_EMAIL = "email"
    CHANNEL_INTERNAL = "internal"
    CHANNEL_CHOICES = [
        (CHANNEL_WHATSAPP, "WhatsApp"),
        (CHANNEL_CALL, "Call"),
        (CHANNEL_EMAIL, "Email"),
        (CHANNEL_INTERNAL, "Internal"),
    ]

    TYPE_FOLLOW_UP = "follow_up"
    TYPE_TRIAL = "trial"
    TYPE_PAYMENT = "payment"
    TYPE_RETENTION = "retention"
    TYPE_CHURN = "churn"
    TYPE_NOTE = "note"
    MESSAGE_TYPE_CHOICES = [
        (TYPE_FOLLOW_UP, "Follow Up"),
        (TYPE_TRIAL, "Trial Update"),
        (TYPE_PAYMENT, "Payment Update"),
        (TYPE_RETENTION, "Retention"),
        (TYPE_CHURN, "Churn"),
        (TYPE_NOTE, "General Note"),
    ]

    lead = models.ForeignKey(
        "members.AdmissionApplication",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="communication_logs",
    )
    member = models.ForeignKey(
        "members.Member",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="communication_logs",
    )
    happened_at = models.DateTimeField(default=timezone.now)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default=CHANNEL_WHATSAPP)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, default=TYPE_FOLLOW_UP)
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="communication_logs",
    )
    outcome = models.CharField(max_length=255)
    notes = models.TextField(blank=True)
    next_step = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-happened_at", "-created_at"]

    def __str__(self):
        target = self.member or self.lead
        return f"{target} - {self.get_channel_display()}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        happened_date = timezone.localtime(self.happened_at).date()
        if self.lead_id:
            update_fields = ["last_followed_up_at"]
            self.lead.last_followed_up_at = happened_date
            if self.next_step:
                self.lead.next_action = self.next_step
                update_fields.append("next_action")
            self.lead.save(update_fields=update_fields + ["updated_at"])
        if self.member_id:
            update_fields = ["last_contacted_at"]
            self.member.last_contacted_at = happened_date
            if self.next_step:
                self.member.next_action = self.next_step
                update_fields.append("next_action")
            self.member.save(update_fields=update_fields + ["updated_at"])


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
