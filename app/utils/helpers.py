"""Utility helpers."""
from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def format_pips(value: float, digits: int = 5) -> float:
    """Convert price difference to pips."""
    if digits == 3 or digits == 5:
        return round(value * 10000, 1)
    elif digits == 2 or digits == 4:
        return round(value * 100, 1)
    return round(value, 2)
