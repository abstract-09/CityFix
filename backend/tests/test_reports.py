import io
import json
from unittest import mock

from backend.services import ai_service
from .base import JPG, MP3, PNG, BaseTest


class ReportCreationTests(BaseTest):
    def test_create_ticket_stub_mode(self):
        r = self.report(lat="25.6000", lon="84.9000", contact="reporter@example.com")
        self.assertEqual(r.status_code, 201)
        j = r.get_json()
        self.assertRegex(j["ticket_id"], r"^CIV-\d{4}-\d{4}$")
        self.assertTrue(j["url"].endswith("/#/track/" + j["ticket_id"]))
        self.assertEqual((j["category"], j["severity"]), ("Other", "Medium"))
        self.assertEqual(j["assigned_department"], "General Municipal Services")  # outside every boundary
        got = self.client.get("/api/v1/tickets/" + j["ticket_id"]).get_json()
        self.assertEqual(got["status"], "Received")
        self.assertEqual(got["history"][0]["kind"], "created")

    def test_category_override_and_routing(self):
        j = self.report(lat="25.5562", lon="84.8512", category="Road Damage").get_json()
        self.assertEqual(j["category"], "Road Damage")
        self.assertEqual(j["assigned_department"], "Road Construction Department Bihar")
        j2 = self.report(lat="25.5601", lon="84.8550", category="Water Leak").get_json()  # near sample 2? different category
        self.assertEqual(j2["assigned_department"], "Municipal Corporation")

    def test_audio_upload_accepted(self):
        r = self.report(data=MP3, filename="voice.mp3")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.client.get("/api/v1/tickets/" + r.get_json()["ticket_id"]).get_json()["media_type"], "audio")

    def test_missing_media_or_location(self):
        msg = "Please attach media and ensure GPS location permission is enabled"
        r = self.client.post("/api/v1/tickets", data={"latitude": "25.5", "longitude": "84.8"})
        self.assertEqual((r.status_code, r.get_json()["message"]), (400, msg))
        r = self.client.post("/api/v1/tickets", content_type="multipart/form-data",
                             data={"media": (io.BytesIO(PNG), "a.png")})
        self.assertEqual((r.status_code, r.get_json()["message"]), (400, msg))

    def test_invalid_coordinates(self):
        self.assertEqual(self.report(lat="95", lon="84").status_code, 400)
        self.assertEqual(self.report(lat="abc", lon="84").status_code, 400)
        self.assertEqual(self.report(lat="nan", lon="84").status_code, 400)

    def test_unsupported_file_types(self):
        msg = "Unsupported file format. Please upload JPG, PNG, or MP3 files"
        for data, name in [(b"MZ\x90\x00 evil", "run.exe"), (b"hello", "notes.txt"),
                           (b"MZ\x90\x00 evil", "evil.png"),          # wrong content, right extension
                           (PNG, "photo.mp3"), (JPG, "photo.png")]:  # content does not match extension
            r = self.report(data=data, filename=name)
            self.assertEqual((r.status_code, r.get_json()["message"]), (415, msg), name)

    def test_jpeg_extension_alias(self):
        self.assertEqual(self.report(data=JPG, filename="a.jpeg").status_code, 201)
        self.assertEqual(self.report(data=JPG, filename="a.JPG", lat="25.7", lon="84.7").status_code, 201)

    def test_invalid_contact_and_category(self):
        self.assertEqual(self.report(contact="not a contact").status_code, 400)
        self.assertEqual(self.report(contact="12345").status_code, 400)
        self.assertEqual(self.report(category="Alien Invasion").status_code, 400)
        self.assertEqual(self.report(contact="9876543210", category="Water Leak").status_code, 201)

    def test_duplicate_within_50m_is_merged(self):
        first = self.report(lat="25.6000", lon="84.9000", category="Water Leak").get_json()
        # ~22 m north of the first report, same category
        r = self.report(lat="25.6002", lon="84.9000", category="Water Leak")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j["merged"])
        self.assertEqual(j["ticket_id"], first["ticket_id"])
        self.assertEqual(j["message"], "Similar issue already reported nearby. Your report has been merged to increment priority")
        t = self.client.get("/api/v1/tickets/" + first["ticket_id"]).get_json()
        self.assertEqual(t["report_count"], 2)
        self.assertIn("duplicate_report", [e["kind"] for e in t["history"]])

    def test_no_merge_when_far_or_different_category_or_resolved(self):
        self.report(lat="25.6000", lon="84.9000", category="Water Leak")
        self.assertEqual(self.report(lat="25.6010", lon="84.9000", category="Water Leak").status_code, 201)  # ~110 m
        self.assertEqual(self.report(lat="25.6000", lon="84.9000", category="Road Damage").status_code, 201)
        # Sample ticket 3 is Resolved: a new report at the same spot must NOT merge into it
        r = self.report(lat="25.5580", lon="84.8525", category="Streetlight Defect")
        self.assertEqual(r.status_code, 201)

    def test_sequential_ticket_ids(self):
        a = self.report(lat="25.61", lon="84.91").get_json()["ticket_id"]
        b = self.report(lat="25.62", lon="84.92").get_json()["ticket_id"]
        self.assertEqual(int(b[-4:]), int(a[-4:]) + 1)

    def test_route_preview(self):
        r = self.client.get("/api/v1/route-preview?latitude=25.5562&longitude=84.8512").get_json()
        self.assertEqual(r["assigned_department"], "Road Construction Department Bihar")
        self.assertEqual(self.client.get("/api/v1/route-preview").status_code, 400)

    def test_triage_requires_location(self):
        r = self.client.post("/api/v1/triage", content_type="multipart/form-data",
                             data={"media": (io.BytesIO(PNG), "p.png")})
        self.assertEqual(r.status_code, 400)


