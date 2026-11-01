"""Applies the business rules around raw AI output (confidence threshold, failure fallback)."""
from __future__ import annotations

from dataclasses import dataclass

from ..constants import (AI_FAILURE_DESCRIPTION, CATEGORIES, CONFIDENCE_THRESHOLD, LOW_CONFIDENCE_DESCRIPTION,
                         MAX_DESCRIPTION_CHARS, SEVERITIES)
from . import ai_service


@dataclass
class TriageResult:
    category: str
    severity: str
    description: str
    confidence: float | None
    mode: str            # stub | live | fallback
    failed: bool = False  # True when the AI provider could not be reached
    needs_review: bool = False
    ai_category: str | None = None
    ai_severity: str | None = None
    ai_description: str | None = None


def run(settings, media_bytes: bytes, lat: float, lon: float) -> TriageResult:
    try:
        raw = ai_service.analyze_grievance_media(
            media_bytes, {"latitude": lat, "longitude": lon},
            api_key=settings.ai_service_api_key, model=settings.ai_model,
            url=settings.ai_service_url, timeout=settings.ai_timeout_seconds,
        )
    except ai_service.AIServiceUnavailable:
        return TriageResult("Other", "Medium", AI_FAILURE_DESCRIPTION, None, "fallback", failed=True, needs_review=True)

    raw_fields = dict(ai_category=raw["category"], ai_severity=raw["severity"], ai_description=raw["description"])

    if raw["mode"] == "stub":
        return TriageResult(raw["category"], raw["severity"], raw["description"], raw["confidence"],
                            "stub", needs_review=True, **raw_fields)

    usable = raw["category"] in CATEGORIES and raw["severity"] in SEVERITIES
    if usable and raw["confidence"] >= CONFIDENCE_THRESHOLD:
        description = raw["description"] or f"{raw['category']} reported ({raw['severity']} severity)"
        return TriageResult(raw["category"], raw["severity"], description[:MAX_DESCRIPTION_CHARS],
                            raw["confidence"], "live", **raw_fields)

    return TriageResult("Other", "Medium", LOW_CONFIDENCE_DESCRIPTION, raw["confidence"], "live",
                        needs_review=True, **raw_fields)
