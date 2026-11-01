"""Public dashboard data and SLA metrics."""
from __future__ import annotations

from ..constants import DEPARTMENTS, MARKER_COLORS
from ..models import ticket as ticket_model
from ..utils import timeutil


def marker_for(row) -> str:
    return MARKER_COLORS["Resolved"] if row["status"] == "Resolved" else MARKER_COLORS[row["severity"]]


def ticket_point(row, now_iso: str) -> dict:
    return {
        "ticket_id": row["ticket_id"],
        "latitude": round(row["latitude"], 6),
        "longitude": round(row["longitude"], 6),
        "category": row["category"],
        "severity": row["severity"],
        "status": row["status"],
        "assigned_department": row["assigned_department"],
        "reported_at": row["reported_at"],
        "resolved_at": row["resolved_at"],
        "description": row["description"],
        "report_count": row["report_count"],
        "marker": marker_for(row),
        "elapsed_hours": ticket_model.elapsed_hours(row, now_iso),
    }


def compute_metrics(rows, now_iso: str) -> dict:
    per_dept = {d: {"open": 0, "resolved": 0, "resolved_hours": 0.0, "open_hours": 0.0} for d in DEPARTMENTS}
    for r in rows:
        bucket = per_dept.setdefault(r["assigned_department"], {"open": 0, "resolved": 0, "resolved_hours": 0.0, "open_hours": 0.0})
        hours = timeutil.hours_between(r["reported_at"], r["resolved_at"] or now_iso)
        if r["status"] == "Resolved":
            bucket["resolved"] += 1
            bucket["resolved_hours"] += hours
        else:
            bucket["open"] += 1
            bucket["open_hours"] += hours

    departments = []
    for name, b in per_dept.items():
        departments.append({
            "department": name,
            "open": b["open"],
            "resolved": b["resolved"],
            # average = total resolved SLA hours / resolved ticket count
            "avg_resolution_hours": round(b["resolved_hours"] / b["resolved"], 2) if b["resolved"] else None,
            "avg_open_age_hours": round(b["open_hours"] / b["open"], 2) if b["open"] else None,
        })

    total_resolved = sum(b["resolved"] for b in per_dept.values())
    total_hours = sum(b["resolved_hours"] for b in per_dept.values())
    return {
        "total_tickets": len(rows),
        "open_tickets": sum(b["open"] for b in per_dept.values()),
        "resolved_tickets": total_resolved,
        "avg_resolution_hours": round(total_hours / total_resolved, 2) if total_resolved else None,
        "departments": departments,
    }
