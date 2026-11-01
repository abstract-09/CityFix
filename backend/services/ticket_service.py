"""Ticket creation (with duplicate merging) and the officer-driven status lifecycle."""
from __future__ import annotations

from dataclasses import dataclass

from ..constants import (DUPLICATE_RADIUS_M, MSG_DUPLICATE, MSG_TICKET_NOT_FOUND)
from ..db import transaction
from ..models import boundary, ticket as ticket_model
from ..utils import timeutil, uploads
from ..utils.errors import ApiError
from . import routing_service, triage_service


@dataclass
class CreateResult:
    merged: bool
    row: object
    triage: triage_service.TriageResult
    routing: dict
    message: str


def create_report(conn, settings, vault, *, media, lat, lon, accuracy, category_override, contact) -> CreateResult:
    triage = triage_service.run(settings, media.data, lat, lon)
    category = category_override or triage.category
    routing = routing_service.route_location(lat, lon, boundary.get_geojson(conn))
    now = timeutil.now()
    now_iso = timeutil.iso(now)

    saved = None
    try:
        with transaction(conn):
            dup = ticket_model.find_duplicate(conn, lat, lon, category, DUPLICATE_RADIUS_M)
            if dup:
                conn.execute(
                    "UPDATE tickets SET report_count = report_count + 1, updated_at = ? WHERE ticket_id = ?",
                    (now_iso, dup["ticket_id"]),
                )
                ticket_model.add_event(conn, dup["ticket_id"], now_iso, "duplicate_report", dup["status"],
                                       "Another nearby report was merged into this ticket.", "system")
                return CreateResult(True, ticket_model.get(conn, dup["ticket_id"]), triage, routing, MSG_DUPLICATE)

            ticket_id = ticket_model.next_ticket_id(conn, now.year)
            saved = uploads.save_media(media, settings.upload_dir)
            ticket_model.insert(conn, {
                "ticket_id": ticket_id,
                "media_url": saved,
                "media_type": media.kind,
                "latitude": lat,
                "longitude": lon,
                "accuracy_m": accuracy,
                "reported_at": now_iso,
                "category": category,
                "severity": triage.severity,
                "status": "Received",
                "assigned_department": routing["department"],
                "jurisdiction": routing["jurisdiction"],
                "description": triage.description,
                "reporter_contact_enc": vault.encrypt(contact),
                "ai_category": triage.ai_category,
                "ai_severity": triage.ai_severity,
                "ai_confidence": triage.confidence,
                "ai_description": triage.ai_description,
                "ai_mode": triage.mode,
                "updated_at": now_iso,
            })
            ticket_model.add_event(conn, ticket_id, now_iso, "created", "Received",
                                   f"Report received and routed to {routing['department']}.", "system")
            return CreateResult(False, ticket_model.get(conn, ticket_id), triage, routing,
                                "Your report has been received.")
    except Exception:
        if saved:
            uploads.remove_media(saved, settings.upload_dir)
        raise


def _must_get(conn, ticket_id):
    row = ticket_model.get(conn, ticket_id)
    if row is None:
        raise ApiError(404, MSG_TICKET_NOT_FOUND)
    return row


def start_work(conn, ticket_id: str, note: str | None):
    now_iso = timeutil.iso(timeutil.now())
    with transaction(conn):
        row = _must_get(conn, ticket_id)
        if row["status"] == "Resolved":
            raise ApiError(422, "Resolved tickets cannot be reopened")
        if row["status"] == "In Progress":
            raise ApiError(422, "Ticket is already In Progress")
        conn.execute("UPDATE tickets SET status = 'In Progress', updated_at = ? WHERE ticket_id = ?",
                     (now_iso, ticket_id))
        ticket_model.add_event(conn, ticket_id, now_iso, "status_change", "In Progress",
                               note or "Work has started.", row["assigned_department"])
    return ticket_model.get(conn, ticket_id)


def resolve(conn, ticket_id: str, proof_url: str, note: str | None):
    now_iso = timeutil.iso(timeutil.now())
    with transaction(conn):
        row = _must_get(conn, ticket_id)
        if row["status"] == "Resolved":
            raise ApiError(422, "Ticket is already resolved")
        if row["status"] != "In Progress":
            raise ApiError(422, "Move the ticket to In Progress before resolving it")
        conn.execute(
            "UPDATE tickets SET status = 'Resolved', resolution_proof_url = ?, resolved_at = ?, updated_at = ? "
            "WHERE ticket_id = ?", (proof_url, now_iso, now_iso, ticket_id))
        ticket_model.add_event(conn, ticket_id, now_iso, "status_change", "Resolved",
                               note or "Marked resolved. Photo proof attached.", row["assigned_department"])
    return ticket_model.get(conn, ticket_id)


def request_info(conn, ticket_id: str, message: str):
    now_iso = timeutil.iso(timeutil.now())
    with transaction(conn):
        row = _must_get(conn, ticket_id)
        if row["status"] == "Resolved":
            raise ApiError(422, "Resolved tickets cannot receive information requests")
        ticket_model.add_event(conn, ticket_id, now_iso, "info_request", row["status"], message,
                               row["assigned_department"])
    return ticket_model.get(conn, ticket_id)
