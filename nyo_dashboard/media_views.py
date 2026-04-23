from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.utils._os import safe_join

from accounts.utils import ROLE_ADMIN, has_role


def _payment_proof_visible_to(user, normalized_path):
    """Payment proofs are only visible to admins, the uploader, and the
    assigned coach for the member the invoice belongs to.
    """
    if has_role(user, ROLE_ADMIN):
        return True
    from payments.models import Payment

    # MEDIA_ROOT is stripped — path is the FileField's stored value.
    payment = Payment.objects.filter(proof_image=normalized_path).select_related(
        "paid_by", "invoice__member__assigned_coach", "invoice__member__parent_user"
    ).first()
    if not payment:
        return False
    if payment.paid_by_id == user.id:
        return True
    if payment.invoice.member.parent_user_id == user.id:
        return True
    if payment.invoice.member.assigned_coach_id == user.id:
        return True
    return False


@login_required
def media_file_view(request, path):
    normalized_path = Path(path).as_posix()
    absolute_path = Path(safe_join(str(settings.MEDIA_ROOT), normalized_path))
    if not absolute_path.exists() or not absolute_path.is_file():
        raise Http404("File not found.")

    if normalized_path.startswith("payment_proofs/"):
        if not _payment_proof_visible_to(request.user, normalized_path):
            raise PermissionDenied("You do not have access to this file.")

    return FileResponse(absolute_path.open("rb"))
