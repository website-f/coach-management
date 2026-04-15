from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.utils.text import slugify


ZERO_DECIMAL = Decimal("0.00")
DEFAULT_BRANCH_LABEL = "Unassigned Branch"
DEFAULT_PROGRAM_LABEL = "Unassigned Program"

PAYMENT_METHOD_BANK_TRANSFER = "bank_transfer"
PAYMENT_METHOD_CASH = "cash"
PAYMENT_METHOD_CARD = "card"
PAYMENT_METHOD_EWALLET = "ewallet"
PAYMENT_METHOD_OTHER = "other"
PAYMENT_METHOD_CHOICES = [
    (PAYMENT_METHOD_BANK_TRANSFER, "Bank Transfer"),
    (PAYMENT_METHOD_CASH, "Cash"),
    (PAYMENT_METHOD_CARD, "Card"),
    (PAYMENT_METHOD_EWALLET, "E-Wallet"),
    (PAYMENT_METHOD_OTHER, "Other"),
]


def format_ringgit(amount):
    value = Decimal(amount or "0")
    if value == value.to_integral():
        return f"RM{int(value)}"
    return f"RM{value.quantize(Decimal('0.01'))}"


class BillingConfiguration(models.Model):
    registration_fee_name = models.CharField(max_length=120, default="Registration Fee")
    registration_fee_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("60.00"))
    registration_bonus_text = models.CharField(max_length=255, blank=True, default="1 free training jersey")
    trial_session_limit = models.PositiveIntegerField(default=1)
    opening_cash_balance = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO_DECIMAL)
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
    STATUS_PARTIAL = "partial"
    STATUS_PAID = "paid"
    STATUS_OVERDUE = "overdue"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_UNPAID, "Unpaid"),
        (STATUS_PENDING, "Pending Verification"),
        (STATUS_PARTIAL, "Partial"),
        (STATUS_PAID, "Paid"),
        (STATUS_OVERDUE, "Overdue"),
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
    branch_tag = models.CharField(max_length=255, blank=True)
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

    def save(self, *args, **kwargs):
        if self.period:
            self.period = self.period.replace(day=1)
        super().save(*args, **kwargs)

    @property
    def latest_payment(self):
        return self.payments.order_by("-submitted_at").first()

    @property
    def latest_approved_payment(self):
        return self.payments.filter(status="approved").order_by("-reviewed_at", "-submitted_at").first()

    @property
    def approved_amount(self):
        return self.payments.filter(status="approved").aggregate(total=Sum("amount_received"))["total"] or ZERO_DECIMAL

    @property
    def outstanding_amount(self):
        remaining = Decimal(self.amount or ZERO_DECIMAL) - Decimal(self.approved_amount or ZERO_DECIMAL)
        return remaining if remaining > ZERO_DECIMAL else ZERO_DECIMAL

    @property
    def receipt_history(self):
        return self.payments.order_by("-submitted_at")

    @property
    def student_label(self):
        return self.member.full_name

    @property
    def coach_label(self):
        if self.member.assigned_coach_id:
            return self.member.assigned_coach.get_full_name() or self.member.assigned_coach.username
        return "Unassigned Coach"

    @property
    def program_label(self):
        return self.member.program_enrolled or (self.payment_plan.name if self.payment_plan_id else DEFAULT_PROGRAM_LABEL)

    @property
    def branch_label(self):
        if self.branch_tag:
            return self.branch_tag
        latest_application = self.member.latest_application
        if latest_application and latest_application.preferred_location:
            return latest_application.preferred_location
        return DEFAULT_BRANCH_LABEL

    @property
    def payment_method_label(self):
        latest_payment = self.latest_approved_payment or self.latest_payment
        return latest_payment.get_payment_method_display() if latest_payment else "Not captured"

    @property
    def is_overdue(self):
        return self.outstanding_amount > ZERO_DECIMAL and self.due_date < timezone.localdate()

    def refresh_status_from_payments(self, reference_date=None, save=True):
        from payments.models import Payment

        today = reference_date or timezone.localdate()
        pending_exists = self.payments.filter(status=Payment.STATUS_PENDING).exists()
        approved_amount = self.approved_amount
        rejected_exists = self.payments.filter(status=Payment.STATUS_REJECTED).exists()

        if pending_exists:
            resolved_status = self.STATUS_PENDING
        elif approved_amount >= self.amount:
            resolved_status = self.STATUS_PAID
        elif approved_amount > ZERO_DECIMAL:
            resolved_status = self.STATUS_OVERDUE if self.due_date < today else self.STATUS_PARTIAL
        elif rejected_exists:
            resolved_status = self.STATUS_OVERDUE if self.due_date < today else self.STATUS_REJECTED
        else:
            resolved_status = self.STATUS_OVERDUE if self.due_date < today else self.STATUS_UNPAID

        self.status = resolved_status
        if save and self.pk:
            self.save(update_fields=["status", "updated_at"])
        return self.status

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


