"""Reference data + demo data. Safe to run repeatedly."""
from __future__ import annotations

import json
import random
import secrets
from datetime import timedelta
from pathlib import Path

from ..constants import (CATEGORIES, DEPT_GENERAL, DEPT_MUNICIPAL, DEPT_NHAI, DEPT_RCD, SHARED_DIR)
from ..db import connect, transaction
from ..models import boundary, ticket as ticket_model, user as user_model
from ..utils import timeutil
from . import routing_service

DEMO_USERS = [
    ("officer_rcd", "officer", DEPT_RCD),
    ("officer_nhai", "officer", DEPT_NHAI),
    ("officer_municipal", "officer", DEPT_MUNICIPAL),
    ("officer_general", "officer", DEPT_GENERAL),
    ("admin", "admin", None),
]

DESCRIPTIONS = {
    "Road Damage": ["Deep pothole on the carriageway", "Cracked and sunken road surface", "Broken road edge near a junction"],
    "Water Leak": ["Pipe leaking onto the street", "Valve leaking near the footpath"],
    "Streetlight Defect": ["Streetlight not working after dark", "Flickering lamp on a busy road"],
    "Waste Management": ["Garbage heap blocking the lane", "Overflowing community bin"],
    "Drainage Overflow": ["Drain overflowing onto the road", "Blocked drain causing waterlogging"],
    "Other": ["Issue needs manual review"],
}


def load_json(name: str):
    return json.loads((SHARED_DIR / name).read_text(encoding="utf-8"))


def ensure_reference_data(conn) -> None:
    """Boundaries and department rows must exist for routing to work."""
    if conn.execute("SELECT 1 FROM boundaries WHERE id = 1").fetchone() is None:
        boundary.set_geojson(conn, load_json("boundaries.demo.geojson"), timeutil.iso(timeutil.now()))
    boundary.ensure_departments(conn)


def _insert_sample(conn, vault, sample: dict, geojson: dict) -> None:
    routing = routing_service.route_location(sample["latitude"], sample["longitude"], geojson)
    ticket_model.insert(conn, {
        "ticket_id": sample["ticket_id"],
        "media_url": sample["media_url"],
        "media_type": "image",
        "latitude": sample["latitude"],
        "longitude": sample["longitude"],
        "reported_at": sample["reported_at"],
        "category": sample["category"],
        "severity": sample["severity"],
        "status": sample["status"],
        "assigned_department": sample["assigned_department"],
        "jurisdiction": routing["jurisdiction"],
        "description": sample["description"],
        "reporter_contact_enc": vault.encrypt(sample.get("reporter_contact")),
        "resolution_proof_url": sample.get("resolution_proof_url"),
        "resolved_at": sample.get("resolved_at"),
        "ai_mode": "seed",
        "updated_at": sample.get("resolved_at") or sample["reported_at"],
    })
    for ev in sample["history"]:
        ticket_model.add_event(conn, sample["ticket_id"], ev["at"], ev["kind"], ev["status"], ev["message"], ev["actor"])


def _insert_generated(conn, vault, geojson, count: int, rng: random.Random) -> int:
    now = timeutil.now()
    made = 0
    for n in range(count):
        lat = round(rng.uniform(25.545, 25.575), 6)
        lon = round(rng.uniform(84.838, 84.868), 6)
        category = rng.choice(CATEGORIES)
        severity = rng.choices(["Low", "Medium", "Critical"], weights=[4, 4, 2])[0]
        status = rng.choices(["Received", "In Progress", "Resolved"], weights=[4, 3, 4])[0]
        reported = now - timedelta(hours=rng.randint(2, 20 * 24))
        routing = routing_service.route_location(lat, lon, geojson)
        reported_iso = timeutil.iso(reported)
        resolved_iso = proof = None
        if status == "Resolved":
            resolved = min(now, reported + timedelta(hours=rng.randint(4, 200)))
            resolved_iso = timeutil.iso(resolved)
            proof = "https://storage.cityfix.local/samples/generated_fixed.jpg"
        ticket_id = ticket_model.next_ticket_id(conn, reported.year)
        ticket_model.insert(conn, {
            "ticket_id": ticket_id, "media_url": f"https://storage.cityfix.local/samples/generated-{n + 1}.jpg",
            "media_type": "image", "latitude": lat, "longitude": lon, "reported_at": reported_iso,
            "category": category, "severity": severity, "status": status,
            "assigned_department": routing["department"], "jurisdiction": routing["jurisdiction"],
            "description": rng.choice(DESCRIPTIONS[category]), "reporter_contact_enc": None,
            "resolution_proof_url": proof, "resolved_at": resolved_iso,
            "ai_mode": "seed", "updated_at": resolved_iso or reported_iso,
        })
        ticket_model.add_event(conn, ticket_id, reported_iso, "created", "Received",
                               f"Report received and routed to {routing['department']}.", "system")
        if status != "Received":
            ticket_model.add_event(conn, ticket_id, reported_iso, "status_change", "In Progress",
                                   "Work has started.", routing["department"])
        if resolved_iso:
            ticket_model.add_event(conn, ticket_id, resolved_iso, "status_change", "Resolved",
                                   "Marked resolved. Photo proof attached.", routing["department"])
        made += 1
    return made


def seed(conn, vault, settings, *, reset: bool = False, extra: int = 0, create_users: bool = True) -> dict:
    """Returns {"tickets": int, "credentials": {username: password}} (credentials only for newly created users)."""
    extra = max(0, min(int(extra), 200))
    created_users: dict[str, str] = {}
    with transaction(conn):
        if reset:
            conn.execute("DELETE FROM subscriptions")
            conn.execute("DELETE FROM ticket_events")
            conn.execute("DELETE FROM tickets")
            conn.execute("DELETE FROM boundaries")
        ensure_reference_data(conn)
        geojson = boundary.get_geojson(conn)

        if create_users:
            password = settings.demo_user_password or secrets.token_urlsafe(9)
            for username, role, dept in DEMO_USERS:
                if user_model.create_user(conn, username, password, role, dept, settings.password_hash_method):
                    created_users[username] = password

        inserted = 0
        if conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 0:
            for sample in load_json("sample_tickets.json"):
                _insert_sample(conn, vault, sample, geojson)
                inserted += 1
        if extra:
            inserted += _insert_generated(conn, vault, geojson, extra, random.Random(42))
    return {"tickets": inserted, "credentials": created_users}


def seed_app(app, *, reset: bool = False, extra: int = 0, quiet: bool = False) -> dict:
    """Seeds using the app's own settings. Writes new demo credentials to instance/demo_credentials.txt."""
    c = app.extensions["cityfix"]
    conn = connect(c.settings.db_path)
    try:
        result = seed(conn, c.vault, c.settings, reset=reset, extra=extra)
    finally:
        conn.close()
    creds = result["credentials"]
    if creds and not quiet:
        path = Path(c.settings.instance_dir) / "demo_credentials.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["CityFix demo logins (local demo only - never reuse these):"] + [f"  {u} / {p}" for u, p in creds.items()]
        path.write_text("\n".join(lines) + "\n")
        print("\n".join(lines))
        print(f"  (saved to {path})")
    return result
