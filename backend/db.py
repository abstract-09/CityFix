"""SQLite persistence (stdlib sqlite3). Tickets, events, users, GIS boundaries and settings live here."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticket_id TEXT NOT NULL UNIQUE,
  media_url TEXT NOT NULL,
  media_type TEXT NOT NULL DEFAULT 'image',
  latitude REAL NOT NULL,
  longitude REAL NOT NULL,
  accuracy_m REAL,
  reported_at TEXT NOT NULL,
  category TEXT NOT NULL,
  severity TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Received',
  assigned_department TEXT NOT NULL,
  jurisdiction TEXT,
  description TEXT,
  reporter_contact_enc TEXT,
  resolution_proof_url TEXT,
  resolved_at TEXT,
  report_count INTEGER NOT NULL DEFAULT 1,
  ai_category TEXT, ai_severity TEXT, ai_confidence REAL, ai_description TEXT, ai_mode TEXT,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_dept ON tickets(assigned_department);

CREATE TABLE IF NOT EXISTS ticket_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticket_id TEXT NOT NULL REFERENCES tickets(ticket_id) ON DELETE CASCADE,
  at TEXT NOT NULL,
  kind TEXT NOT NULL,
  status TEXT,
  message TEXT,
  actor TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_ticket ON ticket_events(ticket_id);

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('officer', 'admin')),
  department TEXT
);

CREATE TABLE IF NOT EXISTS boundaries (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  geojson TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS departments (
  name TEXT PRIMARY KEY,
  email TEXT
);

CREATE TABLE IF NOT EXISTS subscriptions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticket_id TEXT NOT NULL REFERENCES tickets(ticket_id) ON DELETE CASCADE,
  phone_enc TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=10, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: str) -> None:
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = connect(path)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.DatabaseError:
        pass
    conn.executescript(SCHEMA)
    conn.close()


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = connect(current_app.extensions["cityfix"].settings.db_path)
    return g.db


def close_db(_exc=None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection):
    """Write transaction that takes the write lock up front (safe ticket-number allocation)."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
