import unittest
from unittest import mock

from backend.constants import (DEPT_GENERAL, DEPT_MUNICIPAL, DEPT_NHAI, DEPT_RCD)
from backend.services import ai_service, routing_service
from backend.services.seed_service import load_json
from backend.utils import geo, timeutil, uploads
from backend.utils.crypto import ContactVault, load_or_create_secrets
from backend.utils.errors import ApiError
from backend.utils.validation import validate_contact


class GeoTests(unittest.TestCase):
    def test_haversine(self):
        self.assertAlmostEqual(geo.haversine_m(25.0, 84.0, 25.0, 84.0), 0, places=3)
        self.assertAlmostEqual(geo.haversine_m(0, 0, 0, 1), 111195, delta=100)

    def test_point_in_polygon_with_hole(self):
        outer = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
        hole = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]
        self.assertTrue(geo.polygon_contains(2, 2, [outer, hole]))
        self.assertFalse(geo.polygon_contains(5, 5, [outer, hole]))
        self.assertFalse(geo.polygon_contains(11, 5, [outer]))

    def test_distance_to_segment(self):
        a, b = [84.84, 25.5562], [84.865, 25.5562]
        self.assertAlmostEqual(geo.distance_to_segment_m(25.5562, 84.85, a, b), 0, delta=0.5)
        # 0.0004 deg of latitude is ~44.5 m
        self.assertAlmostEqual(geo.distance_to_segment_m(25.5566, 84.85, a, b), 44.5, delta=1.0)
        # beyond the segment end the distance is to the endpoint, not the infinite line
        # 0.035 deg of longitude at this latitude is ~3.5 km
        self.assertAlmostEqual(geo.distance_to_segment_m(25.5562, 84.90, a, b), 3511, delta=25)


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.geo = load_json("boundaries.demo.geojson")

    def dept(self, lat, lon):
        return routing_service.route_location(lat, lon, self.geo)["department"]

    def test_rules(self):
        self.assertEqual(self.dept(25.5562, 84.8512), DEPT_RCD)        # on the state highway
        self.assertEqual(self.dept(25.5601, 84.8550), DEPT_MUNICIPAL)  # inside a ward
        self.assertEqual(self.dept(25.5580, 84.8525), DEPT_MUNICIPAL)
        self.assertEqual(self.dept(25.60, 84.90), DEPT_GENERAL)        # outside everything

    def test_50m_buffer_edges(self):
        self.assertEqual(self.dept(25.5562 + 0.00040, 84.85), DEPT_RCD)        # ~44 m
        self.assertEqual(self.dept(25.5562 + 0.00060, 84.85), DEPT_MUNICIPAL)  # ~67 m, ward fallback
        # National highway passes ~5 m from (25.5708, 84.85) but ~95 m from (25.5700, 84.85)
        self.assertEqual(self.dept(25.5708, 84.85), DEPT_NHAI)
        self.assertEqual(self.dept(25.5700, 84.85), DEPT_GENERAL)

    def test_national_highway(self):
        r = routing_service.route_location(25.5711, 84.8550, self.geo)
        self.assertEqual(r["department"], DEPT_NHAI)
        self.assertEqual(r["rule"], "highway_proximity")

    def test_ward_name_is_reported(self):
        self.assertEqual(routing_service.route_location(25.5601, 84.8550, self.geo)["jurisdiction"], "Ward 13 (Market)")


class UploadTests(unittest.TestCase):
    def test_sniff(self):
        self.assertEqual(uploads.sniff(b"\x89PNG\r\n\x1a\n...."), "png")
        self.assertEqual(uploads.sniff(b"\xff\xd8\xff\xe0...."), "jpg")
        self.assertEqual(uploads.sniff(b"RIFF\x00\x00\x00\x00WAVEfmt "), "wav")
        self.assertEqual(uploads.sniff(b"\x00\x00\x00\x20ftypM4A \x00"), "m4a")
        self.assertEqual(uploads.sniff(b"ID3\x04\x00"), "mp3")
        self.assertEqual(uploads.sniff(b"\xff\xfb\x90\x00"), "mp3")
        self.assertIsNone(uploads.sniff(b"MZ executable"))
        self.assertIsNone(uploads.sniff(b""))

    def test_classify_requires_matching_extension(self):
        with self.assertRaises(ApiError) as cm:
            uploads.classify(b"\x89PNG\r\n\x1a\n", "x.jpg", uploads.IMAGE_TYPES)
        self.assertEqual(cm.exception.status, 415)


class MiscTests(unittest.TestCase):
    def test_contact_validation(self):
        self.assertEqual(validate_contact("  A@Example.com "), "a@example.com")
        self.assertEqual(validate_contact("98765-43210"), "9876543210")
        self.assertEqual(validate_contact("+91 9876543210"), "9876543210")
        self.assertIsNone(validate_contact(""))
        self.assertIsNone(validate_contact(None))
        for bad in ("12345", "98765432101", "a@b", "<script>"):
            with self.assertRaises(ApiError):
                validate_contact(bad)

    def test_vault_roundtrip(self):
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as d:
            keys = load_or_create_secrets(pathlib.Path(d), env={})
            again = load_or_create_secrets(pathlib.Path(d), env={})
            self.assertEqual(keys, again)  # generated once, then reused
            vault = ContactVault(keys["fernet_key"])
            token = vault.encrypt("me@example.com")
            self.assertNotIn("example", token)
            self.assertEqual(vault.decrypt(token), "me@example.com")
            self.assertIsNone(vault.decrypt("garbage"))
            env_keys = load_or_create_secrets(pathlib.Path(d), env={"SECRET_KEY": "from-env"})
            self.assertEqual(env_keys["secret_key"], "from-env")

    def test_ai_stub_is_deterministic_and_makes_no_network_call(self):
        with mock.patch.object(ai_service.requests, "post") as post:
            for key in ("stub_key", "", None):
                r = ai_service.analyze_grievance_media(b"\x89PNG\r\n\x1a\n", {"latitude": 1, "longitude": 2}, api_key=key if key is not None else "stub_key")
                self.assertEqual((r["category"], r["severity"]), ("Other", "Medium"))
                self.assertEqual(r["description"], "Automated triage unavailable - stub mode active")
        post.assert_not_called()

    def test_time_helpers(self):
        self.assertEqual(timeutil.hours_between("2026-10-29T10:00:00Z", "2026-10-30T11:45:00Z"), 25.75)
        self.assertEqual(timeutil.hours_between("2026-10-30T10:00:00Z", "2026-10-29T10:00:00Z"), 0.0)  # clock skew clamps to 0
