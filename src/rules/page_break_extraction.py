"""Strip page break lines and surrounding whitespace from content text.

Page breaks (PAGE N lines) are extracted to JSON and removed from the
body. Empty lines before and after each page break are removed to
merge continuous text.
"""

from rebulk import Rule
from rebulk.match import Match
from rebulk.rules import Consequence

from ..rules.classification_extraction import ExtractClassificationMarker


class StripPageBreaks(Consequence):
    """Strip page breaks + surrounding empty lines from text."""

    def then(self, matches, when_response, context):
        text_end, attr_start, pb_matches, output_value = when_response

        ranges = context.setdefault("_strip_ranges", [])
        for m in sorted(pb_matches, key=lambda m: m.start, reverse=True):
            s = m.start - text_end
            e = m.end - text_end
            ranges.append((s, e))

        for old in matches.named("page_break"):
            if old in matches:
                matches.remove(old)

        matches.append(
            Match(
                pb_matches[0].start,
                pb_matches[-1].end,
                value=output_value,
                name="page_break",
                tags=["page_break"],
            )
        )
        return True


class ExtractPageBreak(Rule):
    """Identify and extract page breaks from message content.

    Runs after ExtractClassificationMarker — classification markers
    must be removed first since page breaks are used to validate
    classification adjacency.
    """

    priority = 128
    dependency = ExtractClassificationMarker
    consequence = StripPageBreaks()

    def when(self, matches, context):
        text_ms = matches.markers.named("message_text_marker")
        attr_ms = matches.markers.named("message_attributes_marker")
        if len(text_ms) != 1 or len(attr_ms) != 1:
            return False
        text_end, attr_start = text_ms[0].end, attr_ms[0].start

        pb_matches = [
            m for m in matches.named("page_break") if text_end <= m.start < attr_start
        ]
        if not pb_matches:
            return False

        page_entries = []
        for m in pb_matches:
            parts = m.raw.strip().split()
            entry = {"line": m.raw.strip()}
            if len(parts) >= 2 and parts[0].upper() == "PAGE" and parts[1].isdigit():
                entry["page"] = int(parts[1])
            page_entries.append(entry)

        return text_end, attr_start, pb_matches, page_entries
