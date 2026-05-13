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


class SessionRosterPersistenceTests(TestCase):
    """Lock the bug we fixed: when admin saves a session with members picked,
    the roster must end up in attendance_records, otherwise the coach opens
    the session and sees "No players assigned yet"."""

    def setUp(self):
        self.admin = User.objects.create_user(username="admin_qa", password="x")
        self.admin.profile.role = UserProfile.ROLE_ADMIN
        self.admin.profile.save()

        self.coach = User.objects.create_user(username="coach_qa", password="x")
        self.coach.profile.role = UserProfile.ROLE_COACH
        self.coach.profile.save()

        self.members = [
            Member.objects.create(
                full_name=f"Player {i}",
                date_of_birth="2015-01-01",
                contact_number="0123",
                emergency_contact_name="Guardian",
                emergency_contact_phone="0123",
                status=Member.STATUS_ACTIVE,
                skill_level=Member.LEVEL_BASIC,
                payment_plan=PaymentPlan.get_default(),
            )
            for i in range(3)
        ]
        ensure_default_syllabus()

    def _post_body(self, members):
        return {
            "title": "Kelas QA",
            "session_date": "2026-05-20",
            "start_time": "10:00",
            "end_time": "11:30",
            "court": "Court 1",
            "syllabus_root": str(SyllabusRoot.get_default().pk),
            "notes": "",
            "members": [str(m.pk) for m in members],
            "coaches": [str(self.coach.pk)],
            "schedule_mode": TrainingSessionForm.SCHEDULE_MODE_ONE_TIME,
        }

    def test_create_session_with_members_persists_roster(self):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse("sessions:create"), self._post_body(self.members))
        # 302 redirect on success, 200 means form errors
        self.assertEqual(resp.status_code, 302, msg=getattr(resp, "context", {}).get("form").errors if resp.status_code == 200 else "")
        session = TrainingSession.objects.get(title="Kelas QA")
        roster_ids = set(session.attendance_records.values_list("member_id", flat=True))
        self.assertEqual(roster_ids, {m.pk for m in self.members})

    def test_edit_session_repick_members_persists_roster(self):
        # Create the session with no members first, then re-edit and attach all three.
        session = TrainingSession.objects.create(
            title="Kelas QA",
            session_date="2026-05-20",
            start_time="10:00",
            end_time="11:30",
            court="Court 1",
            coach=self.coach,
        )
        self.assertEqual(session.attendance_records.count(), 0)

        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse("sessions:edit", kwargs={"pk": session.pk}),
            self._post_body(self.members),
        )
        self.assertEqual(resp.status_code, 302)
        session.refresh_from_db()
        roster_ids = set(session.attendance_records.values_list("member_id", flat=True))
        self.assertEqual(roster_ids, {m.pk for m in self.members})

    def test_attendance_form_lists_members_in_both_desktop_and_mobile_blocks(self):
        """Regression: zip() in the view exhausts after the first {% for %}
        loop in the template, so the mobile cards block silently fell back to
        the empty state ("No players assigned yet") even when the roster was
        populated. The fix is to materialise the zip into a list."""
        session = TrainingSession.objects.create(
            title="Kelas QA",
            session_date="2026-05-20",
            start_time="10:00",
            end_time="11:30",
            court="Court 1",
            coach=self.coach,
        )
        for m in self.members:
            session.attendance_records.create(member=m)

        self.client.force_login(self.coach)
        resp = self.client.get(reverse("sessions:attendance", kwargs={"pk": session.pk}))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()

        # Each player name should appear at least TWICE in the rendered HTML —
        # once in the desktop <table> and once in the mobile card list. If the
        # iterator was exhausted by the first loop, the second copy would be
        # missing.
        for m in self.members:
            self.assertGreaterEqual(
                body.count(m.full_name),
                2,
                f"{m.full_name} appears < 2x — mobile block likely empty (zip iterator exhausted).",
            )
        # And the empty-state must NOT render when the roster is populated.
        self.assertNotIn("No players assigned yet", body)

    def test_create_session_without_members_shows_warning(self):
        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse("sessions:create"),
            self._post_body([]),
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        # Warning toast text from SessionCreateView.form_valid
        self.assertContains(resp, "without any assigned students")


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
        self.assertContains(response, "Write Report")

    def test_feedback_form_uses_radar_evaluation_workspace(self):
        response = self.client.get(
            reverse("sessions:feedback", kwargs={"session_pk": self.session.pk, "member_pk": self.member_one.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Session Report Form")
        self.assertContains(response, "evaluationRadarChart")
        self.assertContains(response, "report-slider-input")
        self.assertContains(response, "Save Session Report")

    def test_save_and_next_redirects_to_next_pending_student_and_saves_skill_snapshot(self):
        response = self.client.post(
            reverse("sessions:feedback", kwargs={"session_pk": self.session.pk, "member_pk": self.member_one.pk}),
            {
                "feedback_text": "Sharper footwork today and better patience in rallies.",
                "skill_service": "70",
                "note_service": "Cleaner contact and better control under pressure.",
                "skill_lobbing": "60",
                "skill_smashing": "75",
                "skill_drop_shot": "55",
                "skill_netting": "65",
                "skill_footwork": "80",
                "skill_defense": "50",
                "save_and_next": "1",
            },
        )

        self.assertRedirects(
            response,
            reverse("sessions:feedback", kwargs={"session_pk": self.session.pk, "member_pk": self.member_two.pk}),
        )
        report = SessionFeedback.objects.get(training_session=self.session, member=self.member_one)
        self.assertAlmostEqual(report.skill_snapshot["Service"], 3.5)
        self.assertAlmostEqual(report.skill_snapshot["Footwork"], 4.0)
        self.assertEqual(report.skill_notes["Service"], "Cleaner contact and better control under pressure.")

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
        self.assertContains(response, "Report Opens On")
        self.assertContains(response, "Available On")
