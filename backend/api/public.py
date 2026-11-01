"""Citizen-facing and public endpoints. No authentication, no contact details in any response."""
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request

from ..constants import (CATEGORIES, CONSTANTS, MSG_AI_UNAVAILABLE, STATUSES, TICKET_ID_RE)
from ..db import get_db
from ..models import boundary, ticket as ticket_model
from ..services import ai_service, dashboard_service, routing_service, ticket_service, triage_service
from ..utils import timeutil, uploads
from ..utils.errors import ApiError
from ..utils.ratelimit import rate_limited
from ..utils.validation import parse_coord, validate_contact
from .helpers import json_body, load_ticket_or_404, site_base

bp = Blueprint("public", __name__, url_prefix="/api/v1")


def _ctx():
    return current_app.extensions["cityfix"]


@bp.get("/health")
def health():
    c = _ctx()
    db_state = "ok"
    try:
        get_db().execute("SELECT 1").fetchone()
    except Exception:
        db_state = "error"
    body = {
        "status": "ok" if db_state == "ok" else "degraded",
        "database": db_state,
        "ai_service": ai_service.connectivity_status(c.settings.ai_service_api_key, c.settings.ai_service_url),
        "gis": "local_geojson",
        "time": timeutil.iso(timeutil.now()),
    }
    return jsonify(body), (200 if db_state == "ok" else 503)


@bp.get("/meta")
def meta():
    c = _ctx()
    return jsonify({**CONSTANTS, "max_upload_mb": c.settings.max_upload_mb})


@bp.get("/route-preview")
@rate_limited()
def route_preview():
    lat = parse_coord(request.args.get("latitude"), -90, 90, "Latitude")
    lon = parse_coord(request.args.get("longitude"), -180, 180, "Longitude")
    if lat is None or lon is None:
        raise ApiError(400, "latitude and longitude are required")
    r = routing_service.route_location(lat, lon, boundary.get_geojson(get_db()))
    return jsonify({"assigned_department": r["department"], "jurisdiction": r["jurisdiction"]})


@bp.post("/triage")
@rate_limited()
def triage():
    c = _ctx()
    media, lat, lon, _acc = uploads.parse_report_request(request, c.settings.max_upload_bytes)
    result = triage_service.run(c.settings, media.data, lat, lon)
    routing = routing_service.route_location(lat, lon, boundary.get_geojson(get_db()))
    body = {
        "status": "ok",
        "category": result.category,
        "severity": result.severity,
        "description": result.description,
        "assigned_department": routing["department"],
        "jurisdiction": routing["jurisdiction"],
        "needs_review": result.needs_review,
    }
    if result.failed:
        body.update(status="error", message=MSG_AI_UNAVAILABLE)
        return jsonify(body), 503
    return jsonify(body)


@bp.post("/tickets")
@rate_limited()
def create_ticket():
    c = _ctx()
    media, lat, lon, accuracy = uploads.parse_report_request(request, c.settings.max_upload_bytes)
    category = (request.form.get("category") or "").strip()
    if category in ("", "auto"):
        category = None
    elif category not in CATEGORIES:
        raise ApiError(400, "Category must be one of: " + ", ".join(CATEGORIES))
    contact = validate_contact(request.form.get("contact"))

    result = ticket_service.create_report(
        get_db(), c.settings, c.vault, media=media, lat=lat, lon=lon, accuracy=accuracy,
        category_override=category, contact=contact,
    )
    row = result.row
    base = site_base()
    body = {
        "status": "merged" if result.merged else "created",
        "merged": result.merged,
        "ticket_id": row["ticket_id"],
        "url": f"{base}/#/track/{row['ticket_id']}",
        "api_url": f"{base}/api/v1/tickets/{row['ticket_id']}",
        "category": row["category"],
        "severity": row["severity"],
        "description": row["description"],
        "assigned_department": row["assigned_department"],
        "jurisdiction": row["jurisdiction"],
        "message": result.message,
    }
    if result.triage.failed and not result.merged:
        body["triage_warning"] = MSG_AI_UNAVAILABLE
    return jsonify(body), (200 if result.merged else 201)


@bp.get("/tickets/<ticket_id>")
def get_ticket(ticket_id):
    row = load_ticket_or_404(ticket_id)
    return jsonify(ticket_model.to_public(row, ticket_model.get_events(get_db(), ticket_id)))


@bp.get("/public/dashboard")
def dashboard():
    category = request.args.get("category") or None
    status = request.args.get("status") or None
    if category and category not in CATEGORIES:
        raise ApiError(400, "Unknown category")
    if status and status not in (*STATUSES, "open"):
        raise ApiError(400, "Unknown status")

    where, params = [], []
    if category:
        where.append("category = ?")
        params.append(category)
    if status == "open":
        where.append("status != 'Resolved'")
    elif status:
        where.append("status = ?")
        params.append(status)
    sql = "SELECT * FROM tickets" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY reported_at DESC"

    conn = get_db()
    rows = conn.execute(sql, params).fetchall()
    now_iso = timeutil.iso(timeutil.now())
    return jsonify({
        "generated_at": now_iso,
        "filters": {"category": category, "status": status},
        "tickets": [dashboard_service.ticket_point(r, now_iso) for r in rows],
        "metrics": dashboard_service.compute_metrics(rows, now_iso),
        "boundaries": boundary.get_geojson(conn),
    })


@bp.post("/notifications/subscribe")
@rate_limited()
def subscribe():
    """Stores a phone number for status updates. No SMS provider is wired up in this MVP,
    so the response says so plainly instead of pretending messages will be sent."""
    c = _ctx()
    body = json_body()
    ticket_id = str(body.get("ticket_id") or "")
    load_ticket_or_404(ticket_id)
    if body.get("consent") is not True:
        raise ApiError(400, "Please confirm you agree to receive status updates")
    phone = validate_contact(body.get("phone"))
    if not phone or "@" in phone:
        raise ApiError(400, "Please enter a 10-digit phone number")
    conn = get_db()
    if conn.execute("SELECT COUNT(*) FROM subscriptions WHERE ticket_id = ?", (ticket_id,)).fetchone()[0] >= 5:
        raise ApiError(429, "This ticket already has the maximum number of subscribers")
    conn.execute("INSERT INTO subscriptions (ticket_id, phone_enc, created_at) VALUES (?, ?, ?)",
                 (ticket_id, c.vault.encrypt(phone), timeutil.iso(timeutil.now())))
    return jsonify({
        "status": "subscribed",
        "delivery": "not_configured",
        "message": "Your number is saved, but SMS delivery is not configured on this server yet, so no messages will be sent.",
    }), 201
