"""Strip classification markers from text, output aggregated match.

Classification markers (UNCLASSIFIED, CONFIDENTIAL, SECRET, etc.) that
are directly NEXT to page_break or end_marker are extracted to JSON and
removed from the text body. Validity uses exact adjacency to those
structures -- the intervening source bytes must be blank (or already
recognized removal spans), not a byte cap or an allowance of arbitrary
nonblank lines. Only accepted marker lines are stripped.
"""

from rebulk import Rule
from rebulk.match import Match
from rebulk.rules import Consequence

from ..patterns.locator import TagLocatorTextOnline


class StripClassificationMarkers(Consequence):
    """Strip accepted classification markers, output aggregated match."""

    def then(self, matches, when_response, context):
        text_end, attr_start, valid_matches, output_value = when_response

        ranges = context.setdefault("_strip_ranges", [])
        coverage_ranges = context.setdefault("_coverage_ranges", [])
        for m in valid_matches:
            start = m.start - text_end
            end = m.end - text_end
            if start < 0:
                start = 0
            ranges.append((start, end))
            # Individual raw spans: coverage must use these rather than
            # the aggregate outer bounds (see coverage.calculate_coverage).
            coverage_ranges.append((m.start, m.end))

        for old in matches.named("classification_marker"):
            if old in matches:
                matches.remove(old)

        matches.append(
            Match(
                valid_matches[0].start,
                valid_matches[-1].end,
                value=output_value,
                name="classification_marker",
                tags=["classification"],
            )
        )
        return True


class ExtractClassificationMarker(Rule):
    """Identify and extract classification markers near page breaks/end markers.

    Runs after TagLocatorTextOnline — only operates when text-online
    locator exists.
    """

    priority = 144
    dependency = TagLocatorTextOnline
    consequence = StripClassificationMarkers()

    def when(self, matches, context):
        text_ms = matches.markers.named("message_text_marker")
        attr_ms = matches.markers.named("message_attributes_marker")
        if len(text_ms) != 1 or len(attr_ms) != 1:
            return False
        text_end, attr_start = text_ms[0].end, attr_ms[0].start
        if attr_start <= text_end:
            return False

        cm_matches = [
            m
            for m in matches.named("classification_marker")
            if text_end <= m.start < attr_start
        ]
        if not cm_matches:
            return False

        valid = self._filter_adjacent(cm_matches, matches, text_end, attr_start)
        if not valid:
            return False

        unique_values = list(dict.fromkeys(m.value for m in valid))
        return text_end, attr_start, valid, unique_values

    def _filter_adjacent(self, cm_matches, matches, text_end, attr_start):
        """Only keep markers directly NEXT to page_break or end_marker."""
        text = matches.input_string
        page_breaks = list(matches.named("page_break"))
        end_markers = list(matches.named("end_marker"))

        valid = []
        for m in cm_matches:
            if self._near_page_break(m, text, page_breaks):
                valid.append(m)
            elif self._near_end_marker(m, text, end_markers):
                valid.append(m)
            elif self._near_content_end(m, text, attr_start):
                valid.append(m)
        return valid

    @staticmethod
    def _gap_is_blank(text, start, end):
        """Return whether the intervening bytes are blank/removal spans.

        Exact adjacency: only whitespace between the marker and the
        page/end structure. An empty gap (abutting matches) is the
        tightest adjacency. No byte caps, no nonblank-line allowance.
        """
        if start >= end:
            return True
        return not text[start:end].strip()

    @classmethod
    def _near_page_break(cls, m, text, page_breaks):
        for pb in page_breaks:
            if m.end <= pb.start:
                gap_blank = cls._gap_is_blank(text, m.end, pb.start)
            elif pb.end <= m.start:
                gap_blank = cls._gap_is_blank(text, pb.end, m.start)
            else:
                continue
            if gap_blank:
                return True
        return False

    @classmethod
    def _near_end_marker(cls, m, text, end_markers):
        for em in end_markers:
            if em.start >= m.end:
                if cls._gap_is_blank(text, m.end, em.start):
                    return True
        return False

    @classmethod
    def _near_content_end(cls, m, text, content_end):
        if content_end is None:
            return False
        if m.end >= content_end:
            return False
        # Content-end path must not accept substantive lines: only a
        # blank gap to the attributes boundary validates.
        return cls._gap_is_blank(text, m.end, content_end)
