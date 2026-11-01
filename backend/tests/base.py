import io
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.app import create_app
from backend.services import seed_service

PASSWORD = "test-password-123"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
MP3 = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 64


class BaseTest(unittest.TestCase):
    overrides: dict = {}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        settings = dict(
            database_url=f"sqlite:///{base / 'test.db'}", instance_dir=base / "instance",
            upload_dir=base / "uploads", auto_seed=False, rate_limit_per_minute=0, login_rate_limit=0,
            password_hash_method="pbkdf2:sha256:1000", demo_user_password=PASSWORD,
            ai_service_api_key="stub_key",
        )
        settings.update(self.overrides)
        self.app = create_app(settings, dotenv=False)
        seed_service.seed_app(self.app, quiet=True)
        self.client = self.app.test_client()
        self.db_path = settings["database_url"].replace("sqlite:///", "")

    def tearDown(self):
        self.tmp.cleanup()

    # helpers
    def login(self, username="officer_rcd"):
        r = self.client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
        self.assertEqual(r.status_code, 200, r.get_json())
        return {"Authorization": "Bearer " + r.get_json()["token"]}

    def report(self, data=PNG, filename="issue.png", lat="25.6000", lon="84.9000", **extra):
        form = {"media": (io.BytesIO(data), filename), "latitude": lat, "longitude": lon}
        form.update(extra)
        return self.client.post("/api/v1/tickets", data=form, content_type="multipart/form-data")

    def raw_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
