"""Encryption at rest for reporter contact details, plus generated-on-first-run secrets."""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


class ContactVault:
    def __init__(self, key):
        self._fernet = Fernet(key)

    def encrypt(self, value: str | None) -> str | None:
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii") if value else None

    def decrypt(self, token: str | None) -> str | None:
        if not token:
            return None
        try:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except InvalidToken:
            return None


def load_or_create_secrets(instance_dir: Path, env=None) -> dict:
    """SECRET_KEY / CONTACT_ENCRYPTION_KEY come from the environment when set.
    Otherwise they are generated once and kept in instance/secrets.json (git-ignored, chmod 600)."""
    env = os.environ if env is None else env
    path = Path(instance_dir) / "secrets.json"
    stored = json.loads(path.read_text()) if path.exists() else {}
    changed = False

    secret_key = env.get("SECRET_KEY")
    if not secret_key:
        secret_key = stored.get("secret_key")
        if not secret_key:
            secret_key = stored["secret_key"] = secrets.token_urlsafe(48)
            changed = True

    fernet_key = env.get("CONTACT_ENCRYPTION_KEY")
    if not fernet_key:
        fernet_key = stored.get("fernet_key")
        if not fernet_key:
            fernet_key = stored["fernet_key"] = Fernet.generate_key().decode("ascii")
            changed = True

    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(stored))
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return {"secret_key": secret_key, "fernet_key": fernet_key}
