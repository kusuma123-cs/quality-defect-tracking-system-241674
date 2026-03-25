from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Mapping


# PUBLIC_INTERFACE
def utc_now_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# PUBLIC_INTERFACE
def parse_date(value: str | None) -> date | None:
    """Parse YYYY-MM-DD string to date, returning None for empty values."""
    if value is None or value == "":
        return None
    return date.fromisoformat(value)


# PUBLIC_INTERFACE
def row_to_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a sqlite3.Row (or mapping) into a plain dict."""
    return {k: row[k] for k in row.keys()}
