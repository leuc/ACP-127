"""Extract the E.O. 11652 line from message content.

The Executive Order line appears in the message body header, after the
classification/location line and before TAGS. It has many variant
writings but limited values. The entire raw line is captured as-is.

Output field:
  _executive_order — the raw E.O. 11652 line
"""

from rebulk import Rebulk, Rule
from rebulk.match import Match
from rebulk.remodule import re

from ..rules.message_content import BuildMessageContent

_EO_RE = re.compile(r"^E\.?\s*O\.?\s*11652:\s*.+", re.MULTILINE | re.IGNORECASE)


def eo_line():
    """Build pattern that matches the E.O. 11652 line."""
    rebulk = Rebulk()
    rebulk.rules(ParseExecutiveOrder)
    return rebulk


class ParseExecutiveOrder(Rule):
    """Extract the E.O. 11652 line from message content."""

    priority = 31
    dependency = BuildMessageContent

    def when(self, matches, context):
        mc = matches.named("message_content")
        if not mc:
            return False

        mc_text = mc[0].value
        mc_start = mc[0].start

        eo_m = _EO_RE.search(mc_text)
        if not eo_m:
            return False

        return Match(
            mc_start + eo_m.start(),
            mc_start + eo_m.end(),
            value=eo_m.group(0).strip(),
            name="executive_order",
            tags=["message_content"],
        )

    def then(self, matches, when_response, context):
        matches.append(when_response)
