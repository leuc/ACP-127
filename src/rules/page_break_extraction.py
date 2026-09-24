"""Strip page break lines and surrounding whitespace from content text.

Page breaks (PAGE N lines) are extracted to JSON and removed from the
body. The page-break line and only the directly adjacent blank lines
are removed to merge continuous text.
"""

from rebulk import Rule
from rebulk.match import Match
from rebulk.rules import Consequence

from ..rules.classification_extraction import ExtractClassificationMarker


class StripPageBreaks(Consequence):
    """Strip page breaks + directly adjacent blank lines from text."""

    def then(self, matches, when_response, context):
        text_end, attr_start, pb_matches, output_value, strip_spans = when_response

        ranges = context.setdefault("_strip_ranges", [])
        coverage_ranges = context.setdefault("_coverage_ranges", [])
        for start, end in strip_spans:
            ranges.append((start - text_end, end - text_end))
        for m in pb_matches:
            # Individual raw spans for coverage (not the aggregate bounds).
            coverage_ranges.append((m.start, m.end))

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

        text = matches.input_string
        page_entries = []
        strip_spans = []
        for m in pb_matches:
            # Prefer the named page_number group where available; fall
            # back to raw-text parsing instead of re-matching.
            page_number = None
            for child in m.children:
                if child.name == "page_number":
                    try:
                        page_number = int(str(child.value).strip())
                    except (TypeError, ValueError):
                        page_number = None
                    break
            entry = {"line": m.raw.strip()}
            if page_number is not None:
                entry["page"] = page_number
            else:
                parts = m.raw.strip().split()
                if (
                    len(parts) >= 2
                    and parts[0].upper() == "PAGE"
                    and parts[1].isdigit()
                ):
                    entry["page"] = int(parts[1])
            page_entries.append(entry)
            strip_spans.append(self._strip_span(text, m.start, m.end))

        return text_end, attr_start, pb_matches, page_entries, strip_spans

    @staticmethod
    def _strip_span(text, start, end):
        """Extend a page-break span over directly adjacent blank lines only."""
        # Walk backwards over blank lines (whitespace-only between newlines).
        while True:
            line_end = start
            # step over the newline run preceding start
            cursor = line_end - 1
            while cursor >= 0 and text[cursor] in "\n\r":
                cursor -= 1
            line_start = cursor + 1
            # find the start of that line
            while line_start > 0 and text[line_start - 1] not in "\n\r":
                line_start -= 1
            if line_start >= line_end - 1:
                break
            if text[line_start:cursor + 1].strip():
                break
            start = line_start
        # Walk forwards over blank lines.
        while True:
            cursor = end
            while cursor < len(text) and text[cursor] in "\n\r":
                cursor += 1
            line_end = cursor
            while line_end < len(text) and text[line_end] not in "\n\r":
                line_end += 1
            if line_end <= cursor:
                end = cursor
                break
            if text[cursor:line_end].strip():
                break
            end = line_end
        return (start, end)
