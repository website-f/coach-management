import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import FormView, ListView, RedirectView, TemplateView, UpdateView

from accounts.forms import CoachAccountForm, LandingPageContentForm
from accounts.mixins import AdminRequiredMixin, ParentRequiredMixin
from accounts.models import LandingPageContent, Notification, UserProfile
from accounts.utils import (
    ROLE_ADMIN,
    ROLE_COACH,
    ROLE_HEADCOUNT,
    ROLE_PARENT,
    get_role_label,
    get_user_role,
    has_role,
)
from finance.models import Invoice, Product
from members.models import AdmissionApplication, Member, ProgressReport
from members.services import (
    attendance_streak,
    build_recent_progress_items,
    build_training_plan_items,
    calculate_report_overall_score,
    format_session_duration,
    report_goal_percentage,
    report_grade_label,
    report_score_delta,
)
from payments.models import Payment
from sessions.models import AttendanceRecord, SessionFeedback, TrainingSession

User = get_user_model()


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


def attendance_rate_for_queryset(queryset):
    scoped_queryset = queryset.exclude(status=AttendanceRecord.STATUS_SCHEDULED)
    total = scoped_queryset.count()
    if not total:
        return 0
    attended = scoped_queryset.filter(
        status__in=[AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE]
    ).count()
    return round((attended / total) * 100, 1)


def build_portal_highlights(latest_report, previous_report):
    progress_items = build_recent_progress_items(latest_report, previous_report, limit=2)
    if progress_items:
        return progress_items
    return [
        {"label": "Footwork Speed", "value": 64, "delta": 0, "delta_label": "Stable", "tone": "neutral"},
        {"label": "Smash Power", "value": 58, "delta": 0, "delta_label": "Stable", "tone": "neutral"},
    ]


class HomeRedirectView(RedirectView):
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            return reverse("accounts:dashboard")
        return reverse("accounts:login")


