from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from finance.models import BillingConfiguration, PaymentPlan
from members.models import Member
from sessions.forms import TrainingSessionForm
from sessions.models import SessionFeedback, SyllabusRoot, TrainingSession
from sessions.services import ensure_default_syllabus


User = get_user_model()


class TrialSessionLimitTests(TestCase):
    def create_user(self, username, role):
        user = User.objects.create_user(username=username, password="testpass123")
        user.profile.role = role
        user.profile.save()
        return user

    def setUp(self):
        self.admin = self.create_user("admin_user", UserProfile.ROLE_ADMIN)
        self.member = Member.objects.create(
            full_name="Trial Student",
            date_of_birth="2016-03-10",
            contact_number="0101112222",
            email="trial@example.com",
            emergency_contact_name="Guardian",
            emergency_contact_phone="0101112222",
            status=Member.STATUS_TRIAL,
            payment_plan=PaymentPlan.get_default(),
        )
        config = BillingConfiguration.get_solo()
        config.trial_session_limit = 1
        config.save(update_fields=["trial_session_limit", "updated_at"])

        existing_session = TrainingSession.objects.create(
            title="Trial Session 1",
            session_date="2026-04-10",
            start_time="09:00",
            end_time="10:00",
            court="Court 1",
        )
        existing_session.attendance_records.create(member=self.member)

    def test_trial_limit_blocks_extra_session_booking(self):
        form = TrainingSessionForm(
            data={
                "title": "Trial Session 2",
                "session_date": "2026-04-17",
                "start_time": "09:00",
                "end_time": "10:00",
                "court": "Court 2",
                "syllabus_root": "",
                "coach": "",
                "notes": "",
                "members": [str(self.member.pk)],
                "schedule_mode": TrainingSessionForm.SCHEDULE_MODE_ONE_TIME,
            },
            current_user=self.admin,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Trial limit exceeded", form.errors["members"][0])


class SyllabusPageTests(TestCase):
    def create_user(self, username, role):
        user = User.objects.create_user(username=username, password="testpass123")
        user.profile.role = role
        user.profile.save()
        return user

    def setUp(self):
        self.admin = self.create_user("syllabus_admin", UserProfile.ROLE_ADMIN)
        self.client.force_login(self.admin)

    def test_syllabus_page_does_not_auto_open_first_root(self):
        response = self.client.get(reverse("sessions:syllabus"))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["selected_root"])
        self.assertContains(response, "Choose a syllabus root above")
        self.assertTrue(SyllabusRoot.objects.exists())

    def test_syllabus_page_opens_details_when_root_selected(self):
        root = SyllabusRoot.objects.create(
            name="Holiday Camp Curriculum",
            code="holiday_camp_curriculum",
            description="Short-format holiday programme.",
            updated_by=self.admin,
        )

        response = self.client.get(reverse("sessions:syllabus"), {"root": root.pk})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_root"].pk, root.pk)
        self.assertContains(response, "Holiday Camp Curriculum")


