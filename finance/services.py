from collections import defaultdict
from datetime import date
from decimal import Decimal
from math import ceil

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from accounts.models import LandingPageContent
from finance.models import (
    DEFAULT_BRANCH_LABEL,
    DEFAULT_PROGRAM_LABEL,
    BillingConfiguration,
    ExpenseEntry,
    FinanceAuditLog,
    ForecastScenario,
    HistoricalLock,
    Invoice,
    PaymentPlan,
    PayrollRecord,
    format_ringgit,
)
from members.models import Member
from payments.models import Payment


ZERO_DECIMAL = Decimal("0.00")


def decimal_or_zero(value):
    return Decimal(value or ZERO_DECIMAL)


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


def resolve_member_latest_application(member):
    prefetched = getattr(member, "_prefetched_objects_cache", {})
    cached_applications = prefetched.get("admission_applications")
    if cached_applications is not None:
        if not cached_applications:
            return None
        return sorted(cached_applications, key=lambda item: item.submitted_at, reverse=True)[0]
    return member.latest_application


def resolve_member_branch(member):
    latest_application = resolve_member_latest_application(member)
    if latest_application and latest_application.preferred_location:
        return latest_application.preferred_location
    return DEFAULT_BRANCH_LABEL


def resolve_member_program(member):
    return member.program_enrolled or (member.payment_plan.name if member.payment_plan_id else DEFAULT_PROGRAM_LABEL)


def build_branch_choices():
    labels = {label for label in LandingPageContent.get_solo().available_locations if label}
    labels.update(value for value in Invoice.objects.exclude(branch_tag="").values_list("branch_tag", flat=True))
    labels.update(value for value in ExpenseEntry.objects.exclude(branch_tag="").values_list("branch_tag", flat=True))
    labels.update(value for value in PayrollRecord.objects.exclude(branch_tag="").values_list("branch_tag", flat=True))
    return sorted(labels)


def normalize_period(value):
    if hasattr(value, "date"):
        value = value.date()
    return value.replace(day=1)


def build_month_window(month_count=6, anchor=None):
    current = normalize_period(anchor or timezone.localdate())
    window = []
    for offset in range(month_count - 1, -1, -1):
        month_index = current.month - 1 - offset
        year = current.year + month_index // 12
        month = month_index % 12 + 1
        window.append(date(year, month, 1))
    return window


def is_period_locked(period):
    return HistoricalLock.objects.filter(period=normalize_period(period), is_closed=True).exists()


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
            "branch_tag": resolve_member_branch(member),
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
            "branch_tag": resolve_member_branch(member),
            "status": Invoice.STATUS_UNPAID,
        },
    )
    if monthly_created:
        created_invoices.append(monthly_invoice)

    return created_invoices


