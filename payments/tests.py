from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from finance.models import Invoice, PaymentPlan
from members.models import CommunicationLog, Member
from payments.models import Payment


User = get_user_model()
GIF_BYTES = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00"
    b"\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,"
    b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


class PaymentReviewTests(TestCase):
    def create_user(self, username, role, email=""):
        user = User.objects.create_user(username=username, password="testpass123", email=email)
        user.profile.role = role
        user.profile.save()
        return user

    def create_member(self, status=Member.STATUS_TRIAL, parent_user=None):
        return Member.objects.create(
            full_name="Hana Noor",
            date_of_birth="2015-05-20",
            contact_number="0112233445",
            email="hana@example.com",
            emergency_contact_name="Noor",
            emergency_contact_phone="0112233445",
            status=status,
            payment_plan=PaymentPlan.get_default(),
            parent_user=parent_user,
        )

    def create_payment(self, member, invoice_type, paid_by):
        today = timezone.localdate()
        invoice = Invoice.objects.create(
            member=member,
            payment_plan=member.payment_plan,
            invoice_type=invoice_type,
            description="Test invoice",
            amount=member.payment_plan.monthly_fee,
            due_date=today + timedelta(days=7),
            period=today.replace(day=1),
            status=Invoice.STATUS_PENDING,
        )
        payment = Payment.objects.create(
            invoice=invoice,
            paid_by=paid_by,
            proof_image=SimpleUploadedFile("proof.gif", GIF_BYTES, content_type="image/gif"),
            status=Payment.STATUS_PENDING,
        )
        return payment, invoice

    def setUp(self):
        self.admin = self.create_user("admin_user", UserProfile.ROLE_ADMIN, "admin@example.com")
        self.parent = self.create_user("parent_user", UserProfile.ROLE_PARENT, "parent@example.com")
        self.client.force_login(self.admin)

    def test_approving_registration_payment_keeps_student_in_trial(self):
        member = self.create_member(parent_user=self.parent)
        payment, invoice = self.create_payment(member, Invoice.TYPE_REGISTRATION, self.parent)

        response = self.client.post(
            reverse("payments:review", args=[payment.pk]),
            data={"action": "approve"},
        )

        self.assertEqual(response.status_code, 302)
        member.refresh_from_db()
        payment.refresh_from_db()
        invoice.refresh_from_db()

        self.assertEqual(member.status, Member.STATUS_TRIAL)
        self.assertEqual(payment.status, Payment.STATUS_APPROVED)
        self.assertEqual(invoice.status, Invoice.STATUS_PAID)
        self.assertTrue(
            CommunicationLog.objects.filter(
                member=member,
                outcome__icontains="Payment approved",
            ).exists()
        )

    def test_approving_monthly_payment_converts_trial_to_active(self):
        member = self.create_member(parent_user=self.parent)
        payment, invoice = self.create_payment(member, Invoice.TYPE_MONTHLY, self.parent)

        response = self.client.post(
            reverse("payments:review", args=[payment.pk]),
            data={"action": "approve"},
        )

        self.assertEqual(response.status_code, 302)
        member.refresh_from_db()
        payment.refresh_from_db()
        invoice.refresh_from_db()

        self.assertEqual(member.status, Member.STATUS_ACTIVE)
        self.assertEqual(member.subscription_started_at, timezone.localdate())
        self.assertEqual(member.trial_outcome, Member.TRIAL_OUTCOME_CONVERTED)
        self.assertEqual(payment.status, Payment.STATUS_APPROVED)
        self.assertEqual(invoice.status, Invoice.STATUS_PAID)

    def test_approving_partial_monthly_payment_keeps_student_in_trial(self):
        member = self.create_member(parent_user=self.parent)
        payment, invoice = self.create_payment(member, Invoice.TYPE_MONTHLY, self.parent)
        payment.amount_received = member.payment_plan.monthly_fee / 2
        payment.save(update_fields=["amount_received"])

        response = self.client.post(
            reverse("payments:review", args=[payment.pk]),
            data={"action": "approve"},
        )

        self.assertEqual(response.status_code, 302)
        member.refresh_from_db()
        payment.refresh_from_db()
        invoice.refresh_from_db()

        self.assertEqual(member.status, Member.STATUS_TRIAL)
        self.assertIsNone(member.subscription_started_at)
        self.assertEqual(payment.status, Payment.STATUS_APPROVED)
        self.assertEqual(invoice.status, Invoice.STATUS_PARTIAL)
