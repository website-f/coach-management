from django import forms
from django.contrib.auth import get_user_model

from accounts.models import UserProfile
from accounts.utils import ROLE_ADMIN, ROLE_COACH, has_role
from members.models import Member
from sessions.models import TrainingSession

User = get_user_model()


class TrainingSessionForm(forms.ModelForm):
    members = forms.ModelMultipleChoiceField(
        queryset=Member.objects.filter(status=Member.STATUS_ACTIVE).order_by("full_name"),
        required=False,
        widget=forms.SelectMultiple(attrs={"size": 8}),
    )

    class Meta:
        model = TrainingSession
        fields = [
            "title",
            "session_date",
            "start_time",
            "end_time",
            "court",
            "coach",
            "members",
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
        self.fields["coach"].queryset = User.objects.filter(profile__role=UserProfile.ROLE_COACH).order_by(
            "first_name", "username"
        )
        if self.instance.pk:
            self.fields["members"].initial = self.instance.attendance_records.values_list("member_id", flat=True)
        if current_user and has_role(current_user, ROLE_COACH) and not has_role(current_user, ROLE_ADMIN):
            self.fields["coach"].queryset = User.objects.filter(pk=current_user.pk)
            self.fields["coach"].initial = current_user

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        if start_time and end_time and end_time <= start_time:
            self.add_error("end_time", "End time must be later than start time.")
        return cleaned_data

    def save(self, commit=True):
        training_session = super().save(commit=False)
        if self.current_user and has_role(self.current_user, ROLE_COACH) and not has_role(self.current_user, ROLE_ADMIN):
            training_session.coach = self.current_user
        if commit:
            training_session.save()
            self.save_members(training_session)
        return training_session

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
