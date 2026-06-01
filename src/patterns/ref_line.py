"""Extract raw REF/REFS/REFERENCE/REF :/REFTEL/RETELS line from message content.

Reference lines appear in the message body header, often after TAGS/E.O./SUBJECT.
They can span multiple lines with continuation lines.

Output field:
  _reference — raw string from REF: line through continuation lines until
    next empty line or 200 characters (whichever comes first).

Reference splitting into individual MRNs is handled by
``src.reftel_normalize._split_refs``.
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
    """Extract raw reference text from message content."""

    priority = 31
    dependency = BuildMessageContent

    _REF_RE = re.compile(
        r"^(?:REF(?:ERENCE)?S?\s*:|REF\s*:|REFTEL:|RETELS?\s*:)[ \t]*"
        r"((?:(?!\n[ \t]*\n).){0,200})",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
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

        return Match(
            mc_start + m.start(),
            mc_start + m.end(),
            value=mc_text[m.start() : m.end()],
            name="reference",
            tags=["message_content"],
        )

    def then(self, matches, when_response, context):
        matches.append(when_response)
