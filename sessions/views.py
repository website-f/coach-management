import calendar
import json
from collections import defaultdict
from datetime import date

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.forms import modelformset_factory
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from accounts.mixins import AdminOrCoachRequiredMixin, AdminRequiredMixin, HeadcountOrAboveRequiredMixin
from accounts.notifications import notify_users
from accounts.utils import ROLE_ADMIN, ROLE_COACH, ROLE_HEADCOUNT, ROLE_PARENT, has_role
from members.models import Member, ProgressReport
from sessions.ai_planner import PlannerAssistantError, generate_ai_planner_reply
from sessions.forms import (
    SessionFeedbackForm,
    SyllabusRootForm,
    SyllabusStandardForm,
    SyllabusTemplateForm,
    TrainingSessionForm,
    WeeklySyllabusForm,
)
from sessions.models import (
    AttendanceRecord,
    SessionChecklistReport,
    SessionFeedback,
    SessionPlannerEntry,
    SyllabusRoot,
    SyllabusStandard,
    SyllabusTemplate,
    TrainingSession,
    WeeklySyllabus,
)
from sessions.services import (
    auto_assign_monthly_sessions,
    build_session_plan,
    ensure_default_syllabus,
    expire_trial_if_needed,
)
from sessions.video_utils import compress_session_feedback_video

User = get_user_model()

AttendanceFormSet = modelformset_factory(
    AttendanceRecord,
    fields=("status",),
    extra=0,
)


def visible_sessions_for_user(user):
    queryset = TrainingSession.objects.select_related("coach", "created_by", "syllabus_root")
    if has_role(user, ROLE_COACH) and not has_role(user, ROLE_ADMIN):
        return queryset.filter(Q(coach=user) | Q(coaches=user)).distinct()
    if has_role(user, ROLE_HEADCOUNT) and not has_role(user, ROLE_ADMIN):
        return queryset.filter(
            attendance_records__member__status=Member.STATUS_TRIAL,
            attendance_records__member__assigned_staff=user,
        ).distinct()
    if has_role(user, ROLE_PARENT):
        return queryset.filter(attendance_records__member__parent_user=user).distinct()
    return queryset


def visible_members_for_session_filters(user):
    queryset = Member.objects.select_related("assigned_coach", "parent_user", "payment_plan", "syllabus_root").filter(
        status__in=[Member.STATUS_ACTIVE, Member.STATUS_TRIAL]
    ).order_by("full_name")
    if has_role(user, ROLE_COACH) and not has_role(user, ROLE_ADMIN):
        return queryset.filter(assigned_coach=user)
    if has_role(user, ROLE_HEADCOUNT) and not has_role(user, ROLE_ADMIN):
        return queryset.filter(status=Member.STATUS_TRIAL, assigned_staff=user)
    if has_role(user, ROLE_PARENT):
        return queryset.filter(parent_user=user)
    return queryset


def session_feedback_is_open(training_session):
    return training_session.session_date <= timezone.localdate()


def ordered_session_records(training_session):
    return list(
        training_session.attendance_records.select_related(
            "member",
            "member__payment_plan",
            "member__assigned_coach",
            "member__parent_user",
        ).order_by("member__full_name")
    )


def build_session_feedback_rows(training_session, records=None):
    records = records if records is not None else ordered_session_records(training_session)
    feedback_is_open = session_feedback_is_open(training_session)
    feedback_map = {
        feedback.member_id: feedback
        for feedback in training_session.feedback_entries.select_related("member", "coach")
    }
    rows = []
    for record in records:
        feedback = feedback_map.get(record.member_id)
        needs_feedback = feedback is None
        rows.append(
            {
                "record": record,
                "feedback": feedback,
                "needs_feedback": needs_feedback,
                "feedback_status_label": (
                    "Report submitted" if feedback else ("Needs report" if feedback_is_open else "Opens on session date")
                ),
                "feedback_status_tone": "success" if feedback else ("warning" if feedback_is_open else "neutral"),
                "action_label": "Edit Report" if feedback else "Write Report",
            }
        )
    return sorted(rows, key=lambda row: (0 if row["needs_feedback"] else 1, row["record"].member.full_name.lower()))


def get_next_pending_feedback_member(training_session, current_member_id=None):
    records = list(training_session.attendance_records.select_related("member").order_by("member__full_name"))
    if not records:
        return None

    feedback_member_ids = set(training_session.feedback_entries.values_list("member_id", flat=True))
    pending_ids = [record.member_id for record in records if record.member_id not in feedback_member_ids]
    if not pending_ids:
        return None

    if current_member_id is None:
        next_member_id = pending_ids[0]
    else:
        positions = {record.member_id: index for index, record in enumerate(records)}
        current_position = positions.get(current_member_id, -1)
        after_current = [member_id for member_id in pending_ids if positions[member_id] > current_position]
        next_member_id = after_current[0] if after_current else pending_ids[0]
        if next_member_id == current_member_id:
            return None

    for record in records:
        if record.member_id == next_member_id:
            return record.member
    return None


def build_feedback_form_navigation(training_session, member):
    records = list(training_session.attendance_records.select_related("member").order_by("member__full_name"))
    total_students = len(records)
    completed_count = training_session.feedback_entries.count()
    current_position = next((index for index, record in enumerate(records, start=1) if record.member_id == member.id), None)
    return {
        "feedback_total_count": total_students,
        "feedback_completed_count": completed_count,
        "feedback_pending_count": max(total_students - completed_count, 0),
        "current_member_position": current_position,
        "next_feedback_member": get_next_pending_feedback_member(training_session, current_member_id=member.id),
    }


def build_session_feedback_form_context(member, training_session, current_feedback=None):
    previous_reports = list(
        ProgressReport.objects.filter(member=member)
        .select_related("coach")
        .order_by("-period_end", "-created_at")[:4]
    )
    recent_feedback_entries = SessionFeedback.objects.filter(member=member).select_related("training_session", "coach")
    if current_feedback and current_feedback.pk:
        recent_feedback_entries = recent_feedback_entries.exclude(pk=current_feedback.pk)
    recent_feedback_entries = list(recent_feedback_entries.order_by("-training_session__session_date", "-created_at")[:4])
    return {
        "selected_report_member": member,
        "previous_reports": previous_reports,
        "recent_feedback_entries": recent_feedback_entries,
        "session_report_reference_date": training_session.session_date,
    }


def resolve_month_anchor(raw_value):
    if raw_value:
        try:
            year_str, month_str = raw_value.split("-")
            return date(int(year_str), int(month_str), 1)
        except (TypeError, ValueError):
            pass
    return timezone.localdate().replace(day=1)


def month_bounds(anchor):
    _, days_in_month = calendar.monthrange(anchor.year, anchor.month)
    return anchor, anchor.replace(day=days_in_month)


