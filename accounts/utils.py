from django.contrib.auth.models import Group, Permission

from accounts.models import UserProfile

ROLE_ADMIN = UserProfile.ROLE_ADMIN
ROLE_COACH = UserProfile.ROLE_COACH
ROLE_HEADCOUNT = UserProfile.ROLE_HEADCOUNT
ROLE_PARENT = UserProfile.ROLE_PARENT

ROLE_GROUP_MAP = {
    ROLE_ADMIN: "Admin",
    ROLE_COACH: "Coach",
    ROLE_HEADCOUNT: "Headcount",
    ROLE_PARENT: "Parent",
}

GROUP_ROLE_MAP = {group_name: role for role, group_name in ROLE_GROUP_MAP.items()}

GROUP_PERMISSION_MAP = {
    "Admin": [
        ("members", "member", ["add", "change", "delete", "view"]),
        ("members", "admissionapplication", ["add", "change", "delete", "view"]),
        ("members", "progressreport", ["add", "change", "delete", "view"]),
        ("club_sessions", "trainingsession", ["add", "change", "delete", "view"]),
        ("club_sessions", "attendancerecord", ["add", "change", "delete", "view"]),
        ("finance", "invoice", ["add", "change", "delete", "view"]),
        ("finance", "product", ["add", "change", "delete", "view"]),
        ("payments", "payment", ["add", "change", "delete", "view"]),
        ("payments", "qrcode", ["add", "change", "delete", "view"]),
        ("accounts", "userprofile", ["add", "change", "delete", "view"]),
        ("accounts", "landingpagecontent", ["add", "change", "delete", "view"]),
    ],
    "Coach": [
        ("members", "member", ["add", "change", "view"]),
        ("members", "admissionapplication", ["add", "change", "view"]),
        ("members", "progressreport", ["add", "change", "view"]),
        ("club_sessions", "trainingsession", ["add", "change", "view"]),
        ("club_sessions", "attendancerecord", ["add", "change", "view"]),
        ("finance", "invoice", ["add", "change", "view"]),
        ("finance", "product", ["view"]),
        ("payments", "payment", ["add", "change", "view"]),
        ("payments", "qrcode", ["add", "change", "view"]),
    ],
    "Headcount": [
        ("members", "member", ["view"]),
        ("club_sessions", "trainingsession", ["view"]),
        ("club_sessions", "attendancerecord", ["change", "view"]),
        ("finance", "product", ["view"]),
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
        return ROLE_ADMIN
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
    return get_user_role(user) in roles


def sync_user_role(user, role=None):
    if not user:
        return
    resolved_role = role or get_user_role(user) or ROLE_PARENT
    target_group_name = ROLE_GROUP_MAP[resolved_role]
    target_group, _ = Group.objects.get_or_create(name=target_group_name)
    managed_groups = ROLE_GROUP_MAP.values()
    existing_groups = list(user.groups.exclude(name__in=managed_groups))
    user.groups.set(existing_groups + [target_group])
    user.is_staff = resolved_role in {ROLE_ADMIN, ROLE_COACH, ROLE_HEADCOUNT} or user.is_superuser
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
