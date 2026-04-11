from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class QRCode(models.Model):
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_qr_codes",
    )
    invoice = models.ForeignKey(
        "finance.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="qr_codes",
    )
    payment_period = models.DateField(null=True, blank=True)
    image = models.ImageField(upload_to="qr_codes/")
    label = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.label

    def clean(self):
        if not self.invoice and not self.payment_period:
            raise ValidationError("Link the QR code to an invoice or a payment period.")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_active:
            queryset = QRCode.objects.filter(is_active=True).exclude(pk=self.pk)
            if self.invoice_id:
                queryset = queryset.filter(invoice_id=self.invoice_id)
            elif self.payment_period:
                queryset = queryset.filter(payment_period=self.payment_period)
            queryset.update(is_active=False)


class Payment(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    invoice = models.ForeignKey("finance.Invoice", on_delete=models.CASCADE, related_name="payments")
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="submitted_payments",
    )
    proof_image = models.ImageField(upload_to="payment_proofs/")
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_payments",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.invoice.member.full_name} - {self.get_status_display()}"

# Create your models here.
