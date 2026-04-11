from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand

from members.models import Member

User = get_user_model()


class Command(BaseCommand):
    help = "Seed the system login accounts and demo data on a fresh database only."

    def handle(self, *args, **options):
        if User.objects.exists() or Member.objects.exists():
            self.stdout.write("Existing data detected. Skipping system bootstrap.")
            return

        call_command("seed_nyo_dashboard")
        self.stdout.write(self.style.SUCCESS("System login accounts and demo data bootstrapped."))
