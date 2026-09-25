"""Match declassification boilerplate lines that should be stripped from message content.

These are EO Systematic Review markings added by the declassification process,
not part of the original ACP-127 telegram text.
"""

from rebulk import Rebulk, Rule
from rebulk.rules import Consequence

from ..rules.validate import ValidateSingleMessageAttributes

_MARKING_STRINGS = [
    "Sheryl P. Walter Declassified/Released US Department of State EO Systematic Review 20 Mar 2014",
    "Declassified/Released US Department of State EO Systematic Review 30 JUN 2005",
    "Margaret P. Grafeld Declassified/Released US Department of State EO Systematic Review 04 MAY 2006",
    "Margaret P. Grafeld Declassified/Released US Department of State EO Systematic Review 22 May 2009",
    "Margaret P. Grafeld Declassified/Released US Department of State EO Systematic Review 06 JUL 2006",
    "Margaret P. Grafeld Declassified/Released US Department of State EO Systematic Review 05 JUL 2006",
]


class RemoveMatchesWithCoverage(Consequence):
    """Remove known boilerplate while retaining its coverage spans."""

    def then(self, matches, when_response, context):
        removed = list(when_response)
        ranges = context.setdefault("_coverage_ranges", [])
        ranges.extend((match.start, match.end) for match in removed)
        for match in removed:
            if match in matches:
                matches.remove(match)


def declass_markings():
    """Build pattern that matches declassification marking lines.

    Removal of outside-region markings (both ``marking_line`` and
    ``content_footer_marker``) lives in exactly one rule --
    ``src/rules/declass_removal.py::RemoveDeclassMarkings`` -- so the two
    overlapping removers cannot drift apart. In-region markers are left
    for ``BuildMessageContent``.
    """
    rebulk = Rebulk()

    for s in _MARKING_STRINGS:
        rebulk.string(
            s,
            name="marking_line",
            tags=["marking"],
            # Removed without output; must never serialize raw.
            private=True,
        )

    return rebulk


# Backwards-compatible alias: removal now happens only in
# ``rules.declass_removal.RemoveDeclassMarkings``. Kept so existing
# imports do not break; no longer registered as a rule.
class CollectMarkings(Rule):
    """Deprecated -- see RemoveDeclassMarkings (not registered)."""

    priority = 200
    dependency = ValidateSingleMessageAttributes
    consequence = RemoveMatchesWithCoverage()

    def when(self, matches, context):
        return False
