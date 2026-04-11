from datetime import date
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image, ImageDraw

from accounts.models import UserProfile
from accounts.utils import (
    ROLE_ADMIN,
    ROLE_COACH,
    ROLE_HEADCOUNT,
    ROLE_PARENT,
    bootstrap_groups,
)
from finance.models import Invoice
from members.models import Member
from payments.models import Payment, QRCode
from sessions.models import AttendanceRecord, TrainingSession

User = get_user_model()


def month_shift(source_date, delta):
    month_index = source_date.month - 1 + delta
    year = source_date.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def build_image(label, background, foreground):
    image = Image.new("RGB", (420, 420), background)
    draw = ImageDraw.Draw(image)
    step = 40
    for row in range(1, 9):
        for col in range(1, 9):
            if (row + col) % 2 == 0:
                x1 = col * step
                y1 = row * step
                draw.rectangle((x1, y1, x1 + 22, y1 + 22), fill=foreground)
    draw.rectangle((40, 40, 140, 140), outline=foreground, width=8)
    draw.rectangle((280, 40, 380, 140), outline=foreground, width=8)
    draw.rectangle((40, 280, 140, 380), outline=foreground, width=8)
    draw.text((150, 18), label, fill=foreground)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return ContentFile(buffer.getvalue(), name=f"{label.lower().replace(' ', '_')}.png")


