from django.conf import settings
from django.utils import timezone

from finance.models import Invoice


def create_initial_invoices_for_member(member, created_by=None):
    if not member:
        return []

    today = timezone.localdate()
    billing_period = today.replace(day=1)
    created_invoices = []

    registration_invoice, registration_created = Invoice.objects.get_or_create(
        member=member,
        period=billing_period,
        invoice_type=Invoice.TYPE_REGISTRATION,
        defaults={
            "description": "One-time registration fee",
            "is_onboarding_fee": True,
            "amount": settings.DEFAULT_REGISTRATION_FEE,
            "due_date": today,
            "created_by": created_by,
            "status": Invoice.STATUS_UNPAID,
        },
    )
    if registration_created:
        created_invoices.append(registration_invoice)

    monthly_invoice, monthly_created = Invoice.objects.get_or_create(
        member=member,
        period=billing_period,
        invoice_type=Invoice.TYPE_MONTHLY,
        defaults={
            "description": "Initial monthly fee",
            "is_onboarding_fee": True,
            "amount": settings.DEFAULT_MONTHLY_FEE,
            "due_date": today,
            "created_by": created_by,
            "status": Invoice.STATUS_UNPAID,
        },
    )
    if monthly_created:
        created_invoices.append(monthly_invoice)

    return created_invoices
