from django.db import migrations, models


def migrate_membership_packages(apps, schema_editor):
    Member = apps.get_model("members", "Member")
    Member.objects.filter(membership_type="monthly").update(membership_type="monthly_4")
    Member.objects.filter(membership_type="yearly").update(membership_type="monthly_8")


class Migration(migrations.Migration):

    dependencies = [
        ("members", "0003_admissionapplication_playing_experience_and_more"),
    ]

    operations = [
        migrations.RunPython(migrate_membership_packages, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="member",
            name="membership_type",
            field=models.CharField(
                choices=[
                    ("monthly_4", "Monthly Package - RM100 (4 sessions)"),
                    ("monthly_8", "Monthly Package - RM160 (8 sessions)"),
                ],
                default="monthly_4",
                max_length=20,
            ),
        ),
    ]
