"""Shared date parsing: Message-Attribute date strings and DTG components.

Centralizes every string/component -> ISO 8601 conversion used across the
project, so rebulk (src/patterns/) stays extraction-only and
src/date_normalize.py, src/reftel_normalize.py, src/tags_normalize.py share
one implementation instead of each duplicating format lists and calendar
math.
"""

from __future__ import annotations

from datetime import datetime

_DATE_FORMATS = [
    "%d %b %Y",
    "%d-%b-%Y %I:%M:%S %p",
    "%d-%b-%Y",
    "%d/%m/%Y",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
]


def parse_date(raw: str | None) -> str | None:
    """Parse a raw Message-Attribute date string into ISO 8601, or None if unparseable."""
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if "%H" in fmt or "%I" in fmt:
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        return dt.strftime("%Y-%m-%d")
    return None


_MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}

_PRECEDENCE_MAP = {
    "Z": "FLASH",
    "O": "IMMEDIATE",
    "P": "PRIORITY",
    "R": "ROUTINE",
}


def _dtg_year(yy: str) -> int:
    """Convert 2-digit year to 4-digit per ACP-127(G) Section 113.

    06-99 -> 1906-1999, 00-05 -> 2000-2005.
    """
    y = int(yy)
    return 2000 + y if y <= 5 else 1900 + y


def parse_dtg(components: dict | None, year_min: int = 1973, year_max: int = 1979) -> dict | None:
    """Parse raw DTG components (from src/patterns/dtg.py) into {raw, precedence, date_iso}.

    Returns None if the components don't form a valid, in-range calendar date.
    """
    if not components:
        return None

    dd, hh, mm = int(components["dd"]), int(components["hh"]), int(components["mm"])
    if dd < 1 or dd > 31 or hh > 23 or mm > 59:
        return None

    yyyy = _dtg_year(components["yy"])
    if yyyy < year_min or yyyy > year_max:
        return None

    try:
        dt = datetime(yyyy, _MONTHS[components["mon"]], dd, hh, mm)
    except ValueError:
        return None

    prec_raw = components.get("precedence_raw") or ""
    return {
        "raw": components["raw"],
        "precedence": [_PRECEDENCE_MAP.get(c, c) for c in prec_raw.split()],
        "date_iso": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
