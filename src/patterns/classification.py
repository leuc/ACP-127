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
        r"^\s*(" + "|".join(_CLASSIFICATIONS) + r")\s*$",
        name="classification_marker",
        tags=["classification"],
        flags=re.MULTILINE | re.IGNORECASE,
    )

    rebulk.rules(CollectClassificationMarkers)

    return rebulk


class CollectClassificationMarkers(Rule):
    """Aggregate all classification markers into a single match with a list value."""

    priority = 32
    consequence = [RemoveMatch, AppendMatch]

    def when(self, matches, context):
        markers = list(matches.named("classification_marker"))
        if not markers:
            return False

        unique_values = list(dict.fromkeys(m.raw.strip().upper() for m in markers))

        to_remove = list(markers)
        to_append = [
            Match(
                markers[0].start,
                markers[0].end,
                value=unique_values,
                name="classification_markers",
                tags=["classification"],
            )
        ]
        return to_remove, to_append
