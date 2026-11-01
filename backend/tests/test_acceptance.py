"""One test per acceptance criterion in the specification (AC1-AC9; AC10 is the whole suite + frontend build)."""
import io

from .base import PNG, BaseTest


class AcceptanceTests(BaseTest):
    def test_ac1_health(self):
        r = self.client.get("/api/v1/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["status"], "ok")
        self.assertEqual(r.get_json()["database"], "ok")

    def test_ac2_sample_row_1(self):
        j = self.client.get("/api/v1/tickets/CIV-2026-0001").get_json()
        self.assertEqual(j["ticket_id"], "CIV-2026-0001")
        self.assertEqual(j["category"], "Road Damage")
        self.assertEqual(j["severity"], "Critical")
        self.assertEqual(j["status"], "Received")
        self.assertEqual(j["assigned_department"], "Road Construction Department Bihar")

    def test_ac3_sample_row_2(self):
        j = self.client.get("/api/v1/tickets/CIV-2026-0002").get_json()
        self.assertEqual(j["status"], "In Progress")
        self.assertEqual(j["assigned_department"], "Municipal Corporation")

    def test_ac4_sample_row_3(self):
        j = self.client.get("/api/v1/tickets/CIV-2026-0003").get_json()
        self.assertEqual(j["status"], "Resolved")
        self.assertTrue(j["resolution_proof_url"])
        self.assertEqual(j["resolved_at"], "2026-10-30T11:45:00Z")

    def test_ac5_triage_stub_mode(self):
        r = self.client.post("/api/v1/triage", content_type="multipart/form-data", data={
            "media": (io.BytesIO(PNG), "p.png"), "latitude": "25.556200", "longitude": "84.851200"})
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertEqual((j["category"], j["severity"]), ("Other", "Medium"))
        self.assertEqual(j["description"], "Automated triage unavailable - stub mode active")
        self.assertEqual(j["status"], "ok")

    def test_ac6_oversized_file(self):
        big = PNG + b"0" * (10 * 1024 * 1024)  # > 10 MB
        r = self.client.post("/api/v1/triage", content_type="multipart/form-data", data={
            "media": (io.BytesIO(big), "big.png"), "latitude": "25.5", "longitude": "84.8"})
        self.assertEqual(r.status_code, 413)
        self.assertEqual(r.get_json()["message"], "Please use a file smaller than 10 MB")

    def test_ac6b_very_oversized_request(self):
        huge = PNG + b"0" * (13 * 1024 * 1024)  # exceeds the whole-request cap
        r = self.client.post("/api/v1/tickets", content_type="multipart/form-data", data={
            "media": (io.BytesIO(huge), "huge.png"), "latitude": "25.5", "longitude": "84.8"})
        self.assertEqual(r.status_code, 413)
        self.assertEqual(r.get_json()["message"], "Please use a file smaller than 10 MB")

    def test_ac7_resolve_without_proof(self):
        h = self.login("officer_rcd")
        r = self.client.patch("/api/v1/authority/tickets/CIV-2026-0001/resolve", headers=h)
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.get_json()["message"], "Mandatory resolution photo proof is required prior to closing ticket")

    def test_ac8_unknown_ticket(self):
        r = self.client.get("/api/v1/tickets/CIV-9999-9999")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.get_json()["message"], "Ticket not found. Please check your tracking reference code")
        self.assertEqual(self.client.get("/api/v1/tickets/not-an-id").status_code, 404)

    def test_ac9_dashboard(self):
        j = self.client.get("/api/v1/public/dashboard").get_json()
        m = j["metrics"]
        self.assertEqual(len(j["tickets"]), 3)
        self.assertEqual((m["total_tickets"], m["open_tickets"], m["resolved_tickets"]), (3, 2, 1))
        depts = {d["department"]: d for d in m["departments"]}
        # CIV-2026-0003: 2026-10-29T10:00Z -> 2026-10-30T11:45Z = 25.75 h
        self.assertEqual(depts["Municipal Corporation"]["avg_resolution_hours"], 25.75)
        self.assertEqual(depts["Municipal Corporation"]["resolved"], 1)
        self.assertEqual(depts["Municipal Corporation"]["open"], 1)
        self.assertIsNone(depts["Road Construction Department Bihar"]["avg_resolution_hours"])
        colors = {t["ticket_id"]: t["marker"] for t in j["tickets"]}
        self.assertEqual(colors, {"CIV-2026-0001": "red", "CIV-2026-0002": "orange", "CIV-2026-0003": "green"})

    def test_dashboard_filters(self):
        j = self.client.get("/api/v1/public/dashboard?category=Water Leak").get_json()
        self.assertEqual([t["ticket_id"] for t in j["tickets"]], ["CIV-2026-0002"])
        j = self.client.get("/api/v1/public/dashboard?status=open").get_json()
        self.assertEqual(j["metrics"]["total_tickets"], 2)
        self.assertEqual(self.client.get("/api/v1/public/dashboard?category=Nope").status_code, 400)
