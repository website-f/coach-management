from django.db import migrations, models


def forward(apps, schema_editor):
    UserProfile = apps.get_model("accounts", "UserProfile")
    Group = apps.get_model("auth", "Group")
    # Promote existing "admin" (formerly superadmin-level) to "superadmin"
    UserProfile.objects.filter(role="admin").update(role="superadmin")
    # Promote "headcount" to the new regular "admin"
    UserProfile.objects.filter(role="headcount").update(role="admin")
    # Rename Django groups to match new semantics
    Group.objects.filter(name="Admin").update(name="Superadmin")
    Group.objects.filter(name="Headcount").update(name="Admin")


def reverse(apps, schema_editor):
    UserProfile = apps.get_model("accounts", "UserProfile")
    Group = apps.get_model("auth", "Group")
    UserProfile.objects.filter(role="admin").update(role="headcount")
    UserProfile.objects.filter(role="superadmin").update(role="admin")
    Group.objects.filter(name="Admin").update(name="Headcount")
    Group.objects.filter(name="Superadmin").update(name="Admin")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_userprofile_must_change_password"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userprofile",
            name="role",
            field=models.CharField(
                choices=[
                    ("superadmin", "Superadmin"),
                    ("admin", "Admin"),
                    ("coach", "Coach"),
                    ("parent", "Parent"),
                ],
                default="parent",
                max_length=20,
            ),
        ),
        migrations.RunPython(forward, reverse),
    ]