def _fake_response(payload, status=200):
    resp = mock.Mock()
    resp.status_code = status
    resp.json.return_value = payload
    resp.raise_for_status.side_effect = None if status < 400 else ai_service.requests.HTTPError("boom")
    return resp


def _model_reply(**fields):
    return _fake_response({"content": [{"type": "text", "text": "Here you go: " + json.dumps(fields)}]})


class LiveAiTests(BaseTest):
    overrides = {"ai_service_api_key": "sk-test-key"}

    def triage(self, data=PNG, filename="p.png"):
        return self.client.post("/api/v1/triage", content_type="multipart/form-data", data={
            "media": (io.BytesIO(data), filename), "latitude": "25.5562", "longitude": "84.8512"})

    def test_high_confidence_result_is_used(self):
        reply = _model_reply(category="Road Damage", severity="Critical", description="Deep pothole.", confidence=0.93)
        with mock.patch.object(ai_service.requests, "post", return_value=reply) as post:
            j = self.triage().get_json()
        self.assertEqual((j["category"], j["severity"], j["description"]), ("Road Damage", "Critical", "Deep pothole."))
        sent = post.call_args.kwargs
        self.assertEqual(sent["headers"]["x-api-key"], "sk-test-key")
        self.assertEqual(sent["json"]["messages"][0]["content"][0]["type"], "image")

    def test_low_confidence_falls_back(self):
        reply = _model_reply(category="Road Damage", severity="Critical", description="Maybe a pothole.", confidence=0.69)
        with mock.patch.object(ai_service.requests, "post", return_value=reply):
            j = self.triage().get_json()
        self.assertEqual((j["category"], j["severity"], j["description"]), ("Other", "Medium", "Needs manual review"))
        self.assertTrue(j["needs_review"])

    def test_threshold_is_inclusive(self):
        reply = _model_reply(category="Water Leak", severity="Low", description="Small leak.", confidence=0.70)
        with mock.patch.object(ai_service.requests, "post", return_value=reply):
            self.assertEqual(self.triage().get_json()["category"], "Water Leak")

    def test_invalid_model_output_treated_as_low_confidence(self):
        reply = _model_reply(category="Volcano", severity="Apocalyptic", description="x", confidence=0.99)
        with mock.patch.object(ai_service.requests, "post", return_value=reply):
            self.assertEqual(self.triage().get_json()["description"], "Needs manual review")

    def test_ai_failure_returns_503_with_fallback(self):
        with mock.patch.object(ai_service.requests, "post", side_effect=ai_service.requests.Timeout()):
            r = self.triage()
        j = r.get_json()
        self.assertEqual(r.status_code, 503)
        self.assertEqual(j["message"], "AI triage service temporarily unavailable. Default fallback applied")
        self.assertEqual((j["category"], j["severity"], j["description"]), ("Other", "Medium", "Manual review required"))

    def test_ai_failure_does_not_block_ticket_creation(self):
        with mock.patch.object(ai_service.requests, "post", side_effect=ai_service.requests.ConnectionError()):
            r = self.report(lat="25.7", lon="84.7")
        self.assertEqual(r.status_code, 201)
        j = r.get_json()
        self.assertEqual(j["description"], "Manual review required")
        self.assertIn("temporarily unavailable", j["triage_warning"])

    def test_audio_is_never_sent_to_the_vision_api(self):
        with mock.patch.object(ai_service.requests, "post") as post:
            j = self.triage(data=MP3, filename="v.mp3").get_json()
        post.assert_not_called()
        self.assertEqual(j["description"], "Needs manual review")

    def test_garbled_model_text_is_a_failure(self):
        reply = _fake_response({"content": [{"type": "text", "text": "I cannot help with that"}]})
        with mock.patch.object(ai_service.requests, "post", return_value=reply):
            self.assertEqual(self.triage().status_code, 503)
