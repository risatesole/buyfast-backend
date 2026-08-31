from rest_framework.decorators import api_view, authentication_classes
from rest_framework.response import Response

from api.utils import CsrfExemptSessionAuthentication
from api.permissions import require_superuser
from accounts.models import AdminActionLog


def _serialize_user_ref(user):
    if not user:
        return {"id": None, "name": "Usuario eliminado", "email": None}
    return {
        "id": user.id,
        "name": f"{user.first_name} {user.last_name}",
        "email": user.email,
    }


def _serialize_log(log):
    return {
        "id": log.id,
        "performed_by": _serialize_user_ref(log.performed_by),
        "target_user": _serialize_user_ref(log.target_user),
        "action": log.action,
        "changes": log.changes,
        "created_at": log.created_at,
    }


@api_view(["GET"])
@authentication_classes([CsrfExemptSessionAuthentication])
def admin_action_logs_view(request):
    """
    GET /api/v1/admin/users/logs/

    Superuser-only audit trail of admin edits to a user's core identity
    (email, password, name, matricula). Query params:
      ?limit=   max number of results (default 20)
      ?offset=  number of results to skip (default 0)
    """
    error = require_superuser(request)
    if error:
        return error

    qs = AdminActionLog.objects.select_related("performed_by", "target_user").all()
    total = qs.count()

    try:
        limit = max(1, int(request.query_params.get("limit", 20)))
    except ValueError:
        limit = 20
    try:
        offset = max(0, int(request.query_params.get("offset", 0)))
    except ValueError:
        offset = 0

    logs = qs[offset: offset + limit]

    return Response({
        "data": [_serialize_log(log) for log in logs],
        "total": total,
    })
