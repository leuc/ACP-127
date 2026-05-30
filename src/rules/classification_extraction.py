"""Strip classification markers from text, output aggregated match.

Classification markers (UNCLASSIFIED, CONFIDENTIAL, SECRET, etc.) that
are directly NEXT to page_break or end_marker are extracted to JSON and
removed from the text body.
"""

from rebulk import Rule
from rebulk.match import Match
from rebulk.rules import Consequence

from ..patterns.locator import TagLocatorTextOnline

_MAX_GAP = 500
_MAX_END_DISTANCE = 1500


class StripClassificationMarkers(Consequence):
    """Strip classification markers from text, output aggregated match."""

    def then(self, matches, when_response, context):
        text_end, attr_start, all_matches, valid_matches, output_value = when_response

        ranges = context.setdefault("_strip_ranges", [])
        raw = matches.input_string[text_end:attr_start]
        for m in all_matches:
            start = m.start - text_end
            end = m.end - text_end
            m_start = start
            if start < 0:
                start = 0
            while start > 0 and raw[start - 1] in "\n\r":
                start -= 1
            if start < m_start:
                start += 1
            while end < len(raw) and raw[end] in "\n\r":
                end += 1
            ranges.append((start, end))

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

        unique_values = list(dict.fromkeys(m.raw.strip().upper() for m in valid))
        return text_end, attr_start, cm_matches, valid, unique_values

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
    def _near_page_break(m, text, page_breaks):
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

    @staticmethod
    def _near_end_marker(m, text, end_markers):
        for em in end_markers:
            if em.start >= m.end:
                gap = text[m.end : em.start]
                if not gap.strip() and len(gap) < _MAX_GAP:
                    return True
        return False

    @staticmethod
    def _near_content_end(m, text, content_end):
        if content_end is None:
            return False
        distance = content_end - m.end
        if 0 < distance < _MAX_END_DISTANCE:
            gap = text[m.end : content_end]
            non_blank = [l for l in gap.split("\n") if l.strip()]
            if len(non_blank) <= 4:
                return True
        return False
