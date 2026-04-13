from django import template

register = template.Library()


STATUS_BADGE_CLASSES = {
    "active":               "badge-success",
    "inactive":             "badge-neutral",
    "suspended":            "badge-danger",
    "paid":                 "badge-success",
    "approved":             "badge-success",
    "pending":              "badge-warning",
    "pending verification": "badge-warning",
    "pending_verification": "badge-warning",
    "rejected":             "badge-danger",
    "unpaid":               "badge-neutral",
    "overdue":              "badge-danger",
    "present":              "badge-success",
    "late":                 "badge-info",
    "absent":               "badge-danger",
    "scheduled":            "badge-neutral",
    "elite":                "badge-success",
    "advanced":             "badge-info",
    "developing":           "badge-warning",
    "foundation":           "badge-neutral",
    "ready":                "badge-success",
    "preorder":             "badge-warning",
    "sold out":             "badge-danger",
    "sold_out":             "badge-danger",
    "draft":                "badge-neutral",
    "published":            "badge-success",
}


@register.simple_tag(takes_context=True)
def nav_active(context, url_prefix):
    request = context["request"]
    path = request.path
    if path == url_prefix or path.startswith(url_prefix):
        return "active"
    return ""


@register.simple_tag(takes_context=True)
def nav_active_section(context, url_prefix, *excluded_prefixes):
    request = context["request"]
    path = request.path
    if any(path == excluded or path.startswith(excluded) for excluded in excluded_prefixes):
        return ""
    if path == url_prefix or path.startswith(url_prefix):
        return "active"
    return ""


@register.simple_tag(takes_context=True)
def nav_active_exact(context, url_value):
    request = context["request"]
    if request.path == url_value:
        return "active"
    return ""


@register.filter
def status_badge(value):
    key = str(value).replace("_", " ").lower()
    return STATUS_BADGE_CLASSES.get(key, "badge-neutral")


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    query = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            query.pop(key, None)
        else:
            query[key] = value
    return query.urlencode()
