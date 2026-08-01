"""Extract Date-Time Group (DTG) from message content — raw components only.

Per ACP-127(G) §113: DTG is 6 digits (DDHHMM) + zone suffix Z +
3-letter month + optional 2-digit year.  The line may be prefixed
by precedence prosigns (§150): Z=FLASH, O=IMMEDIATE, P=PRIORITY, R=ROUTINE.
Dual precedence (§152) is indicated by two prosigns (e.g. "P R").

This module only extracts the raw matched pieces — century inference,
calendar validation, and precedence-letter mapping happen downstream in
src/date_utils.py::parse_dtg (see src/date_normalize.py), so rebulk stays
extraction-only and all date parsing lives in one shared place.

Output fields:
  _dtg — {raw, precedence_raw, dd, hh, mm, mon, yy}

Stripped from message_content after extraction.
"""

from rebulk import Rebulk, Rule
from rebulk.remodule import re

_MONTH_NAMES = [
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
]

_MONTH_PAT = "|".join(_MONTH_NAMES)

_DTG_RE = re.compile(
    rf"^(?P<full>(?:[ZOPR] [ZOPR] |[ZOPR] )(?P<dd>\d{{2}})(?P<hh>\d{{2}})(?P<mm>\d{{2}})Z (?P<mon>{_MONTH_PAT}) (?P<yy>\d{{2}}))\s*$",
    re.MULTILINE,
)


def _raw_dtg(line):
    """Return the raw captured DTG components, unparsed."""
    m = _DTG_RE.match(line)
    if not m:
        return None
    g = m.groupdict()
    precedence_raw = g["full"][: g["full"].index(g["dd"])].strip()
    return {
        "raw": g["full"],
        "precedence_raw": precedence_raw,
        "dd": g["dd"],
        "hh": g["hh"],
        "mm": g["mm"],
        "mon": g["mon"],
        "yy": g["yy"],
    }


def dtg():
    """Build pattern that matches DTG lines in message content."""
    rebulk = Rebulk()

    rebulk.regex(
        _DTG_RE,
        name="dtg",
        tags=["message_content"],
        every=True,
        private_names=["full", "dd", "hh", "mm", "mon", "yy"],
        formatter=_raw_dtg,
    )

    rebulk.rules(ParseDTG)

    return rebulk


class ParseDTG(Rule):
    """Scope DTG matches to the message content region.

    Only structural scoping happens here — a match must fall between the
    message_text_marker and message_attributes_marker. Calendar validation
    (century inference, day/month bounds, 1973-1979 plausibility) happens
    downstream in src/date_utils.py::parse_dtg.
    """

    priority = 32

    def when(self, matches, context):
        text_ms = matches.markers.named("message_text_marker")
        attr_ms = matches.markers.named("message_attributes_marker")
        if len(text_ms) != 1 or len(attr_ms) != 1:
            return list(matches.named("dtg"))

        region_start = text_ms[0].end
        region_end = attr_ms[0].start

        return [
            m for m in matches.named("dtg") if not (region_start <= m.start < region_end)
        ]

    def then(self, matches, when_response, context):
        for m in when_response:
            if m in matches:
                matches.remove(m)
