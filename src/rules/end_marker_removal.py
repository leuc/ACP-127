"""Strip end-of-message markers (NNN, NNNN, NNNNMAFVVZCZ, etc.) from content text.

End markers are removed without JSON output.
"""

from rebulk import Rule
from rebulk.rules import Consequence

from ..rules.page_break_extraction import ExtractPageBreak


class StripEndMarkers(Consequence):
    """Strip end markers from text."""

    def then(self, matches, when_response, context):
        text_end, attr_start, em_matches = when_response

        ranges = context.setdefault("_strip_ranges", [])
        for m in em_matches:
            start = m.start - text_end
            end = m.end - text_end
            if start < 0:
                start = 0
            ranges.append((start, end))

        for old in matches.named("end_marker"):
            if old in matches:
                matches.remove(old)

        return True


class RemoveEndMarker(Rule):
    """Remove end-of-message markers from content text.

    Runs after ExtractPageBreak — page breaks must be removed first
    since they are used for classification adjacency validation.
    """

    priority = 112
    dependency = ExtractPageBreak
    consequence = StripEndMarkers()

    def when(self, matches, context):
        text_ms = matches.markers.named("message_text_marker")
        attr_ms = matches.markers.named("message_attributes_marker")
        if len(text_ms) != 1 or len(attr_ms) != 1:
            return False
        text_end, attr_start = text_ms[0].end, attr_ms[0].start

        em_matches = [
            m for m in matches.named("end_marker") if text_end <= m.start < attr_start
        ]
        if not em_matches:
            return False

        return text_end, attr_start, em_matches
