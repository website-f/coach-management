import csv
import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, TemplateView, UpdateView

from accounts.notifications import notify_users
from accounts.decorators import role_required
from accounts.mixins import AdminOrCoachRequiredMixin, AdminRequiredMixin, SalesOrAdminRequiredMixin
from accounts.utils import ROLE_ADMIN, ROLE_COACH, ROLE_HEADCOUNT, ROLE_PARENT, has_role
from accounts.models import LandingPageContent, UserProfile
from finance.services import create_initial_invoices_for_member, get_billing_configuration, get_default_payment_plan
from finance.models import Invoice
from members.forms import (
    AdmissionApplicationPublicForm,
    AdmissionApplicationReviewForm,
    CommunicationLogForm,
    MemberForm,
    MemberLevelForm,
    ParentRegistrationForm,
    ProgressReportForm,
)
from members.models import AdmissionApplication, CommunicationLog, DEFAULT_SKILLS, Member, ProgressReport
from members.services import (
    calculate_report_overall_score,
    pick_best_available_coach,
    report_goal_percentage,
    report_grade_label,
    report_score_delta,
)
from sessions.models import AttendanceRecord, SessionFeedback, SyllabusRoot

User = get_user_model()


def visible_members_for_user(user):
    queryset = Member.objects.select_related(
        "assigned_coach",
        "assigned_staff",
        "parent_user",
        "created_by",
        "payment_plan",
        "syllabus_root",
    )
    if has_role(user, ROLE_COACH) and not has_role(user, ROLE_ADMIN):
        return queryset.filter(assigned_coach=user)
    if has_role(user, ROLE_HEADCOUNT) and not has_role(user, ROLE_ADMIN):
        return queryset.filter(status=Member.STATUS_TRIAL).filter(Q(assigned_staff=user) | Q(assigned_staff__isnull=True))
    if has_role(user, ROLE_PARENT):
        return queryset.filter(parent_user=user)
    return queryset


def visible_applications_for_user(user):
    queryset = AdmissionApplication.objects.select_related(
        "reviewed_by",
        "linked_member",
        "linked_parent_user",
        "assigned_staff",
    )
    if has_role(user, ROLE_HEADCOUNT) and not has_role(user, ROLE_ADMIN):
        return queryset.filter(Q(assigned_staff=user) | Q(assigned_staff__isnull=True))
    if has_role(user, ROLE_ADMIN):
        return queryset
    return queryset.none()


def visible_reports_for_user(user):
    queryset = ProgressReport.objects.select_related("member", "coach", "member__assigned_coach", "member__parent_user")
    if has_role(user, ROLE_COACH) and not has_role(user, ROLE_ADMIN):
        return queryset.filter(member__assigned_coach=user)
    if has_role(user, ROLE_PARENT):
        return queryset.filter(member__parent_user=user, is_published=True)
    if has_role(user, ROLE_ADMIN):
        return queryset
    return queryset.none()


def build_progress_report_form_context(user, member=None, current_report=None):
    if not member:
        return {
            "selected_report_member": None,
            "previous_reports": [],
            "recent_feedback_entries": [],
        }

    reports_queryset = visible_reports_for_user(user).filter(member=member).order_by("-period_end", "-created_at")
    if current_report and current_report.pk:
        reports_queryset = reports_queryset.exclude(pk=current_report.pk)

    previous_reports = list(reports_queryset[:4])
    recent_feedback_entries = list(
        SessionFeedback.objects.filter(member=member)
        .select_related("training_session", "coach")
        .order_by("-training_session__session_date", "-created_at")[:4]
    )
    return {
        "selected_report_member": member,
        "previous_reports": previous_reports,
        "recent_feedback_entries": recent_feedback_entries,
    }


def visible_communication_logs_for_user(user):
    queryset = CommunicationLog.objects.select_related(
        "staff",
        "lead",
        "member",
        "member__assigned_coach",
        "member__assigned_staff",
    )
    if has_role(user, ROLE_COACH) and not has_role(user, ROLE_ADMIN):
        return queryset.filter(member__assigned_coach=user)
    if has_role(user, ROLE_HEADCOUNT) and not has_role(user, ROLE_ADMIN):
        return queryset.filter(Q(lead__assigned_staff=user) | Q(member__assigned_staff=user))
    if has_role(user, ROLE_PARENT):
        return queryset.filter(member__parent_user=user)
    return queryset


def attendance_rate_for_member(member):
    attendance_queryset = member.attendance_records.exclude(status=AttendanceRecord.STATUS_SCHEDULED)
    total = attendance_queryset.count()
    if not total:
        return 0
    attended = attendance_queryset.filter(
        status__in=[AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE]
    ).count()
    return round((attended / total) * 100, 1)