def build_finance_snapshot(today=None, scenario=None):
    today = today or timezone.localdate()
    current_period = normalize_period(today)
    months = build_month_window(anchor=today)
    config = get_billing_configuration()

    invoices = list(
        Invoice.objects.select_related("member", "member__assigned_coach", "member__payment_plan", "payment_plan")
        .prefetch_related("payments", "member__admission_applications")
        .order_by("-period", "member__full_name")
    )
    payments = list(
        Payment.objects.select_related("invoice", "invoice__member", "invoice__member__assigned_coach", "paid_by", "reviewed_by")
        .prefetch_related("invoice__member__admission_applications")
        .order_by("-submitted_at")
    )
    approved_payments = [payment for payment in payments if payment.status == Payment.STATUS_APPROVED]
    expenses = list(ExpenseEntry.objects.order_by("-expense_date", "-created_at"))
    payroll_rows = list(PayrollRecord.objects.select_related("coach").order_by("-period", "coach__username"))
    active_members = list(
        Member.objects.select_related("assigned_coach", "payment_plan").filter(status=Member.STATUS_ACTIVE)
    )
    scenario = scenario or ForecastScenario.objects.filter(is_primary=True).first() or ForecastScenario.objects.order_by("title").first()

    monthly_recurring_revenue = sum(decimal_or_zero(member.payment_plan.monthly_fee if member.payment_plan_id else ZERO_DECIMAL) for member in active_members)
    active_student_count = len(active_members)
    average_revenue_per_student = (
        monthly_recurring_revenue / active_student_count if active_student_count else ZERO_DECIMAL
    )

    current_month_revenue = sum(
        decimal_or_zero(payment.amount_received)
        for payment in approved_payments
        if payment.reviewed_at
        and payment.reviewed_at.year == today.year
        and payment.reviewed_at.month == today.month
    )
    billed_this_month = sum(
        decimal_or_zero(invoice.amount) for invoice in invoices if invoice.period.year == today.year and invoice.period.month == today.month
    )
    outstanding_invoices = [invoice for invoice in invoices if invoice.status != Invoice.STATUS_PAID]
    overdue_invoices = [invoice for invoice in invoices if invoice.is_overdue]
    pending_verification_total = sum(
        decimal_or_zero(invoice.amount) for invoice in invoices if invoice.status == Invoice.STATUS_PENDING
    )
    overdue_total = sum(decimal_or_zero(invoice.outstanding_amount) for invoice in overdue_invoices)
    outstanding_total = sum(decimal_or_zero(invoice.outstanding_amount) for invoice in outstanding_invoices)
    collection_rate = round((current_month_revenue / billed_this_month) * 100, 1) if billed_this_month else 0

    current_month_expenses = [expense for expense in expenses if expense.expense_date.year == today.year and expense.expense_date.month == today.month]
    fixed_expenses = sum(decimal_or_zero(expense.amount) for expense in current_month_expenses if expense.expense_type == ExpenseEntry.TYPE_FIXED)
    variable_expenses = sum(decimal_or_zero(expense.amount) for expense in current_month_expenses if expense.expense_type == ExpenseEntry.TYPE_VARIABLE)
    paid_payroll_rows = [
        payroll
        for payroll in payroll_rows
        if payroll.status == PayrollRecord.STATUS_PAID and payroll.period.year == today.year and payroll.period.month == today.month
    ]
    payroll_total = sum(decimal_or_zero(payroll.total_pay) for payroll in paid_payroll_rows)
    total_expenses = fixed_expenses + variable_expenses + payroll_total
    gross_profit = current_month_revenue - (variable_expenses + payroll_total)
    net_profit = current_month_revenue - total_expenses
    margin = round((net_profit / current_month_revenue) * 100, 1) if current_month_revenue else 0

    all_time_cash_in = sum(decimal_or_zero(payment.amount_received) for payment in approved_payments)
    all_time_cash_out = sum(decimal_or_zero(expense.amount) for expense in expenses) + sum(
        decimal_or_zero(payroll.total_pay) for payroll in payroll_rows if payroll.status == PayrollRecord.STATUS_PAID
    )
    cash_balance = decimal_or_zero(config.opening_cash_balance) + all_time_cash_in - all_time_cash_out

    monthly_fixed_cost = fixed_expenses + payroll_total
    average_variable_cost_per_student = (
        variable_expenses / active_student_count if active_student_count else ZERO_DECIMAL
    )
    contribution_per_student = average_revenue_per_student - average_variable_cost_per_student
    break_even_students = ceil(monthly_fixed_cost / contribution_per_student) if contribution_per_student > ZERO_DECIMAL else None

    revenue_by_program = defaultdict(lambda: ZERO_DECIMAL)
    revenue_by_branch = defaultdict(lambda: ZERO_DECIMAL)
    revenue_by_coach = defaultdict(lambda: ZERO_DECIMAL)
    revenue_by_student = defaultdict(lambda: ZERO_DECIMAL)
    payment_method_totals = defaultdict(lambda: ZERO_DECIMAL)
    revenue_trend = {month: ZERO_DECIMAL for month in months}
    cash_in_trend = {month: ZERO_DECIMAL for month in months}
    cash_out_trend = {month: ZERO_DECIMAL for month in months}
    branch_direct_expenses = defaultdict(lambda: ZERO_DECIMAL)
    program_expense_allocation = defaultdict(lambda: ZERO_DECIMAL)
    expense_by_category = defaultdict(lambda: ZERO_DECIMAL)
    expense_by_branch = defaultdict(lambda: ZERO_DECIMAL)
    payroll_by_coach = defaultdict(lambda: ZERO_DECIMAL)
    payroll_by_branch = defaultdict(lambda: ZERO_DECIMAL)

    for payment in approved_payments:
        invoice = payment.invoice
        amount = decimal_or_zero(payment.amount_received)
        program_label = resolve_member_program(invoice.member)
        branch_label = invoice.branch_label
        coach_label = invoice.coach_label
        student_label = invoice.student_label
        revenue_by_program[program_label] += amount
        revenue_by_branch[branch_label] += amount
        revenue_by_coach[coach_label] += amount
        revenue_by_student[student_label] += amount
        payment_method_totals[payment.get_payment_method_display()] += amount
        if payment.reviewed_at:
            reviewed_month = normalize_period(payment.reviewed_at)
            if reviewed_month in revenue_trend:
                revenue_trend[reviewed_month] += amount
                cash_in_trend[reviewed_month] += amount

    for expense in expenses:
        expense_month = normalize_period(expense.expense_date)
        branch_label = expense.branch_label
        expense_by_category[expense.get_category_tag_display()] += decimal_or_zero(expense.amount)
        expense_by_branch[branch_label] += decimal_or_zero(expense.amount)
        branch_direct_expenses[branch_label] += decimal_or_zero(expense.amount)
        if expense_month in cash_out_trend:
            cash_out_trend[expense_month] += decimal_or_zero(expense.amount)

    for payroll in payroll_rows:
        branch_label = payroll.branch_label
        payroll_by_coach[payroll.coach.get_full_name() or payroll.coach.username] += decimal_or_zero(payroll.total_pay)
        payroll_by_branch[branch_label] += decimal_or_zero(payroll.total_pay)
        branch_direct_expenses[branch_label] += decimal_or_zero(payroll.total_pay)
        if payroll.status == PayrollRecord.STATUS_PAID:
            payroll_month = normalize_period(payroll.paid_at or payroll.period)
            if payroll_month in cash_out_trend:
                cash_out_trend[payroll_month] += decimal_or_zero(payroll.total_pay)

    total_shared_expenses = sum(decimal_or_zero(expense.amount) for expense in expenses if not expense.branch_tag) + sum(
        decimal_or_zero(payroll.total_pay) for payroll in payroll_rows if not payroll.branch_tag
    )
    total_revenue_for_allocation = sum(revenue_by_branch.values()) or ZERO_DECIMAL

    branch_pnl_rows = []
    for branch_label, revenue_amount in sorted(revenue_by_branch.items(), key=lambda item: item[1], reverse=True):
        revenue_share = (revenue_amount / total_revenue_for_allocation) if total_revenue_for_allocation else ZERO_DECIMAL
        allocated_shared = total_shared_expenses * revenue_share
        branch_expenses_total = branch_direct_expenses[branch_label] + allocated_shared
        branch_net_profit = revenue_amount - branch_expenses_total
        branch_pnl_rows.append(
            {
                "label": branch_label,
                "revenue": revenue_amount,
                "expenses": branch_expenses_total,
                "net_profit": branch_net_profit,
                "margin": round((branch_net_profit / revenue_amount) * 100, 1) if revenue_amount else 0,
            }
        )

    total_revenue_for_program_allocation = sum(revenue_by_program.values()) or ZERO_DECIMAL
    total_operating_expenses = sum(decimal_or_zero(expense.amount) for expense in expenses) + sum(
        decimal_or_zero(payroll.total_pay) for payroll in payroll_rows
    )
    program_pnl_rows = []
    for program_label, revenue_amount in sorted(revenue_by_program.items(), key=lambda item: item[1], reverse=True):
        revenue_share = (revenue_amount / total_revenue_for_program_allocation) if total_revenue_for_program_allocation else ZERO_DECIMAL
        allocated_expenses = total_operating_expenses * revenue_share
        program_expense_allocation[program_label] = allocated_expenses
        program_net_profit = revenue_amount - allocated_expenses
        program_pnl_rows.append(
            {
                "label": program_label,
                "revenue": revenue_amount,
                "expenses": allocated_expenses,
                "net_profit": program_net_profit,
                "margin": round((program_net_profit / revenue_amount) * 100, 1) if revenue_amount else 0,
            }
        )

    monthly_report_rows = []
    for month in months:
        month_expenses = sum(
            decimal_or_zero(expense.amount)
            for expense in expenses
            if expense.expense_date.year == month.year and expense.expense_date.month == month.month
        )
        month_payroll = sum(
            decimal_or_zero(payroll.total_pay)
            for payroll in payroll_rows
            if payroll.status == PayrollRecord.STATUS_PAID and payroll.period.year == month.year and payroll.period.month == month.month
        )
        month_revenue = revenue_trend.get(month, ZERO_DECIMAL)
        month_net = month_revenue - month_expenses - month_payroll
        monthly_report_rows.append(
            {
                "period": month,
                "revenue": month_revenue,
                "expenses": month_expenses + month_payroll,
                "net_profit": month_net,
                "locked": HistoricalLock.objects.filter(period=month, is_closed=True).exists(),
            }
        )

    risk_buffer_percent = decimal_or_zero(scenario.risk_buffer_percent if scenario else Decimal("10.00"))
    target_buffer = total_expenses * (risk_buffer_percent / Decimal("100"))

    salary_increase_percent = decimal_or_zero(scenario.salary_increase_percent if scenario else ZERO_DECIMAL)
    student_change_percent = decimal_or_zero(scenario.student_count_change_percent if scenario else ZERO_DECIMAL)
    revenue_drop_percent = decimal_or_zero(scenario.revenue_drop_percent if scenario else ZERO_DECIMAL)
    additional_coach_hires = scenario.additional_coach_hires if scenario else 0
    average_new_coach_cost = decimal_or_zero(scenario.average_new_coach_monthly_cost if scenario else Decimal("2500.00"))
    new_branch_student_count = scenario.new_branch_student_count if scenario else 0
    new_branch_monthly_overhead = decimal_or_zero(scenario.new_branch_monthly_overhead if scenario else ZERO_DECIMAL)
    one_time_expansion_cost = decimal_or_zero(scenario.one_time_expansion_cost if scenario else ZERO_DECIMAL)

    forecasted_student_count = max(
        Decimal(active_student_count) * (Decimal("1.00") + (student_change_percent / Decimal("100"))),
        Decimal("0.00"),
    ) + Decimal(new_branch_student_count)
    forecasted_revenue = (
        average_revenue_per_student
        * forecasted_student_count
        * (Decimal("1.00") - (revenue_drop_percent / Decimal("100")))
    )
    forecasted_variable_expense = average_variable_cost_per_student * forecasted_student_count
    forecasted_fixed_expense = fixed_expenses + new_branch_monthly_overhead
    forecasted_payroll = (payroll_total * (Decimal("1.00") + (salary_increase_percent / Decimal("100")))) + (
        average_new_coach_cost * Decimal(additional_coach_hires)
    )
    forecasted_total_expenses = forecasted_variable_expense + forecasted_fixed_expense + forecasted_payroll
    forecasted_net_profit = forecasted_revenue - forecasted_total_expenses
    burn_after_drop = forecasted_total_expenses - forecasted_revenue
    runway_months = (cash_balance / burn_after_drop) if burn_after_drop > ZERO_DECIMAL else None

    new_branch_revenue = average_revenue_per_student * Decimal(new_branch_student_count)
    new_branch_net = new_branch_revenue - new_branch_monthly_overhead - (average_new_coach_cost * Decimal(additional_coach_hires))
    can_hire_more_coach = net_profit >= average_new_coach_cost or cash_balance >= (average_new_coach_cost * Decimal("3"))
    can_open_new_branch = new_branch_net > ZERO_DECIMAL and cash_balance >= one_time_expansion_cost

    biggest_leakage = None
    if expense_by_category:
        biggest_leakage = max(expense_by_category.items(), key=lambda item: item[1])
    elif overdue_total > ZERO_DECIMAL:
        biggest_leakage = ("Overdue receivables", overdue_total)

    answer_cards = [
        {
            "question": "Are we profitable?",
            "answer": "Yes" if net_profit >= ZERO_DECIMAL else "No",
            "detail": f"Current month net profit is {format_ringgit(net_profit)} with a {margin}% margin.",
            "tone": "success" if net_profit >= ZERO_DECIMAL else "danger",
        },
        {
            "question": "Where is money leaking?",
            "answer": biggest_leakage[0] if biggest_leakage else "No clear leak yet",
            "detail": (
                f"Current leak signal is {biggest_leakage[0]} at {format_ringgit(biggest_leakage[1])}."
                if biggest_leakage
                else "Start tagging expenses and overdue accounts to surface leakage automatically."
            ),
            "tone": "warning" if biggest_leakage else "neutral",
        },
        {
            "question": "Can we hire one more coach?",
            "answer": "Yes" if can_hire_more_coach else "Not safely yet",
            "detail": f"Estimated extra monthly coach cost is {format_ringgit(average_new_coach_cost)}.",
            "tone": "success" if can_hire_more_coach else "warning",
        },
        {
            "question": "Can we open another branch?",
            "answer": "Yes" if can_open_new_branch else "Not yet",
            "detail": f"Projected branch net contribution is {format_ringgit(new_branch_net)} after operating overhead.",
            "tone": "success" if can_open_new_branch else "warning",
        },
        {
            "question": "How long can we survive if revenue drops?",
            "answer": "Stable" if runway_months is None else f"{runway_months.quantize(Decimal('0.1'))} months",
            "detail": (
                "The current scenario still stays cash-positive under the simulated drop."
                if runway_months is None
                else f"Runway assumes a {revenue_drop_percent}% revenue drop and the current cash balance."
            ),
            "tone": "success" if runway_months is None or runway_months >= Decimal("6") else "danger",
        },
    ]

    tax_summary = {
        "year_to_date_revenue": sum(
            decimal_or_zero(payment.amount_received) for payment in approved_payments if payment.reviewed_at and payment.reviewed_at.year == today.year
        ),
        "year_to_date_deductible_expenses": sum(
            decimal_or_zero(expense.amount) for expense in expenses if expense.is_tax_deductible and expense.expense_date.year == today.year
        ),
        "year_to_date_payroll": sum(
            decimal_or_zero(payroll.total_pay) for payroll in payroll_rows if payroll.status == PayrollRecord.STATUS_PAID and payroll.period.year == today.year
        ),
    }

    return {
        "today": today,
        "current_period": current_period,
        "months": months,
        "monthly_recurring_revenue": monthly_recurring_revenue,
        "billed_this_month": billed_this_month,
        "revenue_this_month": current_month_revenue,
        "pending_verification_total": pending_verification_total,
        "outstanding_total": outstanding_total,
        "overdue_total": overdue_total,
        "collection_rate": collection_rate,
        "fixed_expenses": fixed_expenses,
        "variable_expenses": variable_expenses,
        "payroll_total": payroll_total,
        "total_expenses": total_expenses,
        "gross_profit": gross_profit,
        "net_profit": net_profit,
        "margin": margin,
        "cash_balance": cash_balance,
        "target_buffer": target_buffer,
        "break_even_students": break_even_students,
        "active_student_count": active_student_count,
        "average_revenue_per_student": average_revenue_per_student,
        "revenue_by_program": sorted(revenue_by_program.items(), key=lambda item: item[1], reverse=True),
        "revenue_by_branch": sorted(revenue_by_branch.items(), key=lambda item: item[1], reverse=True),
        "revenue_by_coach": sorted(revenue_by_coach.items(), key=lambda item: item[1], reverse=True),
        "revenue_by_student": sorted(revenue_by_student.items(), key=lambda item: item[1], reverse=True),
        "payment_method_totals": sorted(payment_method_totals.items(), key=lambda item: item[1], reverse=True),
        "expense_by_category": sorted(expense_by_category.items(), key=lambda item: item[1], reverse=True),
        "expense_by_branch": sorted(expense_by_branch.items(), key=lambda item: item[1], reverse=True),
        "payroll_by_coach": sorted(payroll_by_coach.items(), key=lambda item: item[1], reverse=True),
        "payroll_by_branch": sorted(payroll_by_branch.items(), key=lambda item: item[1], reverse=True),
        "branch_pnl_rows": branch_pnl_rows,
        "program_pnl_rows": program_pnl_rows,
        "monthly_report_rows": monthly_report_rows,
        "invoice_rows": invoices[:12],
        "outstanding_rows": sorted(outstanding_invoices, key=lambda invoice: (invoice.due_date, invoice.student_label))[:10],
        "payment_rows": payments[:12],
        "expense_rows": current_month_expenses[:10],
        "payroll_rows": payroll_rows[:12],
        "approved_payments": approved_payments,
        "expenses": expenses,
        "all_payroll_rows": payroll_rows,
        "tax_summary": tax_summary,
        "audit_rows": list(FinanceAuditLog.objects.select_related("actor").order_by("-happened_at")[:15]),
        "lock_rows": list(HistoricalLock.objects.select_related("locked_by").order_by("-period")[:12]),
        "scenario": scenario,
        "forecast": {
            "student_count": forecasted_student_count,
            "revenue": forecasted_revenue,
            "expenses": forecasted_total_expenses,
            "net_profit": forecasted_net_profit,
            "runway_months": runway_months,
            "new_branch_net": new_branch_net,
            "can_hire_more_coach": can_hire_more_coach,
            "can_open_new_branch": can_open_new_branch,
        },
        "answer_cards": answer_cards,
        "chart": {
            "labels": [month.strftime("%b %Y") for month in months],
            "revenue": [float(revenue_trend[month]) for month in months],
            "cash_in": [float(cash_in_trend[month]) for month in months],
            "cash_out": [float(cash_out_trend[month]) for month in months],
            "net_cashflow": [float(cash_in_trend[month] - cash_out_trend[month]) for month in months],
        },
    }
