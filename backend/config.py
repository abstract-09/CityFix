"""Runtime settings, read from environment variables (and an optional .env file)."""
from __future__ import annotations

import os
from pathlib import Path

from .constants import ROOT


def load_dotenv(path: Path) -> None:
    """Tiny .env reader. Real environment variables always win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _int(env, name, default):
    try:
        return int(env.get(name, default))
    except (TypeError, ValueError):
        return default


def _float(env, name, default):
    try:
        return float(env.get(name, default))
    except (TypeError, ValueError):
        return default


def db_path_from_url(url: str) -> str:
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        raise ValueError("DATABASE_URL must start with sqlite:/// (this MVP supports SQLite only)")
    return url[len(prefix):]


class Settings:
    def __init__(self):
        self.ai_service_api_key = "stub_key"
        self.gis_map_api_key = "stub_key"
        self.port = 8000
        self.database_url = "sqlite:///./cityfix.db"
        self.max_upload_mb = 10
        self.ai_model = "claude-sonnet-5-5"
        self.ai_service_url = "https://api.anthropic.com/v1/messages"
        self.ai_timeout_seconds = 4.0
        self.allowed_origins = ["http://localhost:8000", "http://127.0.0.1:8000"]
        self.rate_limit_per_minute = 30
        self.login_rate_limit = 10
        self.auto_seed = True
        self.instance_dir = ROOT / "instance"
        self.upload_dir = None
        self.password_hash_method = "scrypt"
        self.demo_user_password = None
        self.public_base_url = None
        self.token_ttl_hours = 12

    @classmethod
    def load(cls, overrides: dict | None = None, dotenv: bool = True) -> "Settings":
        if dotenv:
            load_dotenv(ROOT / ".env")
        env = os.environ
        s = cls()
        s.ai_service_api_key = env.get("AI_SERVICE_API_KEY", s.ai_service_api_key) or "stub_key"
        s.gis_map_api_key = env.get("GIS_MAP_API_KEY", s.gis_map_api_key) or "stub_key"
        s.port = _int(env, "PORT", s.port)
        s.database_url = env.get("DATABASE_URL", s.database_url)
        s.max_upload_mb = _float(env, "MAX_UPLOAD_SIZE_MB", s.max_upload_mb)
        s.ai_model = env.get("AI_MODEL", s.ai_model)
        s.ai_service_url = env.get("AI_SERVICE_URL", s.ai_service_url)
        s.ai_timeout_seconds = _float(env, "AI_TIMEOUT_SECONDS", s.ai_timeout_seconds)
        origins = env.get("ALLOWED_ORIGINS")
        if origins:
            s.allowed_origins = [o.strip() for o in origins.split(",") if o.strip()]
        s.rate_limit_per_minute = _int(env, "RATE_LIMIT_PER_MINUTE", s.rate_limit_per_minute)
        s.login_rate_limit = _int(env, "LOGIN_RATE_LIMIT_PER_MINUTE", s.login_rate_limit)
        s.auto_seed = env.get("AUTO_SEED", "true").lower() not in ("0", "false", "no")
        s.instance_dir = Path(env.get("INSTANCE_DIR", s.instance_dir))
        s.demo_user_password = env.get("DEMO_USER_PASSWORD") or None
        s.public_base_url = env.get("PUBLIC_BASE_URL") or None
        s.token_ttl_hours = _int(env, "TOKEN_TTL_HOURS", s.token_ttl_hours)
        for key, value in (overrides or {}).items():
            setattr(s, key, value)
        s.instance_dir = Path(s.instance_dir)
        s.upload_dir = Path(s.upload_dir) if s.upload_dir else s.instance_dir / "uploads"
        s.db_path = db_path_from_url(s.database_url)
        return s

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)