def shift_month(anchor, delta):
    month_index = anchor.month - 1 + delta
    year = anchor.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def summarize_session_dates(training_sessions):
    session_dates = [
        session.session_date.strftime("%d %b %Y")
        for session in sorted(training_sessions, key=lambda item: (item.session_date, item.start_time))
    ]
    if len(session_dates) <= 4:
        return ", ".join(session_dates)
    return f"{', '.join(session_dates[:4])}, +{len(session_dates) - 4} more"


def notify_schedule_participants(training_sessions, updated=False):
    sessions = list(training_sessions)
    if not sessions:
        return

    primary_session = sessions[0]
    roster = Member.objects.filter(attendance_records__training_session__in=sessions).select_related(
        "parent_user",
        "payment_plan",
    ).distinct()
    coach = primary_session.coach
    coach_name = "To be assigned"
    if coach:
        coach_name = coach.get_full_name() or coach.username
    parent_users = [member.parent_user for member in roster if member.parent_user_id]
    title = "Session updated" if updated else "New session scheduled"
    message = (
        f"{primary_session.title} is scheduled on {summarize_session_dates(sessions)} at "
        f"{primary_session.start_time.strftime('%H:%M')} on Court {primary_session.court}."
    )
    email_subject = title
    email_message = (
        f"{primary_session.title}\n"
        f"Coach: {coach_name}\n"
        f"Dates: {summarize_session_dates(sessions)}\n"
        f"Time: {primary_session.start_time.strftime('%H:%M')} - {primary_session.end_time.strftime('%H:%M')}\n"
        f"Court: {primary_session.court}\n"
        "Please check the dashboard calendar for the latest schedule."
    )
    notify_users(
        [coach],
        title=title,
        message=message,
        url=reverse("sessions:list"),
        email_subject=email_subject,
        email_message=email_message,
    )
    notify_users(
        parent_users,
        title=title,
        message=message,
        url=reverse("sessions:list"),
        email_subject=email_subject,
        email_message=email_message,
    )


def notify_feedback_ready(feedback_entry):
    member = feedback_entry.member
    session = feedback_entry.training_session
    coach_name = feedback_entry.coach.get_full_name() if feedback_entry.coach else "Your coach"
    notify_users(
        [member.parent_user],
        title="New session report available",
        message=f"{coach_name} uploaded a session report for {member.full_name} after {session.title}.",
        url=reverse("members:detail", kwargs={"pk": member.pk}),
        email_subject=f"New session report for {member.full_name}",
        email_message=(
            f"{coach_name} uploaded a session report for {member.full_name}.\n"
            f"Session: {session.title}\n"
            f"Date: {session.session_date:%d %b %Y}\n"
            "Log in to the dashboard to review the report and video proof."
        ),
    )


def can_manage_session_plan(user, training_session):
    if has_role(user, ROLE_ADMIN):
        return True
    if not has_role(user, ROLE_COACH):
        return False
    if training_session.coach_id == user.id:
        return True
    return training_session.coaches.filter(pk=user.id).exists()


def clone_default_syllabus_root_structure(target_root):
    ensure_default_syllabus()
    source_root = SyllabusRoot.get_default()
    if not source_root or source_root.pk == target_root.pk:
        return

    template_map = {}
    for template in SyllabusTemplate.objects.filter(root=source_root).order_by("track"):
        cloned_template, _ = SyllabusTemplate.objects.get_or_create(
            root=target_root,
            track=template.track,
            defaults={
                "name": template.name,
                "source_document_name": template.source_document_name,
                "curriculum_year_label": template.curriculum_year_label,
                "annual_goal": template.annual_goal,
                "year_end_outcomes": template.year_end_outcomes,
                "assessment_approach": template.assessment_approach,
                "assessment_methods": template.assessment_methods,
                "curriculum_values": template.curriculum_values,
                "annual_phase_notes": template.annual_phase_notes,
                "ai_planner_instructions": template.ai_planner_instructions,
                "is_active": template.is_active,
            },
        )
        template_map[template.pk] = cloned_template

    standard_map = {}
    for standard in SyllabusStandard.objects.select_related("template").filter(template__root=source_root):
        cloned_standard, _ = SyllabusStandard.objects.get_or_create(
            template=template_map[standard.template_id],
            code=standard.code,
            defaults={
                "sort_order": standard.sort_order,
                "title": standard.title,
                "focus": standard.focus,
                "learning_standard_items": standard.learning_standard_items,
                "performance_band_items": standard.performance_band_items,
                "coach_hints": standard.coach_hints,
                "assessment_focus": standard.assessment_focus,
                "is_active": standard.is_active,
            },
        )
        standard_map[standard.pk] = cloned_standard

    for week in WeeklySyllabus.objects.filter(root=source_root).select_related("template", "standard"):
        WeeklySyllabus.objects.get_or_create(
            root=target_root,
            track=week.track,
            week_number=week.week_number,
            defaults={
                "template": template_map.get(week.template_id),
                "standard": standard_map.get(week.standard_id),
                "month_number": week.month_number,
                "phase_name": week.phase_name,
                "title": week.title,
                "objective": week.objective,
                "warm_up_plan": week.warm_up_plan,
                "technical_focus": week.technical_focus,
                "tactical_focus": week.tactical_focus,
                "coaching_cues": week.coaching_cues,
                "assessment_focus": week.assessment_focus,
                "success_criteria": week.success_criteria,
                "coach_notes": week.coach_notes,
                "homework": week.homework,
                "is_active": week.is_active,
            },
        )


