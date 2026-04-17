from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("members", "0006_admissionapplication_assigned_staff_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="progressreport",
            name="improvement_plan",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="progressreport",
            name="report_brief",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="progressreport",
            name="video_proof",
            field=models.FileField(blank=True, upload_to="progress_report_videos/"),
        ),
    ]