def latest_invoice_for_member(member):
    return member.invoices.select_related("payment_plan").order_by("-period", "-due_date", "-pk").first()


def payment_status_for_member(member):
    latest_invoice = latest_invoice_for_member(member)
    if not latest_invoice:
        return "Not billed"
    return latest_invoice.get_status_display()


def derived_retention_risk(member):
    attendance_rate = attendance_rate_for_member(member)
    risk = member.retention_risk_score or 0
    latest_invoice = latest_invoice_for_member(member)
    if latest_invoice and latest_invoice.status in {Invoice.STATUS_UNPAID, Invoice.STATUS_REJECTED}:
        risk = max(risk, 55)
    if latest_invoice and latest_invoice.status == Invoice.STATUS_PENDING:
        risk = max(risk, 35)
    if attendance_rate and attendance_rate < 60:
        risk = max(risk, 70)
    elif attendance_rate and attendance_rate < 80:
        risk = max(risk, 40)
    if member.status in {Member.STATUS_INACTIVE, Member.STATUS_CHURNED}:
        risk = max(risk, 85)
    return min(risk, 100)


def crm_stage_for_member(member):
    if member.status == Member.STATUS_TRIAL:
        return {
            "label": "Trial",
            "badge": "badge-warning",
            "summary": "Trial student is waiting for conversion into a paid package.",
        }
    if member.status == Member.STATUS_CHURNED:
        return {
            "label": "Churned",
            "badge": "badge-danger",
            "summary": member.churn_reason or "Student has left and needs a win-back decision.",
        }
    if member.status == Member.STATUS_INACTIVE:
        return {
            "label": "Inactive",
            "badge": "badge-neutral",
            "summary": member.next_action or "Student is paused and needs a reactivation plan.",
        }
    if payment_status_for_member(member) in {"Unpaid", "Rejected"}:
        return {
            "label": "At Risk",
            "badge": "badge-danger",
            "summary": "Active student needs billing or retention follow-up.",
        }
    return {
        "label": "Active",
        "badge": "badge-success",
        "summary": "Student is enrolled and currently active.",
    }


class CRMWorkspaceView(SalesOrAdminRequiredMixin, TemplateView):
    template_name = "members/crm_workspace.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search = self.request.GET.get("q", "").strip()
        if search:
            lead_queryset = visible_applications_for_user(self.request.user).filter(
                Q(student_name__icontains=search)
                | Q(guardian_name__icontains=search)
                | Q(contact_number__icontains=search)
            )
            member_queryset = visible_members_for_user(self.request.user).filter(
                Q(full_name__icontains=search)
                | Q(contact_number__icontains=search)
                | Q(program_enrolled__icontains=search)
            )
            log_queryset = visible_communication_logs_for_user(self.request.user).filter(
                Q(outcome__icontains=search)
                | Q(notes__icontains=search)
                | Q(member__full_name__icontains=search)
                | Q(lead__student_name__icontains=search)
            )
        else:
            lead_queryset = visible_applications_for_user(self.request.user)
            member_queryset = visible_members_for_user(self.request.user)
            log_queryset = visible_communication_logs_for_user(self.request.user)

        leads = lead_queryset.filter(status=AdmissionApplication.STATUS_PENDING).order_by("-submitted_at")[:8]
        trials = member_queryset.filter(status=Member.STATUS_TRIAL).order_by("-trial_linked_date", "full_name")[:8]
        active_students = []
        inactive_students = []
        if has_role(self.request.user, ROLE_ADMIN):
            active_students = list(
                Member.objects.select_related("assigned_coach", "assigned_staff", "payment_plan", "parent_user", "syllabus_root")
                .filter(status=Member.STATUS_ACTIVE)
                .order_by("full_name")[:8]
            )
            inactive_students = list(
                Member.objects.select_related("assigned_coach", "assigned_staff", "payment_plan", "parent_user", "syllabus_root")
                .filter(status__in=[Member.STATUS_INACTIVE, Member.STATUS_CHURNED])
                .order_by("full_name")[:8]
            )

        trial_session_limit = get_billing_configuration().trial_session_limit
        trial_rows = []
        for member in trials:
            attendance_count = member.attendance_records.count()
            latest_feedback = member.session_feedback_entries.select_related("training_session", "coach").first()
            trial_rows.append(
                {
                    "member": member,
                    "linked_date": member.trial_linked_date or member.joined_at,
                    "trial_date": member.trial_date,
                    "class_type": member.syllabus_root.name if member.syllabus_root_id else member.program_enrolled,
                    "attendance_count": attendance_count,
                    "attendance_summary": f"{attendance_count}/{trial_session_limit}",
                    "payment_status": payment_status_for_member(member),
                    "latest_feedback": latest_feedback,
                }
            )

        active_rows = [
            {
                "member": member,
                "attendance_rate": attendance_rate_for_member(member),
                "payment_status": payment_status_for_member(member),
                "retention_risk": derived_retention_risk(member),
            }
            for member in active_students
        ]
        inactive_rows = [
            {
                "member": member,
                "payment_status": payment_status_for_member(member),
                "why_left": member.churn_reason or member.next_action,
            }
            for member in inactive_students
        ]
        lead_rows = [
            {
                "lead": lead,
                "latest_touch": lead.communication_logs.select_related("staff").first(),
            }
            for lead in leads
        ]

        context.update(
            {
                "search_query": search,
                "lead_rows": lead_rows,
                "trial_rows": trial_rows,
                "active_rows": active_rows,
                "inactive_rows": inactive_rows,
                "communication_logs": log_queryset.order_by("-happened_at")[:12],
                "crm_kpis": {
                    "lead_count": visible_applications_for_user(self.request.user).filter(status=AdmissionApplication.STATUS_PENDING).count(),
                    "trial_count": visible_members_for_user(self.request.user).filter(status=Member.STATUS_TRIAL).count(),
                    "active_count": Member.objects.filter(status=Member.STATUS_ACTIVE).count() if has_role(self.request.user, ROLE_ADMIN) else 0,
                    "inactive_count": Member.objects.filter(status__in=[Member.STATUS_INACTIVE, Member.STATUS_CHURNED]).count()
                    if has_role(self.request.user, ROLE_ADMIN)
                    else 0,
                },
                "trial_session_limit": trial_session_limit,
                "show_active_sections": has_role(self.request.user, ROLE_ADMIN),
            }
        )
        return context


