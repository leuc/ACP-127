"""Extract the FM (FROM) line from message content.

Per ACP-127: the FM line identifies the originator of the message.
It appears after the DTG line and before TO/INFO routing lines.

Output field:
  _from — the originator text (e.g. "USMISSION NATO")
"""

from rebulk import Rebulk, Rule
from rebulk.remodule import re

from ..content_view import TAG_HEADER, TAG_STRIP, ZONE_ROUTING


def _parse_from_line(line):
    """Return the originator text after the FM prefix."""
    return line[3:].strip()


def from_line():
    """Build pattern that matches the FM (FROM) line."""
    rebulk = Rebulk()

    # Strict line-start FM anchor with horizontal spacing after FM: a
    # space/tab class so the prefix cannot consume a newline. The
    # transmitted value is preserved verbatim, including a relay-station
    # originator that differs from the From attribute.
    rebulk.regex(
        r"^FM[ \t]+(?P<from>.+)$",
        name="from",
        tags=["message_content"],
        formatter=_parse_from_line,
        flags=re.MULTILINE,
    )

    rebulk.rules(ValidateFrom)

    return rebulk


class ValidateFrom(Rule):
    """Validate FM matches: must be within message content region."""

    priority = 32

    def when(self, matches, context):
        from ..content_view import get_view, register_field_span

        text_ms = matches.markers.named("message_text_marker")
        attr_ms = matches.markers.named("message_attributes_marker")
        if len(text_ms) != 1 or len(attr_ms) != 1:
            return list(matches.named("from"))

        region_start = text_ms[0].end
        region_end = attr_ms[0].start

        view = get_view(context)
        if view is not None:
            for m in matches.named("from"):
                if not (region_start <= m.start < region_end):
                    continue
                clean_start = view.raw_to_clean(m.start)
                clean_end = view.raw_to_clean(m.end - 1)
                if clean_start is not None and clean_end is not None:
                    segments = view.clean_to_raw(clean_start, clean_end + 1)
                    if segments == [(m.start, m.end)]:
                        register_field_span(
                            context, "from", clean_start, clean_end + 1
                        )
                    if ZONE_ROUTING not in (m.tags or []):
                        m.tags.extend(
                            ["message_content", ZONE_ROUTING, TAG_STRIP, TAG_HEADER]
                        )

        to_remove = []
        for m in matches.named("from"):
            if not (region_start <= m.start < region_end):
                to_remove.append(m)

        return to_remove

    def then(self, matches, when_response, context):
        for m in when_response:
            if m in matches:
                matches.remove(m)
