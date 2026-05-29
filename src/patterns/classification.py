"""Identify standalone classification marker lines (UNCLASSIFIED, CONFIDENTIAL, etc.)."""

from rebulk import Rebulk, Rule, RemoveMatch, AppendMatch
from rebulk.match import Match
from rebulk.remodule import re

_CLASSIFICATIONS = [
    "UNCLASSIFIED",
    "LIMITED OFFICIAL USE",
    "CONFIDENTIAL",
    "SECRET",
    "TOP SECRET",
]


def classification():
    """Build pattern that matches standalone classification marker lines."""
    rebulk = Rebulk()

    rebulk.regex(
        r"^\s*(?P<classification>" + "|".join(_CLASSIFICATIONS) + r")\s*$",
        name="classification_marker",
        tags=["classification"],
        flags=re.MULTILINE | re.IGNORECASE,
    )

    rebulk.rules(CollectClassificationMarkers)

    return rebulk


_MAX_GAP = 500
_MAX_END_DISTANCE = 1500


class CollectClassificationMarkers(Rule):
    """Aggregate classification markers into a single match with a list value.

    Only includes markers that are near page breaks, end markers, or
    the end of the message content region — this filters out
    classification words that happen to appear as standalone lines
    within the message body.
    """

    priority = 32
    consequence = [RemoveMatch, AppendMatch]

    def _near_page_break(self, m, text, page_breaks):
        for pb in page_breaks:
            if m.end <= pb.start:
                gap = text[m.end : pb.start]
            elif pb.end <= m.start:
                gap = text[pb.end : m.start]
            else:
                continue
            if not gap.strip() and len(gap) < _MAX_GAP:
                return True
        return False

    def _near_end_marker(self, m, text, end_markers):
        for em in end_markers:
            if em.start >= m.end:
                gap = text[m.end : em.start]
                if not gap.strip() and len(gap) < _MAX_GAP:
                    return True
        return False

    def _near_content_end(self, m, text, content_end):
        if content_end is None:
            return False
        distance = content_end - m.end
        if 0 < distance < _MAX_END_DISTANCE:
            gap = text[m.end : content_end]
            non_blank = [l for l in gap.split("\n") if l.strip()]
            if len(non_blank) <= 4:
                return True
        return False

    def when(self, matches, context):
        markers = list(matches.named("classification_marker"))
        if not markers:
            return False

        text = matches.input_string
        page_breaks = list(matches.named("page_break"))
        end_markers = list(matches.named("end_marker"))

        attr_ms = matches.markers.named("message_attributes_marker")
        content_end = attr_ms[0].start if attr_ms else None

        valid = []
        for m in markers:
            if self._near_page_break(m, text, page_breaks):
                valid.append(m)
            elif self._near_end_marker(m, text, end_markers):
                valid.append(m)
            elif self._near_content_end(m, text, content_end):
                valid.append(m)

        if not valid:
            return list(markers), []

        unique_values = list(dict.fromkeys(m.raw.strip().upper() for m in valid))

        to_remove = list(markers)
        to_append = [
            Match(
                valid[0].start,
                valid[0].end,
                value=unique_values,
                name="classification_markers",
                tags=["classification"],
            )
        ]
        return to_remove, to_append
