"""Validation rules for document structure.

Moved from split.py, unchanged.
"""

from rebulk import Rule, RemoveMatch


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
