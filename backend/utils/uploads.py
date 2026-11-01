"""Upload handling: size limits, content sniffing (never trust Content-Type), safe storage."""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from ..constants import MSG_MISSING_FIELDS, MSG_UNSUPPORTED_TYPE, msg_too_large
from .errors import ApiError
from .validation import parse_accuracy, parse_coord

IMAGE_TYPES = {"jpg", "png"}
AUDIO_TYPES = {"mp3", "wav", "m4a"}
EXT_ALIASES = {"jpeg": "jpg"}
M4A_BRANDS = {b"M4A ", b"M4B ", b"M4P ", b"mp41", b"mp42", b"isom"}


@dataclass
class Media:
    data: bytes
    ext: str      # normalised extension: jpg | png | mp3 | wav | m4a
    kind: str     # image | audio


def sniff(data: bytes) -> str | None:
    """Identify the real file type from its first bytes."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if data[4:8] == b"ftyp" and data[8:12] in M4A_BRANDS:
        return "m4a"
    if data.startswith(b"ID3") or (len(data) > 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return "mp3"
    return None


def read_limited(file_storage, max_bytes: int) -> bytes:
    data = file_storage.stream.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ApiError(413, msg_too_large(max_bytes / (1024 * 1024)))
    return data


def classify(data: bytes, filename: str, allowed: set[str]) -> Media:
    ext = os.path.splitext(filename or "")[1].lstrip(".").lower()
    ext = EXT_ALIASES.get(ext, ext)
    detected = sniff(data)
    if detected is None or detected not in allowed or ext != detected:
        raise ApiError(415, MSG_UNSUPPORTED_TYPE)
    return Media(data=data, ext=detected, kind="image" if detected in IMAGE_TYPES else "audio")


def parse_report_request(req, max_bytes: int):
    """Shared parsing for POST /triage and POST /tickets.
    Order matters: missing media (400) -> size (413) -> type (415) -> location (400)."""
    file = req.files.get("media")
    if file is None or not file.filename:
        raise ApiError(400, MSG_MISSING_FIELDS)
    data = read_limited(file, max_bytes)
    if not data:
        raise ApiError(400, MSG_MISSING_FIELDS)
    media = classify(data, file.filename, IMAGE_TYPES | AUDIO_TYPES)
    lat = parse_coord(req.form.get("latitude"), -90.0, 90.0, "Latitude")
    lon = parse_coord(req.form.get("longitude"), -180.0, 180.0, "Longitude")
    if lat is None or lon is None:
        raise ApiError(400, MSG_MISSING_FIELDS)
    return media, lat, lon, parse_accuracy(req.form.get("accuracy"))


def save_media(media: Media, upload_dir: Path) -> str:
    """Stores the file under a random name and returns the app-relative URL path."""
    upload_dir = Path(upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.{media.ext}"
    (upload_dir / name).write_bytes(media.data)
    return f"/media/{name}"


def remove_media(url_path: str, upload_dir: Path) -> None:
    name = url_path.rsplit("/", 1)[-1]
    try:
        (Path(upload_dir) / name).unlink()
    except OSError:
        pass
