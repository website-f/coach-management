from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.utils import ROLE_ADMIN

User = get_user_model()


class Command(BaseCommand):
    help = "Create an initial superuser if one does not already exist."

    def handle(self, *args, **options):
        username = self.get_env("DJANGO_SUPERUSER_USERNAME", "INITIAL_SUPERUSER_USERNAME")
        email = self.get_env("DJANGO_SUPERUSER_EMAIL", "INITIAL_SUPERUSER_EMAIL", default="")
        password = self.get_env("DJANGO_SUPERUSER_PASSWORD", "INITIAL_SUPERUSER_PASSWORD")
        first_name = self.get_env("DJANGO_SUPERUSER_FIRST_NAME", "INITIAL_SUPERUSER_FIRST_NAME", default="")
        last_name = self.get_env("DJANGO_SUPERUSER_LAST_NAME", "INITIAL_SUPERUSER_LAST_NAME", default="")

        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write("Superuser already exists. Skipping bootstrap.")
            return

        if not username or not password:
            self.stdout.write(
                "Missing superuser env vars. Set DJANGO_SUPERUSER_USERNAME and "
                "DJANGO_SUPERUSER_PASSWORD to bootstrap an admin account."
            )
            return

        if User.objects.filter(username=username).exists():
            self.stdout.write(f"User '{username}' already exists. Skipping bootstrap.")
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
