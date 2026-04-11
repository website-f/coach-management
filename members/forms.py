from django import forms
from django.contrib.auth import get_user_model

from accounts.models import UserProfile
from accounts.utils import ROLE_ADMIN, ROLE_COACH, has_role
from members.models import Member

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
        self.fields["assigned_coach"].queryset = User.objects.filter(profile__role=UserProfile.ROLE_COACH).order_by(
            "first_name", "username"
        )
        self.fields["parent_user"].queryset = User.objects.filter(profile__role=UserProfile.ROLE_PARENT).order_by(
            "first_name", "username"
        )
        if current_user and has_role(current_user, ROLE_COACH) and not has_role(current_user, ROLE_ADMIN):
            self.fields["assigned_coach"].queryset = User.objects.filter(pk=current_user.pk)
            self.fields["assigned_coach"].initial = current_user
