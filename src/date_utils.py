"""Shared date parsing: Message-Attribute date strings and DTG components.

Centralizes every string/component -> ISO 8601 conversion used across the
project, so rebulk (src/patterns/) stays extraction-only and
src/date_normalize.py, src/reftel_normalize.py, src/tags_normalize.py share
one implementation instead of each duplicating format lists and calendar
math.
"""

from __future__ import annotations

import re
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
    """Parse a raw Message-Attribute date string into a bare ISO date, or None if unparseable.

    Always returns YYYY-MM-DD, even when the matched format carries a time
    component -- every Message-Attribute date's time-of-day, when present, is
    exactly midnight (a NARA export padding artifact, never real sub-day
    precision), so keeping it would just make the output shape inconsistent
    across documents for no informational gain.
    """
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


def _build_datetime(yyyy: int, mon: str, dd: int, hh: int, mm: int) -> datetime | None:
    if dd < 1 or dd > 31 or hh > 23 or mm > 59:
        return None
    try:
        return datetime(yyyy, _MONTHS[mon], dd, hh, mm)
    except (ValueError, KeyError):
        return None


def parse_dtg(components: dict | None, year_min: int = 1973, year_max: int = 1979) -> dict | None:
    """Parse raw DTG components (from src/patterns/dtg.py) into {raw, precedence, datetime_iso}.

    Returns None if the components don't form a valid, in-range calendar date.
    Named datetime_iso (not date_iso) because the DTG's HH/MM are genuine
    transmission-time precision extracted from the message header itself --
    unlike Message-Attribute dates, this is not padding.
    """
    if not components:
        return None

    yyyy = _dtg_year(components["yy"])
    if yyyy < year_min or yyyy > year_max:
        return None

    dt = _build_datetime(yyyy, components["mon"], int(components["dd"]), int(components["hh"]), int(components["mm"]))
    if dt is None:
        return None

    prec_raw = components.get("precedence_raw") or ""
    return {
        "raw": components["raw"],
        "precedence": [_PRECEDENCE_MAP.get(c, c) for c in prec_raw.split()],
        "datetime_iso": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


_FILING_TIME_RE = re.compile(r"^(?P<dd>\d{2})(?P<hh>\d{2})(?P<mm>\d{2})Z$")


def reconstruct_filing_datetime(filing_time: str | None, dtg_components: dict | None) -> str | None:
    """Reconstruct a full datetime from a bare DDHHMMZ filing-time fragment.

    _dash_counters.filing_time (src/patterns/dash_counter.py) carries only a
    day/hour/minute -- no month/year of its own. Borrows mon/yy from the same
    document's _dtg components (the filing event and the message DTG are the
    same transmission), and applies the same bounds/calendar validation as
    parse_dtg. Returns None if either input is missing, malformed, or the
    reconstructed date is invalid/out of the plausible 1973-1979 range.
    """
    if not filing_time or not dtg_components:
        return None

    m = _FILING_TIME_RE.match(filing_time)
    if not m:
        return None

    yyyy = _dtg_year(dtg_components["yy"])
    if yyyy < 1973 or yyyy > 1979:
        return None

    dt = _build_datetime(yyyy, dtg_components["mon"], int(m["dd"]), int(m["hh"]), int(m["mm"]))
    if dt is None:
        return None

    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
