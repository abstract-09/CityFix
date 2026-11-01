"""All timestamps are UTC, ISO 8601, formatted YYYY-MM-DDTHH:mm:ssZ.

Call these through the module (timeutil.now()) so tests can patch the clock.
"""
from datetime import datetime, timezone

FMT = "%Y-%m-%dT%H:%M:%SZ"


def now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(FMT)


def parse(value: str) -> datetime:
    return datetime.strptime(value, FMT).replace(tzinfo=timezone.utc)


def hours_between(start_iso: str, end_iso: str) -> float:
    return max(0.0, (parse(end_iso) - parse(start_iso)).total_seconds() / 3600.0)
