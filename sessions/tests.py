from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import UserProfile
from finance.models import BillingConfiguration, PaymentPlan
from members.models import Member
from sessions.forms import TrainingSessionForm
from sessions.models import TrainingSession


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