class MemberListView(LoginRequiredMixin, ListView):
    model = Member
    template_name = "members/member_list.html"
    context_object_name = "members"
    paginate_by = 10

    def get_queryset(self):
        queryset = visible_members_for_user(self.request.user)
        search = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "").strip()
        coach = self.request.GET.get("coach", "").strip()
        level = self.request.GET.get("level", "").strip()
        if search:
            queryset = queryset.filter(full_name__icontains=search)
        if status:
            queryset = queryset.filter(status=status)
        if coach:
            queryset = queryset.filter(assigned_coach_id=coach)
        if level:
            queryset = queryset.filter(skill_level=level)
        return queryset.order_by("full_name", "id").distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        is_parent_view = has_role(self.request.user, ROLE_PARENT)
        parent_applications = AdmissionApplication.objects.none()
        if is_parent_view:
            parent_applications = (
                AdmissionApplication.objects.select_related("linked_member")
                .filter(linked_parent_user=self.request.user)
                .order_by("-submitted_at")
            )
        context["can_manage"] = has_role(self.request.user, ROLE_ADMIN, ROLE_HEADCOUNT)
        context["is_admin"] = has_role(self.request.user, ROLE_ADMIN)
        context["is_sales"] = has_role(self.request.user, ROLE_HEADCOUNT) and not has_role(self.request.user, ROLE_ADMIN)
        context["is_parent_view"] = is_parent_view
        context["statuses"] = Member.STATUS_CHOICES
        context["levels"] = Member.LEVEL_CHOICES
        context["coaches"] = (
            User.objects.filter(profile__role=UserProfile.ROLE_COACH)
            .select_related("profile")
            .order_by("first_name", "username")
        )
        context["show_coach_filter"] = not is_parent_view
        active_filter_count = sum(
            1
            for key in ("status", "coach", "level")
            if self.request.GET.get(key, "").strip()
        )
        context["active_filter_count"] = active_filter_count
        context["filters_open"] = active_filter_count > 0
        context["application_submitted"] = self.request.GET.get("application_submitted") == "1"
        context["linked_children_count"] = visible_members_for_user(self.request.user).count() if is_parent_view else None
        context["trial_children_count"] = (
            visible_members_for_user(self.request.user).filter(status=Member.STATUS_TRIAL).count() if is_parent_view else None
        )
        context["active_children_count"] = (
            visible_members_for_user(self.request.user).filter(status=Member.STATUS_ACTIVE).count() if is_parent_view else None
        )
        context["parent_applications"] = parent_applications[:6] if is_parent_view else []
        context["pending_child_application_count"] = (
            parent_applications.filter(status=AdmissionApplication.STATUS_PENDING).count() if is_parent_view else 0
        )
        return context


