from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from finance.models import BillingConfiguration, Invoice, PaymentPlan, format_ringgit


def get_billing_configuration():
    config = BillingConfiguration.get_solo()
    if not config.registration_fee_amount:
        config.registration_fee_amount = Decimal(getattr(settings, "DEFAULT_REGISTRATION_FEE", "60.00"))
    return config


def get_active_payment_plans(include_inactive=False):
    PaymentPlan.ensure_seeded()
    queryset = PaymentPlan.objects.order_by("sort_order", "sessions_per_month", "monthly_fee", "name")
    if include_inactive:
        return queryset
    return queryset.filter(is_active=True)


def get_default_payment_plan(include_inactive=False):
    return PaymentPlan.get_default(active_only=not include_inactive)


def resolve_member_payment_plan(member):
    if member and getattr(member, "payment_plan_id", None):
        return member.payment_plan
    if member and getattr(member, "membership_type", ""):
        matched_plan = PaymentPlan.objects.filter(code=member.membership_type).first()
        if matched_plan:
            return matched_plan
    return get_default_payment_plan()


def registration_fee_description():
    return get_billing_configuration().registration_invoice_description


def registration_fee_amount():
    return get_billing_configuration().registration_fee_amount


def monthly_package_amount_for_member(member):
    payment_plan = resolve_member_payment_plan(member)
    if payment_plan:
        return payment_plan.monthly_fee
    return Decimal(getattr(settings, "DEFAULT_MONTHLY_FEE", "100.00"))


def monthly_package_description_for_member(member):
    payment_plan = resolve_member_payment_plan(member)
    if payment_plan:
        return payment_plan.invoice_description
    return "Monthly package fee"


def registration_fee_summary(config=None):
    config = config or get_billing_configuration()
    return config.registration_summary


def payment_plan_summary_text(plans=None):
    plan_rows = list(plans if plans is not None else get_active_payment_plans())
    if not plan_rows:
        return "custom monthly packages managed by the admin team"

    phrases = [
        f"{format_ringgit(plan.monthly_fee)} for {plan.sessions_per_month} sessions per month"
        for plan in plan_rows
    ]
    if len(phrases) == 1:
        return phrases[0]
    if len(phrases) == 2:
        return f"{phrases[0]} or {phrases[1]}"
    return f"{', '.join(phrases[:-1])}, or {phrases[-1]}"


def billing_overview_text(config=None, plans=None):
    config = config or get_billing_configuration()
    plan_summary = payment_plan_summary_text(plans)
    return f"{registration_fee_summary(config)}, plus monthly packages of {plan_summary}."


def billing_context_data():
    config = get_billing_configuration()
    plans = list(get_active_payment_plans())
    return {
        "billing_configuration": config,
        "billing_plans": plans,
        "registration_fee_summary": registration_fee_summary(config),
        "billing_plan_summary": payment_plan_summary_text(plans),
        "billing_overview_text": billing_overview_text(config, plans),
    }


def create_initial_invoices_for_member(member, created_by=None):
    if not member:
        return []

    payment_plan = resolve_member_payment_plan(member)
    today = timezone.localdate()
    billing_period = today.replace(day=1)
    created_invoices = []

    registration_invoice, registration_created = Invoice.objects.get_or_create(
        member=member,
        period=billing_period,
        invoice_type=Invoice.TYPE_REGISTRATION,
        defaults={
            "description": registration_fee_description(),
            "is_onboarding_fee": True,
            "amount": registration_fee_amount(),
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
            "payment_plan": payment_plan,
            "description": monthly_package_description_for_member(member),
            "is_onboarding_fee": True,
            "amount": monthly_package_amount_for_member(member),
            "due_date": today,
            "created_by": created_by,
            "status": Invoice.STATUS_UNPAID,
        },
    )
    if monthly_created:
        created_invoices.append(monthly_invoice)

    return created_invoices
