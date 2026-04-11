from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.utils._os import safe_join

from accounts.utils import ROLE_ADMIN, ROLE_COACH, has_role


@login_required
def media_file_view(request, path):
    normalized_path = Path(path).as_posix()
    absolute_path = Path(safe_join(str(settings.MEDIA_ROOT), normalized_path))
    if not absolute_path.exists() or not absolute_path.is_file():
        raise Http404("File not found.")

    if normalized_path.startswith("payment_proofs/") and not has_role(request.user, ROLE_ADMIN, ROLE_COACH):
        raise PermissionDenied("You do not have access to this file.")

    return FileResponse(absolute_path.open("rb"))
