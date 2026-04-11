from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from accounts.utils import ROLE_ADMIN, ROLE_COACH, ROLE_HEADCOUNT, ROLE_PARENT, has_role


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    allowed_roles = ()
    raise_exception = True

    def test_func(self):
        return has_role(self.request.user, *self.allowed_roles)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect_to_login(self.request.get_full_path())
        raise PermissionDenied("You do not have access to this page.")


class AdminRequiredMixin(RoleRequiredMixin):
    allowed_roles = (ROLE_ADMIN,)


class AdminOrCoachRequiredMixin(RoleRequiredMixin):
    allowed_roles = (ROLE_ADMIN, ROLE_COACH)


class HeadcountOrAboveRequiredMixin(RoleRequiredMixin):
    allowed_roles = (ROLE_ADMIN, ROLE_COACH, ROLE_HEADCOUNT)


class ParentRequiredMixin(RoleRequiredMixin):
    allowed_roles = (ROLE_PARENT,)
