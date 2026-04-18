from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("club_sessions", "0006_syllabusroot_alter_syllabustemplate_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="sessionfeedback",
            name="skill_notes",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="sessionfeedback",
            name="skill_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
