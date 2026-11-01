"""Small, dependency-free geometry helpers. GeoJSON order is [longitude, latitude]."""
import math

EARTH_RADIUS_M = 6371000.0


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def _ring_contains(lon, lat, ring) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def polygon_contains(lon, lat, rings) -> bool:
    """rings[0] is the outer ring, the rest are holes."""
    if not rings or not _ring_contains(lon, lat, rings[0]):
        return False
    return not any(_ring_contains(lon, lat, hole) for hole in rings[1:])


def distance_to_segment_m(lat, lon, a, b) -> float:
    """Distance in metres from (lat, lon) to the segment a-b, using a local flat projection."""
    cos_lat = math.cos(math.radians(lat))

    def to_xy(p):
        return (math.radians(p[0] - lon) * cos_lat * EARTH_RADIUS_M,
                math.radians(p[1] - lat) * EARTH_RADIUS_M)

    ax, ay = to_xy(a)
    bx, by = to_xy(b)
    dx, dy = bx - ax, by - ay
    seg2 = dx * dx + dy * dy
    if seg2 == 0:
        return math.hypot(ax, ay)
    t = max(0.0, min(1.0, -(ax * dx + ay * dy) / seg2))
    return math.hypot(ax + t * dx, ay + t * dy)


def distance_to_line_m(lat, lon, coords) -> float:
    if len(coords) == 1:
        return haversine_m(lat, lon, coords[0][1], coords[0][0])
    return min(distance_to_segment_m(lat, lon, coords[i], coords[i + 1]) for i in range(len(coords) - 1))
