"""Strip pure NARA replacement-character blocks before extraction.

Only complete lines whose non-whitespace content is a contiguous run of the
literal ``¿`` character are matched. Mixed-content lines are intentionally
left untouched for auditability.
"""

from rebulk import PRE_PROCESS, Rebulk, Rule
from rebulk.remodule import re

from .declass_markings import RemoveMatchesWithCoverage

_PURE_REPLACEMENT_BLOCK_RE = (
    r"^[ \t]*¿+[ \t]*\r?(?:\n[ \t]*¿+[ \t]*\r?)*$"
)


def reproduction_artifacts():
    """Build the exact pure-replacement-block pattern and removal rule."""
    rebulk = Rebulk()
    rebulk.regex(
        _PURE_REPLACEMENT_BLOCK_RE,
        name="reproduction_artifact_marker",
        tags=["reproduction_artifact"],
        flags=re.MULTILINE,
        private=True,
    )
    rebulk.rules(RemoveReproductionArtifacts)
    return rebulk


class RemoveReproductionArtifacts(Rule):
    """Remove pure replacement-character blocks before every other rule."""

    priority = PRE_PROCESS + 1
    consequence = RemoveMatchesWithCoverage()

    def when(self, matches, context):
        found = list(matches.named("reproduction_artifact_marker"))
        return found or False
