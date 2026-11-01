import json
import logging

from backend.utils.logging_utils import MaskingFilter, mask
from .base import PNG, BaseTest


class AdminAndPrivacyTests(BaseTest):
    def test_contact_is_encrypted_at_rest(self):
        t = self.report(contact="secret.person@example.com").get_json()["ticket_id"]
        with self.raw_db() as db:
            raw = db.execute("SELECT reporter_contact_enc FROM tickets WHERE ticket_id=?", (t,)).fetchone()[0]
            dump = "".join(db.iterdump())
        self.assertTrue(raw and "secret.person" not in raw)
        self.assertNotIn("secret.person@example.com", dump)
        self.assertNotIn("9876543210", dump)           # sample row 3 phone number
        self.assertNotIn("citizen1@example.com", dump)  # sample row 1 email

    def test_contact_never_in_public_responses(self):
        t = self.report(contact="secret.person@example.com").get_json()["ticket_id"]
        for path in (f"/api/v1/tickets/{t}", "/api/v1/tickets/CIV-2026-0001", "/api/v1/tickets/CIV-2026-0003",
                     "/api/v1/public/dashboard"):
            body = self.client.get(path).get_data(as_text=True)
            self.assertNotIn("secret.person", body, path)
            self.assertNotIn("citizen1@example.com", body, path)
            self.assertNotIn("9876543210", body, path)
            self.assertNotIn("reporter_contact", body, path)
        # ...nor in the officer queue, nor in the ticket-creation response
        self.assertNotIn("citizen1", self.client.get("/api/v1/authority/tickets", headers=self.login("officer_rcd")).get_data(as_text=True))
        self.assertNotIn("secret.person", json.dumps(self.report(contact="secret.person@example.com", lat="25.8", lon="84.8").get_json()))

    def test_admin_sees_contact_and_ai_details(self):
        tickets = self.client.get("/api/v1/admin/tickets", headers=self.login("admin")).get_json()["tickets"]
        by_id = {t["ticket_id"]: t for t in tickets}
        self.assertEqual(by_id["CIV-2026-0001"]["reporter_contact"], "citizen1@example.com")
        self.assertEqual(by_id["CIV-2026-0003"]["reporter_contact"], "9876543210")
        self.assertIsNone(by_id["CIV-2026-0002"]["reporter_contact"])
        new = self.report(lat="25.9", lon="84.9").get_json()["ticket_id"]
        ai = next(t for t in self.client.get("/api/v1/admin/tickets", headers=self.login("admin")).get_json()["tickets"] if t["ticket_id"] == new)["ai"]
        self.assertEqual((ai["mode"], ai["category"]), ("stub", "Other"))

    def test_admin_only_endpoints_reject_officers(self):
        h = self.login("officer_rcd")
        self.assertEqual(self.client.get("/api/v1/admin/tickets", headers=h).status_code, 403)
        self.assertEqual(self.client.post("/api/v1/admin/seed", headers=h, json={}).status_code, 403)
        self.assertEqual(self.client.put("/api/v1/admin/boundaries", headers=h, json={}).status_code, 403)

    def test_boundaries_update_changes_routing(self):
        h = self.login("admin")
        fc = self.client.get("/api/v1/admin/boundaries", headers=h).get_json()
        fc["features"].append({"type": "Feature", "properties": {"type": "national_highway", "name": "NH test"},
                               "geometry": {"type": "LineString", "coordinates": [[84.89, 25.6], [84.91, 25.6]]}})
        self.assertEqual(self.client.put("/api/v1/admin/boundaries", headers=h, json=fc).status_code, 200)
        j = self.report(lat="25.6", lon="84.9").get_json()
        self.assertEqual(j["assigned_department"], "National Highways Authority of India")

    def test_boundaries_validation(self):
        h = self.login("admin")
        bad = [
            {"type": "Feature"},
            {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"type": "lake"}, "geometry": {"type": "Polygon", "coordinates": []}}]},
            {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"type": "ward"}, "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}}]},
            {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"type": "state_highway"}, "geometry": {"type": "LineString", "coordinates": [[500, 0], [1, 1]]}}]},
        ]
        for payload in bad:
            self.assertEqual(self.client.put("/api/v1/admin/boundaries", headers=h, json=payload).status_code, 400, payload)

    def test_department_email_settings(self):
        h = self.login("admin")
        name = "Municipal Corporation"
        self.assertEqual(self.client.put(f"/api/v1/admin/departments/{name}", headers=h, json={"email": "ward@example.org"}).status_code, 200)
        self.assertEqual(self.client.put(f"/api/v1/admin/departments/{name}", headers=h, json={"email": "nope"}).status_code, 400)
        self.assertEqual(self.client.put("/api/v1/admin/departments/Unknown", headers=h, json={"email": "a@b.co"}).status_code, 404)
        depts = {d["name"]: d["email"] for d in self.client.get("/api/v1/admin/departments", headers=h).get_json()["departments"]}
        self.assertEqual(depts[name], "ward@example.org")

    def test_seed_endpoint(self):
        h = self.login("admin")
        r = self.client.post("/api/v1/admin/seed", headers=h, json={"reset": True, "extra": 25})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get("/api/v1/public/dashboard").get_json()["metrics"]["total_tickets"], 28)
        self.client.post("/api/v1/admin/seed", headers=h, json={"reset": True})
        self.assertEqual(self.client.get("/api/v1/public/dashboard").get_json()["metrics"]["total_tickets"], 3)
        self.assertEqual(self.client.post("/api/v1/admin/seed", headers=h, json={"extra": 9999}).status_code, 400)

    def test_notification_subscription_is_honest_and_encrypted(self):
        r = self.client.post("/api/v1/notifications/subscribe", json={"ticket_id": "CIV-2026-0001", "phone": "9123456789", "consent": True})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()["delivery"], "not_configured")
        with self.raw_db() as db:
            self.assertNotIn("9123456789", "".join(db.iterdump()))
        self.assertEqual(self.client.post("/api/v1/notifications/subscribe", json={"ticket_id": "CIV-2026-0001", "phone": "9123456789"}).status_code, 400)
        self.assertEqual(self.client.post("/api/v1/notifications/subscribe", json={"ticket_id": "CIV-9999-9999", "phone": "9123456789", "consent": True}).status_code, 404)

    def test_log_masking(self):
        self.assertEqual(mask("call 9876543210 or mail a.b@example.com now"), "call [phone] or mail [email] now")
        self.assertEqual(mask("ticket CIV-2026-0001 at 25.556200,84.851200"), "ticket CIV-2026-0001 at 25.556200,84.851200")
        rec = logging.LogRecord("x", logging.INFO, "f", 1, "user %s", ("me@example.com",), None)
        MaskingFilter().filter(rec)
        self.assertEqual(rec.getMessage(), "user [email]")

    def test_security_headers_and_cors(self):
        r = self.client.get("/api/v1/health", headers={"Origin": "http://localhost:8000"})
        self.assertEqual(r.headers["Access-Control-Allow-Origin"], "http://localhost:8000")
        self.assertIn("default-src 'self'", r.headers["Content-Security-Policy"])
        r = self.client.get("/api/v1/health", headers={"Origin": "https://evil.example"})
        self.assertNotIn("Access-Control-Allow-Origin", r.headers)

    def test_stored_text_is_returned_as_data_not_markup(self):
        h = self.login("officer_rcd")
        self.client.post("/api/v1/authority/tickets/CIV-2026-0001/info-request", headers=h,
                         json={"message": "<script>alert(1)</script> please confirm"})
        r = self.client.get("/api/v1/tickets/CIV-2026-0001")
        self.assertEqual(r.mimetype, "application/json")  # never rendered as HTML by the server

    def test_database_failure_returns_500_message(self):
        import sqlite3
        from unittest import mock
        with mock.patch("backend.models.ticket.get", side_effect=sqlite3.OperationalError("database is locked")):
            r = self.client.get("/api/v1/tickets/CIV-2026-0001")
        self.assertEqual(r.status_code, 500)
        self.assertEqual(r.get_json()["message"], "System error occurred. Please try again shortly")

    def test_health_reports_database_failure(self):
        from unittest import mock
        with mock.patch("backend.api.public.get_db", side_effect=RuntimeError("down")):
            r = self.client.get("/api/v1/health")
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.get_json()["database"], "error")

    def test_media_route_blocks_traversal(self):
        for p in ("/media/../secrets.json", "/media/notahash.png", "/media/..%2Fsecrets.json"):
            self.assertEqual(self.client.get(p).status_code, 404, p)

    def test_unknown_api_route_is_json_404(self):
        r = self.client.get("/api/v1/nope")
        self.assertEqual((r.status_code, r.mimetype), (404, "application/json"))
