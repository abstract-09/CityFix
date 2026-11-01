"""Shared constants. The enums live in shared/constants.json so the frontend reads the same values."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHARED_DIR = ROOT / "shared"

with open(SHARED_DIR / "constants.json", encoding="utf-8") as _fh:
    CONSTANTS = json.load(_fh)

CATEGORIES = tuple(CONSTANTS["categories"])
SEVERITIES = tuple(CONSTANTS["severities"])
STATUSES = tuple(CONSTANTS["statuses"])
DEPARTMENTS = tuple(CONSTANTS["departments"])
CONFIDENCE_THRESHOLD = float(CONSTANTS["confidence_threshold"])
DUPLICATE_RADIUS_M = float(CONSTANTS["duplicate_radius_m"])
HIGHWAY_BUFFER_M = float(CONSTANTS["highway_buffer_m"])
MAX_DESCRIPTION_CHARS = int(CONSTANTS["max_description_chars"])
MARKER_COLORS = CONSTANTS["markers"]

DEPT_RCD, DEPT_NHAI, DEPT_MUNICIPAL, DEPT_GENERAL = DEPARTMENTS
SEVERITY_RANK = {"Critical": 0, "Medium": 1, "Low": 2}

TICKET_ID_RE = re.compile(r"^CIV-\d{4}-\d{4,}$")

# User-facing messages (literal strings from the specification)
MSG_MISSING_FIELDS = "Please attach media and ensure GPS location permission is enabled"
MSG_UNSUPPORTED_TYPE = "Unsupported file format. Please upload JPG, PNG, or MP3 files"
MSG_TICKET_NOT_FOUND = "Ticket not found. Please check your tracking reference code"
MSG_AI_UNAVAILABLE = "AI triage service temporarily unavailable. Default fallback applied"
MSG_DUPLICATE = "Similar issue already reported nearby. Your report has been merged to increment priority"
MSG_PROOF_REQUIRED = "Mandatory resolution photo proof is required prior to closing ticket"
MSG_SYSTEM_ERROR = "System error occurred. Please try again shortly"
STUB_DESCRIPTION = "Automated triage unavailable - stub mode active"
LOW_CONFIDENCE_DESCRIPTION = "Needs manual review"
AI_FAILURE_DESCRIPTION = "Manual review required"


def msg_too_large(max_mb: float) -> str:
    shown = int(max_mb) if float(max_mb).is_integer() else max_mb
    return f"Please use a file smaller than {shown} MB"
