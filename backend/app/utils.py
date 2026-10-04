from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC datetime (SQLite stores naive datetimes)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
