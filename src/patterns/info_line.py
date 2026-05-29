"""Extract the INFO (information addressee) lines from message content.

The INFO field lists information addressees and may span multiple lines.
It appears in the routing header (between FM and first blank line).
TO lines act as section boundaries — INFO lines between TO sections
and their continuations are captured.

Output field:
  _info — the information addressee text, "INFO " prefix stripped,
          lines joined with spaces
"""

from rebulk import Rebulk, Rule
from rebulk.match import Match

from ..rules.message_content import BuildMessageContent
from .routing import find_routing_header


def info_line():
    """Build pattern that matches the INFO block within the routing header."""
    rebulk = Rebulk()
    rebulk.rules(ParseInfo)
    return rebulk


class ParseInfo(Rule):
    """Parse INFO addressee lines from the routing header region.

    Walks lines from FM through the routing header.
    Lines starting with 'INFO ' begin an INFO section.
    Lines starting with 'TO ' begin a TO section (no INFO output).
    Lines without a prefix belong to the current section.
    """

    priority = 32
    dependency = BuildMessageContent

    @staticmethod
    def _collect_info_lines(header_text):
        """Collect INFO addressee lines including continuations."""
        lines = header_text.split("\n")
        parts = []
        current_section = None
        range_start = None
        range_end = None

        offset = 0
        for line in lines:
            stripped = line.strip()
            stripped_upper = stripped.upper()
            if not stripped:
                offset += len(line) + 1
                continue

            if stripped_upper.startswith("INFO "):
                current_section = "INFO"
                content = stripped[5:].strip()
                parts.append(content)
                if range_start is None:
                    range_start = offset
                range_end = offset + len(line)
            elif stripped_upper.startswith("TO "):
                current_section = "TO"
            elif current_section == "INFO":
                parts.append(stripped)
                range_end = offset + len(line)
            # else: continuation after TO — skip

            offset += len(line) + 1

        if not parts:
            return None, None, None
        return parts, range_start, range_end

    def when(self, matches, context):
        mc = matches.named("message_content")
        if not mc:
            return False

        mc_text = mc[0].value
        mc_start = mc[0].start

        header = find_routing_header(mc_text)
        if header is None:
            return False
        header_start, header_end, header_text = header

        parts, info_start_rel, info_end_rel = self._collect_info_lines(header_text)
        if not parts:
            return False

        value = " ".join(parts)
        info_start = mc_start + header_start + info_start_rel
        info_end = mc_start + header_start + info_end_rel

        return Match(
            info_start,
            info_end,
            value=value,
            name="info",
            tags=["message_content"],
        )

    def then(self, matches, when_response, context):
        matches.append(when_response)
