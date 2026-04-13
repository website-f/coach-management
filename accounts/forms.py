from django import forms
from django.contrib.auth import get_user_model

from accounts.models import LandingPageContent, UserProfile
from accounts.utils import ROLE_COACH

User = get_user_model()


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
        self.fields["available_programs_text"].initial = "\n".join(self.instance.available_programs or [])
        self.fields["available_locations_text"].initial = "\n".join(self.instance.available_locations or [])

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
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm password")

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("This username is already in use.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Passwords do not match.")
        return cleaned_data

    def save(self):
        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data.get("email", ""),
            password=self.cleaned_data["password1"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data.get("last_name", ""),
            is_staff=True,
        )
        profile = user.profile
        profile.role = ROLE_COACH
        profile.phone_number = self.cleaned_data.get("phone_number", "")
        profile.save()
        return user