class MemberDetailView(LoginRequiredMixin, DetailView):
    model = Member
    template_name = "members/member_detail.html"
    context_object_name = "member"

    def get_queryset(self):
        return visible_members_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        member = self.object
        is_parent_view = has_role(self.request.user, ROLE_PARENT)
        attendance_history = AttendanceRecord.objects.filter(member=member).select_related("training_session")
        invoices = Invoice.objects.select_related("payment_plan").filter(member=member).order_by("-period", "-due_date")
        report_history = visible_reports_for_user(self.request.user).filter(member=member)
        attendance_logged = attendance_history.exclude(status=AttendanceRecord.STATUS_SCHEDULED)
        attendance_total = attendance_logged.count()
        attendance_present = attendance_logged.filter(
            status__in=[AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE]
        ).count()
        lead = member.latest_application
        communication_logs = visible_communication_logs_for_user(self.request.user).filter(member=member)
        context["attendance_history"] = attendance_history[:10]
        context["invoices"] = invoices[:10]
        context["upcoming_sessions"] = member.training_sessions.filter(session_date__gte=timezone.localdate()).order_by(
            "session_date",
            "start_time",
        )[:5]
        context["attendance_rate"] = round((attendance_present / attendance_total) * 100, 1) if attendance_total else 0
        context["outstanding_balance"] = invoices.exclude(status=Invoice.STATUS_PAID).aggregate(total=Sum("amount"))[
            "total"
        ] or 0
        context["latest_invoice"] = invoices.first()
        context["report_history"] = report_history[:6]
        context["latest_report"] = report_history.first()
        context["recent_feedback"] = (
            SessionFeedback.objects.filter(member=member)
            .select_related("training_session", "coach")
            .order_by("-training_session__session_date", "-created_at")[:5]
        )
        context["lead"] = lead
        context["lead_source_label"] = lead.get_source_display() if lead else "Not captured"
        context["interest_level_label"] = lead.get_interest_level_display() if lead else "Not captured"
        context["communication_logs"] = communication_logs[:10] if has_role(self.request.user, ROLE_ADMIN, ROLE_HEADCOUNT) else []
        context["communication_form"] = CommunicationLogForm(
            initial={"happened_at": timezone.localtime().replace(second=0, microsecond=0)}
        )
        context["payment_status"] = payment_status_for_member(member)
        context["retention_risk"] = derived_retention_risk(member)
        context["trial_session_limit"] = get_billing_configuration().trial_session_limit
        context["trial_sessions_used"] = member.attendance_records.count()
        context["why_stayed"] = member.conversion_reason or member.parent_feedback or ""
        context["why_left"] = member.churn_reason or ""
        context["what_next"] = member.next_action or (lead.next_action if lead else "")
        context["is_parent_view"] = is_parent_view
        context["can_manage"] = has_role(self.request.user, ROLE_ADMIN) or (
            has_role(self.request.user, ROLE_HEADCOUNT) and member.status == Member.STATUS_TRIAL
        )
        context["can_manage_crm"] = has_role(self.request.user, ROLE_ADMIN, ROLE_HEADCOUNT)
        context["can_update_level"] = has_role(self.request.user, ROLE_ADMIN) or (
            has_role(self.request.user, ROLE_COACH) and member.assigned_coach_id == self.request.user.id
        )
        context["level_form"] = MemberLevelForm(instance=member)
        return context


