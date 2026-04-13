from accounts.utils import ROLE_ADMIN, ROLE_COACH, get_role_label, get_user_role, has_role


def global_dashboard_context(request):
    role = get_user_role(request.user)
    pending_payment_reviews = 0
    pending_applications = 0
    unread_notifications = 0
    if request.user.is_authenticated and has_role(request.user, ROLE_ADMIN, ROLE_COACH):
        from members.models import AdmissionApplication
        from payments.models import Payment

        if has_role(request.user, ROLE_ADMIN):
            pending_payment_reviews = Payment.objects.filter(status=Payment.STATUS_PENDING).count()
        pending_applications = AdmissionApplication.objects.filter(
            status=AdmissionApplication.STATUS_PENDING
        ).count()
    if request.user.is_authenticated:
        from accounts.models import Notification

        unread_notifications = Notification.objects.filter(user=request.user, is_read=False).count()

    return {
        "current_role": role,
        "current_role_label": get_role_label(role),
        "pending_payment_reviews": pending_payment_reviews,
        "pending_applications": pending_applications,
        "unread_notifications": unread_notifications,
    }
