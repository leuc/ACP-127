"""Validation rules for document structure."""

from rebulk import Rule, AppendMatch, RemoveMatch
from rebulk.match import Match

from ..patterns.locator import TagLocatorTextOnline


class ValidateSingleMessageText(Rule):
    """Ensure exactly one Message Text marker exists."""

    priority = 256
    consequence = RemoveMatch

    def when(self, matches, context):
        found = matches.markers.named("message_text_marker")
        if len(found) != 1:
            return list(found)
        return False


class ValidateSingleMessageAttributes(Rule):
    """Ensure exactly one Message Attributes marker exists."""

    priority = 256
    dependency = ValidateSingleMessageText
    consequence = RemoveMatch

    def when(self, matches, context):
        found = matches.markers.named("message_attributes_marker")
        if len(found) != 1:
            return list(found)
        return False


class MessageContentRegion(Rule):
    """Define message_content as the region between Message Text
    and Message Attributes markers.  Requires Locator tagged with
    text-online — without it the message text is not available.

    Marking lines (declassification boilerplate) are stripped
    via CollectMarkings rule + marking_line match removal.
    """

    priority = 144
    dependency = TagLocatorTextOnline
    consequence = AppendMatch

    def when(self, matches, context):
        text_ms = matches.markers.named("message_text_marker")
        attr_ms = matches.markers.named("message_attributes_marker")
        if len(text_ms) != 1 or len(attr_ms) != 1:
            return False

        if not any("text-online" in m.tags for m in matches.named("Locator")):
            return False

        text_end = text_ms[0].end
        attr_start = attr_ms[0].start

        if attr_start <= text_end:
            return False

        raw = matches.input_string[text_end:attr_start]

        # Strip markers and page breaks for continuous body text.
        ranges = []
        for cm in matches.named("classification_marker"):
            if text_end <= cm.start < attr_start:
                ranges.append((cm.start - text_end, cm.end - text_end))
        for pb in matches.named("page_break"):
            if text_end <= pb.start < attr_start:
                start = pb.start - text_end
                end = pb.end - text_end
                while start > 0 and raw[start - 1] in "\n\r":
                    start -= 1
                while end < len(raw) and raw[end] in "\n\r":
                    end += 1
                ranges.append((start, end))
        for m in matches.named("content_footer_marker"):
            if text_end <= m.start < attr_start:
                ranges.append((m.start - text_end, m.end - text_end))
        for m in matches.named("end_marker"):
            if text_end <= m.start < attr_start:
                ranges.append((m.start - text_end, m.end - text_end))
        for m in matches.named("marking_line"):
            if text_end <= m.start < attr_start:
                start = m.start - text_end
                while start > 0 and raw[start - 1] not in "\n\r":
                    start -= 1
                end = m.end - text_end
                while end < len(raw) and raw[end] not in "\n\r":
                    end += 1
                if end < len(raw):
                    end += 1
                ranges.append((start, end))
        if ranges:
            ranges.sort()
            merged = [list(ranges[0])]
            for start, end in ranges[1:]:
                if start <= merged[-1][1]:
                    merged[-1][1] = max(merged[-1][1], end)
                else:
                    merged.append([start, end])
            for start, end in reversed(merged):
                raw = raw[:start] + raw[end:]

        m = Match(
            text_end,
            attr_start,
            value=raw,
            name="message_content",
            tags=["region"],
        )
        return [m]
