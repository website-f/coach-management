from django.core.management import call_command
from django.core.management.base import BaseCommand

from accounts.models import SystemFlag

STARTER_DATA_FLAG = "starter_dataset_seeded"


class Command(BaseCommand):
    help = "Seed the system login accounts and demo data if the starter dataset is missing."

    def handle(self, *args, **options):
        if SystemFlag.objects.filter(key=STARTER_DATA_FLAG).exists():
            self.stdout.write("Starter dataset already exists. Skipping bootstrap.")
            return

        call_command("seed_nyo_dashboard")
        SystemFlag.objects.update_or_create(key=STARTER_DATA_FLAG, defaults={"value": "true"})
        self.stdout.write(self.style.SUCCESS("System login accounts and demo data bootstrapped."))