class ExpenseEntry(models.Model):
    TYPE_FIXED = "fixed"
    TYPE_VARIABLE = "variable"
    TYPE_CHOICES = [
        (TYPE_FIXED, "Fixed"),
        (TYPE_VARIABLE, "Variable"),
    ]

    CATEGORY_RENT = "rent"
    CATEGORY_SOFTWARE = "software"
    CATEGORY_SALARIES = "salaries"
    CATEGORY_EQUIPMENT = "equipment"
    CATEGORY_EVENTS = "events"
    CATEGORY_TRANSPORT = "transport"
    CATEGORY_MARKETING = "marketing"
    CATEGORY_UTILITIES = "utilities"
    CATEGORY_TAX = "tax"
    CATEGORY_OTHER = "other"
    CATEGORY_CHOICES = [
        (CATEGORY_RENT, "Rent"),
        (CATEGORY_SOFTWARE, "Software"),
        (CATEGORY_SALARIES, "Salaries"),
        (CATEGORY_EQUIPMENT, "Equipment"),
        (CATEGORY_EVENTS, "Events"),
        (CATEGORY_TRANSPORT, "Transport"),
        (CATEGORY_MARKETING, "Marketing"),
        (CATEGORY_UTILITIES, "Utilities"),
        (CATEGORY_TAX, "Tax"),
        (CATEGORY_OTHER, "Other"),
    ]

    title = models.CharField(max_length=255)
    expense_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_FIXED)
    category_tag = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    branch_tag = models.CharField(max_length=255, blank=True)
    vendor_name = models.CharField(max_length=255, blank=True)
    expense_date = models.DateField(default=timezone.localdate)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES, default=PAYMENT_METHOD_BANK_TRANSFER)
    receipt_upload = models.FileField(upload_to="expense_receipts/", blank=True)
    is_tax_deductible = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_expenses",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_expenses",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-expense_date", "-created_at"]

    def __str__(self):
        return f"{self.title} - {format_ringgit(self.amount)}"

    @property
    def period(self):
        return self.expense_date.replace(day=1)

    @property
    def branch_label(self):
        return self.branch_tag or DEFAULT_BRANCH_LABEL


