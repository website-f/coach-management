from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.utils import ROLE_ADMIN

User = get_user_model()


class Command(BaseCommand):
    help = "Create an initial superuser if one does not already exist."

    def handle(self, *args, **options):
        username = self.get_env(
            "DJANGO_SUPERUSER_USERNAME",
            "INITIAL_SUPERUSER_USERNAME",
            "SUPERUSER_USERNAME",
            "ADMIN_USERNAME",
            default="admin",
        )
        email = self.get_env(
            "DJANGO_SUPERUSER_EMAIL",
            "INITIAL_SUPERUSER_EMAIL",
            "SUPERUSER_EMAIL",
            "ADMIN_EMAIL",
            default="admin@example.com",
        )
        password = self.get_env(
            "DJANGO_SUPERUSER_PASSWORD",
            "INITIAL_SUPERUSER_PASSWORD",
            "SUPERUSER_PASSWORD",
            "ADMIN_PASSWORD",
        )
        first_name = self.get_env(
            "DJANGO_SUPERUSER_FIRST_NAME",
            "INITIAL_SUPERUSER_FIRST_NAME",
            "SUPERUSER_FIRST_NAME",
            "ADMIN_FIRST_NAME",
            default="System",
        )
        last_name = self.get_env(
            "DJANGO_SUPERUSER_LAST_NAME",
            "INITIAL_SUPERUSER_LAST_NAME",
            "SUPERUSER_LAST_NAME",
            "ADMIN_LAST_NAME",
            default="Admin",
        )

        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write("Superuser already exists. Skipping bootstrap.")
            return

        if not password:
            self.stdout.write(
                "Missing superuser password env var. Set DJANGO_SUPERUSER_PASSWORD "
                "(or ADMIN_PASSWORD). Username defaults to 'admin'."
            )
            return

        existing_user = User.objects.filter(username=username).first()
        if existing_user:
            existing_user.email = email or existing_user.email
            existing_user.first_name = first_name or existing_user.first_name
            existing_user.last_name = last_name or existing_user.last_name
            existing_user.is_staff = True
            existing_user.is_superuser = True
            existing_user.set_password(password)
            existing_user.save()
            existing_user.profile.role = ROLE_ADMIN
            existing_user.profile.save()
            self.stdout.write(self.style.SUCCESS(f"Promoted existing user '{username}' to superuser."))
            return

        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        user.profile.role = ROLE_ADMIN
        user.profile.save()
        self.stdout.write(self.style.SUCCESS(f"Created superuser '{username}' successfully."))

    def get_env(self, *keys, default=None):
        import os

        for key in keys:
            value = os.environ.get(key)
            if value is not None and value != "":
                return value
        return default
