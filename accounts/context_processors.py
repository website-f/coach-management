from django.urls import reverse
from django.utils import timezone

from accounts.utils import ROLE_ADMIN, ROLE_COACH, ROLE_PARENT, ROLE_SUPERADMIN, get_role_label, get_user_role, has_role


def global_dashboard_context(request):
    role = get_user_role(request.user)
    # Templates compare against 'admin' — superadmin collapses into the admin
    # bucket for display purposes; use `is_superadmin` for super-only UI.
    template_role = ROLE_ADMIN if role == ROLE_SUPERADMIN else role
    parent_is_inactive = False
    if request.user.is_authenticated and role == ROLE_PARENT:
        from members.models import Member
        has_live_child = Member.objects.filter(
            parent_user=request.user,
            status__in=[Member.STATUS_ACTIVE, Member.STATUS_TRIAL],
        ).exists()
        has_any_child = Member.objects.filter(parent_user=request.user).exists()
        parent_is_inactive = has_any_child and not has_live_child
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
        pending_applications = AdmissionApplication.objects.filter(status=AdmissionApplication.STATUS_PENDING).count()

        session_queryset = TrainingSession.objects.select_related("coach").only(
            "id",
            "session_date",
            "start_time",
            "coach__first_name",
            "coach__last_name",
            "coach__username",
        ).order_by("session_date", "start_time")
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
        "current_role": template_role,
        "current_role_raw": role,
        "is_superadmin": role == ROLE_SUPERADMIN,
        "parent_is_inactive": parent_is_inactive,
        "current_role_label": get_role_label(role),
        "pending_payment_reviews": pending_payment_reviews,
        "pending_applications": pending_applications,
        "unread_notifications": unread_notifications,
        "sidebar_planner_url": sidebar_planner_url,
        "sidebar_planner_session": sidebar_planner_session,
    }
