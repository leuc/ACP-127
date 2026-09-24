"""Extract the INFO (information addressee) lines from message content.

The INFO field lists information addressees and may span multiple lines.
It appears in the routing header (between FM and first blank line).
Uses the joint routing walk (see patterns.routing.walk_routing) shared
with TO, so neither value can swallow later header lines.

Output field:
  _info — the information addressee text, "INFO " prefix stripped,
          lines joined with spaces
"""

from rebulk import Rebulk, Rule
from rebulk.match import Match

from ..content_view import (
    TAG_HEADER,
    TAG_STRIP,
    ZONE_ROUTING,
    get_view,
    register_field_span,
)
from ..rules.message_content import BuildMessageContent
from .routing import walk_routing


def info_line():
    """Build pattern that matches the INFO block within the routing header."""
    rebulk = Rebulk()
    rebulk.rules(ParseInfo)
    return rebulk


class ParseInfo(Rule):
    """Parse INFO addressee lines from the joint routing walk.

    Walks lines from FM through the routing header. Lines starting with
    'INFO ' begin an INFO section; lines starting with 'TO ' begin a TO
    section. Lines without a prefix belong to the current section.
    """

    priority = 32
    dependency = BuildMessageContent

    def when(self, matches, context):
        view = get_view(context)
        mc = matches.named("message_content")
        if view is None or not mc:
            return False

        mc_text = view.text
        walked = walk_routing(mc_text)
        if walked is None or walked["info"] is None:
            return False

        value = walked["info"]["value"]
        spans = walked["info"]["spans"]
        if not value.strip() or not spans:
            return False

        raw_spans = []
        for clean_start, clean_end in spans:
            bounding = view.clean_to_raw_bounding(clean_start, clean_end)
            if bounding is None:
                return False
            raw_spans.append(bounding)
            register_field_span(context, "info", clean_start, clean_end)

        return Match(
            raw_spans[0][0],
            raw_spans[-1][1],
            value=value,
            name="info",
            tags=["message_content", ZONE_ROUTING, TAG_STRIP, TAG_HEADER],
        )

    def then(self, matches, when_response, context):
        matches.append(when_response)
