from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from accounts.models import LandingPageContent, UserProfile
from finance.models import Invoice
from finance.models import Product
from members.models import AdmissionApplication, Member
from payments.models import Payment
from sessions.models import TrainingSession


class HealthCheckView(View):
    def get(self, request, *args, **kwargs):
        return JsonResponse({"status": "ok"})


class LandingPageView(TemplateView):
    template_name = "landing.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("accounts:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        landing_content = LandingPageContent.get_solo()
        context.update(
            {
                "landing_content": landing_content,
                "active_members": Member.objects.filter(status=Member.STATUS_ACTIVE).count(),
                "coach_count": UserProfile.objects.filter(role=UserProfile.ROLE_COACH).count(),
                "pending_reviews": Payment.objects.filter(status=Payment.STATUS_PENDING).count(),
                "sessions_this_month": TrainingSession.objects.filter(
                    session_date__year=today.year,
                    session_date__month=today.month,
                ).count(),
                "new_registrations": Member.objects.filter(
                    joined_at__year=today.year,
                    joined_at__month=today.month,
                ).count(),
                "monthly_paid_invoices": Invoice.objects.filter(
                    period__year=today.year,
                    period__month=today.month,
                    status=Invoice.STATUS_PAID,
                ).count(),
                "application_count": AdmissionApplication.objects.filter(status=AdmissionApplication.STATUS_PENDING).count(),
                "product_count": Product.objects.filter(is_active=True).count(),
                "role_cards": [
                    {
                        "title": "Parents",
                        "subtitle": "Track children, invoices, and attendance in one place.",
                        "icon": "fa-child-reaching",
                        "url": "/accounts/login/?role=parent",
                    },
                    {
                        "title": "Coaches",
                        "subtitle": "Manage sessions, review proofs, and stay on top of your squad.",
                        "icon": "fa-user-check",
                        "url": "/accounts/login/?role=coach",
                    },
                    {
                        "title": "Admins",
                        "subtitle": "Run club operations, finance, and approvals from the same workspace.",
                        "icon": "fa-shield-halved",
                        "url": "/accounts/login/?role=admin",
                    },
                ],
            }
        )
        return context