class MemberCreateView(AdminRequiredMixin, CreateView):
    model = Member
    form_class = MemberForm
    template_name = "members/member_form.html"
    success_url = reverse_lazy("members:list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["current_user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        create_initial_invoices_for_member(self.object, created_by=self.request.user)
        messages.success(self.request, "Member profile created successfully and onboarding invoices were generated.")
        return response


class MemberUpdateView(SalesOrAdminRequiredMixin, UpdateView):
    model = Member
    form_class = MemberForm
    template_name = "members/member_form.html"
    success_url = reverse_lazy("members:list")

    def get_queryset(self):
        return visible_members_for_user(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["current_user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Member profile updated successfully.")
        return response


class MemberDeleteView(AdminRequiredMixin, DeleteView):
    model = Member
    template_name = "members/member_confirm_delete.html"
    success_url = reverse_lazy("members:list")

    def form_valid(self, form):
        messages.success(self.request, "Member profile deleted.")
        return super().form_valid(form)


class AdmissionApplicationCreateView(FormView):
    template_name = "members/application_apply.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not has_role(request.user, ROLE_PARENT):
            messages.warning(request, "Only parents can use this intake page. Staff can manage leads from the workspace.")
            return redirect("accounts:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def is_parent_portal(self):
        return self.request.user.is_authenticated and has_role(self.request.user, ROLE_PARENT)

    def get_template_names(self):
        if self.is_parent_portal():
            return ["members/application_apply.html"]
        return ["accounts/parent_register.html"]

    def get_form_class(self):
        if self.is_parent_portal():
            return AdmissionApplicationPublicForm
        return ParentRegistrationForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.is_parent_portal():
            content = LandingPageContent.get_solo()
            kwargs["program_options"] = content.available_programs
            kwargs["location_options"] = content.available_locations
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        if self.is_parent_portal():
            parent_user = self.request.user
            initial["guardian_name"] = parent_user.get_full_name() or parent_user.username
            initial["guardian_email"] = parent_user.email
            initial["desired_username"] = parent_user.username

            linked_child = visible_members_for_user(parent_user).order_by("full_name").first()
            latest_application = (
                AdmissionApplication.objects.filter(linked_parent_user=parent_user).order_by("-submitted_at").first()
            )
            if linked_child:
                initial["contact_number"] = linked_child.emergency_contact_phone or linked_child.contact_number
                if linked_child.program_enrolled:
                    initial["preferred_program"] = linked_child.program_enrolled
                elif linked_child.syllabus_root_id:
                    initial["preferred_program"] = linked_child.syllabus_root.name
            if latest_application:
                initial.setdefault("source", latest_application.source)
                initial.setdefault("preferred_location", latest_application.preferred_location)
                initial.setdefault("training_frequency", latest_application.training_frequency)
                initial.setdefault("primary_goal", latest_application.primary_goal)
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        is_parent_portal = self.is_parent_portal()
        context["landing_content"] = LandingPageContent.get_solo()
        context["is_parent_portal"] = is_parent_portal
        context["is_parent_signup"] = not is_parent_portal
        context["submitted"] = self.request.GET.get("submitted") == "1"
        context["back_url"] = reverse_lazy("members:list") if is_parent_portal else "/"
        return context

    def form_valid(self, form):
        if self.is_parent_portal():
            parent_user = self.request.user
            # Block inactive parents from submitting new applications until
            # they reactivate via a paid plan. Used-up trial or churned family.
            any_child = Member.objects.filter(parent_user=parent_user).exists()
            live_child = Member.objects.filter(
                parent_user=parent_user,
                status__in=[Member.STATUS_ACTIVE, Member.STATUS_TRIAL],
            ).exists()
            if any_child and not live_child:
                messages.error(
                    self.request,
                    "Your account is inactive. Pay a monthly plan to add another child.",
                )
                return redirect("payments:my_payments")
            form.instance.linked_parent_user = parent_user
            form.instance.desired_username = parent_user.username
            # Auto-approve parent self-submissions so the onboarding invoice is
            # generated immediately — parent sees it in the payment hub on
            # redirect and can start paying without waiting for staff review.
            form.instance.status = AdmissionApplication.STATUS_APPROVED
            form.instance.reviewed_at = timezone.now()
            with transaction.atomic():
                self.object = form.save()
                self._provision_member_for_parent(self.object)
            messages.success(
                self.request,
                "Child application submitted. Please complete the onboarding payment to confirm the trial session.",
            )
            return redirect(reverse_lazy("payments:my_payments") + "?onboarding=1")

        user = form.save()
        authenticated_user = authenticate(
            self.request,
            username=user.username,
            password=form.cleaned_data["password1"],
        )
        if authenticated_user is not None:
            login(self.request, authenticated_user)
        messages.success(
            self.request,
            "Parent account created successfully. You can now add your first child from the parent portal.",
        )
        return redirect("members:list")

    def _provision_member_for_parent(self, application):
        """Create a TRIAL member + onboarding invoices from a self-submitted
        parent application so the payment flow is live immediately.
        """
        if application.linked_member_id:
            return application.linked_member
        parent_user = application.linked_parent_user
        assigned_coach = pick_best_available_coach(preferred_level=application.recommended_level)
        member = Member.objects.create(
            full_name=application.student_name,
            date_of_birth=application.date_of_birth or timezone.localdate(),
            contact_number=application.contact_number,
            email=application.guardian_email,
            emergency_contact_name=application.guardian_name,
            emergency_contact_phone=application.contact_number,
            program_enrolled=application.preferred_program,
            syllabus_root=SyllabusRoot.get_default(),
            payment_plan=get_default_payment_plan(),
            skill_level=application.recommended_level,
            assigned_coach=assigned_coach,
            parent_user=parent_user,
            status=Member.STATUS_TRIAL,
            joined_at=timezone.localdate(),
            trial_linked_date=timezone.localdate(),
            trial_date=timezone.localdate(),
            next_action="Complete onboarding payment to confirm the trial slot.",
            notes=f"Self-registered via parent portal. Preferred program: {application.preferred_program}.",
            created_by=parent_user,
        )
        create_initial_invoices_for_member(member, created_by=parent_user)
        application.linked_member = member
        application.save(update_fields=["linked_member", "status", "reviewed_at"])
        return member


class AdmissionApplicationListView(SalesOrAdminRequiredMixin, ListView):
    model = AdmissionApplication
    template_name = "members/application_list.html"
    context_object_name = "applications"
    paginate_by = 10

    def get_queryset(self):
        queryset = visible_applications_for_user(self.request.user)
        status = self.request.GET.get("status", "").strip()
        search = self.request.GET.get("q", "").strip()
        location = self.request.GET.get("location", "").strip()
        if status:
            queryset = queryset.filter(status=status)
        if search:
            queryset = queryset.filter(
                Q(student_name__icontains=search)
                | Q(guardian_name__icontains=search)
                | Q(preferred_program__icontains=search)
            )
        if location:
            queryset = queryset.filter(preferred_location=location)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["statuses"] = AdmissionApplication.STATUS_CHOICES
        context["locations"] = LandingPageContent.get_solo().available_locations
        context["is_sales"] = has_role(self.request.user, ROLE_HEADCOUNT) and not has_role(self.request.user, ROLE_ADMIN)
        return context


class AdmissionApplicationReviewView(SalesOrAdminRequiredMixin, UpdateView):
    model = AdmissionApplication
    form_class = AdmissionApplicationReviewForm
    template_name = "members/application_review.html"
    success_url = reverse_lazy("members:application_list")

    def get_queryset(self):
        return visible_applications_for_user(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["current_user"] = self.request.user
        return kwargs

    def ensure_linked_member(self, application):
        if application.status != AdmissionApplication.STATUS_APPROVED or application.linked_member_id:
            return application.linked_member

        parent_user = application.linked_parent_user
        assigned_coach = pick_best_available_coach(preferred_level=application.recommended_level)
        notes = [
            f"Promoted from lead into trial for {application.preferred_program}.",
            f"Preferred location: {application.preferred_location}.",
            f"Recommended level: {application.get_recommended_level_display()}.",
        ]
        if application.notes:
            notes.append(application.notes)

        linked_member = Member.objects.create(
            full_name=application.student_name,
            date_of_birth=application.date_of_birth or timezone.localdate(),
            contact_number=application.contact_number,
            email=application.guardian_email,
            emergency_contact_name=application.guardian_name,
            emergency_contact_phone=application.contact_number,
            program_enrolled=application.preferred_program,
            syllabus_root=SyllabusRoot.get_default(),
            payment_plan=get_default_payment_plan(),
            skill_level=application.recommended_level,
            assigned_staff=application.assigned_staff or self.request.user,
            assigned_coach=assigned_coach,
            parent_user=parent_user,
            status=Member.STATUS_TRIAL,
            joined_at=timezone.localdate(),
            trial_linked_date=timezone.localdate(),
            trial_date=timezone.localdate(),
            next_action=application.next_action or "Schedule the first trial session and collect subscription payment.",
            notes=" ".join(notes),
            created_by=self.request.user,
        )
        create_initial_invoices_for_member(linked_member, created_by=self.request.user)
        application.linked_member = linked_member
        return linked_member

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["communication_logs"] = visible_communication_logs_for_user(self.request.user).filter(lead=self.object)[:10]
        context["communication_form"] = CommunicationLogForm(
            initial={"happened_at": timezone.localtime().replace(second=0, microsecond=0)}
        )
        return context

    def form_valid(self, form):
        with transaction.atomic():
            if not form.instance.assigned_staff_id:
                form.instance.assigned_staff = self.request.user
            form.instance.reviewed_by = self.request.user
            form.instance.reviewed_at = timezone.now()
            if form.instance.status != AdmissionApplication.STATUS_REJECTED:
                form.instance.rejection_reason = ""
            form.instance.refresh_recommended_level()
            self.ensure_linked_member(form.instance)
            response = super().form_valid(form)
        if self.object.status == AdmissionApplication.STATUS_APPROVED and self.object.linked_member:
            CommunicationLog.objects.create(
                lead=self.object,
                member=self.object.linked_member,
                channel=CommunicationLog.CHANNEL_INTERNAL,
                message_type=CommunicationLog.TYPE_TRIAL,
                staff=self.request.user,
                outcome="Lead approved and moved into trial stage.",
                next_step=self.object.next_action or "Schedule the trial and follow up after coach feedback.",
            )
            notify_users(
                [self.object.linked_parent_user, self.object.linked_member.assigned_coach],
                title="Trial student assigned to coach",
                message=(
                    f"{self.object.student_name} has been approved for trial and assigned to "
                    f"{self.object.linked_member.assigned_coach or 'the coaching team'}."
                ),
                url=reverse_lazy("members:detail", kwargs={"pk": self.object.linked_member.pk}),
                email_subject=f"{self.object.student_name} has been assigned to a trial coach",
                email_message=(
                    f"{self.object.student_name} has been approved for trial.\n"
                    f"Level: {self.object.get_recommended_level_display()}\n"
                    f"Assigned coach: {self.object.linked_member.assigned_coach or 'To be assigned'}\n"
                    "Log in to the dashboard to view the trial schedule and complete the onboarding payments."
                ),
            )
            messages.success(
                self.request,
                f"Lead approved and linked to trial profile {self.object.linked_member.full_name}.",
            )
        elif self.object.status == AdmissionApplication.STATUS_REJECTED:
            CommunicationLog.objects.create(
                lead=self.object,
                channel=CommunicationLog.CHANNEL_INTERNAL,
                message_type=CommunicationLog.TYPE_NOTE,
                staff=self.request.user,
                outcome=f"Lead closed as lost. {self.object.rejection_reason}",
                next_step=self.object.next_action,
            )
            messages.warning(self.request, "Application rejected and parent-facing notes were saved.")
        else:
            messages.success(self.request, "Application review updated successfully.")
        return response


class ProgressReportListView(LoginRequiredMixin, ListView):
    model = ProgressReport
    template_name = "members/report_list.html"
    context_object_name = "reports"
    paginate_by = 10

    def get_queryset(self):
        queryset = visible_reports_for_user(self.request.user)
        member = self.request.GET.get("member", "").strip()
        if member:
            queryset = queryset.filter(member_id=member)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["members"] = visible_members_for_user(self.request.user).values_list("id", "full_name")
        context["can_manage"] = has_role(self.request.user, ROLE_ADMIN, ROLE_COACH)
        return context


class ProgressReportDetailView(LoginRequiredMixin, DetailView):
    model = ProgressReport
    template_name = "members/report_detail.html"
    context_object_name = "report"

    def get_queryset(self):
        return visible_reports_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        report = self.object
        report_history = list(
            ProgressReport.objects.filter(member=report.member)
            .filter(Q(is_published=True) | Q(pk=report.pk))
            .order_by("period_end", "created_at")
        )
        previous_report = next(
            (item for item in reversed(report_history[:-1]) if item.pk != report.pk),
            None,
        )
        overall_score = calculate_report_overall_score(report)
        goal_reached = report_goal_percentage(report, overall_score)
        score_delta = report_score_delta(report, previous_report)
        attended_sessions = round((report.attendance_rate / 100) * report.total_sessions) if report.total_sessions else 0
        absent_sessions = max(report.total_sessions - attended_sessions, 0)
        feedback_entries = list(
            SessionFeedback.objects.filter(
                member=report.member,
                training_session__session_date__range=(report.period_start, report.period_end),
            )
            .select_related("training_session", "coach")
            .order_by("-training_session__session_date", "-created_at")[:4]
        )
        growth_points = [
            {
                "label": item.period_end.strftime("%b %Y"),
                "score": calculate_report_overall_score(item),
            }
            for item in report_history[-6:]
        ]
        skill_rows = [
            {
                "skill": skill,
                "rating": report.skill_snapshot.get(skill, 0),
                "note": report.skill_notes.get(skill, ""),
                "score": round(report.skill_snapshot.get(skill, 0) * 20),
            }
            for skill in DEFAULT_SKILLS
        ]
        sorted_skills = sorted(skill_rows, key=lambda row: row["rating"], reverse=True)
        context["can_manage"] = has_role(self.request.user, ROLE_ADMIN, ROLE_COACH)
        context["skill_rows"] = skill_rows
        context["overall_score"] = overall_score
        context["grade_label"] = report_grade_label(report, overall_score)
        context["goal_reached"] = goal_reached
        context["score_delta"] = score_delta
        context["score_delta_label"] = f"{score_delta:+d}%" if score_delta else "Stable"
        context["attended_sessions"] = attended_sessions
        context["absent_sessions"] = absent_sessions
        context["strength_rows"] = sorted_skills[:3]
        context["focus_rows"] = sorted(skill_rows, key=lambda row: row["rating"])[:3]
        context["feedback_entries"] = feedback_entries
        context["radar_chart_data"] = json.dumps(
            {
                "labels": [row["skill"] for row in skill_rows],
                "datasets": [
                    {
                        "label": "Skill score",
                        "data": [row["score"] for row in skill_rows],
                        "backgroundColor": "rgba(79, 110, 247, 0.22)",
                        "borderColor": "#4f6ef7",
                        "pointBackgroundColor": "#4f6ef7",
                        "borderWidth": 2,
                    }
                ],
            }
        )
        context["growth_chart_data"] = json.dumps(
            {
                "labels": [point["label"] for point in growth_points],
                "datasets": [
                    {
                        "label": "Overall score",
                        "data": [point["score"] for point in growth_points],
                        "borderColor": "#16a34a",
                        "backgroundColor": "rgba(34, 197, 94, 0.14)",
                        "pointBackgroundColor": "#16a34a",
                        "borderWidth": 3,
                        "fill": True,
                        "tension": 0.35,
                    }
                ],
            }
        )
        return context


class ProgressReportCreateView(AdminOrCoachRequiredMixin, CreateView):
    model = ProgressReport
    form_class = ProgressReportForm
    template_name = "members/report_form.html"
    success_url = reverse_lazy("members:report_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["current_user"] = self.request.user
        kwargs["selected_member"] = self.request.POST.get("member") or self.request.GET.get("member")
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        if has_role(self.request.user, ROLE_COACH) and not has_role(self.request.user, ROLE_ADMIN):
            form.instance.coach = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Progress report created successfully.")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context["form"]
        selected_member = getattr(form, "selected_member", None)
        context["form_mode"] = "create"
        context.update(build_progress_report_form_context(self.request.user, selected_member))
        context["form_skill_preview"] = json.dumps(
            [
                {
                    "label": skill,
                    "field_name": f"skill_{skill.lower().replace(' ', '_')}",
                    "value": form[f"skill_{skill.lower().replace(' ', '_')}"].value() or 0,
                }
                for skill in DEFAULT_SKILLS
            ]
        )
        return context


class ProgressReportUpdateView(AdminOrCoachRequiredMixin, UpdateView):
    model = ProgressReport
    form_class = ProgressReportForm
    template_name = "members/report_form.html"
    success_url = reverse_lazy("members:report_list")

    def get_queryset(self):
        return visible_reports_for_user(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["current_user"] = self.request.user
        kwargs["selected_member"] = self.object.member_id
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Progress report updated successfully.")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context["form"]
        context["form_mode"] = "edit"
        context.update(build_progress_report_form_context(self.request.user, self.object.member, self.object))
        context["form_skill_preview"] = json.dumps(
            [
                {
                    "label": skill,
                    "field_name": f"skill_{skill.lower().replace(' ', '_')}",
                    "value": form[f"skill_{skill.lower().replace(' ', '_')}"].value() or 0,
                }
                for skill in DEFAULT_SKILLS
            ]
        )
        return context


@role_required(ROLE_ADMIN)
def export_members_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="members.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "Full Name",
            "DOB",
            "Contact",
            "Package",
            "Level",
            "Coach",
            "Status",
            "Parent Username",
        ]
    )
    for member in Member.objects.select_related("assigned_coach", "parent_user").order_by("full_name"):
        writer.writerow(
            [
                member.full_name,
                member.date_of_birth,
                member.contact_number,
                member.package_label,
                member.skill_level,
                member.assigned_coach.username if member.assigned_coach else "",
                member.status,
                member.parent_user.username if member.parent_user else "",
            ]
        )
    return response


class MemberLevelUpdateView(AdminOrCoachRequiredMixin, UpdateView):
    model = Member
    form_class = MemberLevelForm
    http_method_names = ["post"]

    def get_queryset(self):
        return visible_members_for_user(self.request.user)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"{self.object.full_name}'s level was updated to {self.object.get_skill_level_display()}.")
        return response

    def get_success_url(self):
        return reverse_lazy("members:detail", kwargs={"pk": self.object.pk})


class MemberCommunicationCreateView(SalesOrAdminRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        member = get_object_or_404(visible_members_for_user(request.user), pk=kwargs["pk"])
        form = CommunicationLogForm(request.POST)
        if form.is_valid():
            communication = form.save(commit=False)
            communication.member = member
            communication.staff = request.user
            communication.save()
            messages.success(request, "Communication log added to the student profile.")
        else:
            messages.error(request, "Could not save the communication log. Please check the required fields.")
        return redirect("members:detail", pk=member.pk)


class LeadCommunicationCreateView(SalesOrAdminRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        lead = get_object_or_404(visible_applications_for_user(request.user), pk=kwargs["pk"])
        form = CommunicationLogForm(request.POST)
        if form.is_valid():
            communication = form.save(commit=False)
            communication.lead = lead
            communication.staff = request.user
            communication.save()
            messages.success(request, "Communication log added to the lead.")
        else:
            messages.error(request, "Could not save the communication log. Please check the required fields.")
        return redirect("members:application_review", pk=lead.pk)

# Create your views here.
