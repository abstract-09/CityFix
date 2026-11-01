import json

from ..constants import DEPARTMENTS


def get_geojson(conn) -> dict:
    row = conn.execute("SELECT geojson FROM boundaries WHERE id = 1").fetchone()
    return json.loads(row["geojson"]) if row else {"type": "FeatureCollection", "features": []}


def set_geojson(conn, geojson: dict, now_iso: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO boundaries (id, geojson, updated_at) VALUES (1, ?, ?)",
        (json.dumps(geojson), now_iso),
    )


def ensure_departments(conn) -> None:
    for name in DEPARTMENTS:
        conn.execute("INSERT OR IGNORE INTO departments (name, email) VALUES (?, NULL)", (name,))


def list_departments(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT name, email FROM departments ORDER BY rowid")]


def set_department_email(conn, name: str, email: str | None) -> bool:
    cur = conn.execute("UPDATE departments SET email = ? WHERE name = ?", (email, name))
    return cur.rowcount > 0
