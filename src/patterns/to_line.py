"""Extract the TO (addressee) lines from message content.

The TO field lists primary addressees and may span multiple lines.
It appears after the FM line in the routing header, before INFO.
The routing header is bounded by the first blank line after FM.

Output field:
  _to — the addressee text, "TO " prefix stripped, lines joined with spaces
"""

from rebulk import Rebulk, Rule
from rebulk.match import Match
from rebulk.remodule import re

from ..rules.message_content import BuildMessageContent


def to_line():
    """Build pattern that matches the TO block within the routing header."""
    rebulk = Rebulk()
    rebulk.rules(ParseTo)
    return rebulk


class ParseTo(Rule):
    """Parse TO addressee lines from the routing header region.

    The routing header runs from FM to the first blank line.
    TO lines and their continuations are extracted from within that region.
    """

    priority = 32
    dependency = BuildMessageContent

    @staticmethod
    def _find_routing_header(mc_text):
        """Return (header_start, header_end, header_text) or None."""
        fm_m = re.search(r"^FM\s+", mc_text, re.MULTILINE)
        if not fm_m:
            return None
        header_start = fm_m.start()
        rest = mc_text[header_start:]
        blank_m = re.search(r"\n\s*\n", rest)
        header_end = blank_m.start() if blank_m else len(rest)
        return header_start, header_end, rest[:header_end]

    @staticmethod
    def _collect_to_lines(header_text):
        """Collect TO addressee lines including continuations.

        Walks lines from FM through the routing header.
        Lines starting with 'TO ' begin a TO section.
        Lines starting with 'INFO ' begin an INFO section (skipped for TO output).
        Lines without a prefix belong to the current section.
        """
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

            if stripped_upper.startswith("TO "):
                current_section = "TO"
                content = stripped[3:].strip()
                parts.append(content)
                if range_start is None:
                    range_start = offset
                range_end = offset + len(line)
            elif stripped_upper.startswith("INFO "):
                current_section = "INFO"
            elif current_section == "TO":
                parts.append(stripped)
                range_end = offset + len(line)
            # else: continuation after INFO or start — skip

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

        header = self._find_routing_header(mc_text)
        if header is None:
            return False
        header_start, header_end, header_text = header

        parts, to_start_rel, to_end_rel = self._collect_to_lines(header_text)
        if not parts:
            return False

        value = " ".join(parts)
        to_start = mc_start + header_start + to_start_rel
        to_end = mc_start + header_start + to_end_rel

        return Match(
            to_start,
            to_end,
            value=value,
            name="to",
            tags=["message_content"],
        )

    def then(self, matches, when_response, context):
        matches.append(when_response)
