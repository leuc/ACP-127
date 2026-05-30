"""Detect section headers (classification + SECTION N OF M + location).

Section headers like "LIMITED OFFICIAL USE SECTION 1 OF 2 MEXICO 0679"
appear at the start of each content section after the DTG/FM/TO/INFO block.
They are detected here but NOT removed from message_content yet.

Output fields:
  _section_marker — list of {classification, section, total, mrn}
"""

from rebulk import Rebulk, Rule
from rebulk.match import Match
from rebulk.remodule import re

from ..rules.message_content import BuildMessageContent

_CLASSIFICATIONS = [
    "UNCLASSIFIED",
    "LIMITED OFFICIAL USE",
    "CONFIDENTIAL",
    "SECRET",
    "TOP SECRET",
]


def section_marker():
    """Build pattern that matches section header lines."""
    rebulk = Rebulk()

    rebulk.regex(
        r"^(?P<classification>"
        + "|".join(_CLASSIFICATIONS)
        + r")\s+SECTION\s+(?P<section_number>\d+)\s+OF\s+(?P<section_total>\d+)\s+(?P<section_id>.+)$",
        name="section_marker",
        tags=["message_content"],
        flags=re.MULTILINE | re.IGNORECASE,
        every=True,
        private_names=[
            "classification",
            "section_number",
            "section_total",
            "section_id",
        ],
    )

    rebulk.rules(ExtractSectionMarker)

    return rebulk


class ExtractSectionMarker(Rule):
    """Consolidate section marker matches into a single list value.

    Runs after BuildMessageContent so the message_content region
    is available to scope matches. Does NOT strip markers yet.
    """

    priority = 80
    dependency = BuildMessageContent

    def when(self, matches, context):
        mc = matches.named("message_content")
        if not mc:
            return False

        mc_text = mc[0].value
        mc_start = mc[0].start
        mc_end = mc[0].end

        markers = [
            m for m in matches.named("section_marker") if mc_start <= m.start < mc_end
        ]
        if not markers:
            return False

        sections = []
        for m in markers:
            raw = m.raw.strip()
            parts = raw.split()
            section_info = {"raw": raw}
            try:
                idx = parts.index("SECTION")
                section_info["classification"] = " ".join(parts[:idx])
                section_info["section"] = int(parts[idx + 1])
                section_info["total"] = int(parts[idx + 3])
                section_info["mrn"] = " ".join(parts[idx + 4 :])
            except (ValueError, IndexError):
                pass
            sections.append(section_info)

        return markers, sections

    def then(self, matches, when_response, context):
        markers, sections = when_response
        for m in markers:
            if m in matches:
                matches.remove(m)

        matches.append(
            Match(
                markers[0].start,
                markers[-1].end,
                value=sections,
                name="section_marker",
                tags=["message_content"],
            )
        )
