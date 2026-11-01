from flask import request

from ..constants import MSG_TICKET_NOT_FOUND, TICKET_ID_RE
from ..db import get_db
from ..models import ticket as ticket_model
from ..utils.errors import ApiError


def json_body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def load_ticket_or_404(ticket_id: str):
    """Malformed and unknown IDs get the same 404 so nothing is leaked about ID formats."""
    row = ticket_model.get(get_db(), ticket_id) if TICKET_ID_RE.match(ticket_id or "") else None
    if row is None:
        raise ApiError(404, MSG_TICKET_NOT_FOUND)
    return row


def site_base() -> str:
    from flask import current_app
    base = current_app.extensions["cityfix"].settings.public_base_url or request.host_url
    return base.rstrip("/")
