"""Validation rules for document structure."""

from rebulk import Rule, AppendMatch, RemoveMatch
from rebulk.match import Match
from rebulk.remodule import re


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

        m = Match(
            text_end,
            attr_start,
            value=matches.input_string[text_end:attr_start],
            name="message_content",
            tags=["region"],
        )
        return [m]
