"""Extract the FM (FROM) line from message content.

Per ACP-127: the FM line identifies the originator of the message.
It appears after the DTG line and before TO/INFO routing lines.

Output field:
  _from — the originator text (e.g. "USMISSION NATO")
"""

from rebulk import Rebulk, Rule
from rebulk.remodule import re


def _parse_from_line(line):
    """Return the originator text after the FM prefix."""
    return line[3:].strip()


def from_line():
    """Build pattern that matches the FM (FROM) line."""
    rebulk = Rebulk()

    rebulk.regex(
        r"^FM\s+(?P<from>.+)$",
        name="from",
        tags=["message_content"],
        formatter=_parse_from_line,
        flags=re.MULTILINE,
    )

    rebulk.rules(ValidateFrom)

    return rebulk


class ValidateFrom(Rule):
    """Validate FM matches: must be within message content region."""

    priority = 32

    def when(self, matches, context):
        text_ms = matches.markers.named("message_text_marker")
        attr_ms = matches.markers.named("message_attributes_marker")
        if len(text_ms) != 1 or len(attr_ms) != 1:
            return list(matches.named("from"))

        region_start = text_ms[0].end
        region_end = attr_ms[0].start

        to_remove = []
        for m in matches.named("from"):
            if not (region_start <= m.start < region_end):
                to_remove.append(m)

        return to_remove

    def then(self, matches, when_response, context):
        for m in when_response:
            if m in matches:
                matches.remove(m)
