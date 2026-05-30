"""Extract REF/REFS/REFERENCE/REF :/REFTEL/RETELS line from message content.

Reference lines appear in the message body header, often after TAGS/E.O./SUBJECT.
They can span multiple lines with continuation lines.

Output field:
  reference — list of reference strings, each line as a separate item
"""

from rebulk import Rebulk, Rule
from rebulk.match import Match
from rebulk.remodule import re

from ..rules.message_content import BuildMessageContent


def ref_line():
    """Build pattern that matches REF lines."""
    rebulk = Rebulk()
    rebulk.rules(ParseRef)
    return rebulk


class ParseRef(Rule):
    """Extract REF from message content."""

    priority = 31
    dependency = BuildMessageContent

    _REF_RE = re.compile(
        r"^(?:REF(?:ERENCE)?S?\s*:|REF\s*:|REFTEL:|RETELS?\s*:)\s*(.*?)$",
        re.MULTILINE | re.IGNORECASE,
    )
    _CONT_PAT = re.compile(r"^\s{2,}\S", re.MULTILINE)
    _END_PAT = re.compile(
        r"^(?:REF(?:ERENCE)?S?\s*:|REF\s*:|REFTEL:|RETELS?\s*:|TAGS:|E\.?\s*O\.?\s*\d+:|\n\s*\n)",
        re.MULTILINE | re.IGNORECASE,
    )

    def when(self, matches, context):
        mc = matches.named("message_content")
        if not mc:
            return False

        mc_text = mc[0].value
        mc_start = mc[0].start

        m = self._REF_RE.search(mc_text)
        if not m:
            return False

        start = m.start()
        first_val = m.group(1).strip()

        rest = mc_text[m.end() :]
        # Look for next REF section or known terminator
        cont_end = self._END_PAT.search(rest)
        cont_end_offset = cont_end.start() if cont_end else len(rest)
        block_text = mc_text[m.end() : m.end() + cont_end_offset]

        items = [first_val] if first_val else []
        # Add continuation lines
        for line in block_text.split("\n"):
            stripped = line.strip()
            if stripped:
                items.append(stripped)

        # If no items and no continuations, use the raw match
        if not items:
            items = [m.group(0).strip()]

        return Match(
            mc_start + start,
            mc_start + m.end() + cont_end_offset,
            value=items,
            name="reference",
            tags=["message_content"],
        )

    def then(self, matches, when_response, context):
        matches.append(when_response)