class RoleAwareLoginView(LoginView):
    template_name = "registration/login.html"

    def get_success_url(self):
        if has_role(self.request.user, ROLE_PARENT):
            has_onboarding_fees = Invoice.objects.filter(
                member__parent_user=self.request.user,
                is_onboarding_fee=True,
            ).exclude(status=Invoice.STATUS_PAID).exists()
            if has_onboarding_fees:
                return f"{reverse('payments:my_payments')}?onboarding=1"
        return super().get_success_url()


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
        application_count = AdmissionApplication.objects.filter(status=AdmissionApplication.STATUS_PENDING).count()
        report_queryset = ProgressReport.objects.select_related("member", "coach")
        product_count = Product.objects.filter(is_active=True).count()

        paid_invoices = invoices.filter(status=Invoice.STATUS_PAID)
        pending_payments = Payment.objects.select_related("invoice", "invoice__member", "paid_by").filter(
            status=Payment.STATUS_PENDING
        )
        recent_payments = Payment.objects.select_related(
            "invoice",
            "invoice__member",
            "paid_by",
            "reviewed_by",
        )

        if role == ROLE_COACH and not has_role(user, ROLE_ADMIN):
            pending_payments = pending_payments.filter(invoice__member__assigned_coach=user)
            recent_payments = recent_payments.filter(invoice__member__assigned_coach=user)
        elif role == ROLE_PARENT:
            pending_payments = pending_payments.filter(invoice__member__in=members)
            recent_payments = recent_payments.filter(invoice__member__in=members)

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
        recent_payments = recent_payments.order_by("-submitted_at")[:5]

        dashboard_intro = {
            "eyebrow": "Club Operations",
            "title": "Keep every badminton workflow moving smoothly.",
            "body": "Track the live state of members, sessions, and payments from one connected workspace.",
            "meta": "Live club snapshot",
        }
        dashboard_actions = []
        workspace_highlights = []
        workspace_lists = {}
        child_summaries = []
        student_portal = None

        upcoming_sessions = sessions.filter(session_date__gte=today).order_by("session_date", "start_time")[:5]
        week_window_end = today + timedelta(days=6)

        if role == ROLE_ADMIN:
            coach_count = User.objects.filter(profile__role=UserProfile.ROLE_COACH).count()
            dashboard_intro = {
                "eyebrow": "Admin Workspace",
                "title": "Academy command center",
                "body": "Admin owns planning, staff setup, finance visibility, and payment verification from one central workspace.",
                "meta": f"{pending_count} payment review(s) waiting",
            }
            dashboard_actions = [
                {"label": "Manage Members", "url": reverse("members:list"), "icon": "fa-users"},
                {"label": "Coach Accounts", "url": reverse("accounts:coaches"), "icon": "fa-user-tie"},
                {"label": "Plan Sessions", "url": reverse("sessions:list"), "icon": "fa-calendar-days"},
                {"label": "Progress Reports", "url": reverse("members:report_list"), "icon": "fa-file-lines"},
                {
                    "label": "Applications",
                    "url": reverse("members:application_list"),
                    "icon": "fa-user-plus",
                    "badge": application_count or None,
                },
                {
                    "label": "Review Payments",
                    "url": reverse("payments:pending_reviews"),
                    "icon": "fa-receipt",
                    "badge": pending_count or None,
                },
                {"label": "All Payments", "url": reverse("payments:payment_history"), "icon": "fa-money-check-dollar"},
                {"label": "Store", "url": reverse("finance:product_list"), "icon": "fa-bag-shopping"},
                {"label": "Website", "url": reverse("accounts:website"), "icon": "fa-globe"},
                {"label": "Open Finance", "url": reverse("finance:overview"), "icon": "fa-sack-dollar"},
            ]
            workspace_highlights = [
                {"label": "Sessions This Week", "value": sessions.filter(session_date__range=(today, week_window_end)).count(), "tone": "info"},
                {"label": "Active Coaches", "value": coach_count, "tone": "success"},
                {"label": "Unpaid Invoices", "value": invoices.exclude(status=Invoice.STATUS_PAID).count(), "tone": "warning"},
                {"label": "New Registrations", "value": new_registrations, "tone": "neutral"},
            ]
            workspace_lists = {
                "queue": pending_payments.order_by("-submitted_at")[:5],
                "upcoming_sessions": upcoming_sessions,
                "member_focus": members.order_by("-joined_at", "full_name")[:5],
                "reports": report_queryset.order_by("-period_end")[:5],
                "applications": AdmissionApplication.objects.filter(
                    status=AdmissionApplication.STATUS_PENDING
                ).order_by("-submitted_at")[:5],
            }
        elif role == ROLE_COACH:
            coach_members = members.filter(assigned_coach=user)
            coach_sessions = sessions.filter(coach=user)
            coach_reports = report_queryset.filter(member__assigned_coach=user)
            dashboard_intro = {
                "eyebrow": "Coach Workspace",
                "title": "Your squad, sessions, and coaching follow-ups",
                "body": "Use this view to run the schedule assigned by admin, monitor your students, track attendance, and publish post-session feedback.",
                "meta": f"{coach_sessions.filter(session_date__gte=today).count()} upcoming session(s)",
            }
            dashboard_actions = [
                {"label": "My Sessions", "url": reverse("sessions:list"), "icon": "fa-calendar-days"},
                {"label": "My Players", "url": reverse("members:list"), "icon": "fa-users-viewfinder"},
                {"label": "Progress Reports", "url": reverse("members:report_list"), "icon": "fa-file-lines"},
                {"label": "Student Payments", "url": reverse("payments:payment_history"), "icon": "fa-money-check-dollar"},
                {"label": "Invoices", "url": reverse("finance:invoice_list"), "icon": "fa-file-invoice-dollar"},
                {"label": "Store", "url": reverse("finance:product_list"), "icon": "fa-bag-shopping"},
            ]
            workspace_highlights = [
                {"label": "Assigned Players", "value": coach_members.count(), "tone": "info"},
                {"label": "Upcoming Sessions", "value": coach_sessions.filter(session_date__gte=today).count(), "tone": "success"},
                {"label": "Pending Invoices", "value": invoices.filter(member__assigned_coach=user).exclude(status=Invoice.STATUS_PAID).count(), "tone": "warning"},
                {"label": "Draft Reports", "value": coach_reports.filter(is_published=False).count(), "tone": "neutral"},
            ]
            workspace_lists = {
                "queue": coach_reports.filter(is_published=False).order_by("-period_end")[:5],
                "upcoming_sessions": coach_sessions.filter(session_date__gte=today).order_by("session_date", "start_time")[:5],
                "member_focus": coach_members.order_by("full_name")[:6],
                "reports": coach_reports.order_by("-period_end")[:5],
            }
        elif role == ROLE_HEADCOUNT:
            today_sessions = sessions.filter(session_date=today).order_by("start_time")
            scheduled_today = attendance.filter(
                training_session__session_date=today,
                status=AttendanceRecord.STATUS_SCHEDULED,
            ).count()
            logged_today = attendance.filter(training_session__session_date=today).exclude(
                status=AttendanceRecord.STATUS_SCHEDULED
            ).count()
            dashboard_intro = {
                "eyebrow": "Headcount Workspace",
                "title": "Attendance command center",
                "body": "Move through today’s session list, find open attendance rows fast, and keep the live floor count accurate for coaches and parents.",
                "meta": f"{scheduled_today} attendance row(s) still open today",
            }
            dashboard_actions = [
                {"label": "Open Sessions", "url": reverse("sessions:list"), "icon": "fa-calendar-days"},
                {"label": "Mark Attendance", "url": reverse("sessions:list"), "icon": "fa-clipboard-check"},
                {"label": "Store", "url": reverse("finance:product_list"), "icon": "fa-bag-shopping"},
            ]
            workspace_highlights = [
                {"label": "Sessions Today", "value": today_sessions.count(), "tone": "info"},
                {"label": "Rows Logged", "value": logged_today, "tone": "success"},
                {"label": "Rows Pending", "value": scheduled_today, "tone": "warning"},
                {"label": "Attendance Rate", "value": f"{attendance_rate}%", "tone": "neutral"},
            ]
            workspace_lists = {
                "upcoming_sessions": today_sessions[:5],
                "queue": sessions.filter(attendance_records__status=AttendanceRecord.STATUS_SCHEDULED)
                .distinct()
                .order_by("session_date", "start_time")[:5],
            }
        elif role == ROLE_PARENT:
            dashboard_intro = {
                "eyebrow": "Parent Portal",
                "title": "Your family’s training and payment hub",
                "body": "This flow now matches the original client portal more closely: child overview first, payment status second, and session visibility always close by.",
                "meta": f"{members.count()} linked child(ren)",
            }
            parent_reports = report_queryset.filter(member__parent_user=user, is_published=True)
            dashboard_actions = [
                {"label": "My Payments", "url": reverse("payments:my_payments"), "icon": "fa-credit-card"},
                {"label": "Children Profiles", "url": reverse("members:list"), "icon": "fa-children"},
                {"label": "Session Schedule", "url": reverse("sessions:list"), "icon": "fa-calendar-days"},
                {"label": "Progress Reports", "url": reverse("members:report_list"), "icon": "fa-file-lines"},
                {"label": "Store", "url": reverse("finance:product_list"), "icon": "fa-bag-shopping"},
            ]
            member_list = list(members.order_by("full_name"))
            child_portal_cards = []
            for child in member_list:
                child_records = attendance.filter(member=child)
                child_invoices = invoices.filter(member=child)
                child_upcoming_sessions = list(
                    sessions.filter(attendance_records__member=child, session_date__gte=today)
                    .distinct()
                    .order_by("session_date", "start_time")[:4]
                )
                child_reports = list(parent_reports.filter(member=child).order_by("-period_end", "-created_at")[:6])
                latest_report = child_reports[0] if child_reports else None
                previous_report = child_reports[1] if len(child_reports) > 1 else None
                next_session = child_upcoming_sessions[0] if child_upcoming_sessions else None
                attendance_rate_value = attendance_rate_for_queryset(child_records)
                outstanding_total = child_invoices.exclude(status=Invoice.STATUS_PAID).aggregate(total=Sum("amount"))[
                    "total"
                ] or Decimal("0.00")
                logged_records = child_records.exclude(status=AttendanceRecord.STATUS_SCHEDULED)
                total_logged = logged_records.count()
                attended_count = logged_records.filter(
                    status__in=[AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE]
                ).count()
                overall_score = (
                    calculate_report_overall_score(latest_report)
                    if latest_report
                    else round((attendance_rate_value * 0.6) + (min(100, attended_count * 8) * 0.4))
                )
                goal_reached = (
                    report_goal_percentage(latest_report, overall_score)
                    if latest_report
                    else round(min(100, attendance_rate_value))
                )
                score_delta = report_score_delta(latest_report, previous_report) if latest_report else 0
                progress_items = build_portal_highlights(latest_report, previous_report)
                training_plan = build_training_plan_items(latest_report, limit=3)
                if not training_plan:
                    training_plan = [
                        {
                            "step": 1,
                            "title": "Movement Foundation",
                            "detail": "Maintain split-step rhythm and calm recovery on every rally.",
                            "rating": 3,
                        },
                        {
                            "step": 2,
                            "title": "Consistency Reps",
                            "detail": "Keep contact quality stable across multi-shuttle drills and longer sets.",
                            "rating": 3,
                        },
                    ]
                coach_label = "Coaching team"
                if next_session and next_session.coach:
                    coach_label = next_session.coach.get_full_name() or next_session.coach.username
                elif child.assigned_coach:
                    coach_label = child.assigned_coach.get_full_name() or child.assigned_coach.username
                latest_invoice = child_invoices.order_by("-period", "-due_date").first()
                child_portal = {
                    "member": child,
                    "attendance_rate": attendance_rate_value,
                    "attendance_ring": max(6, min(360, round(attendance_rate_value * 3.6))),
                    "attendance_count": attended_count,
                    "total_logged": total_logged,
                    "streak": attendance_streak(child_records),
                    "outstanding_total": outstanding_total,
                    "latest_invoice": latest_invoice,
                    "next_session": next_session,
                    "next_session_duration": format_session_duration(next_session) if next_session else "",
                    "coach_label": coach_label,
                    "upcoming_sessions": child_upcoming_sessions,
                    "latest_report": latest_report,
                    "overall_score": overall_score,
                    "grade_label": report_grade_label(latest_report, overall_score) if latest_report else "B",
                    "goal_reached": goal_reached,
                    "score_delta": score_delta,
                    "score_delta_label": f"{score_delta:+d}%" if score_delta else "Stable",
                    "progress_items": progress_items,
                    "training_plan": training_plan,
                    "recent_feedback": list(
                        SessionFeedback.objects.filter(member=child)
                        .select_related("training_session", "coach")
                        .order_by("-training_session__session_date", "-created_at")[:3]
                    ),
                    "report_url": reverse("members:report_detail", kwargs={"pk": latest_report.pk})
                    if latest_report
                    else reverse("members:report_list"),
                    "profile_url": reverse("members:detail", kwargs={"pk": child.pk}),
                    "payments_url": reverse("payments:my_payments"),
                    "level_label": child.get_skill_level_display(),
                    "status_label": child.get_status_display(),
                }
                child_summaries.append(
                    {
                        "member": child,
                        "attendance_rate": attendance_rate_value,
                        "outstanding_total": outstanding_total,
                        "latest_invoice": latest_invoice,
                        "next_session": next_session,
                    }
                )
                child_portal_cards.append(child_portal)
            child_portal_cards.sort(
                key=lambda item: (
                    item["next_session"].session_date if item["next_session"] else date.max,
                    item["next_session"].start_time if item["next_session"] else timezone.datetime.max.time(),
                    item["member"].full_name,
                )
            )
            featured_child = child_portal_cards[0] if child_portal_cards else None
            if featured_child:
                featured_child["momentum_label"] = (
                    f"{featured_child['streak']}-day streak" if featured_child["streak"] else "Ready for the next class"
                )
                featured_child["momentum_body"] = (
                    "Training momentum is building nicely. Keep the rhythm going this week."
                    if featured_child["streak"] >= 3
                    else "Class info, attendance progress, and report updates are all ready to review below."
                )
            student_portal = {
                "featured_child": featured_child,
                "children": child_portal_cards,
                "featured_invoice": invoices.exclude(status=Invoice.STATUS_PAID).order_by("due_date", "period").first(),
                "reports": parent_reports.order_by("-period_end")[:5],
            }
            outstanding_total = invoices.exclude(status=Invoice.STATUS_PAID).aggregate(total=Sum("amount"))["total"] or Decimal(
                "0.00"
            )
            workspace_highlights = [
                {"label": "Linked Children", "value": members.count(), "tone": "info"},
                {"label": "Outstanding Balance", "value": f"RM {outstanding_total:,.2f}", "tone": "warning"},
                {"label": "Pending Verification", "value": invoices.filter(status=Invoice.STATUS_PENDING).count(), "tone": "neutral"},
                {"label": "Attendance Rate", "value": f"{attendance_rate}%", "tone": "success"},
            ]
            workspace_lists = {
                "upcoming_sessions": upcoming_sessions,
                "featured_invoice": student_portal["featured_invoice"] if student_portal else None,
                "reports": student_portal["reports"] if student_portal else parent_reports.order_by("-period_end")[:5],
            }

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
                "show_attendance_chart": role in {ROLE_ADMIN, ROLE_COACH, ROLE_HEADCOUNT},
                "revenue_chart_data": build_chart_payload(month_labels, revenue_values, "Monthly Revenue"),
                "attendance_chart_data": build_chart_payload(month_labels, attendance_values, "Attendance Rate"),
                "growth_chart_data": build_chart_payload(month_labels, growth_values, "Member Growth"),
                "recent_sessions": sessions.order_by("-session_date", "-start_time")[:5],
                "recent_payments": recent_payments,
                "children": members.order_by("full_name") if role == ROLE_PARENT else None,
                "dashboard_intro": dashboard_intro,
                "dashboard_actions": dashboard_actions,
                "workspace_highlights": workspace_highlights,
                "workspace_lists": workspace_lists,
                "child_summaries": child_summaries,
                "student_portal": student_portal,
            }
        )
        return context


