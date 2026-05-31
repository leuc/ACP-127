"""Strip extracted header fields from message_content.

Runs as the final cleaning step after all extraction is complete.
Selects existing header matches (distribution, dtg, from, to, subject,
ref) within the message content region and removes their text from
_message_content.

Header matches use two coordinate systems:
  - dtg, from: original raw-text coordinates (regex matches on full input)
  - distribution, to, subject, ref: cleaned-text coordinates (parsed from
    the message_content value)

For original-coord matches, the raw text is searched for within the
cleaned message_content value.  All instances per field are stripped —
section markers cause some headers (DTG, FM) to appear twice.
"""

from rebulk import Rule
from rebulk.match import Match
from rebulk.rules import Consequence

from ..rules.message_content import BuildMessageContent

_HEADER_NAMES = {
    "distribution",
    "dtg",
    "from",
    "to",
    "subject",
    "reference",
    "section_marker",
    "dash_counters",
    "info",
    "drafted_by",
    "approved_by",
    "executive_order",
    "tags",
}
_ORIGINAL_COORDS = {"dtg", "from"}
_CLEANED_COORDS = {
    "distribution",
    "to",
    "subject",
    "reference",
    "info",
    "drafted_by",
    "approved_by",
    "executive_order",
    "tags",
}


def _find_ranges(mc_value, text_end, header_matches, input_string):
    """Compute strip ranges within the cleaned message_content value.

    For cleaned-coord matches the position is directly available via
    match.start - text_end.  For original-coord matches (dtg, from)
    the match's raw text is searched for in the cleaned value.

    Section markers and dash counters use their match value or raw
    text to locate all occurrences within the cleaned text.
    """
    ranges = []
    for m in header_matches:
        name = m.name
        if name in _CLEANED_COORDS:
            c_start = m.start - text_end
            c_end = m.end - text_end
            c_start = max(0, c_start)
            c_end = min(len(mc_value), c_end)
            if c_start < c_end:
                ranges.append((name, c_start, c_end))
        elif name == "section_marker":
            sections = m.value
            if not isinstance(sections, list):
                continue
            for entry in sections:
                raw_text = entry.get("raw", "")
                if not raw_text.strip():
                    continue
                start_search = 0
                while True:
                    pos = mc_value.find(raw_text, start_search)
                    if pos < 0:
                        break
                    ranges.append((name, pos, pos + len(raw_text)))
                    start_search = pos + 1
        elif name == "dash_counters":
            raw_text = m.raw
            if raw_text is None:
                raw_text = input_string[m.start : m.end]
            raw_text = raw_text.strip()
            if not raw_text:
                continue
            start_search = 0
            while True:
                pos = mc_value.find(raw_text, start_search)
                if pos < 0:
                    break
                ranges.append((name, pos, pos + len(raw_text)))
                start_search = pos + 1
        elif name in _ORIGINAL_COORDS:
            raw_text = m.raw.strip()
            if not raw_text:
                continue
            start_search = 0
            while True:
                pos = mc_value.find(raw_text, start_search)
                if pos < 0:
                    break
                ranges.append((name, pos, pos + len(raw_text)))
                start_search = pos + 1
    return ranges


class StripHeaders(Consequence):
    """Strip header fields from the current message_content value."""

    def then(self, matches, when_response, context):
        text_end, attr_start, header_matches = when_response
        mc = matches.named("message_content")
        if not mc:
            return True
        current_value = mc[0].value

        to_strip = _find_ranges(
            current_value, text_end, header_matches, matches.input_string
        )
        if not to_strip:
            return True

        to_strip.sort(key=lambda x: x[1])
        merged = []
        for _, s, e in to_strip:
            if merged and s <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], e))
            else:
                merged.append((s, e))

        cleaned = current_value
        for s, e in reversed(merged):
            cleaned = cleaned[:s] + cleaned[e:]

        for old in matches.named("message_content"):
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


class RemoveHeaders(Rule):
    """Remove extracted header fields from message_content.

    Strips distribution, dtg, from, to, subject, and ref text from
    _message_content after all extraction is complete.  When section
    markers exist, headers that appear in each section (DTG, FM) are
    all stripped.
    """

    priority = 16
    dependency = BuildMessageContent
    consequence = StripHeaders()

    def when(self, matches, context):
        text_ms = matches.markers.named("message_text_marker")
        attr_ms = matches.markers.named("message_attributes_marker")
        if len(text_ms) != 1 or len(attr_ms) != 1:
            return False
        text_end, attr_start = text_ms[0].end, attr_ms[0].start

        header_matches = []
        for name in _HEADER_NAMES:
            for m in matches.named(name):
                if text_end <= m.start < attr_start:
                    header_matches.append(m)

        if not header_matches:
            return False

        return text_end, attr_start, header_matches
