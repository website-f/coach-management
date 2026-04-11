from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.forms import modelformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from accounts.mixins import AdminOrCoachRequiredMixin, HeadcountOrAboveRequiredMixin
from accounts.utils import ROLE_ADMIN, ROLE_COACH, ROLE_HEADCOUNT, ROLE_PARENT, has_role
from accounts.models import UserProfile
from sessions.forms import TrainingSessionForm
from sessions.models import AttendanceRecord, TrainingSession

User = get_user_model()

AttendanceFormSet = modelformset_factory(
    AttendanceRecord,
    fields=("status",),
    extra=0,
    widgets={"status": forms.Select(attrs={"class": "rounded-xl bg-slate-900 border border-slate-700 px-3 py-2 text-sm"})},
)


def visible_sessions_for_user(user):
    queryset = TrainingSession.objects.select_related("coach").prefetch_related("attendance_records__member")
    if has_role(user, ROLE_COACH) and not has_role(user, ROLE_ADMIN):
        return queryset.filter(coach=user)
    if has_role(user, ROLE_PARENT):
        return queryset.filter(attendance_records__member__parent_user=user).distinct()
    return queryset


class SessionListView(LoginRequiredMixin, ListView):
    model = TrainingSession
    template_name = "sessions/session_list.html"
    context_object_name = "sessions"
    paginate_by = 10

    def get_queryset(self):
        queryset = visible_sessions_for_user(self.request.user)
        coach = self.request.GET.get("coach", "").strip()
        session_date = self.request.GET.get("session_date", "").strip()
        if coach:
            queryset = queryset.filter(coach_id=coach)
        if session_date:
            queryset = queryset.filter(session_date=session_date)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_manage"] = has_role(self.request.user, ROLE_ADMIN, ROLE_COACH)
        context["can_mark_attendance"] = has_role(
            self.request.user, ROLE_ADMIN, ROLE_COACH, ROLE_HEADCOUNT
        )
        context["coaches"] = User.objects.filter(profile__role=UserProfile.ROLE_COACH).order_by("first_name", "username")
        return context


class SessionDetailView(LoginRequiredMixin, DetailView):
    model = TrainingSession
    template_name = "sessions/session_detail.html"
    context_object_name = "training_session"

    def get_queryset(self):
        return visible_sessions_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_manage"] = has_role(self.request.user, ROLE_ADMIN, ROLE_COACH)
        context["can_mark_attendance"] = has_role(
            self.request.user, ROLE_ADMIN, ROLE_COACH, ROLE_HEADCOUNT
        )
        return context


class SessionCreateView(AdminOrCoachRequiredMixin, CreateView):
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
        messages.success(self.request, "Session created successfully.")
        return response


class SessionUpdateView(AdminOrCoachRequiredMixin, UpdateView):
    model = TrainingSession
    form_class = TrainingSessionForm
    template_name = "sessions/session_form.html"
    success_url = reverse_lazy("sessions:list")

    def get_queryset(self):
        return visible_sessions_for_user(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["current_user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Session updated successfully.")
        return response


class AttendanceUpdateView(HeadcountOrAboveRequiredMixin, View):
    template_name = "sessions/attendance_form.html"

    def get_training_session(self):
        return get_object_or_404(visible_sessions_for_user(self.request.user), pk=self.kwargs["pk"])

    def render_page(self, request, training_session, formset):
        queryset = training_session.attendance_records.select_related("member").order_by("member__full_name")
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
        queryset = training_session.attendance_records.select_related("member").order_by("member__full_name")
        formset = AttendanceFormSet(queryset=queryset)
        return self.render_page(request, training_session, formset)

    def post(self, request, *args, **kwargs):
        training_session = self.get_training_session()
        queryset = training_session.attendance_records.select_related("member").order_by("member__full_name")
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

# Create your views here.