class PayrollRecord(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_APPROVED = "approved"
    STATUS_PAID = "paid"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_PAID, "Paid"),
    ]

    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payroll_records",
    )
    period = models.DateField(help_text="Use the first day of the payroll month.")
    branch_tag = models.CharField(max_length=255, blank=True)
    base_pay = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO_DECIMAL)
    per_session_rate = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO_DECIMAL)
    session_count = models.PositiveIntegerField(default=0)
    attendance_adjustment = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO_DECIMAL)
    bonus_amount = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO_DECIMAL)
    deduction_amount = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO_DECIMAL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    paid_at = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_payroll_records",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_payroll_records",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period", "coach__username"]
        constraints = [
            models.UniqueConstraint(fields=["coach", "period", "branch_tag"], name="unique_payroll_coach_period_branch")
        ]

    def __str__(self):
        return f"{self.coach} payroll ({self.period:%b %Y})"

    def save(self, *args, **kwargs):
        if self.period:
            self.period = self.period.replace(day=1)
        if self.status == self.STATUS_PAID and not self.paid_at:
            self.paid_at = timezone.localdate()
        super().save(*args, **kwargs)

    @property
    def branch_label(self):
        return self.branch_tag or DEFAULT_BRANCH_LABEL

    @property
    def gross_pay(self):
        return (
            Decimal(self.base_pay or ZERO_DECIMAL)
            + (Decimal(self.per_session_rate or ZERO_DECIMAL) * Decimal(self.session_count or 0))
            + Decimal(self.attendance_adjustment or ZERO_DECIMAL)
            + Decimal(self.bonus_amount or ZERO_DECIMAL)
        )

    @property
    def total_pay(self):
        total = self.gross_pay - Decimal(self.deduction_amount or ZERO_DECIMAL)
        return total if total > ZERO_DECIMAL else ZERO_DECIMAL

    @property
    def sessions_delivered_actual(self):
        from sessions.models import TrainingSession

        return TrainingSession.objects.filter(
            coach=self.coach,
            session_date__year=self.period.year,
            session_date__month=self.period.month,
        ).count()

    @property
    def attendance_units_actual(self):
        from sessions.models import AttendanceRecord

        return AttendanceRecord.objects.filter(
            training_session__coach=self.coach,
            training_session__session_date__year=self.period.year,
            training_session__session_date__month=self.period.month,
            status__in=[AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE],
        ).count()


class ForecastScenario(models.Model):
    title = models.CharField(max_length=255)
    student_count_change_percent = models.DecimalField(max_digits=6, decimal_places=2, default=ZERO_DECIMAL)
    revenue_drop_percent = models.DecimalField(max_digits=6, decimal_places=2, default=ZERO_DECIMAL)
    salary_increase_percent = models.DecimalField(max_digits=6, decimal_places=2, default=ZERO_DECIMAL)
    additional_coach_hires = models.PositiveIntegerField(default=0)
    average_new_coach_monthly_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("2500.00"))
    new_branch_student_count = models.PositiveIntegerField(default=0)
    new_branch_monthly_overhead = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO_DECIMAL)
    one_time_expansion_cost = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO_DECIMAL)
    risk_buffer_percent = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("10.00"))
    is_primary = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_forecast_scenarios",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_forecast_scenarios",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_primary", "title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_primary:
            self.__class__.objects.exclude(pk=self.pk).filter(is_primary=True).update(is_primary=False)


class HistoricalLock(models.Model):
    period = models.DateField(unique=True, help_text="Use the first day of the locked month.")
    notes = models.TextField(blank=True)
    is_closed = models.BooleanField(default=True)
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="historical_locks",
    )
    locked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-period"]

    def __str__(self):
        return f"Lock {self.period:%b %Y}"

    def save(self, *args, **kwargs):
        if self.period:
            self.period = self.period.replace(day=1)
        if self.is_closed and not self.locked_at:
            self.locked_at = timezone.now()
        super().save(*args, **kwargs)


class FinanceAuditLog(models.Model):
    ACTION_CREATED = "created"
    ACTION_UPDATED = "updated"
    ACTION_DELETED = "deleted"
    ACTION_CHOICES = [
        (ACTION_CREATED, "Created"),
        (ACTION_UPDATED, "Updated"),
        (ACTION_DELETED, "Deleted"),
    ]

    source_model = models.CharField(max_length=120)
    object_pk = models.CharField(max_length=64)
    object_repr = models.CharField(max_length=255)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default=ACTION_UPDATED)
    period = models.DateField(null=True, blank=True)
    branch_tag = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="finance_audit_logs",
    )
    happened_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-happened_at"]

    def __str__(self):
        return f"{self.source_model} {self.action} ({self.object_repr})"


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
