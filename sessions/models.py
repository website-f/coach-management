from django.conf import settings
from django.db import models


SYLLABUS_TRACK_BEGINNER = "beginner"
SYLLABUS_TRACK_INTERMEDIATE = "intermediate"
SYLLABUS_TRACK_ADVANCED = "advanced"
SYLLABUS_TRACK_PRO = "pro"
SYLLABUS_TRACK_CHOICES = [
    (SYLLABUS_TRACK_BEGINNER, "Beginner"),
    (SYLLABUS_TRACK_INTERMEDIATE, "Intermediate"),
    (SYLLABUS_TRACK_ADVANCED, "Advanced"),
    (SYLLABUS_TRACK_PRO, "Pro"),
]


class SyllabusTemplate(models.Model):
    TRACK_BEGINNER = SYLLABUS_TRACK_BEGINNER
    TRACK_INTERMEDIATE = SYLLABUS_TRACK_INTERMEDIATE
    TRACK_ADVANCED = SYLLABUS_TRACK_ADVANCED
    TRACK_PRO = SYLLABUS_TRACK_PRO
    TRACK_CHOICES = SYLLABUS_TRACK_CHOICES

    track = models.CharField(max_length=20, choices=TRACK_CHOICES, default=TRACK_BEGINNER, unique=True)
    name = models.CharField(max_length=255)
    source_document_name = models.CharField(max_length=255, blank=True)
    curriculum_year_label = models.CharField(max_length=100, default="Year 1")
    annual_goal = models.TextField()
    year_end_outcomes = models.TextField()
    assessment_approach = models.TextField(blank=True)
    assessment_methods = models.TextField(blank=True)
    curriculum_values = models.TextField(blank=True)
    annual_phase_notes = models.TextField(blank=True)
    ai_planner_instructions = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_syllabus_templates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["track"]

    def __str__(self):
        return f"{self.get_track_display()} Template"

    @property
    def year_end_outcome_list(self):
        return [item.strip("- ").strip() for item in (self.year_end_outcomes or "").splitlines() if item.strip()]

    @property
    def assessment_method_list(self):
        return [item.strip("- ").strip() for item in (self.assessment_methods or "").splitlines() if item.strip()]


class SyllabusStandard(models.Model):
    template = models.ForeignKey(
        SyllabusTemplate,
        on_delete=models.CASCADE,
        related_name="standards",
    )
    sort_order = models.PositiveIntegerField(default=1)
    code = models.CharField(max_length=20)
    title = models.CharField(max_length=255)
    focus = models.TextField()
    learning_standard_items = models.TextField(help_text="One learning standard per line.")
    performance_band_items = models.TextField(help_text="One performance band per line.")
    coach_hints = models.TextField(blank=True)
    assessment_focus = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_syllabus_standards",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["template__track", "sort_order", "code"]
        constraints = [
            models.UniqueConstraint(fields=["template", "code"], name="unique_syllabus_standard_code_per_template")
        ]

    def __str__(self):
        return f"{self.template.get_track_display()} {self.code}: {self.title}"

    @property
    def learning_standard_list(self):
        return [item.strip("- ").strip() for item in (self.learning_standard_items or "").splitlines() if item.strip()]

    @property
    def performance_band_list(self):
        return [item.strip("- ").strip() for item in (self.performance_band_items or "").splitlines() if item.strip()]


