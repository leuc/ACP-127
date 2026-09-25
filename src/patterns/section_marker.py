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
from .classification import _CLASSIFICATIONS, spaced_alternation


def section_marker():
    """Build pattern that matches section header lines."""
    rebulk = Rebulk()

    rebulk.regex(
        r"(?P<before_nl>\n{,3})^"
        r"(?:(?P<classification>" + "|".join(_CLASSIFICATIONS) + r")"
        r"|(?:" + spaced_alternation() + r"))"
        r"\s+SECTION\s+(?P<section_number>\d+)\s+OF\s+(?P<section_total>\d+)\s+"
        r"(?P<section_id>.+)$"
        r"(?P<after_nl>\n{,2})",
        name="section_marker",
        tags=["message_content"],
        flags=re.MULTILINE | re.IGNORECASE,
        every=True,
        # Private candidate: only the ExtractSectionMarker aggregate
        # (list of section dicts) may serialize. Unconvertible raw matches
        # must never leak as last-wins strings into JSON.
        private=True,
        private_names=[
            "classification",
            "section_number",
            "section_total",
            "section_id",
            "before_nl",
            "after_nl",
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
        from ..content_view import content_region, get_view

        markers = list(matches.named("section_marker"))
        if not markers:
            return False

        mc = matches.named("message_content")
        view = get_view(context)
        region = content_region(matches)
        if not mc or view is None or region is None:
            # Cannot convert: drop every raw match so none survives to
            # serialization as an unconverted string.
            return markers, [], []

        text_end, attr_start = region

        in_region = [
            m for m in markers if text_end <= m.start < attr_start
        ]
        if not in_region:
            return markers, [], []

        sections = []
        for m in in_region:
            raw = m.raw
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

        return markers, sections, in_region

    def then(self, matches, when_response, context):
        from ..content_view import (
            TAG_HEADER,
            TAG_STRIP,
            ZONE_ROUTING,
            get_view,
            register_field_span,
        )

        to_remove, sections, kept = when_response
        view = get_view(context)
        coverage_ranges = context.setdefault("_coverage_ranges", [])
        if view is not None:
            # Register one exact interval per actual section line --
            # never the bounding span of the aggregate output carrier.
            for m in kept:
                clean_start = view.raw_to_clean(m.start)
                clean_end = view.raw_to_clean(m.end - 1)
                if clean_start is not None and clean_end is not None:
                    segments = view.clean_to_raw(clean_start, clean_end + 1)
                    if segments == [(m.start, m.end)]:
                        register_field_span(
                            context, "section_marker", clean_start, clean_end + 1
                        )
        for m in kept:
            # Individual raw spans for coverage (not the aggregate bounds).
            coverage_ranges.append((m.start, m.end))
        for m in to_remove:
            if m in matches:
                matches.remove(m)

        if not kept:
            return True

        matches.append(
            Match(
                kept[0].start,
                kept[-1].end,
                value=sections,
                name="section_marker",
                # Output carrier only: stripping uses the registered
                # per-section intervals, never this bounding span.
                tags=["message_content", ZONE_ROUTING, TAG_STRIP, TAG_HEADER],
            )
        )
