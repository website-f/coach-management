from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from members.models import AdmissionApplication, CommunicationLog, Member


User = get_user_model()


class CRMFlowTests(TestCase):
    def create_user(self, username, role, email=""):
        user = User.objects.create_user(username=username, password="testpass123", email=email)
        user.profile.role = role
        user.profile.save()
        return user

    def setUp(self):
        self.admin = self.create_user("admin_user", UserProfile.ROLE_ADMIN, "admin@example.com")
        self.coach = self.create_user("coach_user", UserProfile.ROLE_COACH, "coach@example.com")
        self.client.force_login(self.admin)

    def test_approving_lead_creates_trial_member_profile(self):
        application = AdmissionApplication.objects.create(
            student_name="Aina Lee",
            guardian_name="Maya Lee",
            guardian_email="maya@example.com",
            contact_number="0123456789",
            preferred_program="Junior Development",
            preferred_location="Court 1",
            source=AdmissionApplication.SOURCE_REFERRAL,
            interest_level=AdmissionApplication.INTEREST_HOT,
        )

        response = self.client.post(
            reverse("members:application_review", args=[application.pk]),
            data={
                "source": application.source,
                "interest_level": application.interest_level,
                "assigned_staff": self.admin.pk,
                "last_followed_up_at": "",
                "next_action": "Schedule the first trial and send WhatsApp confirmation.",
                "status": AdmissionApplication.STATUS_APPROVED,
                "rejection_reason": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        application.refresh_from_db()
        self.assertIsNotNone(application.linked_member)

        linked_member = application.linked_member
        self.assertEqual(linked_member.status, Member.STATUS_TRIAL)
        self.assertEqual(linked_member.program_enrolled, "Junior Development")
        self.assertEqual(linked_member.assigned_staff, self.admin)
        self.assertIsNotNone(linked_member.syllabus_root)
        self.assertEqual(linked_member.invoices.count(), 2)
        self.assertTrue(
            CommunicationLog.objects.filter(
                lead=application,
                member=linked_member,
                outcome__icontains="moved into trial stage",
            ).exists()
        )

    def test_member_detail_context_answers_crm_questions(self):
        member = Member.objects.create(
            full_name="Danish Lim",
            date_of_birth="2014-01-15",
            contact_number="0191234567",
            email="parent@example.com",
            emergency_contact_name="Sara Lim",
            emergency_contact_phone="0191234567",
            status=Member.STATUS_CHURNED,
            conversion_reason="Coach feedback was strong and the class fit the family schedule.",
            churn_reason="Paused because of school exams.",
            next_action="Check back in after the exam period.",
            created_by=self.admin,
        )
        application = AdmissionApplication.objects.create(
            student_name=member.full_name,
            guardian_name="Sara Lim",
            guardian_email="parent@example.com",
            contact_number=member.contact_number,
            preferred_program="Competitive Squad",
            preferred_location="Court 2",
            source=AdmissionApplication.SOURCE_REFERRAL,
            interest_level=AdmissionApplication.INTEREST_WARM,
            linked_member=member,
            assigned_staff=self.admin,
            next_action="Check back in after the exam period.",
            status=AdmissionApplication.STATUS_APPROVED,
        )
        CommunicationLog.objects.create(
            lead=application,
            member=member,
            staff=self.admin,
            outcome="Called parent to discuss pause and reactivation timing.",
            next_step="Check back in after the exam period.",
        )

        response = self.client.get(reverse("members:detail", args=[member.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["lead_source_label"], "Referral")
        self.assertEqual(
            response.context["why_stayed"],
            "Coach feedback was strong and the class fit the family schedule.",
        )
        self.assertEqual(response.context["why_left"], "Paused because of school exams.")
        self.assertEqual(response.context["what_next"], "Check back in after the exam period.")
        self.assertEqual(response.context["communication_logs"][0].staff, self.admin)
