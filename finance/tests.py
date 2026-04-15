from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from finance.models import BillingConfiguration, ExpenseEntry, ForecastScenario, Invoice, PayrollRecord, PaymentPlan
from finance.services import build_finance_snapshot
from members.models import Member
from payments.models import Payment


User = get_user_model()
GIF_BYTES = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00"
    b"\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,"
    b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


class FinanceSnapshotTests(TestCase):
    def create_user(self, username, role):
        user = User.objects.create_user(username=username, password="testpass123")
        user.profile.role = role
        user.profile.save()
        return user

    def setUp(self):
        self.admin = self.create_user("finance_admin", UserProfile.ROLE_ADMIN)
        self.coach = self.create_user("coach_user", UserProfile.ROLE_COACH)
        BillingConfiguration.objects.update_or_create(
            pk=1,
            defaults={
                "registration_fee_name": "Registration Fee",
                "registration_fee_amount": "60.00",
                "trial_session_limit": 1,
                "opening_cash_balance": "500.00",
                "updated_by": self.admin,
            },
        )
        self.plan = PaymentPlan.get_default()

    def create_member(self):
        return Member.objects.create(
            full_name="Aiman Lee",
            date_of_birth="2014-04-20",
            contact_number="0121231234",
            email="aiman@example.com",
            emergency_contact_name="Parent Lee",
            emergency_contact_phone="0121231234",
            status=Member.STATUS_ACTIVE,
            payment_plan=self.plan,
            program_enrolled="Elite Juniors",
            assigned_coach=self.coach,
        )

    def test_finance_pages_render_with_active_students_and_no_variable_expenses(self):
        member = self.create_member()
        self.client.force_login(self.admin)

        response = self.client.get(reverse("finance:overview"))
        self.assertEqual(response.status_code, 200)

        forecast_response = self.client.get(reverse("finance:forecasting"))
        self.assertEqual(forecast_response.status_code, 200)

    def test_build_finance_snapshot_answers_owner_questions(self):
        today = timezone.localdate()
        member = self.create_member()
        invoice = Invoice.objects.create(
            member=member,
            payment_plan=self.plan,
            invoice_type=Invoice.TYPE_MONTHLY,
            description="Monthly fee",
            branch_tag="HQ",
            amount=self.plan.monthly_fee,
            due_date=today + timedelta(days=7),
            period=today.replace(day=1),
            status=Invoice.STATUS_UNPAID,
            created_by=self.admin,
        )
        Payment.objects.create(
            invoice=invoice,
            paid_by=self.admin,
            payment_method="bank_transfer",
            amount_received=self.plan.monthly_fee,
            receipt_reference="TXN-001",
            proof_image=SimpleUploadedFile("proof.gif", GIF_BYTES, content_type="image/gif"),
            status=Payment.STATUS_APPROVED,
            reviewed_by=self.admin,
            reviewed_at=timezone.now(),
        )
        invoice.refresh_status_from_payments()

        ExpenseEntry.objects.create(
            title="Branch rent",
            expense_type=ExpenseEntry.TYPE_FIXED,
            category_tag=ExpenseEntry.CATEGORY_RENT,
            branch_tag="HQ",
            expense_date=today,
            amount="40.00",
            payment_method="bank_transfer",
            created_by=self.admin,
            updated_by=self.admin,
        )
        ExpenseEntry.objects.create(
            title="Transport",
            expense_type=ExpenseEntry.TYPE_VARIABLE,
            category_tag=ExpenseEntry.CATEGORY_TRANSPORT,
            branch_tag="HQ",
            expense_date=today,
            amount="10.00",
            payment_method="cash",
            created_by=self.admin,
            updated_by=self.admin,
        )
        PayrollRecord.objects.create(
            coach=self.coach,
            period=today.replace(day=1),
            branch_tag="HQ",
            base_pay="20.00",
            per_session_rate="0.00",
            session_count=0,
            attendance_adjustment="0.00",
            bonus_amount="0.00",
            deduction_amount="0.00",
            status=PayrollRecord.STATUS_PAID,
            paid_at=today,
            created_by=self.admin,
            updated_by=self.admin,
        )
        scenario = ForecastScenario.objects.create(
            title="Base case",
            average_new_coach_monthly_cost="25.00",
            new_branch_student_count=4,
            new_branch_monthly_overhead="60.00",
            one_time_expansion_cost="100.00",
            risk_buffer_percent="10.00",
            is_primary=True,
            created_by=self.admin,
            updated_by=self.admin,
        )

        snapshot = build_finance_snapshot(today=today, scenario=scenario)

        self.assertEqual(snapshot["revenue_this_month"], self.plan.monthly_fee)
        self.assertEqual(snapshot["total_expenses"], 70)
        self.assertEqual(snapshot["net_profit"], 30)
        self.assertEqual(snapshot["cash_balance"], 530)
        self.assertEqual(snapshot["collection_rate"], 100.0)
        self.assertEqual(snapshot["revenue_by_branch"][0][0], "HQ")
        self.assertEqual(snapshot["revenue_by_program"][0][0], "Elite Juniors")
        self.assertTrue(any(card["question"] == "Are we profitable?" for card in snapshot["answer_cards"]))
        self.assertTrue(any(card["question"] == "Where is money leaking?" for card in snapshot["answer_cards"]))
        self.assertIn("can_hire_more_coach", snapshot["forecast"])
        self.assertIn("can_open_new_branch", snapshot["forecast"])
