"""Extract the TO (addressee) lines from message content.

The TO field lists primary addressees and may span multiple lines.
It appears after the FM line in the routing header. Uses the joint
routing walk (see patterns.routing.walk_routing) shared with INFO, so
neither value can swallow later header lines.

Output field:
  _to — the addressee text, "TO " prefix stripped, lines joined with spaces
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


def to_line():
    """Build pattern that matches the TO block within the routing header."""
    rebulk = Rebulk()
    rebulk.rules(ParseTo)
    return rebulk


class ParseTo(Rule):
    """Parse TO addressee lines from the joint routing walk.

    The routing window runs from FM to the first blank line or known
    header label. TO lines and their continuations are extracted with
    exact per-line intervals; INFO lines alternate without being
    absorbed into the TO value.
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
        if walked is None or walked["to"] is None:
            return False

        value = walked["to"]["value"]
        spans = walked["to"]["spans"]
        if not value.strip() or not spans:
            return False

        raw_spans = []
        for clean_start, clean_end in spans:
            bounding = view.clean_to_raw_bounding(clean_start, clean_end)
            if bounding is None:
                return False
            raw_spans.append(bounding)
            register_field_span(context, "to", clean_start, clean_end)

        return Match(
            raw_spans[0][0],
            raw_spans[-1][1],
            value=value,
            name="to",
            tags=["message_content", ZONE_ROUTING, TAG_STRIP, TAG_HEADER],
        )

    def then(self, matches, when_response, context):
        matches.append(when_response)
