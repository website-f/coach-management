from django.conf import settings
from django.db import models


class Invoice(models.Model):
    TYPE_REGISTRATION = "registration"
    TYPE_MONTHLY = "monthly"
    TYPE_MISC = "misc"
    TYPE_CHOICES = [
        (TYPE_REGISTRATION, "Registration Fee"),
        (TYPE_MONTHLY, "Monthly Fee"),
        (TYPE_MISC, "Miscellaneous"),
    ]

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
    invoice_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_MONTHLY)
    description = models.CharField(max_length=255, blank=True)
    is_onboarding_fee = models.BooleanField(default=False)
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
            models.UniqueConstraint(fields=["member", "period", "invoice_type"], name="unique_invoice_period_type_per_member")
        ]

    def __str__(self):
        return f"{self.member.full_name} - {self.get_invoice_type_display()} ({self.period:%b %Y})"

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


class Product(models.Model):
    AVAILABILITY_READY = "ready"
    AVAILABILITY_PREORDER = "preorder"
    AVAILABILITY_SOLD_OUT = "sold_out"
    AVAILABILITY_CHOICES = [
        (AVAILABILITY_READY, "Ready"),
        (AVAILABILITY_PREORDER, "Preorder"),
        (AVAILABILITY_SOLD_OUT, "Sold Out"),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    availability = models.CharField(max_length=20, choices=AVAILABILITY_CHOICES, default=AVAILABILITY_READY)
    image = models.ImageField(upload_to="products/", blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_products",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_products",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

# Create your models here.
