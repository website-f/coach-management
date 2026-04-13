from django.contrib.auth import get_user_model
from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver

from accounts.models import UserProfile
from accounts.utils import bootstrap_groups, sync_user_role

User = get_user_model()


@receiver(post_save, sender=User)
def ensure_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=UserProfile)
def sync_profile_role(sender, instance, **kwargs):
    sync_user_role(instance.user, instance.role)


@receiver(post_migrate)
def sync_role_groups_after_migrate(sender, **kwargs):
    bootstrap_groups()
