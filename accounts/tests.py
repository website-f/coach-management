from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile

User = get_user_model()


class CoachAccountManagementTests(TestCase):
    def create_user(self, username, role, password="testpass123", **extra_fields):
        user = User.objects.create_user(username=username, password=password, **extra_fields)
        user.profile.role = role
        user.profile.save()
        return user

    def test_admin_can_create_coach_with_temporary_password_requirement(self):
        admin = self.create_user("admin_user", UserProfile.ROLE_ADMIN)
        self.client.force_login(admin)

        response = self.client.post(
            reverse("accounts:coaches"),
            {
                "first_name": "Aiman",
                "last_name": "Coach",
                "username": "aiman_coach",
                "email": "aiman@example.com",
                "phone_number": "0123456789",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("accounts:coaches"))
        coach = User.objects.get(username="aiman_coach")
        self.assertEqual(coach.profile.role, UserProfile.ROLE_COACH)
        self.assertTrue(coach.profile.must_change_password)
        created_credentials = self.client.session.get("created_coach_credentials")
        self.assertIsNotNone(created_credentials)
        self.assertEqual(created_credentials["username"], "aiman_coach")
        self.assertTrue(coach.check_password(created_credentials["temporary_password"]))

    def test_flagged_coach_login_redirects_to_password_change(self):
        coach = self.create_user("coach_temp", UserProfile.ROLE_COACH, password="TempPass123!")
        coach.profile.must_change_password = True
        coach.profile.save(update_fields=["must_change_password", "updated_at"])

        response = self.client.post(
            reverse("accounts:login"),
            {"username": "coach_temp", "password": "TempPass123!"},
        )

        self.assertRedirects(response, reverse("accounts:password_change"))

    def test_password_change_clears_required_flag(self):
        coach = self.create_user("coach_reset", UserProfile.ROLE_COACH, password="TempPass123!")
        coach.profile.must_change_password = True
        coach.profile.save(update_fields=["must_change_password", "updated_at"])
        self.client.force_login(coach)

        response = self.client.post(
            reverse("accounts:password_change"),
            {
                "old_password": "TempPass123!",
                "new_password1": "CoachStrongPass456!",
                "new_password2": "CoachStrongPass456!",
            },
        )

        self.assertRedirects(response, reverse("accounts:dashboard"))
        coach.refresh_from_db()
        self.assertFalse(coach.profile.must_change_password)

    def test_password_change_middleware_redirects_flagged_coach(self):
        coach = self.create_user("coach_blocked", UserProfile.ROLE_COACH, password="TempPass123!")
        coach.profile.must_change_password = True
        coach.profile.save(update_fields=["must_change_password", "updated_at"])
        self.client.force_login(coach)

        response = self.client.get(reverse("accounts:dashboard"))

        self.assertRedirects(response, f"{reverse('accounts:password_change')}?required=1")

    def test_admin_can_open_coach_detail_page(self):
        admin = self.create_user("admin_profile", UserProfile.ROLE_ADMIN)
        coach = self.create_user(
            "coach_profile",
            UserProfile.ROLE_COACH,
            first_name="Nadia",
            last_name="Lim",
            email="nadia@example.com",
        )
        coach.profile.phone_number = "0112233445"
        coach.profile.save(update_fields=["phone_number", "updated_at"])
        self.client.force_login(admin)

        response = self.client.get(reverse("accounts:coach_detail", args=[coach.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nadia Lim")
        self.assertContains(response, "Assigned Players")
