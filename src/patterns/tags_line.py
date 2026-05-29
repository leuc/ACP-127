"""Extract the TAGS line from message content as a list.

The TAGS line appears in the message body header, after the E.O. line
and before SUBJECT. Tags are comma-separated and extracted as a list.

Output field:
  _tags — list of tag strings
"""

from rebulk import Rebulk, Rule
from rebulk.match import Match
from rebulk.remodule import re

from ..rules.message_content import BuildMessageContent

_TAGS_RE = re.compile(r"^TAGS:\s*(.+)", re.MULTILINE | re.IGNORECASE)


def tags_line():
    """Build pattern that matches the TAGS line."""
    rebulk = Rebulk()
    rebulk.rules(ParseTags)
    return rebulk


class ParseTags(Rule):
    """Extract TAGS from message content as a list."""

    priority = 31
    dependency = BuildMessageContent

    def when(self, matches, context):
        mc = matches.named("message_content")
        if not mc:
            return False

        mc_text = mc[0].value
        mc_start = mc[0].start

        t_m = _TAGS_RE.search(mc_text)
        if not t_m:
            return False

        raw = t_m.group(1).strip()
        tags = [t.strip() for t in raw.split(",") if t.strip()]

        return Match(
            mc_start + t_m.start(),
            mc_start + t_m.end(),
            value=tags,
            name="tags",
            tags=["message_content"],
        )

    def then(self, matches, when_response, context):
        matches.append(when_response)
