from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils.text import slugify


def format_ringgit(amount):
    value = Decimal(amount or "0")
    if value == value.to_integral():
        return f"RM{int(value)}"
    return f"RM{value.quantize(Decimal('0.01'))}"


class BillingConfiguration(models.Model):
    registration_fee_name = models.CharField(max_length=120, default="Registration Fee")
    registration_fee_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("60.00"))
    registration_bonus_text = models.CharField(max_length=255, blank=True, default="1 free training jersey")
    registration_description = models.TextField(
        blank=True,
        default="Mandatory one-time onboarding fee charged when a student joins the academy.",
    )
    payment_portal_note = models.TextField(
        blank=True,
        default="Scan the QR code, transfer the exact amount, then upload a screenshot for admin verification.",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_billing_configuration",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Billing configuration"
        verbose_name_plural = "Billing configuration"

    def __str__(self):
        return "Billing Configuration"

    @classmethod
    def get_solo(cls):
        obj = cls.objects.order_by("pk").first()
        if obj:
            return obj
        return cls.objects.create()

    @property
    def registration_invoice_description(self):
        if self.registration_bonus_text:
            return f"{self.registration_fee_name} (includes {self.registration_bonus_text})"
        return self.registration_fee_name

    @property
    def registration_summary(self):
        amount_text = format_ringgit(self.registration_fee_amount)
        if self.registration_bonus_text:
            return f"{self.registration_fee_name} {amount_text} with {self.registration_bonus_text}"
        return f"{self.registration_fee_name} {amount_text}"


class PaymentPlan(models.Model):
    name = models.CharField(max_length=120)
    code = models.SlugField(max_length=50, unique=True)
    sessions_per_month = models.PositiveIntegerField(default=4)
    monthly_fee = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_payment_plans",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "sessions_per_month", "monthly_fee", "name"]

    def __str__(self):
        return f"{self.name} - {format_ringgit(self.monthly_fee)}"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = slugify(self.name).replace("-", "_")[:50]
        super().save(*args, **kwargs)
        if self.is_default:
            self.__class__.objects.exclude(pk=self.pk).filter(is_default=True).update(is_default=False)

    @classmethod
    def ensure_seeded(cls):
        if cls.objects.exists():
            return
        cls.objects.bulk_create(
            [
                cls(
                    name="Monthly Package - 4 Sessions",
                    code="monthly_4",
                    sessions_per_month=4,
                    monthly_fee=Decimal("100.00"),
                    description="Recommended for weekly training rhythm and steady fundamentals.",
                    is_default=True,
                    sort_order=1,
                ),
                cls(
                    name="Monthly Package - 8 Sessions",
                    code="monthly_8",
                    sessions_per_month=8,
                    monthly_fee=Decimal("160.00"),
                    description="Best for players who want a higher-volume training schedule each month.",
                    is_default=False,
                    sort_order=2,
                ),
            ]
        )

    @classmethod
    def get_default(cls, active_only=True):
        cls.ensure_seeded()
        queryset = cls.objects.all()
        if active_only:
            queryset = queryset.filter(is_active=True)
        return queryset.filter(is_default=True).first() or queryset.first()

    @property
    def summary(self):
        return f"{format_ringgit(self.monthly_fee)} per month for {self.sessions_per_month} sessions"

    @property
    def invoice_description(self):
        return f"{self.name}: {format_ringgit(self.monthly_fee)} ({self.sessions_per_month} sessions per month)"


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
    payment_plan = models.ForeignKey(
        "finance.PaymentPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
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
