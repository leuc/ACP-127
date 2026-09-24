"""Finalize message content by stripping remaining markers.

Reads all accumulated strip ranges from context, merges them, and applies
to the original input to produce clean message_content. Also builds the
per-document :class:`ContentView <src.content_view.ContentView>` that maps
cleaned offsets back to exact raw source positions for all later parsers.
"""

from rebulk import Rule
from rebulk.match import Match
from rebulk.rules import Consequence

from ..content_view import ContentView, content_region, get_field_spans
from ..patterns.locator import is_text_online
from ..rules.end_marker_removal import RemoveEndMarker


def _strip_ranges_from_text(text, ranges):
    """Remove ranges (start, end) from text, processing in reverse order."""
    if not ranges:
        return text
    for start, end in reversed(ranges):
        if start < 0:
            start = 0
        if end > len(text):
            end = len(text)
        if start >= end:
            continue
        text = text[:start] + text[end:]
    return text


class FinalizeMessageContent(Consequence):
    """Strip remaining markers, build message_content + content view."""

    def then(self, matches, when_response, context):
        text_end, attr_start, remaining_matches = when_response
        raw = matches.input_string[text_end:attr_start]

        ranges = context.get("_strip_ranges", [])
        ranges = list(ranges)

        for m in remaining_matches:
            start = m.start - text_end
            end = m.end - text_end
            m_start = start
            if start < 0:
                start = 0
            if m.name == "content_footer_marker":
                while start > 0 and raw[start - 1] in "\n\r":
                    start -= 1
                if start < m_start:
                    start += 1
                while end < len(raw) and raw[end] in "\n\r":
                    end += 1
                ranges.append((start, end))
            elif m.name == "marking_line":
                while start > 0 and raw[start - 1] not in "\n\r":
                    start -= 1
                while end < len(raw) and raw[end] not in "\n\r":
                    end += 1
                if end < len(raw):
                    end += 1
                while start > 0 and raw[start - 1] in "\n\r":
                    start -= 1
                if start < m_start:
                    start += 1
                while end < len(raw) and raw[end] in "\n\r":
                    end += 1
                ranges.append((start, end))

        view, merged = ContentView.build(raw, text_end, ranges)
        cleaned = view.text
        context["_content_view"] = view
        # Fresh per-document registries for this run (rebulk reuses the
        # same context dict only within one matches() call, but be explicit).
        context["_field_spans"] = {}
        get_field_spans(context)  # ensure key exists
        context["_strip_merged"] = [
            (start + text_end, end + text_end) for start, end in merged
        ]

        for m in remaining_matches:
            if m in matches:
                matches.remove(m)
        for m in matches.named("content_footer_marker"):
            if m in matches:
                matches.remove(m)
        for m in matches.named("marking_line"):
            if m in matches:
                matches.remove(m)
        for old in matches.named("_content"):
            if old in matches:
                matches.remove(old)

        matches.append(
            Match(
                text_end,
                attr_start,
                value=cleaned,
                name="message_content",
                tags=["region"],
            )
        )
        return True


class BuildMessageContent(Rule):
    """Build the final message_content from the cleaned _content.

    Runs after RemoveEndMarker — all markers have been removed.

    Body extraction requires exactly one valid marker pair in the proper
    order plus a scoped Locator with a TEXT ON-LINE form (tolerant
    predicate shared with coverage.has_retrievable_body). Attribute
    extraction continues regardless -- this gate only controls the body.
    """

    priority = 96
    dependency = RemoveEndMarker
    consequence = FinalizeMessageContent()

    def when(self, matches, context):
        region = content_region(matches)
        if region is None:
            context.setdefault("_validation", {})["body_eligible"] = {
                "eligible": False,
                "reason": "markers",
            }
            return False
        text_end, attr_start = region

        eligible = any(
            is_text_online(m.value) and m.start >= attr_start
            for m in matches.named("Locator")
        )
        # Fallback for attribute matches whose value extension has not yet
        # run at this priority: check the raw Locator line text directly.
        if not eligible:
            text = matches.input_string
            for m in matches.named("Locator"):
                if m.start < attr_start:
                    continue
                line_end = text.find("\n", m.start)
                line = text[m.start : line_end if line_end >= 0 else len(text)]
                if is_text_online(line):
                    eligible = True
                    break
        context.setdefault("_validation", {})["body_eligible"] = {
            "eligible": bool(eligible),
            "reason": "ok" if eligible else "locator",
        }
        if not eligible:
            return False

        names = ["content_footer_marker", "marking_line"]
        remaining = [
            m for m in matches if m.name in names and text_end <= m.start < attr_start
        ]

        return text_end, attr_start, remaining
