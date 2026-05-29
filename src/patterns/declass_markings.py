"""Match declassification boilerplate lines that should be stripped from message content.

These are EO Systematic Review markings added by the declassification process,
not part of the original ACP-127 telegram text.
"""

from rebulk import Rebulk, Rule, RemoveMatch

from ..rules.validate import ValidateSingleMessageAttributes

_MARKING_STRINGS = [
    "Sheryl P. Walter Declassified/Released US Department of State EO Systematic Review 20 Mar 2014",
    "Declassified/Released US Department of State EO Systematic Review 30 JUN 2005",
    "Margaret P. Grafeld Declassified/Released US Department of State EO Systematic Review 04 MAY 2006",
    "Margaret P. Grafeld Declassified/Released US Department of State EO Systematic Review 22 May 2009",
    "Margaret P. Grafeld Declassified/Released US Department of State EO Systematic Review 06 JUL 2006",
    "Margaret P. Grafeld Declassified/Released US Department of State EO Systematic Review 05 JUL 2006",
]


def declass_markings():
    """Build pattern that matches declassification marking lines."""
    rebulk = Rebulk()

    for s in _MARKING_STRINGS:
        rebulk.string(s, name="marking_line", tags=["marking"])

    rebulk.rules(CollectMarkings)

    return rebulk


class CollectMarkings(Rule):
    """Remove marking lines that fall outside the validated content region.

    Runs after ValidateSingleMessageAttributes to ensure the content
    region boundaries are known.  Remaining marking lines within the
    region are handled by FinalizeMessageContent.
    """

    priority = 200
    dependency = ValidateSingleMessageAttributes
    consequence = RemoveMatch

    def when(self, matches, context):
        text_ms = matches.markers.named("message_text_marker")
        attr_ms = matches.markers.named("message_attributes_marker")

        if len(text_ms) != 1 or len(attr_ms) != 1:
            return list(matches.named("marking_line"))

        region_start = text_ms[0].end
        region_end = attr_ms[0].start

        to_remove = []
        for m in matches.named("marking_line"):
            if m.start < region_start or m.start >= region_end:
                to_remove.append(m)

        return to_remove if to_remove else False
