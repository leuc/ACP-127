"""Extract dash counter (---- line with count) from message content.

The dash counter is a line of 10+ dashes followed by one or two 6-digit
groups, found at the top of the message body. Its shape changed at a
sharp boundary in December 1976:

  pre-1976:  dashes + space + one 6-digit group, e.g. "--------------------- 054819"
  post-1976: dashes glued directly to the first 6-digit group (no space),
             a second 6-digit group, one of the two tagged with a trailing
             "Z", and an optional "/NN" copies suffix, e.g.
             "------------------201212Z 109980 /20" or
             "------------------107579 280824Z /20" (both digit-group
             orderings occur). Rarer secondary suffixes (hyphen/slash/letter,
             occasional transcription noise) can follow the copies count.

The "Z"-tagged group matches ACP-127(G) §115 "FILING TIME/TIME HANDED IN" —
the date/time a message was received by the communications centre for
transmission — which per §116 "MESSAGE IDENTIFICATION" (format line 3) pairs
with a station serial number: "routing indicator + station serial number +
filing time", e.g. "RPDLE 123 11/1215Z" (docs/acp127g.txt:601-621). The other
(non-"Z") digit group is that station serial number — the pre-1976 field, by
continuity the value historically exposed as a bare int.

Output fields:
  _dash_counters — {raw, counter, filing_time, copies}
    counter: int, the station serial number (non-"Z"-tagged digit group)
    filing_time: str|None, the "Z"-tagged filing time group (e.g. "201212Z")
                 if present
    copies: int|None, the "/NN" suffix if present

It is extracted and removed from message_content.
"""

from rebulk import Rebulk, Rule
from rebulk.match import Match
from rebulk.remodule import re

_DASH_RE = re.compile(
    r"^\s{4,}\-{10,}"
    r"\s*(?P<g1>\d{6})(?P<g1z>Z)?"
    r"(?:\s+(?P<g2>\d{6})(?P<g2z>Z)?)?"
    r"(?:\s*/\s*(?P<copies>\d+))?"
    r"(?:[ \t]*\S+)*",
    re.MULTILINE,
)


def _parse_dash_counter_line(line):
    """Parse a dash counter line into {raw, counter, filing_time, copies}."""
    m = _DASH_RE.match(line)
    if not m:
        return {"raw": line.strip(), "counter": None, "filing_time": None, "copies": None}

    g = m.groupdict()
    g1, g1z = g.get("g1"), g.get("g1z")
    g2, g2z = g.get("g2"), g.get("g2z")
    copies = g.get("copies")

    if g1z and not g2z:
        filing_time, counter = g1 + g1z, g2
    elif g2z and not g1z:
        filing_time, counter = g2 + g2z, g1
    else:
        # pre-1976 (only g1), or neither/both groups tagged "Z" (ambiguous
        # no-Z variant): g1 is the counter, g2 (if any) kept as filing_time untagged
        filing_time, counter = g2, g1

    return {
        "raw": line.strip(),
        "counter": int(counter) if counter else None,
        "filing_time": filing_time,
        "copies": int(copies) if copies else None,
    }


def dash_counter():
    """Build pattern that matches the dash counter line."""
    rebulk = Rebulk()

    rebulk.regex(
        _DASH_RE,
        name="dash_counter",
        tags=["dash_counter"],
        private_names=["g1", "g1z", "g2", "g2z", "copies"],
        formatter=_parse_dash_counter_line,
    )

    rebulk.rules(CollectDashCounters)

    return rebulk


class CollectDashCounters(Rule):
    """Reduce dash counter markers to a single value.

    Only the first marker is kept — there should be exactly one
    per document. Its value is already the structured dict computed
    by the pattern's formatter.
    """

    priority = 32

    def when(self, matches, context):
        markers = list(matches.named("dash_counter"))
        if not markers:
            return False
        return markers

    def then(self, matches, when_response, context):
        markers = when_response
        first = markers[0]
        for m in markers:
            if m in matches:
                matches.remove(m)
        matches.append(
            Match(
                first.start,
                first.end,
                value=first.value,
                name="dash_counters",
                tags=["dash_counter"],
            )
        )
