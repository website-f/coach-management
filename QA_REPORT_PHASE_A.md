# Phase A — QA Discovery Report
**Project:** NYO Badminton Coach Management
**Date:** 2026-04-23
**Scope:** Research-only audit, no code changes

---

## 1. Roles (note: 4 roles, not 3)

Defined in [accounts/models.py:5-16](accounts/models.py#L5-L16):
- `ROLE_ADMIN`
- `ROLE_COACH`
- `ROLE_HEADCOUNT` (sales / lead-conversion staff)
- `ROLE_PARENT`

Authorization: `@role_required` decorator ([accounts/decorators.py](accounts/decorators.py)), `RoleRequiredMixin` family ([accounts/mixins.py](accounts/mixins.py)), `PasswordChangeRequiredMiddleware` forces first-login password change for coaches.

> **Question for you:** QA brief said "3 roles." Do you want the **Headcount** role kept, merged into Admin, or removed? This affects Phase C scope.

---

## 2. Page inventory per role

### ADMIN
| URL | View | Template |
|---|---|---|
| `/accounts/login/` | RoleAwareLoginView ([accounts/views.py:117](accounts/views.py#L117)) | `registration/login.html` |
| `/accounts/dashboard/` | DashboardView ([accounts/views.py:166](accounts/views.py#L166)) | `accounts/dashboard.html` |
| `/accounts/coaches/` | CoachManagementView ([accounts/views.py:732](accounts/views.py#L732)) | `accounts/coach_management.html` |
| `/accounts/coaches/<id>/` | CoachDetailView ([accounts/views.py:765](accounts/views.py#L765)) | `accounts/coach_detail.html` |
| `/accounts/website/` | LandingContentUpdateView ([accounts/views.py:697](accounts/views.py#L697)) | `accounts/website_settings.html` |
| `/members/` | MemberListView | `members/member_list.html` |
| `/members/crm/` | CRMWorkspaceView | `members/crm.html` |
| `/members/create/` | MemberCreateView ([members/views.py:429](members/views.py#L429)) | `members/member_form.html` |
| `/members/<id>/edit/` | MemberUpdateView | `members/member_form.html` |
| `/members/applications/` | AdmissionApplicationListView ([members/views.py:569](members/views.py#L569)) | `members/application_list.html` |
| `/members/applications/<id>/` | AdmissionApplicationReviewView | `members/application_review.html` |
| `/members/reports/` | ProgressReportListView | `members/report_list.html` |
| `/sessions/` | SessionListView ([sessions/views.py:592](sessions/views.py#L592)) | `sessions/session_list.html` |
| `/sessions/create/` | SessionCreateView | `sessions/session_form.html` |
| `/sessions/<id>/attendance/` | AttendanceUpdateView ([sessions/views.py:1164](sessions/views.py#L1164)) | `sessions/attendance_form.html` |
| `/sessions/auto-assign/` | AutoAssignSessionsView ([sessions/views.py:991](sessions/views.py#L991)) | POST only |
| `/finance/invoice-list/` | InvoiceListView | `finance/invoice_list.html` |
| `/finance/billing-settings/` | BillingSettingsView | `finance/billing_settings.html` |
| `/payments/pending-reviews/` | PendingPaymentListView ([payments/views.py:190](payments/views.py#L190)) | `payments/pending_review_list.html` |
| `/payments/review/<id>/` | PaymentReviewView | `payments/payment_form.html` |

### COACH
Dashboard, my-members list, member detail (read-mostly), my progress reports (create/edit), **session checklist (filtered to `coach=user`)**, session plan (AI planner), attendance formset, per-member post-session feedback, filtered invoice list, payroll list, payment history.

### PARENT
Login → **redirects to `/payments/my-payments/` if onboarding fees unpaid** ([accounts/views.py:117](accounts/views.py#L117)). Dashboard, my-children list, add-child application, child detail (read), published reports only, sessions calendar, reschedule (max 2×/session), my-payments hub, submit payment proof.

### HEADCOUNT (sales)
Dashboard (leads pipeline), trial-students list, CRM workspace, application queue (filtered to `assigned_staff=user` or unassigned), application review (approve → trial), lead communication log.

---

## 3. Business-logic audit — **trial / payment flow** (the critical section)

### Pricing found in code
[finance/models.py:88-162](finance/models.py#L88-L162) seeds two plans:

| Code | Name | Sessions/mo | Price |
|---|---|---|---|
| `monthly_4` | Monthly Package — 4 Sessions | 4 | **RM 100.00** |
| `monthly_8` | Monthly Package — 8 Sessions | 8 | **RM 160.00** |

Registration fee: **RM 60.00** + "1 free training jersey" bonus ([finance/models.py:36-38](finance/models.py#L36-L38)).

### What exists today
- `Member.STATUS_TRIAL / ACTIVE / INACTIVE / CHURNED` states defined ([members/models.py:28-39](members/models.py#L28-L39))
- `BillingConfiguration.trial_session_limit` default **1** ([finance/models.py:39](finance/models.py#L39))
- `trial_outcome` tracking exists (pending / converted / no_show / not_ready / declined)
- Trial-limit validation exists **only in the manual session form** ([sessions/forms.py:96-131](sessions/forms.py#L96-L131))

### 🔴 Critical gaps vs your stated requirements

| # | Requirement | Current state | Fix location |
|---|---|---|---|
| **B1** | After trial session attendance ticked → parent becomes inactive | **Not implemented.** AttendanceUpdateView ([sessions/views.py:1188-1201](sessions/views.py#L1188-L1201)) only sets `marked_by`/`marked_at`. No status side-effect. | Add signal on `AttendanceRecord.save()` or post-form hook |
| **B2** | Inactive parents blocked from auto-generated sessions | **Broken.** `auto_assign_monthly_sessions` ([sessions/services.py:1106](sessions/services.py#L1106)) includes `status__in=[ACTIVE, TRIAL]` — trial members get assigned *multiple* sessions beyond the 1-lifetime limit | Filter to ACTIVE-only OR respect `trial_session_limit` inside loop |
| **B3** | Trial is **1 lifetime** (not per month) | Config says 1 but nothing enforces "lifetime" — only checks existing records for the current form | Add lifetime check against `member.attendance_records.count()` regardless of session |
| **B4** | Parents blocked from "requesting sessions" | **Feature doesn't exist.** Parents can reschedule (`ParentRescheduleView` [sessions/views.py:1007](sessions/views.py#L1007)) but cannot request. | No blocking needed — feature absent. Decide: add + block, or skip |
| **B5** | Trial → Active auto-conversion on payment approval | **Manual only.** Admin must edit member status after approving payment. | Hook in `PaymentReviewView` approve path → set `status=ACTIVE`, `subscription_started_at=now` |
| **B6** | Onboarding invoice auto-created on parent self-register | **Missing.** `create_initial_invoices_for_member()` only runs from admin-side member create ([members/views.py:429](members/views.py#L429)). Self-registered parents land with no invoice to pay. | Call in parent-registration `form_valid` |

---

## 4. Parent registration & login flow bugs

- `ParentRegistrationForm.clean_username` ([members/forms.py:134](members/forms.py#L134)) is **case-sensitive** — but `clean_email` is case-insensitive. Inconsistent, allows `Admin` + `admin` collision.
- **No password strength validation** on parent signup (only `password1 == password2`). Django validators aren't applied.
- **No email verification** — account is live immediately on submit.
- `phone_number` optional in form but required on `Member.contact_number` — causes later errors.
- Public signup creates user successfully but **no `Member` row and no invoice** → parent lands on dashboard with nothing to do. Empty-state is confusing.
- Post-login redirect ([accounts/views.py:117](accounts/views.py#L117)) checks "onboarding fees unpaid" but if no invoice exists, the check silently passes → parent never sees the payment page.

---

## 5. UI / responsiveness

**Stack:** custom CSS (no Bootstrap/Tailwind). CSS variables + Grid/Flex in [templates/base.html](templates/base.html).

### Specific responsive problems
- Sidebar `--sidebar-w: 260px` fixed, **no hamburger / mobile collapse** ([templates/base.html:99](templates/base.html#L99))
- Student attendance ring fixed `220×220px` — overflows on mobile ([templates/accounts/partials/student_portal.html:21-22](templates/accounts/partials/student_portal.html#L21-L22))
- Coach dashboard chart fixed `height: 220px` — doesn't scale ([templates/accounts/partials/coach_dashboard.html:231](templates/accounts/partials/coach_dashboard.html#L231))
- `finance/invoice_list.html` + `sessions/session_list.html` tables: **6+ columns, no `overflow-x:auto` wrapper** — hard horizontal scroll on phone
- HTML5 date/time inputs used ([sessions/forms.py:72-75](sessions/forms.py#L72-L75)) — OK on modern browsers but inconsistent iOS behavior
- `FullCalendar` session list has no non-JS fallback

---

## 6. Security & data integrity

| # | Issue | File | Severity |
|---|---|---|---|
| S1 | Media file serving has `@login_required` but **no ownership/role check** — any logged-in coach can download any parent's payment proof if they guess the URL | [nyo_dashboard/media_views.py:12-25](nyo_dashboard/media_views.py#L12-L25) | **MEDIUM** |
| S2 | `Invoice.refresh_status_from_payments()` not auto-called on payment save — scattered manual calls, easy to forget | [payments/views.py](payments/views.py) | **MEDIUM** |
| S3 | `HEADCOUNT` role has no explicit invoice-list filter — can see trial member invoices | [finance/views.py](finance/views.py) | LOW |
| S4 | No DoB sanity check (accepts future dates / 1900) | [members/forms.py](members/forms.py) | LOW |
| S5 | No phone-number format validation | [members/forms.py](members/forms.py) | LOW |
| S6 | No Member status transition validation (INACTIVE → ACTIVE without reason) | [members/models.py](members/models.py) | LOW |

CSRF: ✅ all forms use `{% csrf_token %}`, no `csrf_exempt` found.
XSS: `calendar_events_json|safe` ([sessions/session_list.html:926](templates/sessions/session_list.html#L926)) — safe today (built via `json.dumps`) but fragile.

---

## Critical findings — ranked

1. 🔴 **B1** Attendance tick doesn't flip parent to inactive — **core business rule missing**
2. 🔴 **B2** Auto-assign ignores trial-lifetime limit — trial parents can get many sessions
3. 🔴 **B6** Self-registered parents have no onboarding invoice — payment flow dead
4. 🟡 **B5** Trial→Active conversion is manual
5. 🟡 **S1** Media files leak across roles
6. 🟡 **UI1** Sidebar has no mobile menu
7. 🟢 Minor: password validation, case-sensitive usernames, DoB/phone validation, table mobile overflow

---

## Decisions needed before Phase B

1. **Headcount role** — keep, merge into Admin, or drop?
2. **"Request a session" feature** — build it and then enforce blocking, or skip it entirely? (Currently absent.)
3. **Trial lifetime limit of 1** — confirmed. Should we also add a "trial expires after N days" safety net, or attendance-tick only?
4. **Payment approval → Active** — auto-activate on *any* approved payment, or only when a plan (`monthly_4`/`monthly_8`) invoice is approved?
5. **Inactive parent** — keep booking/reschedule pages visible in read-only with a paywall banner, or hard-redirect to `/payments/my-payments/`?
