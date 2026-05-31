"""Extract REF/REFS/REFERENCE/REF :/REFTEL/RETELS line from message content.

Reference lines appear in the message body header, often after TAGS/E.O./SUBJECT.
They can span multiple lines with continuation lines.

Output field:
  reference — list of reference strings, each individual reference as a separate item
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
    _NEW_REF_RE = re.compile(r"^\s{2,}(?:(?:[A-Z][\).]|\([A-Z]\))\s|[A-Z]\.\s)")
    _CONT_TEXT_RE = re.compile(r"^\s{2,}\S")

    @staticmethod
    def _split_refs(text):
        items = []
        for part in text.split(";"):
            for sub in re.split(r"[,:\s]{2,}(?=(?:[A-Z][\).]|\([A-Z]\))\s)", part):
                sub = sub.strip()
                if sub:
                    items.append(sub)
        return items

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
        items = self._split_refs(m.group(1))

        rest = mc_text[m.end() :]
        lines = rest.split("\n")
        end_offset = 0
        for line in lines:
            if not line.strip():
                end_offset += len(line) + 1
                continue
            if self._NEW_REF_RE.match(line):
                items.extend(self._split_refs(line.strip()))
            elif self._CONT_TEXT_RE.match(line):
                if items:
                    combined = items[-1] + " " + line.strip()
                    items[-1:] = self._split_refs(combined)
            else:
                break
            end_offset += len(line) + 1

        if not items:
            items = [m.group(0).strip()]

        return Match(
            mc_start + start,
            mc_start + m.end() + end_offset,
            value=items,
            name="reference",
            tags=["message_content"],
        )

    def then(self, matches, when_response, context):
        matches.append(when_response)
