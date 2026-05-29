"""Extract dash counter (---- line with count) from message content.

The dash counter is a line of 10+ dashes followed by a count number,
found at the top of the message body. It is extracted and removed
from message_content.
"""

from rebulk import Rebulk, Rule
from rebulk.match import Match
from rebulk.remodule import re


def dash_counter():
    """Build pattern that matches the dash counter line."""
    rebulk = Rebulk()

    rebulk.regex(
        r"^\s{4,}\-{10,}\s*\d+",
        name="dash_counter",
        tags=["dash_counter"],
        flags=re.MULTILINE,
    )

    rebulk.rules(CollectDashCounters)

    return rebulk


class CollectDashCounters(Rule):
    """Reduce dash counter markers to a single scalar value.

    Only the first marker is kept — there should be exactly one
    per document.
    """

    priority = 32

    def when(self, matches, context):
        markers = list(matches.named("dash_counter"))
        if not markers:
            return False

        first = markers[0]
        parts = first.raw.strip().split()
        num = int(parts[-1]) if parts and parts[-1].isdigit() else 0

        dc_match = Match(
            first.start,
            first.end,
            value=num,
            name="dash_counters",
            tags=["dash_counter"],
        )
        return markers, dc_match

    def then(self, matches, when_response, context):
        markers, dc_match = when_response
        for m in markers:
            if m in matches:
                matches.remove(m)
        matches.append(dc_match)
