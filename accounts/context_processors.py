from django.urls import reverse
from django.utils import timezone

from accounts.utils import ROLE_ADMIN, ROLE_COACH, get_role_label, get_user_role, has_role


def global_dashboard_context(request):
    role = get_user_role(request.user)
    pending_payment_reviews = 0
    pending_applications = 0
    unread_notifications = 0
    sidebar_planner_url = ""
    sidebar_planner_session = None
    if request.user.is_authenticated and has_role(request.user, ROLE_ADMIN, ROLE_COACH):
        from members.models import AdmissionApplication
        from payments.models import Payment
        from sessions.models import TrainingSession

        if has_role(request.user, ROLE_ADMIN):
            pending_payment_reviews = Payment.objects.filter(status=Payment.STATUS_PENDING).count()
        pending_applications = AdmissionApplication.objects.filter(
            status=AdmissionApplication.STATUS_PENDING
        ).count()

        session_queryset = TrainingSession.objects.select_related("coach").order_by("session_date", "start_time")
        if has_role(request.user, ROLE_COACH) and not has_role(request.user, ROLE_ADMIN):
            session_queryset = session_queryset.filter(coach=request.user)

        today = timezone.localdate()
        sidebar_planner_session = session_queryset.filter(session_date__gte=today).first() or session_queryset.order_by(
            "-session_date", "-start_time"
        ).first()
        if sidebar_planner_session:
            sidebar_planner_url = (
                f"{reverse('sessions:plan', kwargs={'pk': sidebar_planner_session.pk})}?autostart=1"
            )
        else:
            sidebar_planner_url = reverse("sessions:list")
    if request.user.is_authenticated:
        from accounts.models import Notification

        unread_notifications = Notification.objects.filter(user=request.user, is_read=False).count()

    return {
        "current_role": role,
        "current_role_label": get_role_label(role),
        "pending_payment_reviews": pending_payment_reviews,
        "pending_applications": pending_applications,
        "unread_notifications": unread_notifications,
        "sidebar_planner_url": sidebar_planner_url,
        "sidebar_planner_session": sidebar_planner_session,
    }
