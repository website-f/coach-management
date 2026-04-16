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


class ParentPortalTests(TestCase):
    def create_user(self, username, role, email=""):
        user = User.objects.create_user(username=username, password="testpass123", email=email)
        user.profile.role = role
        user.profile.save()
        return user

    def setUp(self):
        self.parent = self.create_user("parent_user", UserProfile.ROLE_PARENT, "parent@example.com")
        self.other_parent = self.create_user("other_parent", UserProfile.ROLE_PARENT, "other@example.com")
        self.coach = self.create_user("coach_user", UserProfile.ROLE_COACH, "coach@example.com")
        self.child = Member.objects.create(
            full_name="Aina Parent",
            date_of_birth="2014-05-10",
            contact_number="0123000001",
            email="aina@example.com",
            emergency_contact_name="Parent User",
            emergency_contact_phone="0123000001",
            parent_user=self.parent,
            assigned_coach=self.coach,
            status=Member.STATUS_ACTIVE,
            program_enrolled="Junior Development",
        )
        self.other_child = Member.objects.create(
            full_name="Other Family Child",
            date_of_birth="2013-03-03",
            contact_number="0123000002",
            email="otherchild@example.com",
            emergency_contact_name="Other Parent",
            emergency_contact_phone="0123000002",
            parent_user=self.other_parent,
            assigned_coach=self.coach,
            status=Member.STATUS_ACTIVE,
            program_enrolled="Performance Squad",
        )

    def test_parent_member_list_only_shows_their_children(self):
        self.client.force_login(self.parent)

        response = self.client.get(reverse("members:list"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_parent_view"])
        self.assertEqual(list(response.context["members"]), [self.child])
        self.assertContains(response, "My Children")
        self.assertContains(response, "Add Child")
        self.assertNotContains(response, self.other_child.full_name)

    def test_parent_cannot_open_other_parent_child_detail(self):
        self.client.force_login(self.parent)

        response = self.client.get(reverse("members:detail", args=[self.other_child.pk]))

        self.assertEqual(response.status_code, 404)

    def test_parent_add_child_application_links_to_parent_account(self):
        self.client.force_login(self.parent)

        response = self.client.post(
            reverse("members:apply"),
            data={
                "student_name": "New Child Request",
                "date_of_birth": "2015-09-09",
                "guardian_name": "Parent User",
                "guardian_email": "parent@example.com",
                "contact_number": "0123000001",
                "source": AdmissionApplication.SOURCE_WEBSITE,
                "preferred_program": "Junior Development",
                "preferred_location": "Court 1",
                "playing_experience": AdmissionApplication.EXPERIENCE_NONE,
                "training_frequency": AdmissionApplication.TRAINING_OCCASIONAL,
                "primary_goal": AdmissionApplication.GOAL_FUNDAMENTALS,
                "desired_username": "parent_user",
                "notes": "Prefers weekend classes.",
            },
        )

        self.assertRedirects(response, reverse("members:list") + "?application_submitted=1")
        application = AdmissionApplication.objects.get(student_name="New Child Request")
        self.assertEqual(application.linked_parent_user, self.parent)


class ParentRegistrationTests(TestCase):
    def test_public_apply_page_is_parent_registration_first(self):
        response = self.client.get(reverse("members:apply"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/parent_register.html")
        self.assertContains(response, "Create your parent account first")
        self.assertContains(response, "Create Parent Account")

    def test_public_parent_registration_creates_parent_user_and_logs_in(self):
        response = self.client.post(
            reverse("members:apply"),
            data={
                "first_name": "Maya",
                "last_name": "Lee",
                "email": "maya@example.com",
                "phone_number": "0123000099",
                "username": "maya.parent",
                "password1": "StrongParent123!",
                "password2": "StrongParent123!",
            },
        )

        self.assertRedirects(response, reverse("members:list"))
        parent = User.objects.get(username="maya.parent")
        self.assertEqual(parent.profile.role, UserProfile.ROLE_PARENT)
        self.assertEqual(parent.profile.phone_number, "0123000099")

        member_list_response = self.client.get(reverse("members:list"))
        self.assertEqual(member_list_response.status_code, 200)
        self.assertTrue(member_list_response.context["is_parent_view"])
        self.assertContains(member_list_response, "Add Child")