class WeeklySyllabus(models.Model):
    TRACK_BEGINNER = SYLLABUS_TRACK_BEGINNER
    TRACK_INTERMEDIATE = SYLLABUS_TRACK_INTERMEDIATE
    TRACK_ADVANCED = SYLLABUS_TRACK_ADVANCED
    TRACK_PRO = SYLLABUS_TRACK_PRO
    TRACK_CHOICES = SYLLABUS_TRACK_CHOICES

    track = models.CharField(max_length=20, choices=TRACK_CHOICES, default=TRACK_BEGINNER)
    template = models.ForeignKey(
        SyllabusTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="weekly_units",
    )
    standard = models.ForeignKey(
        SyllabusStandard,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="weekly_units",
    )
    month_number = models.PositiveIntegerField(null=True, blank=True)
    phase_name = models.CharField(max_length=120, blank=True)
    week_number = models.PositiveIntegerField()
    title = models.CharField(max_length=255)
    objective = models.TextField()
    warm_up_plan = models.TextField()
    technical_focus = models.TextField()
    tactical_focus = models.TextField()
    coaching_cues = models.TextField()
    assessment_focus = models.TextField(blank=True)
    success_criteria = models.TextField(blank=True)
    coach_notes = models.TextField(blank=True)
    homework = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_weekly_syllabi",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["track", "week_number"]
        constraints = [
            models.UniqueConstraint(fields=["track", "week_number"], name="unique_syllabus_track_week")
        ]

    def __str__(self):
        return f"{self.get_track_display()} Week {self.week_number}: {self.title}"

    @property
    def phase_label(self):
        if self.month_number and self.phase_name:
            return f"Month {self.month_number} - {self.phase_name}"
        if self.month_number:
            return f"Month {self.month_number}"
        return self.phase_name


class TrainingSession(models.Model):
    title = models.CharField(max_length=255)
    session_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    court = models.CharField(max_length=100)
    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="training_sessions",
    )
    members = models.ManyToManyField("members.Member", through="AttendanceRecord", related_name="training_sessions")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_training_sessions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-session_date", "start_time"]

    def __str__(self):
        return f"{self.title} ({self.session_date})"


class AttendanceRecord(models.Model):
    STATUS_SCHEDULED = "scheduled"
    STATUS_PRESENT = "present"
    STATUS_ABSENT = "absent"
    STATUS_LATE = "late"
    STATUS_CHOICES = [
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_PRESENT, "Present"),
        (STATUS_ABSENT, "Absent"),
        (STATUS_LATE, "Late"),
    ]

    training_session = models.ForeignKey(
        TrainingSession,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    member = models.ForeignKey(
        "members.Member",
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SCHEDULED)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_markings",
    )
    marked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["training_session__session_date", "member__full_name"]
        constraints = [
            models.UniqueConstraint(fields=["training_session", "member"], name="unique_member_session_attendance")
        ]

    def __str__(self):
        return f"{self.member} - {self.training_session} ({self.get_status_display()})"


class SessionFeedback(models.Model):
    training_session = models.ForeignKey(
        TrainingSession,
        on_delete=models.CASCADE,
        related_name="feedback_entries",
    )
    member = models.ForeignKey(
        "members.Member",
        on_delete=models.CASCADE,
        related_name="session_feedback_entries",
    )
    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="session_feedback_entries",
    )
    feedback_text = models.TextField()
    video_proof = models.FileField(upload_to="session_feedback_videos/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-training_session__session_date", "member__full_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["training_session", "member"],
                name="unique_feedback_per_member_per_session",
            )
        ]

    def __str__(self):
        return f"{self.member.full_name} feedback for {self.training_session.title}"


class SessionPlannerEntry(models.Model):
    SOURCE_OLLAMA = "ollama"
    SOURCE_FALLBACK = "fallback"
    SOURCE_CHOICES = [
        (SOURCE_OLLAMA, "Ollama"),
        (SOURCE_FALLBACK, "Rule-based fallback"),
    ]

    training_session = models.ForeignKey(
        TrainingSession,
        on_delete=models.CASCADE,
        related_name="planner_entries",
    )
    title = models.CharField(max_length=255)
    user_prompt = models.TextField()
    assistant_response = models.TextField()
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_OLLAMA)
    model_name = models.CharField(max_length=120, blank=True)
    saved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="saved_session_plans",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.training_session.title} - {self.title}"

# Create your models here.
