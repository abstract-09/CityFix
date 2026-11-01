"""Signed bearer tokens + role checks for officer/admin endpoints."""
import functools

from flask import current_app, g, request
from itsdangerous import BadSignature

from ..db import get_db
from .errors import ApiError


def issue_token(user_id: int) -> str:
    return current_app.extensions["cityfix"].serializer.dumps({"uid": user_id})


def current_user():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    c = current_app.extensions["cityfix"]
    try:
        data = c.serializer.loads(header[7:].strip(), max_age=c.settings.token_ttl_hours * 3600)
    except BadSignature:
        return None
    row = get_db().execute(
        "SELECT id, username, role, department FROM users WHERE id = ?", (data.get("uid"),)
    ).fetchone()
    return dict(row) if row else None


def require_role(role: str):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                raise ApiError(401, "Please sign in to continue")
            if user["role"] != role:
                raise ApiError(403, "Your account cannot access this area")
            g.user = user
            return fn(*args, **kwargs)
        return wrapper
    return decorator
