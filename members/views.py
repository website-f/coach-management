import csv
import json

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from accounts.notifications import notify_users
from accounts.decorators import role_required
from accounts.mixins import AdminOrCoachRequiredMixin, AdminRequiredMixin
from accounts.utils import ROLE_ADMIN, ROLE_COACH, ROLE_PARENT, has_role
from accounts.models import LandingPageContent, UserProfile
from finance.services import create_initial_invoices_for_member, get_default_payment_plan
from finance.models import Invoice
from members.forms import (
    AdmissionApplicationPublicForm,
    AdmissionApplicationReviewForm,
    MemberForm,
    MemberLevelForm,
    ProgressReportForm,
)
from members.models import AdmissionApplication, DEFAULT_SKILLS, Member, ProgressReport
from members.services import (
    calculate_report_overall_score,
    pick_best_available_coach,
    report_goal_percentage,
    report_grade_label,
    report_score_delta,
)
from sessions.models import AttendanceRecord, SessionFeedback

User = get_user_model()


def visible_members_for_user(user):
    queryset = Member.objects.select_related("assigned_coach", "parent_user", "created_by", "payment_plan")
    if has_role(user, ROLE_COACH) and not has_role(user, ROLE_ADMIN):
        return queryset.filter(assigned_coach=user)
    if has_role(user, ROLE_PARENT):
        return queryset.filter(parent_user=user)
    return queryset


def visible_applications_for_user(user):
    return AdmissionApplication.objects.select_related(
        "reviewed_by",
        "linked_member",
        "linked_parent_user",
    )


def visible_reports_for_user(user):
    queryset = ProgressReport.objects.select_related("member", "coach", "member__assigned_coach", "member__parent_user")
    if has_role(user, ROLE_COACH) and not has_role(user, ROLE_ADMIN):
        return queryset.filter(member__assigned_coach=user)
    if has_role(user, ROLE_PARENT):
        return queryset.filter(member__parent_user=user, is_published=True)
    if has_role(user, ROLE_ADMIN):
        return queryset
    return queryset.none()


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
        if search:
            queryset = queryset.filter(full_name__icontains=search)
        if status:
            queryset = queryset.filter(status=status)
        if coach:
            queryset = queryset.filter(assigned_coach_id=coach)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_manage"] = has_role(self.request.user, ROLE_ADMIN)
        context["is_admin"] = has_role(self.request.user, ROLE_ADMIN)
        context["statuses"] = Member.STATUS_CHOICES
        context["coaches"] = User.objects.filter(profile__role=UserProfile.ROLE_COACH).order_by("first_name", "username")
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
        attendance_history = AttendanceRecord.objects.filter(member=member).select_related(
            "training_session"
        )
        invoices = Invoice.objects.select_related("payment_plan").filter(member=member).order_by("-period", "-due_date")
        attendance_logged = attendance_history.exclude(status=AttendanceRecord.STATUS_SCHEDULED)
        attendance_total = attendance_logged.count()
        attendance_present = attendance_logged.filter(
            status__in=[AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE]
        ).count()
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
        context["latest_report"] = visible_reports_for_user(self.request.user).filter(member=member).first()
        context["recent_feedback"] = (
            SessionFeedback.objects.filter(member=member)
            .select_related("training_session", "coach")
            .order_by("-training_session__session_date", "-created_at")[:5]
        )
        context["can_manage"] = has_role(self.request.user, ROLE_ADMIN)
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


class MemberUpdateView(AdminRequiredMixin, UpdateView):
    model = Member
    form_class = MemberForm
    template_name = "members/member_form.html"
    success_url = reverse_lazy("members:list")

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


class AdmissionApplicationCreateView(CreateView):
    model = AdmissionApplication
    form_class = AdmissionApplicationPublicForm
    template_name = "members/application_apply.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        content = LandingPageContent.get_solo()
        kwargs["program_options"] = content.available_programs
        kwargs["location_options"] = content.available_locations
        return kwargs

    def get_success_url(self):
        return reverse_lazy("members:apply") + "?submitted=1"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["landing_content"] = LandingPageContent.get_solo()
        context["submitted"] = self.request.GET.get("submitted") == "1"
        return context

    def form_valid(self, form):
        if self.request.user.is_authenticated and has_role(self.request.user, ROLE_PARENT):
            form.instance.linked_parent_user = self.request.user
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Application submitted successfully. Recommended starting level: {self.object.get_recommended_level_display()}.",
        )
        return response


class AdmissionApplicationListView(AdminOrCoachRequiredMixin, ListView):
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
        return context


class AdmissionApplicationReviewView(AdminOrCoachRequiredMixin, UpdateView):
    model = AdmissionApplication
    form_class = AdmissionApplicationReviewForm
    template_name = "members/application_review.html"
    success_url = reverse_lazy("members:application_list")

    def get_queryset(self):
        return visible_applications_for_user(self.request.user)

    def ensure_linked_member(self, application):
        if application.status != AdmissionApplication.STATUS_APPROVED or application.linked_member_id:
            return application.linked_member

        parent_user = application.linked_parent_user
        assigned_coach = (
            self.request.user
            if has_role(self.request.user, ROLE_COACH)
            else pick_best_available_coach(preferred_level=application.recommended_level)
        )
        notes = [
            f"Approved from admission application for {application.preferred_program}.",
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
            payment_plan=get_default_payment_plan(),
            skill_level=application.recommended_level,
            assigned_coach=assigned_coach,
            parent_user=parent_user,
            status=Member.STATUS_ACTIVE,
            joined_at=timezone.localdate(),
            notes=" ".join(notes),
            created_by=self.request.user,
        )
        create_initial_invoices_for_member(linked_member, created_by=self.request.user)
        application.linked_member = linked_member
        return linked_member

    def form_valid(self, form):
        with transaction.atomic():
            form.instance.reviewed_by = self.request.user
            form.instance.reviewed_at = timezone.now()
            if form.instance.status != AdmissionApplication.STATUS_REJECTED:
                form.instance.rejection_reason = ""
            form.instance.refresh_recommended_level()
            self.ensure_linked_member(form.instance)
            response = super().form_valid(form)
        if self.object.status == AdmissionApplication.STATUS_APPROVED and self.object.linked_member:
            notify_users(
                [self.object.linked_parent_user, self.object.linked_member.assigned_coach],
                title="Student assigned to coach",
                message=(
                    f"{self.object.student_name} was approved as a {self.object.get_recommended_level_display()} player and "
                    f"assigned to {self.object.linked_member.assigned_coach or 'the coaching team'}."
                ),
                url=reverse_lazy("members:detail", kwargs={"pk": self.object.linked_member.pk}),
                email_subject=f"{self.object.student_name} has been assigned to a coach",
                email_message=(
                    f"{self.object.student_name} has been approved.\n"
                    f"Level: {self.object.get_recommended_level_display()}\n"
                    f"Assigned coach: {self.object.linked_member.assigned_coach or 'To be assigned'}\n"
                    "Log in to the dashboard to view sessions and complete the onboarding payments."
                ),
            )
            messages.success(
                self.request,
                f"Application approved and linked to member profile {self.object.linked_member.full_name}.",
            )
        elif self.object.status == AdmissionApplication.STATUS_REJECTED:
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
        context["form_mode"] = "create"
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
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Progress report updated successfully.")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_mode"] = "edit"
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

# Create your views here.
