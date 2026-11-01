"""System administrator endpoints: AI inspection, contact details, routing config, demo data."""
import re

from flask import Blueprint, current_app, jsonify, request

from ..constants import DEPARTMENTS
from ..db import get_db
from ..models import boundary, ticket as ticket_model
from ..services import routing_service, seed_service
from ..utils import timeutil
from ..utils.auth import require_role
from ..utils.errors import ApiError
from .helpers import json_body

bp = Blueprint("admin", __name__, url_prefix="/api/v1/admin")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)+$")


@bp.get("/tickets")
@require_role("admin")
def tickets():
    vault = current_app.extensions["cityfix"].vault
    rows = get_db().execute("SELECT * FROM tickets ORDER BY reported_at DESC").fetchall()
    return jsonify({"tickets": [ticket_model.to_admin(r, vault) for r in rows]})


@bp.get("/boundaries")
@require_role("admin")
def get_boundaries():
    return jsonify(boundary.get_geojson(get_db()))


@bp.put("/boundaries")
@require_role("admin")
def put_boundaries():
    data = routing_service.validate_boundaries(request.get_json(silent=True))
    boundary.set_geojson(get_db(), data, timeutil.iso(timeutil.now()))
    return jsonify({"status": "saved", "features": len(data["features"])})


@bp.get("/departments")
@require_role("admin")
def departments():
    return jsonify({"departments": boundary.list_departments(get_db())})


@bp.put("/departments/<path:name>")
@require_role("admin")
def put_department(name):
    if name not in DEPARTMENTS:
        raise ApiError(404, "Unknown department")
    email = str(json_body().get("email") or "").strip()
    if email and (len(email) > 254 or not EMAIL_RE.match(email)):
        raise ApiError(400, "Please enter a valid email address")
    boundary.set_department_email(get_db(), name, email or None)
    return jsonify({"status": "saved", "department": name, "email": email or None})


@bp.post("/seed")
@require_role("admin")
def seed():
    body = json_body()
    try:
        extra = int(body.get("extra", 0))
    except (TypeError, ValueError):
        raise ApiError(400, "extra must be a whole number")
    if not 0 <= extra <= 200:
        raise ApiError(400, "extra must be between 0 and 200")
    result = seed_service.seed_app(current_app, reset=bool(body.get("reset")), extra=extra, quiet=True)
    return jsonify({"status": "seeded", "tickets_added": result["tickets"]})
