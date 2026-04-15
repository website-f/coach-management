import calendar
import json
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
from members.models import Member
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
    SessionFeedback,
    SessionPlannerEntry,
    SyllabusRoot,
    SyllabusStandard,
    SyllabusTemplate,
    TrainingSession,
    WeeklySyllabus,
)
from sessions.services import build_session_plan, ensure_default_syllabus
from sessions.video_utils import compress_session_feedback_video

User = get_user_model()

AttendanceFormSet = modelformset_factory(
    AttendanceRecord,
    fields=("status",),
    extra=0,
    widgets={"status": forms.Select(attrs={"class": "rounded-xl bg-slate-900 border border-slate-700 px-3 py-2 text-sm"})},
)


def visible_sessions_for_user(user):
    queryset = TrainingSession.objects.select_related("coach", "created_by", "syllabus_root")
    if has_role(user, ROLE_COACH) and not has_role(user, ROLE_ADMIN):
        return queryset.filter(coach=user)
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
        title="New session feedback available",
        message=f"{coach_name} uploaded feedback for {member.full_name} after {session.title}.",
        url=reverse("members:detail", kwargs={"pk": member.pk}),
        email_subject=f"New feedback for {member.full_name}",
        email_message=(
            f"{coach_name} uploaded feedback for {member.full_name}.\n"
            f"Session: {session.title}\n"
            f"Date: {session.session_date:%d %b %Y}\n"
            "Log in to the dashboard to review the feedback and video proof."
        ),
    )


def can_manage_session_plan(user, training_session):
    return has_role(user, ROLE_ADMIN) or (
        has_role(user, ROLE_COACH) and training_session.coach_id == user.id
    )


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
        return SyllabusRoot.objects.order_by("name")

    def get_selected_root(self):
        selected_root = self.request.GET.get("root", "").strip()
        queryset = self.get_queryset()
        if selected_root:
            return queryset.filter(pk=selected_root).first()
        return queryset.first()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_track = self.request.GET.get("track", "").strip()
        selected_root = self.get_selected_root()
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
        track = self.request.GET.get("track", "").strip()
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
    model = TrainingSession
    template_name = "sessions/session_list.html"
    context_object_name = "sessions"

    def get_month_anchor(self):
        return resolve_month_anchor(self.request.GET.get("month"))

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
        calendar_events = []
        for training_session in sessions:
            is_past = training_session.session_date < today
            attendee_count = getattr(training_session, "attendee_count", 0)
            tone = "#94a3b8" if is_past else "#f5a623" if has_role(self.request.user, ROLE_ADMIN) else "#22c55e"
            calendar_events.append(
                {
                    "title": f"{training_session.start_time.strftime('%H:%M')} {training_session.title}",
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
                "month_total_sessions": len(sessions),
                "month_total_players": sum(getattr(session, "attendee_count", 0) for session in sessions),
                "month_pending_attendance": sum(
                    getattr(session, "pending_attendance_count", 0) for session in sessions
                ),
                "month_start": month_start,
                "month_end": month_end,
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
        records = list(
            self.object.attendance_records.select_related(
                "member",
                "member__payment_plan",
                "member__assigned_coach",
                "member__parent_user",
            ).order_by("member__full_name")
        )
        feedback_map = {
            feedback.member_id: feedback
            for feedback in self.object.feedback_entries.select_related("member", "coach")
        }
        present_count = sum(1 for record in records if record.status == AttendanceRecord.STATUS_PRESENT)
        late_count = sum(1 for record in records if record.status == AttendanceRecord.STATUS_LATE)
        absent_count = sum(1 for record in records if record.status == AttendanceRecord.STATUS_ABSENT)
        scheduled_count = sum(1 for record in records if record.status == AttendanceRecord.STATUS_SCHEDULED)
        can_feedback = has_role(self.request.user, ROLE_ADMIN) or (
            has_role(self.request.user, ROLE_COACH) and self.object.coach_id == self.request.user.id
        )
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
        context["attendance_rows"] = records
        context["feedback_rows"] = [
            {
                "record": record,
                "feedback": feedback_map.get(record.member_id),
            }
            for record in records
        ]
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
        return response


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
            for form in formset.forms:
                if form.has_changed():
                    record = form.save(commit=False)
                    record.marked_by = request.user
                    record.marked_at = timezone.now()
                    record.save()
            messages.success(request, "Attendance updated successfully.")
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
            has_role(self.request.user, ROLE_COACH) and training_session.coach_id == self.request.user.id
        )

    def render_page(self, request, training_session, member, form, feedback):
        return render(
            request,
            self.template_name,
            {
                "training_session": training_session,
                "member": member,
                "form": form,
                "feedback": feedback,
                "is_edit": bool(feedback and feedback.pk),
            },
        )

    def get(self, request, *args, **kwargs):
        training_session = self.get_training_session()
        if not self.can_manage_feedback(training_session):
            messages.error(request, "Only admin or the assigned coach can submit feedback for this session.")
            return redirect("sessions:detail", pk=training_session.pk)
        member = self.get_member(training_session)
        feedback = self.get_feedback(training_session, member)
        form = SessionFeedbackForm(instance=feedback)
        return self.render_page(request, training_session, member, form, feedback)

    def post(self, request, *args, **kwargs):
        training_session = self.get_training_session()
        if not self.can_manage_feedback(training_session):
            messages.error(request, "Only admin or the assigned coach can submit feedback for this session.")
            return redirect("sessions:detail", pk=training_session.pk)
        if training_session.session_date > timezone.localdate():
            messages.warning(request, "Feedback can only be uploaded after the session date.")
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
            messages.success(request, f"Feedback saved for {member.full_name}.")
            return redirect("sessions:detail", pk=training_session.pk)
        return self.render_page(request, training_session, member, form, feedback)
