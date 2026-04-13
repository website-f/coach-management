from django.conf import settings
from django.core.mail import send_mail

from accounts.models import Notification


def create_notification(user, title, message, url=""):
    if not user:
        return None
    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        url=url or "",
    )


def notify_users(users, title, message, url="", email_subject=None, email_message=None):
    seen_user_ids = set()
    email_targets = []
    for user in users:
        if not user or user.pk in seen_user_ids:
            continue
        seen_user_ids.add(user.pk)
        create_notification(user, title, message, url=url)
        if user.email:
            email_targets.append(user.email)

    if email_targets and email_subject and email_message:
        send_mail(
            email_subject,
            email_message,
            settings.DEFAULT_FROM_EMAIL,
            email_targets,
            fail_silently=True,
        )
