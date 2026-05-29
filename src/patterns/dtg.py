"""Extract Date-Time Group (DTG) from message content and parse to ISO 8601.

Per ACP-127(G) §113: DTG is 6 digits (DDHHMM) + zone suffix Z +
3-letter month + optional 2-digit year.  The line may be prefixed
by precedence prosigns (§150): Z=FLASH, O=IMMEDIATE, P=PRIORITY, R=ROUTINE.
Dual precedence (§152) is indicated by two prosigns (e.g. "P R").

Output fields:
  _dtg — {raw, precedence, date_iso}
"""

from datetime import datetime

from rebulk import Rebulk, Rule, RemoveMatch, AppendMatch
from rebulk.match import Match
from rebulk.remodule import re

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

_MONTH_PAT = "|".join(_MONTHS)

_DTG_RE = re.compile(
    rf"^(?P<full>(?:[ZOPR] [ZOPR] |[ZOPR] )(?P<dd>\d{{2}})(?P<hh>\d{{2}})(?P<mm>\d{{2}})Z (?P<mon>{_MONTH_PAT}) (?P<yy>\d{{2}}))\s*$",
    re.MULTILINE,
)

_PRECEDENCE_MAP = {
    "Z": "FLASH",
    "O": "IMMEDIATE",
    "P": "PRIORITY",
    "R": "ROUTINE",
}


def _parse_year(yy):
    """Convert 2-digit year to 4-digit per ACP-127 spec §113.

    06-99 → 1906-1999, 00-05 → 2000-2005.
    """
    y = int(yy)
    return 2000 + y if y <= 5 else 1900 + y


def _parse_dtg_line(line):
    """Parse a DTG line and return parsed dict or None if invalid."""
    m = _DTG_RE.match(line)
    if not m:
        return None
    g = m.groupdict()
    yyyy = _parse_year(g["yy"])
    dt = datetime(yyyy, _MONTHS[g["mon"]], int(g["dd"]), int(g["hh"]), int(g["mm"]))
    prec_raw = g["full"][: g["full"].index(g["dd"])].strip()
    return {
        "raw": g["full"],
        "precedence": [_PRECEDENCE_MAP.get(c, c) for c in prec_raw.split()],  # type: ignore[arg-type]
        "date_iso": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def dtg():
    """Build pattern that matches DTG lines in message content."""
    rebulk = Rebulk()

    rebulk.regex(
        _DTG_RE,
        name="dtg",
        tags=["message_content"],
    )

    rebulk.rules(ParseDTG)

    return rebulk


class ParseDTG(Rule):
    """Parse DTG lines, validate year 1973-1979, produce parsed match.

    Removes all original regex dtg matches and replaces them with a single
    validated _dtg match containing {raw, precedence, date_iso}.
    """

    priority = 32
    consequence = [RemoveMatch, AppendMatch]

    def when(self, matches, context):
        text_ms = matches.markers.named("message_text_marker")
        attr_ms = matches.markers.named("message_attributes_marker")
        if len(text_ms) != 1 or len(attr_ms) != 1:
            return list(matches.named("dtg")), []

        region_start = text_ms[0].end
        region_end = attr_ms[0].start

        all_dtg = list(matches.named("dtg"))
        if not all_dtg:
            return False

        to_remove = []
        to_append = []
        for m in all_dtg:
            if not (region_start <= m.start < region_end):
                to_remove.append(m)
                continue
            parsed = _parse_dtg_line(m.value)
            if parsed is None or parsed["date_iso"] is None:
                to_remove.append(m)
                continue
            year = int(parsed["date_iso"][:4])
            if year < 1973 or year > 1979:
                to_remove.append(m)
                continue
            to_remove.append(m)
            to_append.append(
                Match(
                    m.start,
                    m.end,
                    value={
                        "raw": parsed["raw"],
                        "precedence": parsed["precedence"],
                        "date_iso": parsed["date_iso"],
                    },
                    name="dtg",
                    tags=["parsed"],
                )
            )

        return to_remove, to_append
