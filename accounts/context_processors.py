from accounts.utils import ROLE_ADMIN, ROLE_COACH, get_role_label, get_user_role, has_role


def global_dashboard_context(request):
    role = get_user_role(request.user)
    pending_payment_reviews = 0
    if request.user.is_authenticated and has_role(request.user, ROLE_ADMIN, ROLE_COACH):
        from payments.models import Payment

        pending_payment_reviews = Payment.objects.filter(status=Payment.STATUS_PENDING).count()

    return {
        "current_role": role,
        "current_role_label": get_role_label(role),
        "pending_payment_reviews": pending_payment_reviews,
    }
