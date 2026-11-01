"""Ticket data access and serialisation. Public serialisers never include contact details."""
from __future__ import annotations

import math

from flask import current_app, has_request_context, request

from ..constants import SEVERITY_RANK
from ..utils import timeutil
from ..utils.geo import haversine_m


def abs_url(path: str | None) -> str | None:
    if not path or path.startswith(("http://", "https://")):
        return path
    base = None
    if has_request_context():
        base = current_app.extensions["cityfix"].settings.public_base_url or request.host_url
    return (base or "").rstrip("/") + path


def next_ticket_id(conn, year: int) -> str:
    row = conn.execute(
        "SELECT MAX(CAST(SUBSTR(ticket_id, 10) AS INTEGER)) AS n FROM tickets WHERE ticket_id LIKE ?",
        (f"CIV-{year}-%",),
    ).fetchone()
    return f"CIV-{year}-{(row['n'] or 0) + 1:04d}"


def insert(conn, values: dict) -> None:
    cols = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    conn.execute(f"INSERT INTO tickets ({cols}) VALUES ({marks})", list(values.values()))


def add_event(conn, ticket_id, at, kind, status, message, actor) -> None:
    conn.execute(
        "INSERT INTO ticket_events (ticket_id, at, kind, status, message, actor) VALUES (?, ?, ?, ?, ?, ?)",
        (ticket_id, at, kind, status, message, actor),
    )


def get(conn, ticket_id: str):
    return conn.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()


def get_events(conn, ticket_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT at, kind, status, message, actor FROM ticket_events WHERE ticket_id = ? ORDER BY id",
        (ticket_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def find_duplicate(conn, lat, lon, category, radius_m):
    """Nearest active (not Resolved) ticket of the same category within radius_m."""
    dlat = radius_m / 111_000.0
    dlon = radius_m / (111_000.0 * max(0.01, math.cos(math.radians(lat))))
    rows = conn.execute(
        "SELECT * FROM tickets WHERE status != 'Resolved' AND category = ? "
        "AND latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?",
        (category, lat - dlat, lat + dlat, lon - dlon, lon + dlon),
    ).fetchall()
    best, best_d = None, None
    for r in rows:
        d = haversine_m(lat, lon, r["latitude"], r["longitude"])
        if d <= radius_m and (best_d is None or d < best_d):
            best, best_d = r, d
    return best


def elapsed_hours(row, now_iso: str) -> float:
    return round(timeutil.hours_between(row["reported_at"], row["resolved_at"] or now_iso), 2)


def queue_order_sql() -> str:
    return ("CASE severity WHEN 'Critical' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END")


def to_public(row, events=None) -> dict:
    now_iso = timeutil.iso(timeutil.now())
    data = {
        "ticket_id": row["ticket_id"],
        "media_url": abs_url(row["media_url"]),
        "media_type": row["media_type"],
        "latitude": round(row["latitude"], 6),
        "longitude": round(row["longitude"], 6),
        "reported_at": row["reported_at"],
        "category": row["category"],
        "severity": row["severity"],
        "status": row["status"],
        "assigned_department": row["assigned_department"],
        "jurisdiction": row["jurisdiction"],
        "description": row["description"],
        "resolution_proof_url": abs_url(row["resolution_proof_url"]),
        "resolved_at": row["resolved_at"],
        "report_count": row["report_count"],
        "elapsed_hours": elapsed_hours(row, now_iso),
    }
    if events is not None:
        data["history"] = events
    return data


def to_admin(row, vault, events=None) -> dict:
    data = to_public(row, events)
    contact = vault.decrypt(row["reporter_contact_enc"])
    data.update(
        reporter_contact=contact,
        ai={
            "category": row["ai_category"],
            "severity": row["ai_severity"],
            "confidence": row["ai_confidence"],
            "description": row["ai_description"],
            "mode": row["ai_mode"],
        },
        accuracy_m=row["accuracy_m"],
    )
    return data
