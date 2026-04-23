from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from accounts.utils import ROLE_ADMIN, ROLE_COACH, ROLE_PARENT, ROLE_SUPERADMIN, has_role


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
    # has_role auto-passes superadmin when ROLE_ADMIN is in the allowed set.
    allowed_roles = (ROLE_ADMIN,)


class SuperadminRequiredMixin(RoleRequiredMixin):
    allowed_roles = (ROLE_SUPERADMIN,)


class AdminOrCoachRequiredMixin(RoleRequiredMixin):
    allowed_roles = (ROLE_ADMIN, ROLE_COACH)


# Back-compat aliases — headcount was merged into admin.
class SalesOrAdminRequiredMixin(AdminRequiredMixin):
    pass


class HeadcountOrAboveRequiredMixin(AdminOrCoachRequiredMixin):
    pass


class ParentRequiredMixin(RoleRequiredMixin):
    allowed_roles = (ROLE_PARENT,)