class Command(BaseCommand):
    help = "Create demo users, groups, members, sessions, invoices, QR code, and payment records."

    def handle(self, *args, **options):
        bootstrap_groups()
        today = timezone.localdate()
        current_month = today.replace(day=1)
        previous_month = month_shift(current_month, -1)

        admin_user = self.create_user(
            username="admin",
            password="Admin123!",
            role=ROLE_ADMIN,
            email="admin@nyo.local",
            first_name="NYO",
            last_name="Admin",
            is_superuser=True,
        )
        coach_user = self.create_user(
            username="coach",
            password="Coach123!",
            role=ROLE_COACH,
            email="coach@nyo.local",
            first_name="Hafiz",
            last_name="Coach",
        )
        self.create_user(
            username="headcount",
            password="Head123!",
            role=ROLE_HEADCOUNT,
            email="headcount@nyo.local",
            first_name="Mina",
            last_name="Headcount",
        )
        parent_user = self.create_user(
            username="parent",
            password="Parent123!",
            role=ROLE_PARENT,
            email="parent@nyo.local",
            first_name="Sarah",
            last_name="Parent",
        )

        member_one, _ = Member.objects.update_or_create(
            full_name="Alya Tan",
            defaults={
                "date_of_birth": date(2013, 5, 14),
                "contact_number": "012-5551001",
                "email": "alya@example.com",
                "emergency_contact_name": "Sarah Tan",
                "emergency_contact_phone": "012-7771001",
                "membership_type": Member.MEMBERSHIP_MONTHLY,
                "assigned_coach": coach_user,
                "parent_user": parent_user,
                "status": Member.STATUS_ACTIVE,
                "joined_at": previous_month,
                "created_by": admin_user,
                "notes": "Junior singles squad.",
            },
        )
        member_two, _ = Member.objects.update_or_create(
            full_name="Bryan Lee",
            defaults={
                "date_of_birth": date(2012, 11, 3),
                "contact_number": "012-5551002",
                "email": "bryan@example.com",
                "emergency_contact_name": "Sarah Tan",
                "emergency_contact_phone": "012-7771001",
                "membership_type": Member.MEMBERSHIP_YEARLY,
                "assigned_coach": coach_user,
                "parent_user": parent_user,
                "status": Member.STATUS_INACTIVE,
                "joined_at": current_month,
                "created_by": admin_user,
                "notes": "Performance group player.",
            },
        )

        previous_invoice, _ = Invoice.objects.update_or_create(
            member=member_one,
            period=previous_month,
            defaults={
                "amount": "180.00",
                "due_date": previous_month.replace(day=7),
                "status": Invoice.STATUS_PAID,
                "created_by": admin_user,
            },
        )
        current_invoice, _ = Invoice.objects.update_or_create(
            member=member_one,
            period=current_month,
            defaults={
                "amount": "180.00",
                "due_date": current_month.replace(day=7),
                "status": Invoice.STATUS_UNPAID,
                "created_by": coach_user,
            },
        )
        pending_invoice, _ = Invoice.objects.update_or_create(
            member=member_two,
            period=current_month,
            defaults={
                "amount": "220.00",
                "due_date": current_month.replace(day=7),
                "status": Invoice.STATUS_PENDING,
                "created_by": coach_user,
            },
        )

        qr_code, created = QRCode.objects.get_or_create(
            label="Club Current Month QR",
            defaults={
                "uploaded_by": coach_user,
                "payment_period": current_month,
                "is_active": True,
            },
        )
        if created or not qr_code.image:
            qr_code.image.save(
                "club_current_month_qr.png",
                build_image("NYO QR", "white", "black"),
                save=False,
            )
        qr_code.uploaded_by = coach_user
        qr_code.payment_period = current_month
        qr_code.is_active = True
        qr_code.save()

        approved_payment = previous_invoice.payments.filter(status=Payment.STATUS_APPROVED).first()
        if not approved_payment:
            approved_payment = Payment(invoice=previous_invoice, paid_by=parent_user, status=Payment.STATUS_APPROVED)
            approved_payment.proof_image.save(
                "approved_payment_proof.png",
                build_image("PAID", "#0f172a", "#f59e0b"),
                save=False,
            )
        approved_payment.reviewed_by = admin_user
        approved_payment.reviewed_at = timezone.now()
        approved_payment.rejection_reason = ""
        approved_payment.save()

        pending_payment = pending_invoice.payments.filter(status=Payment.STATUS_PENDING).first()
        if not pending_payment:
            pending_payment = Payment(invoice=pending_invoice, paid_by=parent_user, status=Payment.STATUS_PENDING)
            pending_payment.proof_image.save(
                "pending_payment_proof.png",
                build_image("PENDING", "#111827", "#f5a623"),
                save=False,
            )
            pending_payment.save()

        session_one, _ = TrainingSession.objects.update_or_create(
            title="Footwork Fundamentals",
            session_date=previous_month.replace(day=18),
            defaults={
                "start_time": "18:00",
                "end_time": "20:00",
                "court": "Court 1",
                "coach": coach_user,
                "notes": "Split-step and recovery drills.",
                "created_by": admin_user,
            },
        )
        session_two, _ = TrainingSession.objects.update_or_create(
            title="Matchplay Rotation",
            session_date=current_month.replace(day=min(today.day, 12)),
            defaults={
                "start_time": "19:00",
                "end_time": "21:00",
                "court": "Court 2",
                "coach": coach_user,
                "notes": "Singles and doubles tactical rotation.",
                "created_by": coach_user,
            },
        )
        session_three, _ = TrainingSession.objects.update_or_create(
            title="Weekend Conditioning",
            session_date=current_month.replace(day=min(today.day + 3, 25)),
            defaults={
                "start_time": "09:00",
                "end_time": "11:00",
                "court": "Court 3",
                "coach": coach_user,
                "notes": "Speed endurance and multi-shuttle work.",
                "created_by": coach_user,
            },
        )

        self.assign_attendance(session_one, member_one, AttendanceRecord.STATUS_PRESENT, coach_user)
        self.assign_attendance(session_one, member_two, AttendanceRecord.STATUS_LATE, coach_user)
        self.assign_attendance(session_two, member_one, AttendanceRecord.STATUS_PRESENT, coach_user)
        self.assign_attendance(session_two, member_two, AttendanceRecord.STATUS_ABSENT, coach_user)
        self.assign_attendance(session_three, member_one, AttendanceRecord.STATUS_SCHEDULED, None)
        self.assign_attendance(session_three, member_two, AttendanceRecord.STATUS_SCHEDULED, None)

        self.stdout.write(self.style.SUCCESS("NYO Admin Dashboard demo data created."))
        self.stdout.write("Admin: admin / Admin123!")
        self.stdout.write("Coach: coach / Coach123!")
        self.stdout.write("Headcount: headcount / Head123!")
        self.stdout.write("Parent: parent / Parent123!")

    def create_user(self, username, password, role, email, first_name, last_name, is_superuser=False):
        defaults = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "is_superuser": is_superuser,
            "is_staff": is_superuser,
        }
        user, created = User.objects.get_or_create(username=username, defaults=defaults)
        if created:
            user.set_password(password)
        changed = created
        for field, value in defaults.items():
            if getattr(user, field) != value:
                setattr(user, field, value)
                changed = True
        if changed:
            user.save()
        user.profile.role = role
        user.profile.save()
        return user

    def assign_attendance(self, training_session, member, status, marked_by):
        record, _ = AttendanceRecord.objects.get_or_create(training_session=training_session, member=member)
        record.status = status
        record.marked_by = marked_by
        record.marked_at = timezone.now() if marked_by else None
        record.save()
