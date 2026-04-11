from django.conf import settings
from django.db import models


class Invoice(models.Model):
    STATUS_UNPAID = "unpaid"
    STATUS_PENDING = "pending_verification"
    STATUS_PAID = "paid"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_UNPAID, "Unpaid"),
        (STATUS_PENDING, "Pending Verification"),
        (STATUS_PAID, "Paid"),
        (STATUS_REJECTED, "Rejected"),
    ]

    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="invoices")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    period = models.DateField(help_text="Use the first day of the billed month.")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_UNPAID)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_invoices",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period", "member__full_name"]
        constraints = [
            models.UniqueConstraint(fields=["member", "period"], name="unique_invoice_period_per_member")
        ]

    def __str__(self):
        return f"{self.member.full_name} - {self.period:%b %Y}"

    @property
    def latest_payment(self):
        return self.payments.order_by("-submitted_at").first()

    @property
    def active_qr_code(self):
        direct_match = self.qr_codes.filter(is_active=True).order_by("-created_at").first()
        if direct_match:
            return direct_match
        from payments.models import QRCode

        period_match = QRCode.objects.filter(payment_period=self.period, is_active=True).order_by("-created_at").first()
        if period_match:
            return period_match
        return self.qr_codes.order_by("-created_at").first() or QRCode.objects.filter(payment_period=self.period).order_by("-created_at").first()

# Create your models here.
