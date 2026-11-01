"""Input validation helpers. All user input is treated as data, never as instructions."""
from __future__ import annotations

import math
import re

from .errors import ApiError

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)+$")


def validate_contact(value) -> str | None:
    """Optional email address or 10-digit phone number. Returns the normalised value or None."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) <= 254 and EMAIL_RE.match(text):
        return text.lower()
    digits = re.sub(r"[\s\-]", "", text)
    if digits.startswith("+91"):
        digits = digits[3:]
    if re.fullmatch(r"\d{10}", digits):
        return digits
    raise ApiError(400, "Contact must be a valid email address or a 10-digit phone number")


def parse_coord(value, low: float, high: float, label: str):
    """Returns a float rounded to 6 decimals, or None when the value is absent."""
    if value is None or str(value).strip() == "":
        return None
    try:
        number = float(str(value).strip())
    except ValueError:
        number = float("nan")
    if not math.isfinite(number) or not (low <= number <= high):
        raise ApiError(400, f"{label} must be a number between {low:g} and {high:g}")
    return round(number, 6)


def parse_accuracy(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        number = float(str(value).strip())
    except ValueError:
        return None
    return round(number, 1) if math.isfinite(number) and 0 <= number <= 1_000_000 else None


def clean_text(value, max_len: int) -> str:
    """Strip control characters, collapse whitespace and cap the length."""
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", str(value or ""))
    return re.sub(r"[ \t]+", " ", text).strip()[:max_len]
