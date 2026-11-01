import io

from .base import JPG, PNG, BaseTest


class AuthorityTests(BaseTest):
    def resolve(self, ticket_id, headers, data=JPG, filename="after.jpg", **extra):
        form = {"resolution_proof": (io.BytesIO(data), filename), **extra}
        return self.client.patch(f"/api/v1/authority/tickets/{ticket_id}/resolve", headers=headers,
                                 data=form, content_type="multipart/form-data")

    def test_login(self):
        self.assertEqual(self.client.post("/api/v1/auth/login", json={"username": "officer_rcd", "password": "wrong"}).status_code, 401)
        self.assertEqual(self.client.post("/api/v1/auth/login", json={}).status_code, 401)
        h = self.login("officer_rcd")
        me = self.client.get("/api/v1/auth/me", headers=h).get_json()["user"]
        self.assertEqual((me["role"], me["department"]), ("officer", "Road Construction Department Bihar"))

    def test_endpoints_require_login(self):
        for method, path in [("get", "/api/v1/authority/tickets"),
                             ("patch", "/api/v1/authority/tickets/CIV-2026-0001"),
                             ("patch", "/api/v1/authority/tickets/CIV-2026-0001/resolve"),
                             ("get", "/api/v1/admin/tickets")]:
            self.assertEqual(getattr(self.client, method)(path).status_code, 401, path)
        bad = {"Authorization": "Bearer not-a-real-token"}
        self.assertEqual(self.client.get("/api/v1/authority/tickets", headers=bad).status_code, 401)

    def test_queue_is_scoped_to_department_and_sorted(self):
        rcd = self.client.get("/api/v1/authority/tickets", headers=self.login("officer_rcd")).get_json()
        self.assertEqual([t["ticket_id"] for t in rcd["tickets"]], ["CIV-2026-0001"])
        muni = self.client.get("/api/v1/authority/tickets", headers=self.login("officer_municipal")).get_json()
        # open ticket first, resolved last
        self.assertEqual([t["ticket_id"] for t in muni["tickets"]], ["CIV-2026-0002", "CIV-2026-0003"])
        self.assertNotIn("reporter_contact", muni["tickets"][0])

    def test_queue_severity_order(self):
        self.report(lat="25.6100", lon="84.9000", category="Water Leak")
        self.report(lat="25.6200", lon="84.9000", category="Road Damage")
        with self.raw_db() as db:
            db.execute("UPDATE tickets SET severity='Low' WHERE ticket_id = (SELECT MIN(ticket_id) FROM tickets WHERE assigned_department='General Municipal Services')")
            db.execute("UPDATE tickets SET severity='Critical' WHERE ticket_id = (SELECT MAX(ticket_id) FROM tickets WHERE assigned_department='General Municipal Services')")
        tickets = self.client.get("/api/v1/authority/tickets", headers=self.login("officer_general")).get_json()["tickets"]
        self.assertEqual([t["severity"] for t in tickets], ["Critical", "Low"])

    def test_officer_cannot_touch_other_departments(self):
        h = self.login("officer_municipal")
        self.assertEqual(self.client.patch("/api/v1/authority/tickets/CIV-2026-0001", headers=h, json={"status": "In Progress"}).status_code, 403)
        self.assertEqual(self.resolve("CIV-2026-0001", h).status_code, 403)

    def test_admin_is_not_an_officer(self):
        self.assertEqual(self.client.get("/api/v1/authority/tickets", headers=self.login("admin")).status_code, 403)

    def test_full_lifecycle(self):
        h = self.login("officer_rcd")
        r = self.client.patch("/api/v1/authority/tickets/CIV-2026-0001", headers=h, json={"status": "In Progress", "note": "Crew on site"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["status"], "In Progress")
        self.assertEqual(r.get_json()["history"][-1]["message"], "Crew on site")

        r = self.resolve("CIV-2026-0001", h, note="Patched")
        self.assertEqual(r.status_code, 200, r.get_json())
        j = r.get_json()
        self.assertEqual(j["status"], "Resolved")
        self.assertTrue(j["resolved_at"].endswith("Z"))
        self.assertIn("/media/", j["resolution_proof_url"])
        media = self.client.get(j["resolution_proof_url"].split("localhost")[-1])
        self.assertEqual(media.status_code, 200)
        self.assertEqual(media.headers["X-Content-Type-Options"], "nosniff")

    def test_cannot_resolve_straight_from_received(self):
        r = self.resolve("CIV-2026-0001", self.login("officer_rcd"))
        self.assertEqual(r.status_code, 422)
        self.assertIn("In Progress", r.get_json()["message"])

    def test_patch_to_resolved_requires_proof_endpoint(self):
        r = self.client.patch("/api/v1/authority/tickets/CIV-2026-0001", headers=self.login("officer_rcd"), json={"status": "Resolved"})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.get_json()["message"], "Mandatory resolution photo proof is required prior to closing ticket")

    def test_no_backwards_transitions(self):
        h = self.login("officer_municipal")
        for target in ("Received", "In Progress"):
            r = self.client.patch("/api/v1/authority/tickets/CIV-2026-0003", headers=h, json={"status": target})
            self.assertEqual(r.status_code, 422, target)
        # In Progress -> Received and In Progress -> In Progress
        self.assertEqual(self.client.patch("/api/v1/authority/tickets/CIV-2026-0002", headers=h, json={"status": "Received"}).status_code, 422)
        self.assertEqual(self.client.patch("/api/v1/authority/tickets/CIV-2026-0002", headers=h, json={"status": "In Progress"}).status_code, 422)
        self.assertEqual(self.resolve("CIV-2026-0003", h).status_code, 422)  # already resolved
        self.assertEqual(self.client.patch("/api/v1/authority/tickets/CIV-2026-0002", headers=h, json={"status": "Bogus"}).status_code, 400)

    def test_proof_must_be_an_image_and_small_enough(self):
        h = self.login("officer_municipal")
        self.assertEqual(self.resolve("CIV-2026-0002", h, data=b"hello", filename="proof.txt").status_code, 415)
        self.assertEqual(self.resolve("CIV-2026-0002", h, data=b"ID3\x03" + b"0" * 50, filename="proof.mp3").status_code, 415)
        self.assertEqual(self.resolve("CIV-2026-0002", h, data=PNG + b"0" * (10 * 1024 * 1024), filename="p.png").status_code, 413)
        self.assertEqual(self.client.get("/api/v1/tickets/CIV-2026-0002").get_json()["status"], "In Progress")

    def test_proof_url_cannot_be_supplied_as_text(self):
        h = self.login("officer_municipal")
        r = self.client.patch("/api/v1/authority/tickets/CIV-2026-0002/resolve", headers=h,
                              json={"resolution_proof_url": "https://evil.example/x.jpg"})
        self.assertEqual(r.status_code, 422)

    def test_info_request_appears_in_public_history(self):
        h = self.login("officer_rcd")
        r = self.client.post("/api/v1/authority/tickets/CIV-2026-0001/info-request", headers=h,
                             json={"message": "Which side of the exit is the pothole on?"})
        self.assertEqual(r.status_code, 200)
        hist = self.client.get("/api/v1/tickets/CIV-2026-0001").get_json()["history"]
        self.assertEqual(hist[-1]["kind"], "info_request")
        self.assertEqual(self.client.post("/api/v1/authority/tickets/CIV-2026-0001/info-request", headers=h, json={"message": "hi"}).status_code, 400)
        h2 = self.login("officer_municipal")
        self.assertEqual(self.client.post("/api/v1/authority/tickets/CIV-2026-0003/info-request", headers=h2, json={"message": "Anything else?"}).status_code, 422)

    def test_login_rate_limit(self):
        self.app.extensions["cityfix"].settings.login_rate_limit = 3
        codes = [self.client.post("/api/v1/auth/login", json={"username": "x", "password": "y"}).status_code for _ in range(5)]
        self.assertEqual(codes, [401, 401, 401, 429, 429])
