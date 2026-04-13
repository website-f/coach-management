from django.conf import settings
from django.db import models


class WeeklySyllabus(models.Model):
    TRACK_BEGINNER = "beginner"
    TRACK_INTERMEDIATE = "intermediate"
    TRACK_ADVANCED = "advanced"
    TRACK_PRO = "pro"
    TRACK_CHOICES = [
        (TRACK_BEGINNER, "Beginner"),
        (TRACK_INTERMEDIATE, "Intermediate"),
        (TRACK_ADVANCED, "Advanced"),
        (TRACK_PRO, "Pro"),
    ]

    track = models.CharField(max_length=20, choices=TRACK_CHOICES, default=TRACK_BEGINNER)
    week_number = models.PositiveIntegerField()
    title = models.CharField(max_length=255)
    objective = models.TextField()
    warm_up_plan = models.TextField()
    technical_focus = models.TextField()
    tactical_focus = models.TextField()
    coaching_cues = models.TextField()
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
