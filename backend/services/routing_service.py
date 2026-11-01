"""Geospatial authority routing against admin-managed GeoJSON boundaries.

Rules (see README for the precedence assumption):
  1. within 50 m of a national / state highway line -> NHAI / RCD Bihar (nearest wins)
  2. inside a municipal ward polygon                  -> Municipal Corporation
  3. otherwise                                        -> General Municipal Services
"""
from __future__ import annotations

from ..constants import DEPT_GENERAL, DEPT_MUNICIPAL, DEPT_NHAI, DEPT_RCD, HIGHWAY_BUFFER_M
from ..utils.errors import ApiError
from ..utils.geo import distance_to_line_m, polygon_contains

HIGHWAY_DEPARTMENTS = {"state_highway": DEPT_RCD, "national_highway": DEPT_NHAI}
FEATURE_TYPES = {"ward", *HIGHWAY_DEPARTMENTS}
MAX_FEATURES = 2000
MAX_POSITIONS = 200_000


def _lines(geom):
    if geom["type"] == "LineString":
        return [geom["coordinates"]]
    return list(geom["coordinates"])  # MultiLineString


def _polygons(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    return list(geom["coordinates"])  # MultiPolygon


def route_location(lat: float, lon: float, geojson: dict) -> dict:
    features = geojson.get("features", [])

    nearest = None
    for f in features:
        kind = f.get("properties", {}).get("type")
        if kind not in HIGHWAY_DEPARTMENTS:
            continue
        d = min(distance_to_line_m(lat, lon, line) for line in _lines(f["geometry"]))
        if d <= HIGHWAY_BUFFER_M and (nearest is None or d < nearest[0]):
            nearest = (d, HIGHWAY_DEPARTMENTS[kind], f["properties"].get("name"))
    if nearest:
        return {"department": nearest[1], "jurisdiction": nearest[2], "rule": "highway_proximity",
                "distance_m": round(nearest[0], 1)}

    for f in features:
        props = f.get("properties", {})
        if props.get("type") == "ward" and any(polygon_contains(lon, lat, p) for p in _polygons(f["geometry"])):
            return {"department": DEPT_MUNICIPAL, "jurisdiction": props.get("name"), "rule": "ward_polygon",
                    "distance_m": None}

    return {"department": DEPT_GENERAL, "jurisdiction": None, "rule": "default", "distance_m": None}


def _check_position(p):
    ok = (isinstance(p, (list, tuple)) and len(p) >= 2 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in p[:2])
          and -180 <= p[0] <= 180 and -90 <= p[1] <= 90)
    if not ok:
        raise ApiError(400, "Every coordinate must be [longitude, latitude] within valid ranges")


def validate_boundaries(obj) -> dict:
    """Validates an admin-supplied FeatureCollection. Raises ApiError(400) with a precise reason."""
    if not isinstance(obj, dict) or obj.get("type") != "FeatureCollection" or not isinstance(obj.get("features"), list):
        raise ApiError(400, "Boundaries must be a GeoJSON FeatureCollection")
    if len(obj["features"]) > MAX_FEATURES:
        raise ApiError(400, f"At most {MAX_FEATURES} features are allowed")
    positions = 0
    for i, f in enumerate(obj["features"], start=1):
        label = f"Feature {i}"
        if not isinstance(f, dict) or not isinstance(f.get("geometry"), dict):
            raise ApiError(400, f"{label}: missing geometry")
        kind = (f.get("properties") or {}).get("type")
        if kind not in FEATURE_TYPES:
            raise ApiError(400, f"{label}: properties.type must be one of {', '.join(sorted(FEATURE_TYPES))}")
        geom = f["geometry"]
        want = ("Polygon", "MultiPolygon") if kind == "ward" else ("LineString", "MultiLineString")
        if geom.get("type") not in want:
            raise ApiError(400, f"{label}: a {kind} must use geometry {' or '.join(want)}")
        try:
            if kind == "ward":
                for rings in _polygons(geom):
                    for ring in rings:
                        if len(ring) < 4:
                            raise ApiError(400, f"{label}: polygon rings need at least 4 positions")
                        for p in ring:
                            _check_position(p)
                            positions += 1
            else:
                for line in _lines(geom):
                    if len(line) < 2:
                        raise ApiError(400, f"{label}: lines need at least 2 positions")
                    for p in line:
                        _check_position(p)
                        positions += 1
        except (TypeError, KeyError):
            raise ApiError(400, f"{label}: malformed coordinates")
        if positions > MAX_POSITIONS:
            raise ApiError(400, "Boundary data is too large")
    return obj