class SessionCalendarPageTests(TestCase):
    def create_user(self, username, role):
        user = User.objects.create_user(username=username, password="testpass123")
        user.profile.role = role
        user.profile.save()
        return user

    def setUp(self):
        self.admin = self.create_user("calendar_admin", UserProfile.ROLE_ADMIN)
        self.client.force_login(self.admin)

    def test_session_calendar_uses_working_fullcalendar_asset_loader(self):
        response = self.client.get(reverse("sessions:list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "index.global.min.js")
        self.assertNotContains(response, "index.global.min.css")
        self.assertContains(response, "Loading calendar...")


class CoachSessionChecklistPageTests(TestCase):
    def create_user(self, username, role):
        user = User.objects.create_user(username=username, password="testpass123")
        user.profile.role = role
        user.profile.save()
        return user

    def setUp(self):
        ensure_default_syllabus()
        self.coach = self.create_user("coach_schedule", UserProfile.ROLE_COACH)
        self.client.force_login(self.coach)
        syllabus_root = SyllabusRoot.get_default()
        self.member = Member.objects.create(
            full_name="Alya Training",
            date_of_birth="2014-05-12",
            contact_number="0101234567",
            email="alya@example.com",
            emergency_contact_name="Parent",
            emergency_contact_phone="0101234567",
            status=Member.STATUS_ACTIVE,
            skill_level=Member.LEVEL_INTERMEDIATE,
            payment_plan=PaymentPlan.get_default(),
            assigned_coach=self.coach,
            syllabus_root=syllabus_root,
        )
        self.session = TrainingSession.objects.create(
            title="Intermediate Squad B",
            session_date=timezone.localdate(),
            start_time="09:00",
            end_time="10:30",
            court="Court 2",
            coach=self.coach,
            syllabus_root=syllabus_root,
        )
        self.session.attendance_records.create(member=self.member)

    def test_coach_session_page_defaults_to_checklist_first(self):
        response = self.client.get(reverse("sessions:list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["session_page_mode"], "checklist")
        self.assertTrue(response.context["show_checklist_view"])
        self.assertFalse(response.context["show_calendar_view"])
        self.assertContains(response, "Checklist First")
        self.assertContains(response, "Training Checklist")
        self.assertContains(response, "Open Calendar")
        self.assertNotContains(response, "Loading calendar...")
        self.assertNotContains(response, "index.global.min.js")

    def test_coach_can_switch_back_to_calendar_view(self):
        response = self.client.get(reverse("sessions:list"), {"view": "calendar"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["session_page_mode"], "calendar")
        self.assertFalse(response.context["show_checklist_view"])
        self.assertTrue(response.context["show_calendar_view"])
        self.assertContains(response, "Loading calendar...")
        self.assertContains(response, "index.global.min.js")


class SessionFeedbackFlowTests(TestCase):
    def create_user(self, username, role):
        user = User.objects.create_user(username=username, password="testpass123")
        user.profile.role = role
        user.profile.save()
        return user

    def setUp(self):
        ensure_default_syllabus()
        self.coach = self.create_user("coach_feedback", UserProfile.ROLE_COACH)
        self.client.force_login(self.coach)
        syllabus_root = SyllabusRoot.get_default()
        self.member_one = Member.objects.create(
            full_name="Alya Focus",
            date_of_birth="2014-05-12",
            contact_number="0102003001",
            email="alya-focus@example.com",
            emergency_contact_name="Parent One",
            emergency_contact_phone="0102003001",
            status=Member.STATUS_ACTIVE,
            payment_plan=PaymentPlan.get_default(),
            assigned_coach=self.coach,
            syllabus_root=syllabus_root,
        )
        self.member_two = Member.objects.create(
            full_name="Zayan Finish",
            date_of_birth="2013-04-08",
            contact_number="0102003002",
            email="zayan-finish@example.com",
            emergency_contact_name="Parent Two",
            emergency_contact_phone="0102003002",
            status=Member.STATUS_ACTIVE,
            payment_plan=PaymentPlan.get_default(),
            assigned_coach=self.coach,
            syllabus_root=syllabus_root,
        )
        self.session = TrainingSession.objects.create(
            title="Coach Feedback Session",
            session_date=timezone.localdate(),
            start_time="09:00",
            end_time="10:30",
            court="Court 4",
            coach=self.coach,
            syllabus_root=syllabus_root,
        )
        self.session.attendance_records.create(member=self.member_one)
        self.session.attendance_records.create(member=self.member_two)

    def test_session_detail_highlights_first_pending_feedback_action(self):
        SessionFeedback.objects.create(
            training_session=self.session,
            member=self.member_two,
            coach=self.coach,
            feedback_text="Strong match focus and better recovery to base.",
        )

        response = self.client.get(reverse("sessions:detail", kwargs={"pk": self.session.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["feedback_is_open"])
        self.assertEqual(response.context["feedback_pending_count"], 1)
        self.assertEqual(response.context["next_feedback_member"], self.member_one)
        self.assertContains(response, f"Start With {self.member_one.full_name}")
        self.assertContains(response, "Coach Action List")

    def test_save_and_next_redirects_to_next_pending_student(self):
        response = self.client.post(
            reverse("sessions:feedback", kwargs={"session_pk": self.session.pk, "member_pk": self.member_one.pk}),
            {
                "feedback_text": "Sharper footwork today and better patience in rallies.",
                "save_and_next": "1",
            },
        )

        self.assertRedirects(
            response,
            reverse("sessions:feedback", kwargs={"session_pk": self.session.pk, "member_pk": self.member_two.pk}),
        )
        self.assertEqual(SessionFeedback.objects.filter(training_session=self.session).count(), 1)

    def test_future_session_detail_shows_feedback_lock_message(self):
        future_session = TrainingSession.objects.create(
            title="Future Coach Feedback Session",
            session_date=timezone.localdate() + timedelta(days=2),
            start_time="11:00",
            end_time="12:30",
            court="Court 5",
            coach=self.coach,
            syllabus_root=self.session.syllabus_root,
        )
        future_session.attendance_records.create(member=self.member_one)

        response = self.client.get(reverse("sessions:detail", kwargs={"pk": future_session.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["feedback_is_open"])
        self.assertContains(response, "Feedback Opens On")
        self.assertContains(response, "Available On")
