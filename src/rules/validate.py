"""Validation rules for document structure.

Root of the dependency tree: exactly one Message Text and one Message
Attributes marker per document, in the proper order.
"""

from rebulk import Rule, RemoveMatch


def _record(context, key, reason):
    """Store a structured per-document validation reason (audit only)."""
    validation = context.setdefault("_validation", {})
    validation[key] = reason


class ValidateSingleMessageText(Rule):
    """Ensure exactly one Message Text marker exists."""

    priority = 256
    consequence = RemoveMatch

    def when(self, matches, context):
        found = matches.markers.named("message_text_marker")
        if len(found) != 1:
            _record(
                context,
                "message_text_marker",
                {"count": len(found),
                 "reason": "zero" if not found else "multiple"},
            )
            return list(found)
        _record(context, "message_text_marker", {"count": 1, "reason": "ok"})
        return False


class ValidateSingleMessageAttributes(Rule):
    """Ensure exactly one Message Attributes marker exists."""

    priority = 256
    dependency = ValidateSingleMessageText
    consequence = RemoveMatch

    def when(self, matches, context):
        found = matches.markers.named("message_attributes_marker")
        if len(found) != 1:
            _record(
                context,
                "message_attributes_marker",
                {"count": len(found),
                 "reason": "zero" if not found else "multiple"},
            )
            return list(found)
        text_ms = matches.markers.named("message_text_marker")
        if len(text_ms) == 1 and not text_ms[0].end <= found[0].start:
            _record(
                context,
                "message_attributes_marker",
                {"count": 1, "reason": "order"},
            )
            return list(found)
        _record(context, "message_attributes_marker", {"count": 1, "reason": "ok"})
        return False
