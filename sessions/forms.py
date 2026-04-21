import calendar
from datetime import date

from django import forms
from django.contrib.auth import get_user_model

from accounts.models import UserProfile
from accounts.utils import ROLE_ADMIN, ROLE_COACH, has_role
from finance.models import BillingConfiguration
from members.models import Member
from sessions.models import (
    SessionFeedback,
    SyllabusRoot,
    SyllabusStandard,
    SyllabusTemplate,
    TrainingSession,
    WeeklySyllabus,
)

User = get_user_model()


class RangeInput(forms.widgets.Input):
    input_type = "range"


class TrainingSessionForm(forms.ModelForm):
    SCHEDULE_MODE_ONE_TIME = "one_time"
    SCHEDULE_MODE_RECURRING = "recurring"
    WEEKDAY_CHOICES = [
        ("0", "Monday"),
        ("1", "Tuesday"),
        ("2", "Wednesday"),
        ("3", "Thursday"),
        ("4", "Friday"),
        ("5", "Saturday"),
        ("6", "Sunday"),
    ]

    members = forms.ModelMultipleChoiceField(
        queryset=Member.objects.filter(status__in=[Member.STATUS_ACTIVE, Member.STATUS_TRIAL]).order_by("full_name"),
        required=False,
        widget=forms.SelectMultiple(attrs={"size": 8}),
    )
    schedule_mode = forms.ChoiceField(
        choices=(
            (SCHEDULE_MODE_ONE_TIME, "Single session"),
            (SCHEDULE_MODE_RECURRING, "Repeat weekly for this month"),
        ),
        initial=SCHEDULE_MODE_ONE_TIME,
        required=False,
    )
    recurring_weekdays = forms.MultipleChoiceField(
        choices=WEEKDAY_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = TrainingSession
        fields = [
            "title",
            "session_date",
            "start_time",
            "end_time",
            "court",
            "syllabus_root",
            "coach",
            "notes",
        ]
        widgets = {
            "session_date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_user = current_user
        self.created_sessions = []
        self.generated_schedule_dates = []
        self.fields["syllabus_root"].queryset = SyllabusRoot.objects.filter(is_active=True).order_by("name")
        self.fields["coach"].queryset = User.objects.filter(profile__role=UserProfile.ROLE_COACH).order_by(
            "first_name", "username"
        )
        if self.instance.pk:
            self.fields["members"].initial = self.instance.attendance_records.values_list("member_id", flat=True)
            self.fields["schedule_mode"].initial = self.SCHEDULE_MODE_ONE_TIME
        if current_user and has_role(current_user, ROLE_COACH) and not has_role(current_user, ROLE_ADMIN):
            self.fields["coach"].queryset = User.objects.filter(pk=current_user.pk)
            self.fields["coach"].initial = current_user
        if self.instance.pk:
            self.fields["schedule_mode"].help_text = "Recurring generation is only used while creating a new schedule."

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        schedule_mode = cleaned_data.get("schedule_mode")
        recurring_weekdays = cleaned_data.get("recurring_weekdays")
        if start_time and end_time and end_time <= start_time:
            self.add_error("end_time", "End time must be later than start time.")
        if (
            not self.instance.pk
            and schedule_mode == self.SCHEDULE_MODE_RECURRING
            and not recurring_weekdays
        ):
            self.add_error("recurring_weekdays", "Choose at least one weekday for the recurring schedule.")
        selected_members = cleaned_data.get("members")
        session_date = cleaned_data.get("session_date")
        if selected_members and session_date:
            prospective_count = 1
            if not self.instance.pk and schedule_mode == self.SCHEDULE_MODE_RECURRING and recurring_weekdays:
                prospective_count = len(self.build_recurring_dates(session_date, recurring_weekdays))
            trial_limit = BillingConfiguration.get_solo().trial_session_limit or 1
            over_limit_names = []
            for member in selected_members:
                if member.status != Member.STATUS_TRIAL:
                    continue
                existing_records = member.attendance_records.all()
                if self.instance.pk:
                    existing_records = existing_records.exclude(training_session=self.instance)
                if existing_records.count() + prospective_count > trial_limit:
                    over_limit_names.append(member.full_name)
            if over_limit_names:
                self.add_error(
                    "members",
                    f"Trial limit exceeded for: {', '.join(over_limit_names)}. Increase the trial limit or move them to an active package first.",
                )
        return cleaned_data

    def save(self, commit=True):
        training_session = super().save(commit=False)
        if self.current_user and has_role(self.current_user, ROLE_COACH) and not has_role(self.current_user, ROLE_ADMIN):
            training_session.coach = self.current_user
        if not commit:
            return training_session

        if self.instance.pk or self.cleaned_data.get("schedule_mode") == self.SCHEDULE_MODE_ONE_TIME:
            training_session.save()
            self.save_members(training_session)
            self.created_sessions = [training_session]
            self.generated_schedule_dates = [training_session.session_date]
            return training_session

        recurring_dates = self.build_recurring_dates(
            training_session.session_date,
            self.cleaned_data.get("recurring_weekdays", []),
        )
        self.generated_schedule_dates = recurring_dates
        for occurrence_date in recurring_dates:
            session = TrainingSession.objects.filter(
                title=training_session.title,
                session_date=occurrence_date,
                start_time=training_session.start_time,
                end_time=training_session.end_time,
                court=training_session.court,
                coach=training_session.coach,
            ).first()
            if not session:
                session = TrainingSession(
                    title=training_session.title,
                    session_date=occurrence_date,
                    start_time=training_session.start_time,
                    end_time=training_session.end_time,
                    court=training_session.court,
                    syllabus_root=training_session.syllabus_root,
                    coach=training_session.coach,
                    notes=training_session.notes,
                    created_by=training_session.created_by,
                )
            else:
                session.syllabus_root = training_session.syllabus_root
                session.notes = training_session.notes
            session.save()
            self.save_members(session)
            self.created_sessions.append(session)
        return self.created_sessions[0]

    def build_recurring_dates(self, anchor_date, weekday_values):
        weekdays = {int(value) for value in weekday_values}
        _, days_in_month = calendar.monthrange(anchor_date.year, anchor_date.month)
        dates = []
        for day in range(1, days_in_month + 1):
            candidate = date(anchor_date.year, anchor_date.month, day)
            if candidate.weekday() in weekdays:
                dates.append(candidate)
        return dates

    def save_members(self, training_session):
        selected_members = self.cleaned_data["members"]
        existing_records = {
            record.member_id: record for record in training_session.attendance_records.all()
        }
        selected_member_ids = set(selected_members.values_list("id", flat=True))
        for member in selected_members:
            if member.id not in existing_records:
                training_session.attendance_records.create(member=member)
        for member_id, record in existing_records.items():
            if member_id not in selected_member_ids:
                record.delete()


class SessionFeedbackForm(forms.ModelForm):
    class Meta:
        model = SessionFeedback
        fields = ["feedback_text", "video_proof"]
        widgets = {
            "feedback_text": forms.Textarea(
                attrs={
                    "rows": 6,
                    "placeholder": "Summarize this session for the student: strongest point, biggest issue, and what comes next. Skill grading is handled once every six months in the progress report.",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["feedback_text"].label = "Session feedback"
        self.fields["feedback_text"].required = True
        self.fields["video_proof"].help_text = "Optional proof clip, rally sequence, or technique example."


class WeeklySyllabusForm(forms.ModelForm):
    class Meta:
        model = WeeklySyllabus
        fields = [
            "root",
            "track",
            "template",
            "standard",
            "month_number",
            "phase_name",
            "week_number",
            "title",
            "objective",
            "warm_up_plan",
            "technical_focus",
            "tactical_focus",
            "coaching_cues",
            "assessment_focus",
            "success_criteria",
            "coach_notes",
            "homework",
            "is_active",
        ]
        widgets = {
            "month_number": forms.NumberInput(attrs={"min": 1, "max": 12}),
            "objective": forms.Textarea(attrs={"rows": 3}),
            "warm_up_plan": forms.Textarea(attrs={"rows": 3}),
            "technical_focus": forms.Textarea(attrs={"rows": 4}),
            "tactical_focus": forms.Textarea(attrs={"rows": 4}),
            "coaching_cues": forms.Textarea(attrs={"rows": 4}),
            "assessment_focus": forms.Textarea(attrs={"rows": 3}),
            "success_criteria": forms.Textarea(attrs={"rows": 3}),
            "coach_notes": forms.Textarea(attrs={"rows": 3}),
            "homework": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["root"].queryset = SyllabusRoot.objects.filter(is_active=True).order_by("name")
        self.fields["template"].queryset = SyllabusTemplate.objects.order_by("root__name", "track", "name")
        self.fields["standard"].queryset = SyllabusStandard.objects.select_related("template").order_by(
            "template__root__name",
            "template__track",
            "sort_order",
            "code",
        )
        if self.instance.pk and self.instance.template_id:
            self.fields["standard"].queryset = self.fields["standard"].queryset.filter(template=self.instance.template)


class SyllabusTemplateForm(forms.ModelForm):
    class Meta:
        model = SyllabusTemplate
        fields = [
            "root",
            "track",
            "name",
            "source_document_name",
            "curriculum_year_label",
            "annual_goal",
            "year_end_outcomes",
            "assessment_approach",
            "assessment_methods",
            "curriculum_values",
            "annual_phase_notes",
            "ai_planner_instructions",
            "is_active",
        ]
        widgets = {
            "annual_goal": forms.Textarea(attrs={"rows": 4}),
            "year_end_outcomes": forms.Textarea(attrs={"rows": 5}),
            "assessment_approach": forms.Textarea(attrs={"rows": 3}),
            "assessment_methods": forms.Textarea(attrs={"rows": 4}),
            "curriculum_values": forms.Textarea(attrs={"rows": 3}),
            "annual_phase_notes": forms.Textarea(attrs={"rows": 4}),
            "ai_planner_instructions": forms.Textarea(attrs={"rows": 4}),
        }


class SyllabusRootForm(forms.ModelForm):
    class Meta:
        model = SyllabusRoot
        fields = ["name", "code", "description", "is_active", "is_default"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }


class SyllabusStandardForm(forms.ModelForm):
    class Meta:
        model = SyllabusStandard
        fields = [
            "template",
            "sort_order",
            "code",
            "title",
            "focus",
            "learning_standard_items",
            "performance_band_items",
            "coach_hints",
            "assessment_focus",
            "is_active",
        ]
        widgets = {
            "sort_order": forms.NumberInput(attrs={"min": 1}),
            "focus": forms.Textarea(attrs={"rows": 3}),
            "learning_standard_items": forms.Textarea(attrs={"rows": 5}),
            "performance_band_items": forms.Textarea(attrs={"rows": 5}),
            "coach_hints": forms.Textarea(attrs={"rows": 3}),
            "assessment_focus": forms.Textarea(attrs={"rows": 3}),
        }
