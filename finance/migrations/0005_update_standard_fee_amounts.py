from decimal import Decimal

from django.db import migrations


REGISTRATION_DESC = "Mandatory registration fee (includes 1 free training jersey)"
MONTHLY_DESC_4 = "Monthly package: RM100 (4 sessions per month)"
MONTHLY_DESC_8 = "Monthly package: RM160 (8 sessions per month)"


def update_standard_fee_amounts(apps, schema_editor):
    Invoice = apps.get_model("finance", "Invoice")

    for invoice in Invoice.objects.select_related("member").all().iterator():
        changed = False

        if invoice.invoice_type == "registration":
            if invoice.amount == Decimal("120.00") or invoice.description in {"", "One-time registration fee"}:
                invoice.amount = Decimal("60.00")
                invoice.description = REGISTRATION_DESC
                changed = True
        elif invoice.invoice_type == "monthly":
            if invoice.amount in {Decimal("180.00"), Decimal("220.00")} or invoice.description in {
                "",
                "Monthly training fee",
                "Initial monthly fee",
            }:
                if invoice.member and invoice.member.membership_type == "monthly_8":
                    invoice.amount = Decimal("160.00")
                    invoice.description = MONTHLY_DESC_8
                else:
                    invoice.amount = Decimal("100.00")
                    invoice.description = MONTHLY_DESC_4
                changed = True

        if changed:
            invoice.save()


class Migration(migrations.Migration):

    dependencies = [
        ("members", "0004_membership_packages"),
        ("finance", "0004_invoice_is_onboarding_fee"),
    ]

    operations = [
        migrations.RunPython(update_standard_fee_amounts, migrations.RunPython.noop),
    ]
