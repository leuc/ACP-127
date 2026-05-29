"""Generic attribute key:value pattern for all Message Attributes."""

from rebulk import Rebulk, Rule, RemoveMatch, AppendMatch
from rebulk.match import Match
from rebulk.validators import chars_before

_KEYS = [
    "Automatic Decaptioning",
    "Capture Date",
    "Channel Indicators",
    "Concepts",
    "Control Number",
    "Copy",
    "Current Classification",
    "Decaption Date",
    "Decaption Note",
    "Disposition Action",
    "Disposition Approved on Date",
    "Disposition Authority",
    "Disposition Case Number",
    "Disposition Comment",
    "Disposition Date",
    "Disposition Event",
    "Disposition History",
    "Disposition Reason",
    "Disposition Remarks",
    "Document Number",
    "Document Source",
    "Document Unique ID",
    "Draft Date",
    "Drafter",
    "Enclosure",
    "Errors",
    "Executive Order",
    "Film Number",
    "From",
    "Handling Restrictions",
    "Image Path",
    "ISecure",
    "Legacy Key",
    "Line Count",
    "Locator",
    "Markings",
    "Office",
    "Original Classification",
    "Original Handling Restrictions",
    "Original Previous Classification",
    "Original Previous Handling Restrictions",
    "Page Count",
    "Previous Channel Indicators",
    "Previous Handling Restrictions",
    "Reference",
    "Review Action",
    "Review Authority",
    "Review Comment",
    "Review Content Flags",
    "Review Date",
    "Review Event",
    "Review History",
    "Review Markings",
    "Review Media Identifier",
    "Review Release Date",
    "Review Release Event",
    "Review Transfer Date",
    "Secure",
    "Status",
    "Subject",
    "TAGS",
    "To",
    "Type",
]

_KEY_SET = set(_KEYS)


def _is_valid_key_start(text, pos):
    if pos > 0 and text[pos - 1] != "\n":
        return False
    end = pos + 1
    while (
        end < len(text)
        and text[end]
        in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 "
    ):
        end += 1
    key = text[pos:end]
    if key in _KEY_SET and end < len(text) and text[end] == ":":
        return True
    return False


def _next_key(text, start):
    for pos in range(start, len(text)):
        if _is_valid_key_start(text, pos):
            return pos
    return None


def attributes():
    """Build pattern that matches all 'Key: value' attribute lines.

    Uses rebulk string matching for each known key, with a validator
    that checks line-start position and colon suffix.
    """
    rebulk = Rebulk()

    for key in _KEYS:

        def make_validator(k):
            return lambda m: (
                chars_before("\n", m)
                and m.end < len(m.input_string)
                and m.input_string[m.end] == ":"
                and m.value == k
            )

        rebulk.string(key, name=key, tags=["attribute"], validator=make_validator(key))

    rebulk.rules(
        ExtendAttributeValue,
        RemoveAttributesBeforeMarker,
        MergeContinuationLines,
    )

    return rebulk


class ExtendAttributeValue(Rule):
    """Extend key-only match to include ': value' on the same line
    plus whitespace-prefixed continuation lines."""

    priority = 160
    consequence = [RemoveMatch, AppendMatch]

    def when(self, matches, context):
        text = matches.input_string
        to_remove = []
        to_append = []
        for match in list(matches):
            if match.marker or match.parent or match.private:
                continue
            if match.name not in _KEY_SET:
                continue
            if match.tags and "attribute" not in match.tags:
                continue
            if ":" in match.raw:
                continue

            start = match.start
            col_pos = match.end
            ext_end = col_pos + 1
            while ext_end < len(text) and text[ext_end] != "\n":
                ext_end += 1
            ext_end += 1
            while ext_end < len(text) and text[ext_end] in (" ", "\t"):
                line_start = ext_end
                while ext_end < len(text) and text[ext_end] != "\n":
                    ext_end += 1
                ext_end += 1

            to_remove.append(match)
            to_append.append(
                Match(
                    start,
                    ext_end,
                    value=text[start:ext_end],
                    name=match.name,
                    tags=match.tags,
                )
            )
        return to_remove, to_append


class RemoveAttributesBeforeMarker(Rule):
    """Remove attribute matches that occur before the Message Attributes marker."""

    priority = 128
    dependency = ExtendAttributeValue
    consequence = RemoveMatch

    def when(self, matches, context):
        attr_ms = matches.markers.named("message_attributes_marker")
        if not attr_ms:
            return []

        marker_start = attr_ms[0].start
        ret = []
        for match in matches:
            if match.marker or match.parent or match.private:
                continue
            if match.tags and "attribute" in match.tags and match.start < marker_start:
                ret.append(match)
        return ret or False


class MergeContinuationLines(Rule):
    """Extend attribute matches to include column-0 continuation lines.

    Fields like Review Markings, Concepts, To, etc. have values that
    span multiple lines where continuation lines do NOT start with
    leading whitespace.  This rule extends each non-last attribute
    match to include non-key, non-blank lines in the gap before the
    next attribute match.
    """

    priority = 96
    dependency = RemoveAttributesBeforeMarker
    consequence = [RemoveMatch, AppendMatch]

    def when(self, matches, context):
        text = matches.input_string
        attrs = sorted(
            (
                m
                for m in matches
                if m.tags
                and "attribute" in m.tags
                and not m.marker
                and not m.parent
                and not m.private
            ),
            key=lambda m: m.start,
        )
        if len(attrs) < 2:
            return [], []

        to_remove = []
        to_append = []

        for i, attr in enumerate(attrs[:-1]):
            gap_text = text[attr.end : attrs[i + 1].start]
            if not gap_text.strip():
                continue

            lines = gap_text.split("\n")
            content_seen = False
            last_idx = -1

            for j, line in enumerate(lines):
                if content_seen and not line.strip():
                    break
                if not line.strip():
                    continue
                stripped = line.lstrip()
                space_or_word = stripped.split()[0] if stripped.split() else ""
                if space_or_word in _KEY_SET:
                    break
                content_seen = True
                last_idx = j

            if last_idx >= 0:
                offset = sum(len(lines[k]) + 1 for k in range(last_idx + 1))
                to_remove.append(attr)
                new_value = text[attr.start : attr.end + offset]
                to_append.append(
                    Match(
                        attr.start,
                        attr.end + offset,
                        value=new_value,
                        name=attr.name,
                        tags=attr.tags,
                    )
                )

        return to_remove, to_append