class SyllabusListView(AdminRequiredMixin, ListView):
    model = SyllabusRoot
    template_name = "sessions/syllabus_list.html"
    context_object_name = "syllabus_roots"

    def get_queryset(self):
        ensure_default_syllabus()
        return SyllabusRoot.objects.annotate(
            template_count=Count("templates", distinct=True),
            standard_count=Count("templates__standards", distinct=True),
            weekly_unit_count=Count("weekly_units", distinct=True),
            session_count=Count("training_sessions", distinct=True),
        ).order_by("name")

    def get_selected_root(self):
        selected_root = self.request.GET.get("root", "").strip()
        if selected_root:
            return self.get_queryset().filter(pk=selected_root).first()
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        syllabus_roots = list(context["syllabus_roots"])
        root_ids = [root.pk for root in syllabus_roots]
        selected_track = self.request.GET.get("track", "").strip()
        selected_root = self.get_selected_root()
        track_sets = defaultdict(set)
        for root_id, track in SyllabusTemplate.objects.filter(root_id__in=root_ids).values_list("root_id", "track"):
            if root_id and track:
                track_sets[root_id].add(track)
        for root_id, track in WeeklySyllabus.objects.filter(root_id__in=root_ids).values_list("root_id", "track"):
            if root_id and track:
                track_sets[root_id].add(track)

        rows = []
        templates = {}
        standards_by_track = {}
        if selected_root:
            rows = list(
                WeeklySyllabus.objects.filter(root=selected_root)
                .select_related("template", "standard")
                .order_by("track", "month_number", "week_number")
            )
            templates = {
                item.track: item
                for item in SyllabusTemplate.objects.filter(root=selected_root).order_by("track")
            }
            for item in SyllabusStandard.objects.select_related("template").filter(template__root=selected_root).order_by(
                "template__track",
                "sort_order",
                "code",
            ):
                standards_by_track.setdefault(item.template.track, []).append(item)
        grouped_rows = []
        for track_value, track_label in WeeklySyllabus.TRACK_CHOICES:
            if selected_track and track_value != selected_track:
                continue
            track_rows = [row for row in rows if row.track == track_value]
            template = templates.get(track_value)
            standards = standards_by_track.get(track_value, [])
            if track_rows or template or standards:
                grouped_rows.append(
                    {
                        "track": track_value,
                        "label": track_label,
                        "rows": track_rows,
                        "template": template,
                        "standards": standards,
                    }
                )
        context["root_cards"] = [
            {
                "root": root,
                "track_count": len(track_sets.get(root.pk, set())),
                "is_selected": bool(selected_root and selected_root.pk == root.pk),
            }
            for root in syllabus_roots
        ]
        context["grouped_rows"] = grouped_rows
        context["track_choices"] = WeeklySyllabus.TRACK_CHOICES
        context["selected_track"] = selected_track
        context["selected_root"] = selected_root
        return context


class SyllabusRootCreateView(AdminRequiredMixin, CreateView):
    model = SyllabusRoot
    form_class = SyllabusRootForm
    template_name = "sessions/syllabus_root_form.html"
    success_url = reverse_lazy("sessions:syllabus")

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        clone_default_syllabus_root_structure(self.object)
        messages.success(self.request, "Syllabus root created and seeded from the default academy framework.")
        return response


class SyllabusRootUpdateView(AdminRequiredMixin, UpdateView):
    model = SyllabusRoot
    form_class = SyllabusRootForm
    template_name = "sessions/syllabus_root_form.html"

    def get_success_url(self):
        return f"{reverse('sessions:syllabus')}?root={self.object.pk}"

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Syllabus root updated successfully.")
        return response


class SyllabusCreateView(AdminRequiredMixin, CreateView):
    model = WeeklySyllabus
    form_class = WeeklySyllabusForm
    template_name = "sessions/syllabus_form.html"

    def get_initial(self):
        initial = super().get_initial()
        root = self.request.GET.get("root", "").strip()
        if root:
            initial["root"] = root
        return initial

    def get_success_url(self):
        root_id = self.object.root_id or self.request.GET.get("root")
        if root_id:
            return f"{reverse('sessions:syllabus')}?root={root_id}"
        return reverse("sessions:syllabus")

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Syllabus week created successfully.")
        return response


class SyllabusUpdateView(AdminRequiredMixin, UpdateView):
    model = WeeklySyllabus
    form_class = WeeklySyllabusForm
    template_name = "sessions/syllabus_form.html"

    def get_success_url(self):
        if self.object.root_id:
            return f"{reverse('sessions:syllabus')}?root={self.object.root_id}"
        return reverse("sessions:syllabus")

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Syllabus week updated successfully.")
        return response


class SyllabusTemplateUpdateView(AdminRequiredMixin, UpdateView):
    model = SyllabusTemplate
    form_class = SyllabusTemplateForm
    template_name = "sessions/syllabus_template_form.html"

    def get_queryset(self):
        ensure_default_syllabus()
        return SyllabusTemplate.objects.order_by("root__name", "track")

    def get_success_url(self):
        if self.object.root_id:
            return f"{reverse('sessions:syllabus')}?root={self.object.root_id}"
        return reverse("sessions:syllabus")

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Syllabus template updated successfully.")
        return response


class SyllabusStandardCreateView(AdminRequiredMixin, CreateView):
    model = SyllabusStandard
    form_class = SyllabusStandardForm
    template_name = "sessions/syllabus_standard_form.html"

    def get_initial(self):
        ensure_default_syllabus()
        initial = super().get_initial()
        track = self.request.GET.get("track", "").strip()
        root = self.request.GET.get("root", "").strip()
        if track:
            template_queryset = SyllabusTemplate.objects.filter(track=track)
            if root:
                template_queryset = template_queryset.filter(root_id=root)
            template = template_queryset.first()
            if template:
                initial["template"] = template
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        root = self.request.GET.get("root", "").strip()
        if root:
            form.fields["template"].queryset = form.fields["template"].queryset.filter(root_id=root)
        return form

    def get_success_url(self):
        root_id = self.request.GET.get("root") or (
            self.object.template.root_id if self.object.template_id and self.object.template.root_id else None
        )
        if root_id:
            return f"{reverse('sessions:syllabus')}?root={root_id}"
        return reverse("sessions:syllabus")

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Syllabus standard created successfully.")
        return response


class SyllabusStandardUpdateView(AdminRequiredMixin, UpdateView):
    model = SyllabusStandard
    form_class = SyllabusStandardForm
    template_name = "sessions/syllabus_standard_form.html"

    def get_success_url(self):
        if self.object.template_id and self.object.template.root_id:
            return f"{reverse('sessions:syllabus')}?root={self.object.template.root_id}"
        return reverse("sessions:syllabus")

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Syllabus standard updated successfully.")
        return response


