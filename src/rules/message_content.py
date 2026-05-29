"""Finalize message content by stripping remaining markers.

Reads all accumulated strip ranges from context, merges them,
and applies to the original input to produce clean message_content.
"""

from rebulk import Rule
from rebulk.match import Match
from rebulk.rules import Consequence

from ..rules.end_marker_removal import RemoveEndMarker


def _merge_ranges(ranges):
    """Sort and merge overlapping/adjacent ranges."""
    if not ranges:
        return []
    sorted_ranges = sorted(ranges, key=lambda r: r[0])
    merged = [list(sorted_ranges[0])]
    for start, end in sorted_ranges[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(s, e) for s, e in merged]


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


class StripContentText(Consequence):
    """Strip text from message_content, remove matches, and append new matches.

    Expects `when_response` as ``(to_remove_matches, texts_to_strip, to_append_matches)``:
      to_remove_matches — Match objects to remove from the match set
      texts_to_strip — strings to find and remove from message_content.value
      to_append_matches — Match objects to append to the match set
    """

    def then(self, matches, when_response, context):
        to_remove, texts_to_strip, to_append = when_response

        for m in to_remove:
            if m in matches:
                matches.remove(m)

        mc = matches.named("message_content")
        if mc and texts_to_strip:
            old = mc[0]
            current = old.value
            for t in texts_to_strip:
                if current.startswith(t):
                    current = current[len(t) :]
                else:
                    idx = current.find(t)
                    if idx >= 0:
                        current = current[:idx] + current[idx + len(t) :]
            matches.remove(old)
            matches.append(
                Match(
                    old.start,
                    old.end,
                    value=current,
                    name=old.name,
                    tags=old.tags,
                )
            )

        for m in to_append:
            matches.append(m)
        return True


class FinalizeMessageContent(Consequence):
    """Strip remaining markers, build message_content."""

    def then(self, matches, when_response, context):
        text_end, attr_start, remaining_matches = when_response
        raw = matches.input_string[text_end:attr_start]

        ranges = context.get("_strip_ranges", [])
        ranges = list(ranges)

        for m in remaining_matches:
            if m.name == "content_footer_marker":
                start = m.start - text_end
                end = m.end - text_end
                if start < 0:
                    start = 0
                ranges.append((start, end))
            elif m.name == "marking_line":
                s = m.start - text_end
                while s > 0 and raw[s - 1] not in "\n\r":
                    s -= 1
                e = m.end - text_end
                while e < len(raw) and raw[e] not in "\n\r":
                    e += 1
                if e < len(raw):
                    e += 1
                ranges.append((s, e))

        merged = _merge_ranges(ranges)
        cleaned = _strip_ranges_from_text(raw, merged)

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
    """

    priority = 96
    dependency = RemoveEndMarker
    consequence = FinalizeMessageContent()

    def when(self, matches, context):
        text_ms = matches.markers.named("message_text_marker")
        attr_ms = matches.markers.named("message_attributes_marker")
        if len(text_ms) != 1 or len(attr_ms) != 1:
            return False
        text_end, attr_start = text_ms[0].end, attr_ms[0].start

        names = ["content_footer_marker", "marking_line"]
        remaining = [
            m for m in matches if m.name in names and text_end <= m.start < attr_start
        ]

        return text_end, attr_start, remaining
