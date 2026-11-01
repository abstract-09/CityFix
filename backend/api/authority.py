"""Officer sign-in and the authority action portal."""
from flask import Blueprint, current_app, g, jsonify, request

from ..constants import MSG_PROOF_REQUIRED, STATUSES
from ..db import get_db
from ..models import ticket as ticket_model, user as user_model
from ..services import ticket_service
from ..utils import uploads
from ..utils.auth import issue_token, require_role
from ..utils.errors import ApiError
from ..utils.ratelimit import rate_limited
from ..utils.validation import clean_text
from .helpers import json_body, load_ticket_or_404

bp = Blueprint("authority", __name__, url_prefix="/api/v1")


def _user_view(user: dict) -> dict:
    return {"username": user["username"], "role": user["role"], "department": user["department"]}


@bp.post("/auth/login")
@rate_limited("login")
def login():
    body = json_body()
    row = user_model.authenticate(get_db(), str(body.get("username") or ""), str(body.get("password") or ""))
    if row is None:
        raise ApiError(401, "Incorrect username or password")
    return jsonify({"token": issue_token(row["id"]), "user": _user_view(dict(row))})


@bp.get("/auth/me")
def me():
    from ..utils.auth import current_user
    user = current_user()
    if user is None:
        raise ApiError(401, "Please sign in to continue")
    return jsonify({"user": _user_view(user)})


def _own_ticket(ticket_id: str):
    row = load_ticket_or_404(ticket_id)
    if row["assigned_department"] != g.user["department"]:
        raise ApiError(403, "This ticket is assigned to another department")
    return row


@bp.get("/authority/tickets")
@require_role("officer")
def queue():
    status = request.args.get("status") or None
    if status and status not in STATUSES:
        raise ApiError(400, "Unknown status")
    sql = "SELECT * FROM tickets WHERE assigned_department = ?"
    params = [g.user["department"]]
    if status:
        sql += " AND status = ?"
        params.append(status)
    # Open tickets first, then severity, then most-reported, then oldest first.
    sql += (f" ORDER BY (status = 'Resolved'), {ticket_model.queue_order_sql()}, report_count DESC, reported_at ASC")
    rows = get_db().execute(sql, params).fetchall()
    return jsonify({"department": g.user["department"], "tickets": [ticket_model.to_public(r) for r in rows]})


@bp.patch("/authority/tickets/<ticket_id>")
@require_role("officer")
def update_status(ticket_id):
    row = _own_ticket(ticket_id)
    body = json_body()
    target = body.get("status")
    note = clean_text(body.get("note"), 300) or None
    if target not in STATUSES:
        raise ApiError(400, "Status must be one of: " + ", ".join(STATUSES))
    if target == "Resolved":
        raise ApiError(422, MSG_PROOF_REQUIRED)  # closing needs the /resolve endpoint with a photo
    if target == "Received" or row["status"] == "Resolved":
        raise ApiError(422, "A ticket cannot move backwards")
    updated = ticket_service.start_work(get_db(), ticket_id, note)
    return jsonify(ticket_model.to_public(updated, ticket_model.get_events(get_db(), ticket_id)))


@bp.patch("/authority/tickets/<ticket_id>/resolve")
@require_role("officer")
def resolve(ticket_id):
    c = current_app.extensions["cityfix"]
    _own_ticket(ticket_id)
    proof = request.files.get("resolution_proof")
    if proof is None or not proof.filename:
        raise ApiError(422, MSG_PROOF_REQUIRED)
    data = uploads.read_limited(proof, c.settings.max_upload_bytes)
    if not data:
        raise ApiError(422, MSG_PROOF_REQUIRED)
    media = uploads.classify(data, proof.filename, uploads.IMAGE_TYPES)  # proof must be a photo
    note = clean_text(request.form.get("note"), 300) or None

    saved = uploads.save_media(media, c.settings.upload_dir)
    try:
        updated = ticket_service.resolve(get_db(), ticket_id, saved, note)
    except Exception:
        uploads.remove_media(saved, c.settings.upload_dir)
        raise
    return jsonify(ticket_model.to_public(updated, ticket_model.get_events(get_db(), ticket_id)))


@bp.post("/authority/tickets/<ticket_id>/info-request")
@require_role("officer")
def info_request(ticket_id):
    _own_ticket(ticket_id)
    message = clean_text(json_body().get("message"), 300)
    if len(message) < 5:
        raise ApiError(400, "Please write what information you need (at least 5 characters)")
    updated = ticket_service.request_info(get_db(), ticket_id, message)
    return jsonify(ticket_model.to_public(updated, ticket_model.get_events(get_db(), ticket_id)))
