"""Extract Date-Time Group (DTG) from message content — raw components only.

Per ACP-127(G) §113: DTG is 6 digits (DDHHMM) + zone suffix Z +
3-letter month + optional 2-digit year.  The line may be prefixed
by precedence prosigns (§150): Z=FLASH, O=IMMEDIATE, P=PRIORITY, R=ROUTINE.
Dual precedence (§152) is indicated by two prosigns (e.g. "P R").

This module only extracts the raw matched pieces — century inference,
calendar validation, and precedence-letter mapping happen downstream in
src/date_utils.py::parse_dtg (see src/date_normalize.py), so rebulk stays
extraction-only and all date parsing lives in one shared place.

Per AGENTS.md, the source text carries NARA reproduction noise, not OCR
noise — the dominant artifact on DTG lines is stray whitespace injected
mid-token ("JUN 7 3", "251346 Z"), not character substitution.  Every
fixed-width piece of the DTG is therefore matched digit-by-digit /
letter-by-letter with optional `\\s*` between characters (same technique
`section_marker.py::_spaced_alternation` uses for spaced classifications),
which recovered ~96% of an otherwise-unmatched sample. The Z zone suffix is
optional (some lines drop it entirely) and a trailing same-line token (a
routing/circuit designator like "ZDK", "ZFF-4") is consumed but discarded
so it doesn't pollute _message_content. Months are also accepted spelled in
full ("JUNE") since that variant appears alongside the standard 3-letter
form; `_raw_dtg` normalizes both spacing and full-month spelling away.

Output fields:
  _dtg — {raw, precedence_raw, dd, hh, mm, mon, yy}

Stripped from message_content after extraction.
"""

from rebulk import Rebulk, Rule
from rebulk.remodule import re

_MONTH_FULL = {
    "JAN": "JANUARY", "FEB": "FEBRUARY", "MAR": "MARCH", "APR": "APRIL",
    "MAY": "MAY", "JUN": "JUNE", "JUL": "JULY", "AUG": "AUGUST",
    "SEP": "SEPTEMBER", "OCT": "OCTOBER", "NOV": "NOVEMBER", "DEC": "DECEMBER",
}
_MONTH_NAMES = list(_MONTH_FULL)


def _spaced(literal):
    """Join a literal's characters with `\\s*` to tolerate injected whitespace."""
    return r"\s*".join(re.escape(c) for c in literal)


def _spaced_digits(n):
    return r"\s*".join([r"\d"] * n)


def _month_pattern(abbr):
    """3-letter abbreviation, with the rest of the full name optional."""
    rest = _MONTH_FULL[abbr][3:]
    if rest:
        return _spaced(abbr) + r"(?:" + _spaced(rest) + r")?"
    return _spaced(abbr)


_MONTH_PAT = "|".join(_month_pattern(m) for m in _MONTH_NAMES)

_DTG_RE = re.compile(
    r"^[ \t]*(?P<full>(?:[ZOPR]\s+[ZOPR]\s+|[ZOPR]\s+)"
    rf"(?P<dd>{_spaced_digits(2)})(?P<hh>{_spaced_digits(2)})(?P<mm>{_spaced_digits(2)})"
    r"\s*Z?\s+"
    rf"(?P<mon>{_MONTH_PAT})"
    rf"\s+(?P<yy>{_spaced_digits(2)}))"
    r"(?:[ \t]+\S.*)?\s*$",
    re.MULTILINE,
)


def _raw_dtg(line):
    """Return the raw captured DTG components, unparsed (whitespace collapsed)."""
    m = _DTG_RE.match(line)
    if not m:
        return None
    g = m.groupdict()
    precedence_raw = g["full"][: g["full"].index(g["dd"])].strip()
    return {
        "raw": g["full"],
        "precedence_raw": precedence_raw,
        "dd": re.sub(r"\s+", "", g["dd"]),
        "hh": re.sub(r"\s+", "", g["hh"]),
        "mm": re.sub(r"\s+", "", g["mm"]),
        "mon": re.sub(r"\s+", "", g["mon"])[:3],
        "yy": re.sub(r"\s+", "", g["yy"]),
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
