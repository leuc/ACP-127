r"""Identify page break markers (PAGE \d+) and end-of-message markers (NNNNMAFVVZCZ).

Page break lines are extracted as _page_breaks and stripped from _message_content
(via MessageContentRegion in split.py using rebulk match positions).
End-of-message markers are used internally for classification proximity validation.
"""

from functools import partial

from rebulk import Rebulk, Rule, RemoveMatch, AppendMatch
from rebulk.match import Match
from rebulk.remodule import re
from rebulk.validators import chars_before

from ..rules.split import MessageContentRegion

_KNOWN_END_MARKERS = {"NNN", "NNNN", "NNNNMAFVVZCZ", "<< END OF DOCUMENT >>"}


def page_break():
    """Build pattern that matches page break and end-of-message markers."""
    rebulk = Rebulk()
    rebulk.defaults(flags=re.MULTILINE)

    rebulk.regex(
        r"^PAGE\s+(?P<page_number>\d+).*",
        name="page_break",
        tags=["page_break"],
        flags=re.MULTILINE | re.IGNORECASE,
        every=True,
        private_names=["page_number"],
    )

    for marker in _KNOWN_END_MARKERS:
        rebulk.string(
            marker,
            name="end_marker",
            tags=["end_marker"],
            validator=partial(chars_before, "\n"),
        )

    rebulk.regex(
        r"^\*\*\* Current (?:Handling Restrictions|Classification) .*",
        name="content_footer_marker",
        tags=["content_footer"],
    )

    rebulk.regex(
        r"^\s{4,}\-{10,}\s*\d+",
        name="dash_counter",
        tags=["dash_counter"],
    )

    rebulk.rules(
        CollectPageBreaks,
        CollectEndMarkers,
        CollectDashCounters,
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

        page_entries = []
        for m in markers:
            text = m.raw.strip()
            parts = text.split()
            entry = {"line": text}
            if len(parts) >= 2 and parts[0].upper() == "PAGE" and parts[1].isdigit():
                entry["page"] = int(parts[1])
            page_entries.append(entry)

        to_remove = list(markers)
        to_append = [
            Match(
                markers[0].start,
                markers[-1].end,
                value=page_entries,
                name="page_breaks",
                tags=["page_break"],
            )
        ]
        return to_remove, to_append


class CollectEndMarkers(Rule):
    """Collect end-of-message markers within message content for internal use.

    Only end markers between Message Text and Message Attributes markers
    are kept — markers outside the content region are simply removed.
    Private so they don't appear in output.
    """

    priority = 32
    dependence = MessageContentRegion
    consequence = [RemoveMatch, AppendMatch]

    def when(self, matches, context):
        text_ms = matches.markers.named("message_text_marker")
        attr_ms = matches.markers.named("message_attributes_marker")

        all_markers = list(matches.named("end_marker"))
        if not all_markers:
            return False

        if len(text_ms) == 1 and len(attr_ms) == 1:
            rs, re = text_ms[0].end, attr_ms[0].start
            markers = [m for m in all_markers if rs <= m.start < re]
        else:
            markers = list(all_markers)

        if not markers:
            return list(all_markers), []

        to_remove = list(all_markers)
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


class CollectDashCounters(Rule):
    """Reduce dash counter markers to a single scalar value.

    Only the first marker is kept — there should be exactly one
    per document.
    """

    priority = 32
    consequence = [RemoveMatch, AppendMatch]

    def when(self, matches, context):
        markers = list(matches.named("dash_counter"))
        if not markers:
            return False

        first = markers[0]
        parts = first.raw.strip().split()
        num = int(parts[-1]) if parts and parts[-1].isdigit() else 0

        to_remove = list(markers)
        to_append = [
            Match(
                first.start,
                first.end,
                value=num,
                name="dash_counters",
                tags=["dash_counter"],
            )
        ]
        return to_remove, to_append
