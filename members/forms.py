from django import forms
from django.contrib.auth import get_user_model

from accounts.models import LandingPageContent, UserProfile
from accounts.utils import ROLE_ADMIN, ROLE_COACH, has_role
from members.models import AdmissionApplication, DEFAULT_SKILLS, Member, ProgressReport
from members.services import pick_best_available_coach

User = get_user_model()


class MemberForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = [
            "full_name",
            "date_of_birth",
            "contact_number",
            "email",
            "emergency_contact_name",
            "emergency_contact_phone",
            "membership_type",
            "skill_level",
            "assigned_coach",
            "parent_user",
            "status",
            "joined_at",
            "notes",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "joined_at": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_user = current_user
        self.fields["assigned_coach"].queryset = User.objects.filter(profile__role=UserProfile.ROLE_COACH).order_by(
            "first_name", "username"
        )
        self.fields["parent_user"].queryset = User.objects.filter(profile__role=UserProfile.ROLE_PARENT).order_by(
            "first_name", "username"
        )
        if current_user and has_role(current_user, ROLE_COACH) and not has_role(current_user, ROLE_ADMIN):
            self.fields["assigned_coach"].queryset = User.objects.filter(pk=current_user.pk)
            self.fields["assigned_coach"].initial = current_user

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.assigned_coach_id:
            instance.assigned_coach = pick_best_available_coach(preferred_level=instance.skill_level)
        if commit:
            instance.save()
        return instance


class AdmissionApplicationPublicForm(forms.ModelForm):
    preferred_program = forms.ChoiceField(choices=(), required=True)
    preferred_location = forms.ChoiceField(choices=(), required=True)

    class Meta:
        model = AdmissionApplication
        fields = [
            "student_name",
            "date_of_birth",
            "guardian_name",
            "guardian_email",
            "contact_number",
            "preferred_program",
            "preferred_location",
            "playing_experience",
            "training_frequency",
            "primary_goal",
            "desired_username",
            "notes",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, program_options=None, location_options=None, **kwargs):
        super().__init__(*args, **kwargs)
        content = LandingPageContent.get_solo()
        programs = program_options or content.available_programs or ["General Training"]
        locations = location_options or content.available_locations or ["Main Hall"]
        self.fields["preferred_program"].choices = [(value, value) for value in programs]
        self.fields["preferred_location"].choices = [(value, value) for value in locations]

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.refresh_recommended_level()
        if commit:
            instance.save()
        return instance


class AdmissionApplicationReviewForm(forms.ModelForm):
    class Meta:
        model = AdmissionApplication
        fields = ["status", "rejection_reason"]
        widgets = {
            "rejection_reason": forms.Textarea(attrs={"rows": 4}),
        }

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get("status")
        rejection_reason = (cleaned_data.get("rejection_reason") or "").strip()
        if status == AdmissionApplication.STATUS_REJECTED and not rejection_reason:
            self.add_error("rejection_reason", "Please explain why this application is being rejected.")
        return cleaned_data


class ProgressReportForm(forms.ModelForm):
    class Meta:
        model = ProgressReport
        fields = [
            "member",
            "coach",
            "period_start",
            "period_end",
            "overall_status",
            "coach_reflection",
            "is_published",
        ]
        widgets = {
            "period_start": forms.DateInput(attrs={"type": "date"}),
            "period_end": forms.DateInput(attrs={"type": "date"}),
            "coach_reflection": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_user = current_user
        member_queryset = Member.objects.select_related("assigned_coach", "parent_user").order_by("full_name")
        coach_queryset = User.objects.filter(profile__role=UserProfile.ROLE_COACH).order_by("first_name", "username")
        if current_user and has_role(current_user, ROLE_COACH) and not has_role(current_user, ROLE_ADMIN):
            member_queryset = member_queryset.filter(assigned_coach=current_user)
            coach_queryset = coach_queryset.filter(pk=current_user.pk)
            self.fields["coach"].initial = current_user
        self.fields["member"].queryset = member_queryset
        self.fields["coach"].queryset = coach_queryset

        for skill in DEFAULT_SKILLS:
            slug = skill.lower().replace(" ", "_")
            self.fields[f"skill_{slug}"] = forms.IntegerField(
                label=f"{skill} rating",
                min_value=0,
                max_value=5,
                required=False,
                widget=forms.NumberInput(attrs={"min": 0, "max": 5}),
            )
            self.fields[f"note_{slug}"] = forms.CharField(
                label=f"{skill} note",
                required=False,
                widget=forms.Textarea(attrs={"rows": 2}),
            )
            if self.instance.pk:
                self.fields[f"skill_{slug}"].initial = self.instance.skill_snapshot.get(skill)
                self.fields[f"note_{slug}"].initial = self.instance.skill_notes.get(skill)

    def clean(self):
        cleaned_data = super().clean()
        period_start = cleaned_data.get("period_start")
        period_end = cleaned_data.get("period_end")
        if period_start and period_end and period_end < period_start:
            self.add_error("period_end", "Period end must be on or after the period start.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.current_user and has_role(self.current_user, ROLE_COACH) and not has_role(self.current_user, ROLE_ADMIN):
            instance.coach = self.current_user
        instance.skill_snapshot = {}
        instance.skill_notes = {}
        for skill in DEFAULT_SKILLS:
            slug = skill.lower().replace(" ", "_")
            rating = self.cleaned_data.get(f"skill_{slug}")
            note = self.cleaned_data.get(f"note_{slug}", "").strip()
            if rating is not None:
                instance.skill_snapshot[skill] = rating
            if note:
                instance.skill_notes[skill] = note
        if instance.member_id and instance.period_start and instance.period_end:
            instance.refresh_metrics()
        if commit:
            instance.save()
        return instance


class MemberLevelForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = ["skill_level"]