class SessionListView(LoginRequiredMixin, ListView):
    VIEW_CALENDAR = "calendar"
    VIEW_CHECKLIST = "checklist"

    model = TrainingSession
    template_name = "sessions/session_list.html"
    context_object_name = "sessions"

    def get_month_anchor(self):
        return resolve_month_anchor(self.request.GET.get("month"))

    def uses_checklist_first_mode(self):
        return has_role(self.request.user, ROLE_COACH) or has_role(self.request.user, ROLE_ADMIN)

    def get_session_page_mode(self):
        requested_mode = self.request.GET.get("view", "").strip()
        if requested_mode == self.VIEW_CALENDAR:
            return self.VIEW_CALENDAR
        if requested_mode == self.VIEW_CHECKLIST and self.uses_checklist_first_mode():
            return self.VIEW_CHECKLIST
        return self.VIEW_CHECKLIST if self.uses_checklist_first_mode() else self.VIEW_CALENDAR

    def get_focus_session(self, sessions):
        if not sessions:
            return None

        requested_focus = self.request.GET.get("focus", "").strip()
        if requested_focus:
            for session in sessions:
                if str(session.pk) == requested_focus:
                    return session

        today = timezone.localdate()
        now_time = timezone.localtime().time()

        today_upcoming = [
            session
            for session in sessions
            if session.session_date == today and session.start_time >= now_time
        ]
        if today_upcoming:
            return min(today_upcoming, key=lambda session: (session.start_time, session.pk))

        today_sessions = [session for session in sessions if session.session_date == today]
        if today_sessions:
            return max(today_sessions, key=lambda session: (session.start_time, session.pk))

        future_sessions = [session for session in sessions if session.session_date > today]
        if future_sessions:
            return min(future_sessions, key=lambda session: (session.session_date, session.start_time, session.pk))

        return max(sessions, key=lambda session: (session.session_date, session.start_time, session.pk))

    def get_queryset(self):
        queryset = visible_sessions_for_user(self.request.user)
        coach = self.request.GET.get("coach", "").strip()
        member = self.request.GET.get("member", "").strip()
        month_start, month_end = month_bounds(self.get_month_anchor())
        queryset = queryset.filter(session_date__range=(month_start, month_end))
        if coach:
            queryset = queryset.filter(coach_id=coach)
        if member:
            queryset = queryset.filter(attendance_records__member_id=member)
        return (
            queryset.annotate(
                attendee_count=Count("attendance_records", distinct=True),
                pending_attendance_count=Count(
                    "attendance_records",
                    filter=Q(attendance_records__status=AttendanceRecord.STATUS_SCHEDULED),
                    distinct=True,
                ),
            )
            .distinct()
            .order_by("session_date", "start_time")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        month_anchor = self.get_month_anchor()
        month_start, month_end = month_bounds(month_anchor)
        sessions = list(context["sessions"])
        today = timezone.localdate()
        session_page_mode = self.get_session_page_mode()
        checklist_enabled = self.uses_checklist_first_mode()
        focus_session = self.get_focus_session(sessions) if checklist_enabled else None
        checklist_plan = None
        focus_session_status_label = ""
        existing_checklist_report = None
        if focus_session and checklist_enabled:
            existing_checklist_report = SessionChecklistReport.objects.filter(
                training_session=focus_session, coach=self.request.user
            ).first()
        if focus_session and checklist_enabled:
            ensure_default_syllabus()
            checklist_plan = build_session_plan(focus_session)
            if focus_session.session_date == today:
                focus_session_status_label = "Today's session"
            elif focus_session.session_date > today:
                focus_session_status_label = "Next session"
            else:
                focus_session_status_label = "Recent session"

        is_parent_user = has_role(self.request.user, ROLE_PARENT)
        parent_attendance_by_session = {}
        parent_package_target = 4
        parent_done_count = 0
        parent_scheduled_count = 0
        if is_parent_user:
            parent_records = AttendanceRecord.objects.filter(
                member__parent_user=self.request.user,
                training_session__session_date__range=(month_start, month_end),
            ).select_related("training_session", "member")
            for record in parent_records:
                parent_attendance_by_session[record.training_session_id] = record
                if record.status in (AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE):
                    parent_done_count += 1
                parent_scheduled_count += 1
            # infer package target from first linked child's package sessions
            first_child = Member.objects.filter(parent_user=self.request.user).first()
            if first_child:
                parent_package_target = first_child.package_sessions or 4

        calendar_events = []
        for training_session in sessions:
            is_past = training_session.session_date < today
            parent_record = parent_attendance_by_session.get(training_session.pk) if is_parent_user else None
            done_by_parent = parent_record and parent_record.status in (
                AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE
            )
            if is_parent_user and done_by_parent:
                tone = "#16a34a"
            elif is_parent_user and parent_record and parent_record.status == AttendanceRecord.STATUS_ABSENT:
                tone = "#ef4444"
            elif is_past:
                tone = "#94a3b8"
            elif has_role(self.request.user, ROLE_ADMIN):
                tone = "#f5a623"
            else:
                tone = "#22c55e"
            title_prefix = "✓ " if done_by_parent else ""
            calendar_events.append(
                {
                    "title": f"{title_prefix}{training_session.start_time.strftime('%H:%M')} {training_session.title}",
                    "start": training_session.session_date.isoformat(),
                    "url": reverse("sessions:detail", kwargs={"pk": training_session.pk}),
                    "backgroundColor": tone,
                    "borderColor": tone,
                }
            )

        context.update(
            {
                "can_plan": has_role(self.request.user, ROLE_ADMIN),
                "can_mark_attendance": has_role(self.request.user, ROLE_ADMIN, ROLE_COACH, ROLE_HEADCOUNT),
                "coaches": User.objects.filter(profile__role=ROLE_COACH).order_by("first_name", "username"),
                "members": visible_members_for_session_filters(self.request.user),
                "calendar_events_json": json.dumps(calendar_events),
                "calendar_initial_date": month_anchor.isoformat(),
                "calendar_month_label": month_anchor.strftime("%B %Y"),
                "prev_month": shift_month(month_anchor, -1).strftime("%Y-%m"),
                "next_month": shift_month(month_anchor, 1).strftime("%Y-%m"),
                "selected_month": month_anchor.strftime("%Y-%m"),
                "selected_coach": self.request.GET.get("coach", "").strip(),
                "selected_member": self.request.GET.get("member", "").strip(),
                "is_parent_user": is_parent_user,
                "parent_package_target": parent_package_target,
                "parent_done_count": parent_done_count,
                "parent_scheduled_count": parent_scheduled_count,
                "parent_attendance_map": parent_attendance_by_session,
                "parent_progress_percent": (
                    min(round((parent_done_count / parent_package_target) * 100), 100)
                    if parent_package_target else 0
                ),
                "month_total_sessions": len(sessions),
                "month_total_players": sum(getattr(session, "attendee_count", 0) for session in sessions),
                "month_pending_attendance": sum(
                    getattr(session, "pending_attendance_count", 0) for session in sessions
                ),
                "month_start": month_start,
                "month_end": month_end,
                "today": today,
                "session_page_mode": session_page_mode,
                "checklist_enabled": checklist_enabled,
                "show_checklist_view": checklist_enabled and session_page_mode == self.VIEW_CHECKLIST,
                "show_calendar_view": not checklist_enabled or session_page_mode == self.VIEW_CALENDAR,
                "selected_focus_session": focus_session,
                "focus_session_status_label": focus_session_status_label,
                "checklist_plan": checklist_plan,
                "checklist_items": checklist_plan["blocks"] if checklist_plan else [],
                "existing_checklist_report": existing_checklist_report,
                "existing_checklist_checked": (existing_checklist_report.checked_items if existing_checklist_report else []),
                "existing_checklist_feedback": (existing_checklist_report.feedback_text if existing_checklist_report else ""),
                "can_submit_checklist": bool(focus_session and can_manage_session_plan(self.request.user, focus_session)),
                "view_query_base": "&".join(
                    part
                    for part in [
                        f"month={month_anchor.strftime('%Y-%m')}",
                        f"coach={self.request.GET.get('coach', '').strip()}" if self.request.GET.get("coach", "").strip() else "",
                        f"member={self.request.GET.get('member', '').strip()}" if self.request.GET.get("member", "").strip() else "",
                    ]
                    if part
                ),
            }
        )
        return context


class SessionDetailView(LoginRequiredMixin, DetailView):
    model = TrainingSession
    template_name = "sessions/session_detail.html"
    context_object_name = "training_session"

    def get_queryset(self):
        return visible_sessions_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        records = ordered_session_records(self.object)
        feedback_rows = build_session_feedback_rows(self.object, records=records)
        present_count = sum(1 for record in records if record.status == AttendanceRecord.STATUS_PRESENT)
        late_count = sum(1 for record in records if record.status == AttendanceRecord.STATUS_LATE)
        absent_count = sum(1 for record in records if record.status == AttendanceRecord.STATUS_ABSENT)
        scheduled_count = sum(1 for record in records if record.status == AttendanceRecord.STATUS_SCHEDULED)
        can_feedback = has_role(self.request.user, ROLE_ADMIN) or (
            has_role(self.request.user, ROLE_COACH) and (
                self.object.coach_id == self.request.user.id
                or self.object.coaches.filter(pk=self.request.user.id).exists()
            )
        )
        feedback_is_open = session_feedback_is_open(self.object)
        feedback_total_count = len(feedback_rows)
        feedback_completed_count = sum(1 for row in feedback_rows if not row["needs_feedback"])
        feedback_pending_rows = [row for row in feedback_rows if row["needs_feedback"]]
        feedback_pending_count = len(feedback_pending_rows)
        context["can_plan"] = has_role(self.request.user, ROLE_ADMIN)
        context["can_mark_attendance"] = has_role(
            self.request.user, ROLE_ADMIN, ROLE_COACH, ROLE_HEADCOUNT
        )
        context["can_feedback"] = can_feedback
        context["attendance_summary"] = [
            {"label": "Present", "value": present_count, "tone": "success"},
            {"label": "Late", "value": late_count, "tone": "warning"},
            {"label": "Absent", "value": absent_count, "tone": "danger"},
            {"label": "Unmarked", "value": scheduled_count, "tone": "info"},
        ]
        context["session_progress_summary"] = context["attendance_summary"] + [
            {"label": "Reports Done", "value": feedback_completed_count, "tone": "success"},
            {
                "label": "Reports Left",
                "value": feedback_pending_count,
                "tone": "warning" if feedback_is_open else "info",
            },
        ]
        context["attendance_rows"] = records
        context["feedback_rows"] = feedback_rows
        context["feedback_is_open"] = feedback_is_open
        context["feedback_total_count"] = feedback_total_count
        context["feedback_completed_count"] = feedback_completed_count
        context["feedback_pending_count"] = feedback_pending_count
        context["feedback_pending_rows"] = feedback_pending_rows
        context["feedback_completion_percent"] = (
            round((feedback_completed_count / feedback_total_count) * 100) if feedback_total_count else 0
        )
        context["next_feedback_member"] = feedback_pending_rows[0]["record"].member if feedback_pending_rows else None
        context["feedback_entries"] = self.object.feedback_entries.select_related("member", "coach").order_by(
            "member__full_name"
        )
        return context


class SessionPlanView(AdminOrCoachRequiredMixin, TemplateView):
    template_name = "sessions/session_plan.html"

    def get_training_session(self):
        training_session = get_object_or_404(visible_sessions_for_user(self.request.user), pk=self.kwargs["pk"])
        if not can_manage_session_plan(self.request.user, training_session):
            messages.error(self.request, "Only admin or the assigned coach can generate this training plan.")
            raise PermissionError
        return training_session

    def dispatch(self, request, *args, **kwargs):
        try:
            self.training_session = self.get_training_session()
        except PermissionError:
            return redirect("sessions:detail", pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        roster = list(
            self.training_session.attendance_records.select_related("member", "member__payment_plan").order_by("member__full_name")
        )
        context.update(
            {
                "training_session": self.training_session,
                "roster": roster,
                "autoload_plan": self.request.GET.get("autostart") == "1",
                "saved_plans": self.training_session.planner_entries.select_related("saved_by")[:8],
                "ai_planner_enabled": settings.AI_PLANNER_ENABLED,
            }
        )
        return context


class SessionPlanGenerateView(AdminOrCoachRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        training_session = get_object_or_404(visible_sessions_for_user(request.user), pk=kwargs["pk"])
        if not can_manage_session_plan(request.user, training_session):
            return JsonResponse({"error": "Only admin or the assigned coach can generate this training plan."}, status=403)
        plan_payload = build_session_plan(training_session)
        return JsonResponse(plan_payload)


class SessionPlanAssistantView(AdminOrCoachRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        training_session = get_object_or_404(visible_sessions_for_user(request.user), pk=kwargs["pk"])
        if not can_manage_session_plan(request.user, training_session):
            return JsonResponse({"error": "Only admin or the assigned coach can use the AI planner."}, status=403)

        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid request payload."}, status=400)

        user_prompt = (payload.get("prompt") or "").strip()
        if not user_prompt:
            return JsonResponse({"error": "Please enter a planner prompt first."}, status=400)

        try:
            result = generate_ai_planner_reply(training_session, user_prompt)
        except PlannerAssistantError as exc:
            return JsonResponse({"error": str(exc)}, status=503)

        return JsonResponse(
            {
                "title": result["title"],
                "prompt": user_prompt,
                "response": result["response"],
                "source": result["source"],
                "source_label": dict(SessionPlannerEntry.SOURCE_CHOICES).get(result["source"], result["source"]),
                "model_name": result["model_name"],
                "warning": result.get("warning", ""),
                "used_fallback": result.get("used_fallback", False),
                "from_cache": result.get("from_cache", False),
                "cached_entry_id": result.get("cached_entry_id"),
            }
        )


class SessionPlanSaveView(AdminOrCoachRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        training_session = get_object_or_404(visible_sessions_for_user(request.user), pk=kwargs["pk"])
        if not can_manage_session_plan(request.user, training_session):
            return JsonResponse({"error": "Only admin or the assigned coach can save AI plans."}, status=403)

        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid request payload."}, status=400)

        user_prompt = (payload.get("prompt") or "").strip()
        response_text = (payload.get("response") or "").strip()
        title = (payload.get("title") or "").strip() or "Saved session plan"
        source = payload.get("source") or SessionPlannerEntry.SOURCE_OLLAMA
        model_name = (payload.get("model_name") or "").strip()

        if not user_prompt or not response_text:
            return JsonResponse({"error": "Prompt and response are required before saving."}, status=400)

        existing_entry = SessionPlannerEntry.objects.filter(
            training_session=training_session,
            user_prompt=user_prompt,
            assistant_response=response_text,
        ).first()
        if existing_entry:
            entry = existing_entry
        else:
            entry = SessionPlannerEntry.objects.create(
                training_session=training_session,
                title=title[:255],
                user_prompt=user_prompt,
                assistant_response=response_text,
                source=source if source in dict(SessionPlannerEntry.SOURCE_CHOICES) else SessionPlannerEntry.SOURCE_OLLAMA,
                model_name=model_name[:120],
                saved_by=request.user,
            )
        return JsonResponse(
            {
                "id": entry.pk,
                "title": entry.title,
                "prompt": entry.user_prompt,
                "response": entry.assistant_response,
                "source": entry.source,
                "source_label": entry.get_source_display(),
                "model_name": entry.model_name,
                "saved_by": (entry.saved_by.get_full_name() or entry.saved_by.username) if entry.saved_by else (request.user.get_full_name() or request.user.username),
                "saved_at": timezone.localtime(entry.created_at).strftime("%d %b %Y %H:%M"),
                "already_saved": bool(existing_entry),
            }
        )


class AutoAssignSessionsView(AdminRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        month_raw = (request.POST.get("month") or "").strip()
        anchor = resolve_month_anchor(month_raw) if month_raw else timezone.localdate().replace(day=1)
        result = auto_assign_monthly_sessions(anchor)
        msg = (
            f"Auto-assigned for {result['month']}: {result['created_sessions']} new session(s), "
            f"{result['created_attendances']} roster placement(s) across {result['members_processed']} member(s)."
        )
        messages.success(request, msg)
        if result["skipped"]:
            for row in result["skipped"][:6]:
                messages.warning(request, f"{row['member']}: {row['reason']}")
        return redirect(f"{reverse('sessions:list')}?view=calendar&month={anchor:%Y-%m}")


class ParentRescheduleView(LoginRequiredMixin, View):
    # Per-parent monthly quota — applies across all their children combined.
    MONTHLY_QUOTA = 2

    def post(self, request, *args, **kwargs):
        if not has_role(request.user, ROLE_PARENT):
            messages.error(request, "Only parent accounts can reschedule sessions.")
            return redirect("sessions:list")
        # Block inactive parents from requesting reschedules.
        if not Member.objects.filter(
            parent_user=request.user, status=Member.STATUS_ACTIVE
        ).exists() and not Member.objects.filter(
            parent_user=request.user, status=Member.STATUS_TRIAL
        ).exists():
            messages.error(
                request,
                "Your account is inactive. Pay a monthly plan to unlock reschedules.",
            )
            return redirect("payments:my_payments")
        record = get_object_or_404(
            AttendanceRecord.objects.select_related("training_session", "member"),
            pk=kwargs["pk"],
            member__parent_user=request.user,
        )
        if record.status != AttendanceRecord.STATUS_SCHEDULED:
            messages.error(request, "Only upcoming sessions can be rescheduled.")
            return redirect("sessions:list")

        now = timezone.now()
        month_start_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        used_this_month = AttendanceRecord.objects.filter(
            member__parent_user=request.user,
            last_rescheduled_at__gte=month_start_dt,
        ).count()
        if used_this_month >= self.MONTHLY_QUOTA:
            messages.error(
                request,
                f"You've used all {self.MONTHLY_QUOTA} reschedules for {now:%B}. "
                "The quota resets next month.",
            )
            return redirect("sessions:list")

        new_date_raw = (request.POST.get("new_date") or "").strip()
        try:
            new_date = date.fromisoformat(new_date_raw)
        except ValueError:
            messages.error(request, "Pick a valid new date.")
            return redirect("sessions:list")
        if new_date <= timezone.localdate():
            messages.error(request, "Choose a future date for the reschedule.")
            return redirect("sessions:list")

        month_start = new_date.replace(day=1)
        _, last_day = calendar.monthrange(new_date.year, new_date.month)
        month_end = new_date.replace(day=last_day)
        month_count = AttendanceRecord.objects.filter(
            member=record.member,
            training_session__session_date__range=(month_start, month_end),
        ).exclude(pk=record.pk).count()
        package_target = record.member.package_sessions or 4
        if month_count + 1 > package_target:
            messages.error(
                request,
                f"{record.member.full_name}'s package only allows {package_target} sessions per month.",
            )
            return redirect("sessions:list")

        if not record.original_session_date:
            record.original_session_date = record.training_session.session_date

        source_session = record.training_session
        new_session, _ = TrainingSession.objects.get_or_create(
            title=source_session.title,
            session_date=new_date,
            start_time=source_session.start_time,
            end_time=source_session.end_time,
            court=source_session.court,
            defaults={
                "coach": source_session.coach,
                "syllabus_root": source_session.syllabus_root,
                "notes": source_session.notes,
                "created_by": request.user,
            },
        )
        record.training_session = new_session
        record.reschedule_count = record.reschedule_count + 1
        record.last_rescheduled_at = now
        record.save()
        remaining = max(self.MONTHLY_QUOTA - (used_this_month + 1), 0)
        messages.success(
            request,
            f"Rescheduled to {new_date:%d %b %Y}. "
            f"{remaining} reschedule(s) left this month.",
        )
        return redirect("sessions:list")


class SessionChecklistSaveView(AdminOrCoachRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        training_session = get_object_or_404(
            visible_sessions_for_user(request.user), pk=kwargs["pk"]
        )
        if not can_manage_session_plan(request.user, training_session):
            messages.error(request, "Only admin or the assigned coach can submit this checklist report.")
            return redirect("sessions:list")
        checked_items = request.POST.getlist("checked_items")
        feedback_text = (request.POST.get("feedback_text") or "").strip()
        report, _ = SessionChecklistReport.objects.update_or_create(
            training_session=training_session,
            coach=request.user,
            defaults={"checked_items": checked_items, "feedback_text": feedback_text},
        )
        messages.success(request, "Session checklist saved. Admins can review it in the audit log.")
        return redirect(f"{reverse('sessions:list')}?view=checklist&focus={training_session.pk}")


class SessionChecklistAuditView(AdminRequiredMixin, ListView):
    template_name = "sessions/checklist_audit.html"
    context_object_name = "checklist_reports"
    paginate_by = 25

    def get_queryset(self):
        queryset = SessionChecklistReport.objects.select_related(
            "training_session", "coach"
        ).order_by("-updated_at")
        coach = self.request.GET.get("coach", "").strip()
        if coach:
            queryset = queryset.filter(coach_id=coach)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["coaches"] = User.objects.filter(profile__role=ROLE_COACH).order_by(
            "first_name", "username"
        )
        context["selected_coach"] = self.request.GET.get("coach", "").strip()
        return context


class SessionCreateView(AdminRequiredMixin, CreateView):
    model = TrainingSession
    form_class = TrainingSessionForm
    template_name = "sessions/session_form.html"
    success_url = reverse_lazy("sessions:list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["current_user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        created_sessions = form.created_sessions or [self.object]
        notify_schedule_participants(created_sessions, updated=False)
        session_count = len(created_sessions)
        if session_count > 1:
            messages.success(self.request, f"{session_count} recurring sessions created and notifications were sent.")
        else:
            messages.success(self.request, "Session created successfully and notifications were sent.")
        # Warn the admin if no students were assigned. The coach view shows
        # "No players assigned yet" if a session is created with an empty
        # roster, so call it out instead of letting it slip through silently.
        empty_count = sum(1 for s in created_sessions if not s.attendance_records.exists())
        if empty_count:
            messages.warning(
                self.request,
                f"{empty_count} session(s) were created without any assigned students. "
                "Open the session and add players, or coaches will see an empty roster.",
            )
        return response


class SessionUpdateView(AdminRequiredMixin, UpdateView):
    model = TrainingSession
    form_class = TrainingSessionForm
    template_name = "sessions/session_form.html"
    success_url = reverse_lazy("sessions:list")

    def get_queryset(self):
        return TrainingSession.objects.select_related("coach").prefetch_related("attendance_records__member")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["current_user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        notify_schedule_participants([self.object], updated=True)
        messages.success(self.request, "Session updated successfully and the schedule alerts were refreshed.")
        if not self.object.attendance_records.exists():
            messages.warning(
                self.request,
                "This session has no assigned students. Coaches will see an empty roster until you add some.",
            )
        return response


class SessionDeleteView(AdminRequiredMixin, View):
    """Admin removes a wrongly-created training session."""

    def post(self, request, *args, **kwargs):
        training_session = get_object_or_404(TrainingSession, pk=kwargs["pk"])
        title = training_session.title
        training_session.delete()
        messages.success(request, f"Session '{title}' deleted.")
        return redirect("sessions:list")


class AttendanceUpdateView(HeadcountOrAboveRequiredMixin, View):
    template_name = "sessions/attendance_form.html"

    def get_training_session(self):
        return get_object_or_404(visible_sessions_for_user(self.request.user), pk=self.kwargs["pk"])

    def render_page(self, request, training_session, formset):
        queryset = training_session.attendance_records.select_related("member", "member__payment_plan").order_by("member__full_name")
        return render(
            request,
            self.template_name,
            {
                "training_session": training_session,
                "attendance_rows": zip(formset.forms, queryset),
                "management_form": formset.management_form,
            },
        )

    def get(self, request, *args, **kwargs):
        training_session = self.get_training_session()
        queryset = training_session.attendance_records.select_related("member", "member__payment_plan").order_by("member__full_name")
        formset = AttendanceFormSet(queryset=queryset)
        return self.render_page(request, training_session, formset)

    def post(self, request, *args, **kwargs):
        training_session = self.get_training_session()
        queryset = training_session.attendance_records.select_related("member", "member__payment_plan").order_by("member__full_name")
        formset = AttendanceFormSet(request.POST, queryset=queryset)
        if formset.is_valid():
            touched_members = []
            for form in formset.forms:
                if form.has_changed():
                    record = form.save(commit=False)
                    record.marked_by = request.user
                    record.marked_at = timezone.now()
                    record.save()
                    touched_members.append(record.member)
            # Trial members deactivate as soon as their lifetime trial quota is hit.
            expired_names = []
            for member in touched_members:
                member.refresh_from_db(fields=["status"])
                if expire_trial_if_needed(member):
                    expired_names.append(member.full_name)
            messages.success(request, "Attendance updated successfully.")
            if expired_names:
                messages.info(
                    request,
                    "Trial complete for: "
                    + ", ".join(expired_names)
                    + ". Account(s) marked inactive until a plan is paid.",
                )
            return redirect("sessions:detail", pk=training_session.pk)
        return self.render_page(request, training_session, formset)


class SessionFeedbackUpsertView(AdminOrCoachRequiredMixin, View):
    template_name = "sessions/feedback_form.html"

    def get_training_session(self):
        return get_object_or_404(visible_sessions_for_user(self.request.user), pk=self.kwargs["session_pk"])

    def get_member(self, training_session):
        record = get_object_or_404(
            training_session.attendance_records.select_related("member"),
            member_id=self.kwargs["member_pk"],
        )
        return record.member

    def get_feedback(self, training_session, member):
        return SessionFeedback.objects.filter(training_session=training_session, member=member).first()

    def can_manage_feedback(self, training_session):
        return has_role(self.request.user, ROLE_ADMIN) or (
            has_role(self.request.user, ROLE_COACH) and (
                training_session.coach_id == self.request.user.id
                or training_session.coaches.filter(pk=self.request.user.id).exists()
            )
        )

    def render_page(self, request, training_session, member, form, feedback):
        navigation_context = build_feedback_form_navigation(training_session, member)
        workspace_context = build_session_feedback_form_context(member, training_session, current_feedback=feedback)
        return render(
            request,
            self.template_name,
            {
                "training_session": training_session,
                "member": member,
                "form": form,
                "feedback": feedback,
                "is_edit": bool(feedback and feedback.pk),
                **navigation_context,
                **workspace_context,
            },
        )

    def get(self, request, *args, **kwargs):
        training_session = self.get_training_session()
        if not self.can_manage_feedback(training_session):
            messages.error(request, "Only admin or the assigned coach can submit the session report for this session.")
            return redirect("sessions:detail", pk=training_session.pk)
        member = self.get_member(training_session)
        feedback = self.get_feedback(training_session, member)
        form = SessionFeedbackForm(instance=feedback)
        return self.render_page(request, training_session, member, form, feedback)

    def post(self, request, *args, **kwargs):
        training_session = self.get_training_session()
        if not self.can_manage_feedback(training_session):
            messages.error(request, "Only admin or the assigned coach can submit the session report for this session.")
            return redirect("sessions:detail", pk=training_session.pk)
        if training_session.session_date > timezone.localdate():
            messages.warning(request, "The session report can only be completed after the session date.")
            return redirect("sessions:detail", pk=training_session.pk)

        member = self.get_member(training_session)
        feedback = self.get_feedback(training_session, member)
        form = SessionFeedbackForm(request.POST, request.FILES, instance=feedback)
        if form.is_valid():
            feedback_entry = form.save(commit=False)
            feedback_entry.training_session = training_session
            feedback_entry.member = member
            feedback_entry.coach = training_session.coach or request.user
            feedback_entry.save()
            compress_session_feedback_video(feedback_entry)
            notify_feedback_ready(feedback_entry)
            if request.POST.get("save_and_next"):
                next_member = get_next_pending_feedback_member(training_session, current_member_id=member.id)
                if next_member:
                    messages.success(
                        request,
                        f"Session report saved for {member.full_name}. Opening {next_member.full_name} next.",
                    )
                    return redirect("sessions:feedback", session_pk=training_session.pk, member_pk=next_member.pk)
            messages.success(request, f"Session report saved for {member.full_name}.")
            return redirect("sessions:detail", pk=training_session.pk)
        return self.render_page(request, training_session, member, form, feedback)


class AttendanceOverviewView(AdminOrCoachRequiredMixin, ListView):
    """Cross-session attendance summary — one row per student.

    Admin / coach see every student they're allowed to see, with totals for
    present / absent / late / scheduled and an attendance rate.
    """

    template_name = "sessions/attendance_overview.html"
    context_object_name = "members"
    paginate_by = 20

    def get_queryset(self):
        from members.views import visible_members_for_user
        queryset = visible_members_for_user(self.request.user).order_by("full_name", "id").distinct()

        search = self.request.GET.get("q", "").strip()
        status_filter = self.request.GET.get("status", "").strip()
        coach_filter = self.request.GET.get("coach", "").strip()
        level_filter = self.request.GET.get("level", "").strip()
        if search:
            queryset = queryset.filter(full_name__icontains=search)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if coach_filter:
            queryset = queryset.filter(assigned_coach_id=coach_filter)
        if level_filter:
            queryset = queryset.filter(skill_level=level_filter)

        # Aggregate attendance counts per member.
        queryset = queryset.annotate(
            total_records=Count("attendance_records"),
            present_count=Count(
                "attendance_records",
                filter=Q(attendance_records__status=AttendanceRecord.STATUS_PRESENT),
            ),
            absent_count=Count(
                "attendance_records",
                filter=Q(attendance_records__status=AttendanceRecord.STATUS_ABSENT),
            ),
            late_count=Count(
                "attendance_records",
                filter=Q(attendance_records__status=AttendanceRecord.STATUS_LATE),
            ),
            scheduled_count=Count(
                "attendance_records",
                filter=Q(attendance_records__status=AttendanceRecord.STATUS_SCHEDULED),
            ),
        )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Compute attendance_rate in Python so we can divide safely.
        rows = []
        for member in context["members"]:
            attended = (member.present_count or 0) + (member.late_count or 0)
            counted = attended + (member.absent_count or 0)
            rate = round((attended / counted) * 100) if counted else None
            rows.append({"member": member, "attendance_rate": rate})
        context["rows"] = rows

        all_members = self.get_queryset()
        agg = all_members.aggregate(
            total=Count("attendance_records"),
            present=Count(
                "attendance_records",
                filter=Q(attendance_records__status=AttendanceRecord.STATUS_PRESENT),
            ),
            absent=Count(
                "attendance_records",
                filter=Q(attendance_records__status=AttendanceRecord.STATUS_ABSENT),
            ),
            late=Count(
                "attendance_records",
                filter=Q(attendance_records__status=AttendanceRecord.STATUS_LATE),
            ),
        )
        attended_total = (agg["present"] or 0) + (agg["late"] or 0)
        counted_total = attended_total + (agg["absent"] or 0)
        context["summary"] = {
            "students": all_members.count(),
            "total_records": agg["total"] or 0,
            "present": agg["present"] or 0,
            "absent": agg["absent"] or 0,
            "late": agg["late"] or 0,
            "rate": round((attended_total / counted_total) * 100) if counted_total else None,
        }

        context["statuses"] = Member.STATUS_CHOICES
        context["levels"] = Member.LEVEL_CHOICES
        context["is_admin"] = has_role(self.request.user, ROLE_ADMIN)
        context["coaches"] = (
            User.objects.filter(profile__role=ROLE_COACH)
            .select_related("profile")
            .order_by("first_name", "username")
            if has_role(self.request.user, ROLE_ADMIN)
            else []
        )
        active_filter_count = sum(
            1
            for key in ("status", "coach", "level")
            if self.request.GET.get(key, "").strip()
        )
        context["active_filter_count"] = active_filter_count
        context["filters_open"] = active_filter_count > 0
        return context


class MemberAttendanceDetailView(AdminOrCoachRequiredMixin, DetailView):
    """Drill-down: every AttendanceRecord for one student, admin can edit inline."""

    template_name = "sessions/attendance_member_detail.html"
    context_object_name = "member"

    def get_queryset(self):
        from members.views import visible_members_for_user
        return visible_members_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        records = (
            self.object.attendance_records
            .select_related("training_session", "training_session__coach", "marked_by")
            .order_by("-training_session__session_date", "-training_session__start_time")
        )
        context["records"] = records
        present = records.filter(status=AttendanceRecord.STATUS_PRESENT).count()
        late = records.filter(status=AttendanceRecord.STATUS_LATE).count()
        absent = records.filter(status=AttendanceRecord.STATUS_ABSENT).count()
        scheduled = records.filter(status=AttendanceRecord.STATUS_SCHEDULED).count()
        attended = present + late
        counted = attended + absent
        context["stats"] = {
            "present": present,
            "absent": absent,
            "late": late,
            "scheduled": scheduled,
            "total": records.count(),
            "attended": attended,
            "rate": round((attended / counted) * 100) if counted else None,
        }
        context["status_choices"] = AttendanceRecord.STATUS_CHOICES
        context["is_admin"] = has_role(self.request.user, ROLE_ADMIN)
        return context


class AttendanceRecordEditView(AdminOrCoachRequiredMixin, View):
    """Inline edit a single AttendanceRecord status from the overview drill-down."""

    def post(self, request, *args, **kwargs):
        record = get_object_or_404(
            AttendanceRecord.objects.select_related("training_session", "member"),
            pk=kwargs["pk"],
        )
        # Coaches can only edit their own sessions; admins can edit any.
        if not has_role(request.user, ROLE_ADMIN):
            ts = record.training_session
            is_session_coach = ts.coach_id == request.user.id or ts.coaches.filter(pk=request.user.id).exists()
            if not is_session_coach:
                messages.error(request, "You can only edit attendance for your own sessions.")
                return redirect("sessions:attendance_overview")

        new_status = (request.POST.get("status") or "").strip()
        valid = {choice[0] for choice in AttendanceRecord.STATUS_CHOICES}
        if new_status not in valid:
            messages.error(request, "Invalid attendance status.")
            return redirect("sessions:member_attendance", pk=record.member_id)

        record.status = new_status
        record.marked_by = request.user
        record.marked_at = timezone.now()
        record.save(update_fields=["status", "marked_by", "marked_at"])
        # Trial-quota check, mirrors AttendanceUpdateView behaviour.
        record.member.refresh_from_db(fields=["status"])
        if expire_trial_if_needed(record.member):
            messages.info(
                request,
                f"Trial complete for {record.member.full_name}. Account marked inactive until a plan is paid.",
            )
        messages.success(
            request,
            f"Marked {record.member.full_name} as {record.get_status_display()} for {record.training_session.title}.",
        )
        return redirect("sessions:member_attendance", pk=record.member_id)
