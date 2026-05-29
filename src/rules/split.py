"""Validation rules for document structure."""

from rebulk import Rule, AppendMatch, RemoveMatch
from rebulk.match import Match
from rebulk.remodule import re


_MARKING_PATTERNS = [
    r"Sheryl P\. Walter Declassified/Released US Department of State EO Systematic Review 20 Mar 2014",
    r"Declassified/Released US Department of State EO Systematic Review 30 JUN 2005",
    r"Margaret P\. Grafeld Declassified/Released US Department of State EO Systematic Review 04 MAY 2006",
    r"Margaret P\. Grafeld Declassified/Released US Department of State EO Systematic Review 22 May 2009",
    r"Margaret P\. Grafeld Declassified/Released US Department of State EO Systematic Review 06 JUL 2006",
    r"Margaret P\. Grafeld Declassified/Released US Department of State EO Systematic Review 05 JUL 2006",
]

_MARKING_RE = re.compile(
    r"^[ \t\f]*(?:" + "|".join(_MARKING_PATTERNS) + r")[ \t]*\n?", re.MULTILINE
)


def _strip_markings(text):
    return _MARKING_RE.sub("", text)


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
    and Message Attributes markers.  Requires Locator to contain
    TEXT ON-LINE — without it the message text is not available.

    Known marking lines (declassification boilerplate) are stripped
    from the extracted content value.
    """

    priority = 144
    dependency = ValidateSingleMessageAttributes
    consequence = AppendMatch

    def when(self, matches, context):
        text_ms = matches.markers.named("message_text_marker")
        attr_ms = matches.markers.named("message_attributes_marker")
        if len(text_ms) != 1 or len(attr_ms) != 1:
            return False

        locator_ms = matches.named("Locator")
        if not locator_ms:
            return False
        if not re.search(r"\bTEXT\s+ON-LINE\b", locator_ms[0].value, re.IGNORECASE):
            return False

        text_end = text_ms[0].end
        attr_start = attr_ms[0].start

        if attr_start <= text_end:
            return False

        raw = matches.input_string[text_end:attr_start]

        # Strip content footer markers at higher priority
        # (*** Current Handling Restrictions / Classification ***)
        # before page break / classification marker lines.
        # Using rebulk match positions avoids offset issues that
        # a second regex pass on the processed value would have.
        ranges = []
        for m in matches.named("content_footer_marker"):
            if text_end <= m.start < attr_start:
                ranges.append((m.start - text_end, m.end - text_end))
        for pb in matches.named("page_break"):
            if text_end <= pb.start < attr_start:
                ranges.append((pb.start - text_end, pb.end - text_end))
        for cm in matches.named("classification_marker"):
            if text_end <= cm.start < attr_start:
                ranges.append((cm.start - text_end, cm.end - text_end))
        if ranges:
            ranges.sort(reverse=True)
            for start, end in ranges:
                raw = raw[:start] + raw[end:]

        m = Match(
            text_end,
            attr_start,
            value=_strip_markings(raw),
            name="message_content",
            tags=["region"],
        )
        return [m]
