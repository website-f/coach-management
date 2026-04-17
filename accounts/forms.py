from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm
from django.utils.crypto import get_random_string

from accounts.models import LandingPageContent, UserProfile
from accounts.utils import ROLE_COACH

User = get_user_model()
TEMP_PASSWORD_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"


def apply_dashboard_control_styles(form):
    for field in form.fields.values():
        existing = field.widget.attrs.get("class", "").split()
        if "form-control" not in existing:
            existing.append("form-control")
        field.widget.attrs["class"] = " ".join(item for item in existing if item).strip()


class LandingPageContentForm(forms.ModelForm):
    available_programs_text = forms.CharField(
        label="Available programs",
        required=False,
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text="Enter one program per line.",
    )
    available_locations_text = forms.CharField(
        label="Available locations",
        required=False,
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text="Enter one location per line.",
    )

    class Meta:
        model = LandingPageContent
        fields = [
            "announcement_text",
            "hero_title",
            "hero_subtitle",
            "primary_cta_text",
            "secondary_cta_text",
            "contact_email",
            "instagram_link",
            "tiktok_link",
        ]
        widgets = {
            "hero_subtitle": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_dashboard_control_styles(self)
        self.fields["available_programs_text"].initial = "\n".join(self.instance.available_programs or [])
        self.fields["available_locations_text"].initial = "\n".join(self.instance.available_locations or [])
        self.fields["announcement_text"].widget.attrs.setdefault("placeholder", "Short top-banner announcement")
        self.fields["hero_title"].widget.attrs.setdefault("placeholder", "Headline shown on the landing page")
        self.fields["hero_subtitle"].widget.attrs.setdefault("placeholder", "Short parent-facing description")
        self.fields["contact_email"].widget.attrs.setdefault("placeholder", "support@example.com")
        self.fields["instagram_link"].widget.attrs.setdefault("placeholder", "https://instagram.com/yourclub")
        self.fields["tiktok_link"].widget.attrs.setdefault("placeholder", "https://tiktok.com/@yourclub")

    def clean_available_programs_text(self):
        raw_value = self.cleaned_data.get("available_programs_text", "")
        return [line.strip() for line in raw_value.splitlines() if line.strip()]

    def clean_available_locations_text(self):
        raw_value = self.cleaned_data.get("available_locations_text", "")
        return [line.strip() for line in raw_value.splitlines() if line.strip()]

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.available_programs = self.cleaned_data["available_programs_text"]
        instance.available_locations = self.cleaned_data["available_locations_text"]
        if commit:
            instance.save()
        return instance


class CoachAccountForm(forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    username = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    phone_number = forms.CharField(max_length=30, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_dashboard_control_styles(self)
        self.fields["first_name"].widget.attrs.update({"autocomplete": "given-name", "placeholder": "Coach first name"})
        self.fields["last_name"].widget.attrs.update({"autocomplete": "family-name", "placeholder": "Coach last name"})
        self.fields["username"].widget.attrs.update({"autocomplete": "off", "placeholder": "Login username"})
        self.fields["email"].widget.attrs.update({"autocomplete": "email", "placeholder": "coach@example.com"})
        self.fields["phone_number"].widget.attrs.update({"autocomplete": "tel", "placeholder": "Optional phone number"})

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already in use.")
        return username

    def generate_temporary_password(self):
        return f"NYO-{get_random_string(10, allowed_chars=TEMP_PASSWORD_CHARS)}"

    def save(self):
        temporary_password = self.generate_temporary_password()
        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data.get("email", ""),
            password=temporary_password,
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data.get("last_name", ""),
            is_staff=True,
        )
        profile = user.profile
        profile.role = ROLE_COACH
        profile.phone_number = self.cleaned_data.get("phone_number", "")
        profile.must_change_password = True
        profile.save()
        return user, temporary_password


class CoachPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_dashboard_control_styles(self)
        self.fields["old_password"].widget.attrs.update(
            {"autocomplete": "current-password", "placeholder": "Enter the temporary password from admin"}
        )
        self.fields["new_password1"].widget.attrs.update(
            {"autocomplete": "new-password", "placeholder": "Choose a new private password"}
        )
        self.fields["new_password2"].widget.attrs.update(
            {"autocomplete": "new-password", "placeholder": "Confirm the new password"}
        )
