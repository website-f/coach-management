import json
from datetime import date
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import RedirectView, TemplateView

from accounts.mixins import ParentRequiredMixin
from accounts.utils import (
    ROLE_ADMIN,
    ROLE_COACH,
    ROLE_HEADCOUNT,
    ROLE_PARENT,
    get_role_label,
    get_user_role,
    has_role,
)
from finance.models import Invoice
from members.models import Member
from payments.models import Payment
from sessions.models import AttendanceRecord, TrainingSession


def shift_month(source_date, delta):
    month_index = source_date.month - 1 + delta
    year = source_date.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def build_month_labels(month_count=6):
    current = timezone.localdate().replace(day=1)
    months = [shift_month(current, offset) for offset in range(-(month_count - 1), 1)]
    return months


def build_chart_payload(labels, values, label):
    return json.dumps(
        {
            "labels": labels,
            "datasets": [
                {
                    "label": label,
                    "data": values,
                    "borderColor": "#F5A623",
                    "backgroundColor": "rgba(245, 166, 35, 0.45)",
                    "borderWidth": 2,
                    "fill": False,
                    "tension": 0.35,
                }
            ],
        }
    )


def normalize_month(value):
    if hasattr(value, "date"):
        value = value.date()
    return value.replace(day=1)


class HomeRedirectView(RedirectView):
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            return reverse("accounts:dashboard")
        return reverse("accounts:login")


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        role = get_user_role(user)
        members = Member.objects.select_related("assigned_coach", "parent_user")
        invoices = Invoice.objects.select_related("member")
        attendance = AttendanceRecord.objects.select_related("member", "training_session")
        sessions = TrainingSession.objects.select_related("coach")

        if role == ROLE_PARENT:
            members = members.filter(parent_user=user)
            invoices = invoices.filter(member__in=members)
            attendance = attendance.filter(member__in=members)
            sessions = sessions.filter(attendance_records__member__in=members).distinct()

        today = timezone.localdate()
        month_start = today.replace(day=1)
        months = build_month_labels()
        month_labels = [month.strftime("%b %Y") for month in months]

        paid_invoices = invoices.filter(status=Invoice.STATUS_PAID)
        pending_payments = Payment.objects.filter(status=Payment.STATUS_PENDING)

        if role == ROLE_PARENT:
            pending_payments = pending_payments.filter(invoice__member__in=members)

        revenue_map = {
            normalize_month(item["month"]): float(item["total"] or 0)
            for item in paid_invoices.annotate(month=TruncMonth("period"))
            .values("month")
            .annotate(total=Sum("amount"))
        }
        revenue_values = [revenue_map.get(month, 0) for month in months]

        attendance_queryset = attendance.exclude(status=AttendanceRecord.STATUS_SCHEDULED)
        monthly_attendance = {
            normalize_month(item["month"]): (
                round((item["attended"] / item["total"]) * 100, 1) if item["total"] else 0
            )
            for item in attendance_queryset.annotate(month=TruncMonth("training_session__session_date"))
            .values("month")
            .annotate(
                total=Count("id"),
                attended=Count(
                    "id",
                    filter=Q(
                        status__in=[
                            AttendanceRecord.STATUS_PRESENT,
                            AttendanceRecord.STATUS_LATE,
                        ]
                    ),
                ),
            )
        }
        attendance_values = [monthly_attendance.get(month, 0) for month in months]

        growth_map = {
            normalize_month(item["month"]): item["count"]
            for item in members.annotate(month=TruncMonth("joined_at"))
            .values("month")
            .annotate(count=Count("id"))
        }
        running_total = 0
        growth_values = []
        for month in months:
            running_total += growth_map.get(month, 0)
            growth_values.append(running_total)

        total_active_members = members.filter(status=Member.STATUS_ACTIVE).count()
        monthly_revenue = (
            paid_invoices.filter(period__year=month_start.year, period__month=month_start.month).aggregate(
                total=Sum("amount")
            )["total"]
            or Decimal("0.00")
        )
        attendance_total = attendance_queryset.count()
        attendance_present = attendance_queryset.filter(
            status__in=[AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE]
        ).count()
        attendance_rate = round((attendance_present / attendance_total) * 100, 1) if attendance_total else 0
        pending_count = pending_payments.count()
        new_registrations = members.filter(joined_at__year=today.year, joined_at__month=today.month).count()

        cards = []
        if role in {ROLE_ADMIN, ROLE_COACH}:
            cards = [
                {"label": "Total Active Members", "value": total_active_members, "icon": "fa-users"},
                {"label": "Monthly Revenue", "value": f"RM {monthly_revenue:,.2f}", "icon": "fa-wallet"},
                {"label": "Attendance Rate", "value": f"{attendance_rate}%", "icon": "fa-chart-line"},
                {"label": "Pending Payments", "value": pending_count, "icon": "fa-hourglass-half"},
                {"label": "New Registrations", "value": new_registrations, "icon": "fa-user-plus"},
            ]
        elif role == ROLE_HEADCOUNT:
            cards = [
                {"label": "Attendance Rate", "value": f"{attendance_rate}%", "icon": "fa-clipboard-check"},
                {"label": "Sessions This Month", "value": sessions.filter(session_date__month=today.month).count(), "icon": "fa-calendar-days"},
            ]
        elif role == ROLE_PARENT:
            outstanding = invoices.exclude(status=Invoice.STATUS_PAID).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
            cards = [
                {"label": "Linked Players", "value": members.count(), "icon": "fa-child-reaching"},
                {"label": "Outstanding Balance", "value": f"RM {outstanding:,.2f}", "icon": "fa-file-invoice-dollar"},
                {"label": "Attendance Rate", "value": f"{attendance_rate}%", "icon": "fa-shield-heart"},
            ]

        context.update(
            {
                "dashboard_cards": cards,
                "current_role_label": get_role_label(role),
                "show_revenue_chart": role in {ROLE_ADMIN, ROLE_COACH},
                "show_growth_chart": role in {ROLE_ADMIN, ROLE_COACH},
                "show_attendance_chart": role in {ROLE_ADMIN, ROLE_COACH, ROLE_HEADCOUNT, ROLE_PARENT},
                "revenue_chart_data": build_chart_payload(month_labels, revenue_values, "Monthly Revenue"),
                "attendance_chart_data": build_chart_payload(month_labels, attendance_values, "Attendance Rate"),
                "growth_chart_data": build_chart_payload(month_labels, growth_values, "Member Growth"),
                "recent_sessions": sessions.order_by("-session_date", "-start_time")[:5],
                "recent_payments": Payment.objects.select_related("invoice", "invoice__member", "paid_by").order_by("-submitted_at")[:5]
                if role in {ROLE_ADMIN, ROLE_COACH}
                else Payment.objects.select_related("invoice", "invoice__member", "paid_by")
                .filter(invoice__member__in=members)
                .order_by("-submitted_at")[:5],
                "children": members.order_by("full_name") if role == ROLE_PARENT else None,
            }
        )
        return context

# Create your views here.
