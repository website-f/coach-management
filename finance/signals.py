from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from finance.models import ExpenseEntry, FinanceAuditLog, ForecastScenario, HistoricalLock, Invoice, PayrollRecord
from payments.models import Payment


def resolve_actor(instance):
    for attr in ("updated_by", "created_by", "locked_by", "reviewed_by", "paid_by", "uploaded_by"):
        actor = getattr(instance, attr, None)
        if actor:
            return actor
    return None


def resolve_period(instance):
    if hasattr(instance, "period") and instance.period:
        return instance.period.replace(day=1)
    if hasattr(instance, "expense_date") and instance.expense_date:
        return instance.expense_date.replace(day=1)
    if hasattr(instance, "invoice") and instance.invoice_id:
        return instance.invoice.period
    return None


def resolve_branch(instance):
    if hasattr(instance, "branch_tag") and instance.branch_tag:
        return instance.branch_tag
    if hasattr(instance, "invoice") and instance.invoice_id:
        return instance.invoice.branch_label
    if hasattr(instance, "branch_label"):
        return instance.branch_label
    return ""


def write_audit_entry(instance, action, created=False):
    if isinstance(instance, FinanceAuditLog):
        return
    FinanceAuditLog.objects.create(
        source_model=instance.__class__.__name__,
        object_pk=str(instance.pk),
        object_repr=str(instance),
        action=FinanceAuditLog.ACTION_CREATED if created else action,
        period=resolve_period(instance),
        branch_tag=resolve_branch(instance),
        actor=resolve_actor(instance),
        notes=f"{instance.__class__.__name__} {action}.",
    )


@receiver(post_save, sender=Invoice)
@receiver(post_save, sender=ExpenseEntry)
@receiver(post_save, sender=PayrollRecord)
@receiver(post_save, sender=ForecastScenario)
@receiver(post_save, sender=HistoricalLock)
@receiver(post_save, sender=Payment)
def finance_post_save_audit(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    write_audit_entry(instance, FinanceAuditLog.ACTION_UPDATED, created=created)


@receiver(post_delete, sender=Invoice)
@receiver(post_delete, sender=ExpenseEntry)
@receiver(post_delete, sender=PayrollRecord)
@receiver(post_delete, sender=ForecastScenario)
@receiver(post_delete, sender=HistoricalLock)
@receiver(post_delete, sender=Payment)
def finance_post_delete_audit(sender, instance, **kwargs):
    write_audit_entry(instance, FinanceAuditLog.ACTION_DELETED, created=False)
