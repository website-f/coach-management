from django.contrib.auth.models import Group, Permission

from accounts.models import UserProfile

ROLE_SUPERADMIN = UserProfile.ROLE_SUPERADMIN
ROLE_ADMIN = UserProfile.ROLE_ADMIN
ROLE_COACH = UserProfile.ROLE_COACH
ROLE_PARENT = UserProfile.ROLE_PARENT

# Deprecated alias — headcount role has been merged into admin. Kept so legacy
# imports keep working; resolves to the same string as ROLE_ADMIN.
ROLE_HEADCOUNT = ROLE_ADMIN

ADMIN_ROLES = (ROLE_SUPERADMIN, ROLE_ADMIN)

ROLE_GROUP_MAP = {
    ROLE_SUPERADMIN: "Superadmin",
    ROLE_ADMIN: "Admin",
    ROLE_COACH: "Coach",
    ROLE_PARENT: "Parent",
}

GROUP_ROLE_MAP = {group_name: role for role, group_name in ROLE_GROUP_MAP.items()}

_ADMIN_PERMS = [
    ("members", "member", ["add", "change", "delete", "view"]),
    ("members", "admissionapplication", ["add", "change", "delete", "view"]),
    ("members", "communicationlog", ["add", "change", "delete", "view"]),
    ("members", "progressreport", ["add", "change", "delete", "view"]),
    ("club_sessions", "trainingsession", ["add", "change", "delete", "view"]),
    ("club_sessions", "attendancerecord", ["add", "change", "delete", "view"]),
    ("club_sessions", "syllabusroot", ["add", "change", "delete", "view"]),
    ("club_sessions", "syllabustemplate", ["add", "change", "delete", "view"]),
    ("club_sessions", "syllabusstandard", ["add", "change", "delete", "view"]),
    ("club_sessions", "weeklysyllabus", ["add", "change", "delete", "view"]),
    ("club_sessions", "sessionplannerentry", ["add", "change", "delete", "view"]),
    ("finance", "invoice", ["add", "change", "delete", "view"]),
    ("finance", "expenseentry", ["add", "change", "delete", "view"]),
    ("finance", "payrollrecord", ["add", "change", "delete", "view"]),
    ("finance", "forecastscenario", ["add", "change", "delete", "view"]),
    ("finance", "historicallock", ["add", "change", "delete", "view"]),
    ("finance", "financeauditlog", ["view"]),
    ("finance", "product", ["add", "change", "delete", "view"]),
    ("payments", "payment", ["add", "change", "delete", "view"]),
    ("payments", "qrcode", ["add", "change", "delete", "view"]),
    ("accounts", "landingpagecontent", ["add", "change", "delete", "view"]),
]

GROUP_PERMISSION_MAP = {
    "Superadmin": _ADMIN_PERMS + [
        ("accounts", "userprofile", ["add", "change", "delete", "view"]),
    ],
    "Admin": _ADMIN_PERMS,
    "Coach": [
        ("members", "member", ["change", "view"]),
        ("members", "progressreport", ["add", "change", "view"]),
        ("club_sessions", "trainingsession", ["view"]),
        ("club_sessions", "attendancerecord", ["change", "view"]),
        ("club_sessions", "syllabustemplate", ["view"]),
        ("club_sessions", "syllabusstandard", ["view"]),
        ("club_sessions", "weeklysyllabus", ["view"]),
        ("club_sessions", "sessionplannerentry", ["add", "view"]),
        ("finance", "invoice", ["view"]),
        ("finance", "payrollrecord", ["view"]),
        ("finance", "product", ["view"]),
        ("payments", "payment", ["view"]),
        ("payments", "qrcode", ["view"]),
    ],
    "Parent": [
        ("members", "member", ["view"]),
        ("members", "admissionapplication", ["add", "view"]),
        ("members", "progressreport", ["view"]),
        ("finance", "invoice", ["view"]),
        ("finance", "product", ["view"]),
        ("payments", "payment", ["add", "view"]),
        ("payments", "qrcode", ["view"]),
    ],
}


def get_user_role(user):
    if not getattr(user, "is_authenticated", False):
        return None
    if getattr(user, "is_superuser", False):
        return ROLE_SUPERADMIN
    profile = getattr(user, "profile", None)
    if profile and profile.role:
        return profile.role
    group = user.groups.order_by("name").first()
    return GROUP_ROLE_MAP.get(group.name) if group else None


def get_role_label(role):
    if not role:
        return "Guest"
    return dict(UserProfile.ROLE_CHOICES).get(role, role.title())


def has_role(user, *roles):
    actual = get_user_role(user)
    if actual is None:
        return False
    # Superadmin implicitly satisfies any ROLE_ADMIN requirement.
    if actual == ROLE_SUPERADMIN and ROLE_ADMIN in roles:
        return True
    return actual in roles


def is_admin_user(user):
    """True for superadmin or regular admin."""
    return has_role(user, ROLE_ADMIN)


def is_superadmin_user(user):
    return get_user_role(user) == ROLE_SUPERADMIN


def sync_user_role(user, role=None):
    if not user:
        return
    resolved_role = role or get_user_role(user) or ROLE_PARENT
    target_group_name = ROLE_GROUP_MAP[resolved_role]
    target_group, _ = Group.objects.get_or_create(name=target_group_name)
    managed_groups = list(ROLE_GROUP_MAP.values()) + ["Headcount"]
    existing_groups = list(user.groups.exclude(name__in=managed_groups))
    user.groups.set(existing_groups + [target_group])
    user.is_staff = resolved_role in {ROLE_SUPERADMIN, ROLE_ADMIN, ROLE_COACH} or user.is_superuser
    user.save(update_fields=["is_staff"])


def bootstrap_groups():
    for group_name, permission_specs in GROUP_PERMISSION_MAP.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        permissions = []
        for app_label, model, verbs in permission_specs:
            for verb in verbs:
                codename = f"{verb}_{model}"
                permission = Permission.objects.filter(
                    content_type__app_label=app_label,
                    codename=codename,
                ).first()
                if permission:
                    permissions.append(permission)
        group.permissions.set(permissions)
    # Remove deprecated Headcount group if it still exists
    Group.objects.filter(name="Headcount").delete()
