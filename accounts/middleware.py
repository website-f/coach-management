from django.shortcuts import redirect
from django.urls import reverse


class PasswordChangeRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if getattr(user, "is_authenticated", False):
            profile = getattr(user, "profile", None)
            if getattr(profile, "must_change_password", False):
                allowed_paths = {
                    reverse("accounts:password_change"),
                    reverse("accounts:logout"),
                }
                if request.path not in allowed_paths:
                    return redirect(f"{reverse('accounts:password_change')}?required=1")
        return self.get_response(request)