class LandingContentUpdateView(AdminRequiredMixin, UpdateView):
    form_class = LandingPageContentForm
    template_name = "accounts/website_settings.html"
    success_url = reverse_lazy("accounts:website")

    def get_object(self, queryset=None):
        return LandingPageContent.get_solo()

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Landing page content updated successfully.")
        return response


class CoachManagementView(AdminRequiredMixin, FormView):
    template_name = "accounts/coach_management.html"
    form_class = CoachAccountForm
    success_url = reverse_lazy("accounts:coaches")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["coach_rows"] = (
            User.objects.filter(profile__role=UserProfile.ROLE_COACH)
            .annotate(
                member_count=Count("assigned_members", distinct=True),
                session_count=Count("training_sessions", distinct=True),
            )
            .order_by("first_name", "username")
        )
        return context

    def form_valid(self, form):
        user = form.save()
        messages.success(
            self.request,
            f"Coach account {user.username} created successfully and is ready for admin scheduling.",
        )
        return super().form_valid(form)


class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = "accounts/notification_list.html"
    context_object_name = "notifications"
    paginate_by = 20

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["unread_count"] = self.get_queryset().filter(is_read=False).count()
        return context


class NotificationReadView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        notification = get_object_or_404(Notification, pk=kwargs["pk"], user=request.user)
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        if notification.url:
            return redirect(notification.url)
        return redirect("accounts:notifications")

# Create your views here.
