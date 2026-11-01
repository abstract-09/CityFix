"""Flask application factory: API + static frontend + uploaded media, one process."""
from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, jsonify, request, send_from_directory
from itsdangerous import URLSafeTimedSerializer
from werkzeug.exceptions import HTTPException

from .api import ALL_BLUEPRINTS
from .config import Settings
from .constants import MSG_SYSTEM_ERROR, ROOT, msg_too_large
from .db import close_db, connect, init_db
from .services import seed_service
from .utils.crypto import ContactVault, load_or_create_secrets
from .utils.errors import ApiError
from .utils.logging_utils import install_log_masking
from .utils.ratelimit import RateLimiter

log = logging.getLogger("cityfix")
MEDIA_NAME_RE = re.compile(r"^[a-f0-9]{32}\.(jpg|png|mp3|wav|m4a)$")

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src https://fonts.gstatic.com; img-src 'self' data: blob: https:; media-src 'self' blob: https:; "
       "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")


def _frontend_dir() -> Path:
    dist = ROOT / "frontend" / "dist"
    return dist if (dist / "index.html").exists() else ROOT / "frontend"


def create_app(overrides: dict | None = None, dotenv: bool = True) -> Flask:
    settings = Settings.load(overrides, dotenv=dotenv)
    install_log_masking()

    app = Flask(__name__, static_folder=None)
    # Allow the 10 MB file plus multipart overhead; the per-file check gives the precise 413.
    app.config["MAX_CONTENT_LENGTH"] = settings.max_upload_bytes + 1024 * 1024

    secrets = load_or_create_secrets(settings.instance_dir)
    app.extensions["cityfix"] = SimpleNamespace(
        settings=settings,
        vault=ContactVault(secrets["fernet_key"]),
        serializer=URLSafeTimedSerializer(secrets["secret_key"], salt="cityfix-auth"),
        limiter=RateLimiter(),
    )

    init_db(settings.db_path)
    conn = connect(settings.db_path)
    try:
        seed_service.ensure_reference_data(conn)
    finally:
        conn.close()

    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)
    app.teardown_appcontext(close_db)
    _register_errors(app)
    _register_hooks(app)
    _register_static(app)

    if settings.auto_seed:
        seed_service.seed_app(app, reset=False, extra=0)
    return app


def _register_errors(app: Flask) -> None:
    def respond(status: int, message: str, **extra):
        body = {"status": "error", "code": status, "message": message, "error": message, **extra}
        return jsonify(body), status

    @app.errorhandler(ApiError)
    def api_error(e: ApiError):
        return respond(e.status, e.message, **e.extra)

    @app.errorhandler(HTTPException)
    def http_error(e: HTTPException):
        if e.code == 413:
            mb = app.extensions["cityfix"].settings.max_upload_mb
            return respond(413, msg_too_large(mb))
        messages = {404: "Not found", 405: "Method not allowed", 400: "Bad request"}
        return respond(e.code or 500, messages.get(e.code, e.name))

    @app.errorhandler(sqlite3.Error)
    def db_error(e):
        log.error("database error: %s", type(e).__name__)
        return respond(500, MSG_SYSTEM_ERROR)

    @app.errorhandler(Exception)
    def unexpected(e):
        log.exception("unhandled error")
        return respond(500, MSG_SYSTEM_ERROR)


def _register_hooks(app: Flask) -> None:
    @app.after_request
    def headers(resp):
        origin = request.headers.get("Origin")
        if origin and origin in app.extensions["cityfix"].settings.allowed_origins:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, PUT, OPTIONS"
            resp.headers.add("Vary", "Origin")
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        resp.headers.setdefault("Content-Security-Policy", CSP)
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp


def _register_static(app: Flask) -> None:
    @app.get("/media/<filename>")
    def media(filename):
        if not MEDIA_NAME_RE.match(filename):
            raise ApiError(404, "Not found")
        return send_from_directory(app.extensions["cityfix"].settings.upload_dir.resolve(), filename)

    @app.get("/")
    def index():
        return send_from_directory(_frontend_dir(), "index.html", max_age=0)

    @app.get("/<path:path>")
    def static_files(path):
        if path.startswith("api/"):
            raise ApiError(404, "Not found")
        return send_from_directory(_frontend_dir(), path, max_age=0)
