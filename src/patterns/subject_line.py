"""Extract the SUBJECT/SUBJ line from message content.

The subject line appears in the message body header after TAGS/E.O.
and before REF. It may span multiple lines with continuation text.

Output field:
  _subject — the subject text, continuation lines joined with spaces
"""

from rebulk import Rebulk, Rule
from rebulk.match import Match
from rebulk.remodule import re

from ..rules.message_content import BuildMessageContent

_SUBJECT_RE = re.compile(
    r"^(?:SUBJECT|SUBJ|SUB|SUJ)\s*:\s*(.*?)$", re.MULTILINE | re.IGNORECASE
)


def subject_line():
    """Build pattern that matches the SUBJECT line."""
    rebulk = Rebulk()
    rebulk.rules(ParseSubject)
    return rebulk


class ParseSubject(Rule):
    """Extract SUBJECT from message content."""

    priority = 31
    dependency = BuildMessageContent

    _CONT_PAT = re.compile(r"^\s{2,}\S", re.MULTILINE)
    _END_PAT = re.compile(
        r"^(?:REF(?:ERENCE)?S?\s*:|REFTELs?\s*:|RETELS?\s*:|TAGS:|E\.?\s*O\.?\s*\d+:|\n\s*\n)",
        re.MULTILINE | re.IGNORECASE,
    )

    def when(self, matches, context):
        mc = matches.named("message_content")
        if not mc:
            return False

        mc_text = mc[0].value
        mc_start = mc[0].start

        m = _SUBJECT_RE.search(mc_text)
        if not m:
            return False

        start = m.start()
        first_val = m.group(1).strip()

        rest = mc_text[m.end() :]
        cont_end = self._END_PAT.search(rest)
        block_end = cont_end.start() if cont_end else len(rest)
        block_text = mc_text[m.end() : m.end() + block_end]

        parts = [first_val]
        end_offset = 0
        for line in block_text.split("\n"):
            next_offset = len(line) + 1
            if not self._CONT_PAT.match(line):
                break
            stripped = line.strip()
            if stripped:
                parts.append(stripped)
            end_offset += next_offset

        value = " ".join(parts)

        return Match(
            mc_start + start,
            mc_start + m.end() + end_offset,
            value=value,
            name="subject",
            tags=["message_content"],
        )

    def then(self, matches, when_response, context):
        matches.append(when_response)
