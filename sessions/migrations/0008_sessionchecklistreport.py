from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("club_sessions", "0007_sessionfeedback_skill_snapshot_and_notes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SessionChecklistReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("checked_items", models.JSONField(blank=True, default=list)),
                ("feedback_text", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "coach",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="session_checklist_reports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "training_session",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="checklist_reports",
                        to="club_sessions.trainingsession",
                    ),
                ),
            ],
            options={
                "ordering": ["-updated_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="sessionchecklistreport",
            constraint=models.UniqueConstraint(
                fields=("training_session", "coach"),
                name="unique_checklist_report_per_session_coach",
            ),
        ),
    ]
