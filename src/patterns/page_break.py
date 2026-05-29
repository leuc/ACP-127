r"""Identify page break markers (PAGE \d+) and end-of-message markers (NNNNMAFVVZCZ).

Page break lines are extracted as _page_breaks and stripped from _message_content
(via MessageContentRegion in split.py using rebulk match positions).
End-of-message markers are used internally for classification proximity validation.
"""

from rebulk import Rebulk, Rule, RemoveMatch, AppendMatch
from rebulk.match import Match
from rebulk.remodule import re

_KNOWN_END_MARKERS = {"NNNNMAFVVZCZ", "NNNN"}


def page_break():
    """Build pattern that matches page break and end-of-message markers."""
    rebulk = Rebulk()

    rebulk.regex(
        r"^PAGE\s+\d+",
        name="page_break",
        tags=["page_break"],
        flags=re.MULTILINE | re.IGNORECASE,
    )

    for marker in _KNOWN_END_MARKERS:
        rebulk.string(
            marker,
            name="end_marker",
            tags=["end_marker"],
            validator=lambda m: m.start == 0 or m.input_string[m.start - 1] == "\n",
        )

    rebulk.regex(
        r"^\*\*\* Current (?:Handling Restrictions|Classification) .*",
        name="content_footer_marker",
        tags=["content_footer"],
        flags=re.MULTILINE,
    )

    rebulk.rules(
        CollectPageBreaks,
        CollectEndMarkers,
    )

    return rebulk


class CollectPageBreaks(Rule):
    """Aggregate all page break markers into a single match with a list value."""

    priority = 32
    consequence = [RemoveMatch, AppendMatch]

    def when(self, matches, context):
        markers = list(matches.named("page_break"))
        if not markers:
            return False

        page_numbers = []
        for m in markers:
            text = m.raw.strip()
            parts = text.split()
            if len(parts) >= 2 and parts[0].upper() == "PAGE" and parts[1].isdigit():
                page_numbers.append(int(parts[1]))

        to_remove = list(markers)
        to_append = [
            Match(
                markers[0].start,
                markers[0].end,
                value=page_numbers,
                name="page_breaks",
                tags=["page_break"],
            )
        ]
        return to_remove, to_append


class CollectEndMarkers(Rule):
    """Collect end-of-message markers for internal use.

    Private matches so they don't appear in output.
    """

    priority = 32
    consequence = [RemoveMatch, AppendMatch]

    def when(self, matches, context):
        markers = list(matches.named("end_marker"))
        if not markers:
            return False

        to_remove = list(markers)
        to_append = [
            Match(
                markers[0].start,
                markers[-1].end,
                value=[m.raw.strip() for m in markers],
                name="end_markers",
                tags=["end_marker"],
                private=True,
            )
        ]
        return to_remove, to_append
