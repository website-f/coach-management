from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("club_sessions", "0008_sessionchecklistreport"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendancerecord",
            name="reschedule_count",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="attendancerecord",
            name="original_session_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]
