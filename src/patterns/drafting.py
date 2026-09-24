"""Extract drafting metadata (DRAFTED BY, APPROVED BY) from message content.

These lines appear in State-originated cables between the distribution
section and the dash counter line. Each is output as a list of strings,
one per line (with the section header prefix stripped from the first line).

Output fields:
  _drafted_by — list of drafting officer lines
  _approved_by — list of approving officer lines and continuations
"""

from rebulk import Rebulk, Rule
from rebulk.match import Match
from rebulk.remodule import re

from ..content_view import (
    TAG_HEADER,
    TAG_STRIP,
    ZONE_PRE,
    get_view,
    register_field_span,
)
from ..rules.message_content import BuildMessageContent
from .dash_counter import CollectDashCounters
from .from_line import ValidateFrom


def drafting():
    """Build pattern that extracts drafting metadata."""
    rebulk = Rebulk()
    rebulk.rules(ParseDrafting)
    return rebulk


_DRAFTED_HEADER = (
    r"DRAFTED(?:Y[ \t]+BY|[ \t]*BY|[ \t]+[A-Z0-9]{1,2})?"
)
_CANONICAL_DRAFTED_HEADER = r"DRAFTED[ \t]+BY"
_APPROVED_HEADER = r"(?:APPROVED(?:[ \t]*BY)?|EPPROVED[ \t]+BY)"
_END_PAT = re.compile(
    r"^(?:"
    + _DRAFTED_HEADER
    + r"|"
    + _APPROVED_HEADER
    + r"|DESIRED DIST(?:RIBUTION|B)|DISTRIBUTION)\b",
    re.MULTILINE | re.IGNORECASE,
)


class ParseDrafting(Rule):
    """Parse DRAFTED BY and APPROVED BY blocks from the metadata region.

    The metadata region is bounded below by the projected dash counter
    line (or FM line if no dash counter). Only lines within this region
    are considered — this avoids false positives from body text. The
    structural final-section fallback is bounded by a section/page break
    or the last blank-line block -- never a fixed byte window. A fallback
    DRAFTED BY still needs a complete header line and nearby APPROVED BY
    or metadata evidence.
    """

    priority = 31
    dependency = (BuildMessageContent, CollectDashCounters, ValidateFrom)

    @staticmethod
    def _metadata_end(mc_text, matches, view):
        """Return the clean offset bounding the metadata region."""
        boundaries = []
        for name in ("dash_counters", "from"):
            for match in matches.named(name):
                clean = view.raw_to_clean(match.start)
                if clean is not None:
                    boundaries.append(clean)
        if boundaries:
            return min(boundaries)
        return len(mc_text)

    @staticmethod
    def _structural_footer_start(mc_text, metadata_end):
        """Return the start of the last blank-line-delimited block.

        Used only for the fallback DRAFTED BY search: bounds the scan to
        the final structural block instead of an arbitrary byte window.
        """
        head = mc_text[:metadata_end]
        blocks = re.split(r"\n[ \t]*\n", head)
        if not blocks:
            return 0
        last = blocks[-1]
        return metadata_end - len(last)

    @staticmethod
    def _collect_section(region_text, header_prefix):
        """Collect lines for a section starting with header_prefix.

        Returns (items, start_offset, end_offset) or (None, None, None).
        Lines after the header that don't start with another header
        keyword are treated as continuations.
        """
        pat = re.compile(
            r"^"
            + header_prefix
            + r"(?P<separator>[ \t]*[:=-][ \t]*|[ \t]+)"
            + r"(?P<value>.*)",
            re.MULTILINE | re.IGNORECASE,
        )
        matches = list(pat.finditer(region_text))
        if not matches:
            return None, None, None

        first = matches[0]
        header_start = first.start()
        header_end = first.end()

        items = [first.group("value")]

        # Collect continuation lines until next section header or end
        rest = region_text[header_end:]
        end_m = _END_PAT.search(rest)
        cont_end = header_end + (end_m.start() if end_m else len(rest))

        for line in region_text[header_end:cont_end].split("\n"):
            stripped = line.strip()
            if stripped:
                items.append(stripped)

        return items, header_start, cont_end

    def when(self, matches, context):
        mc = matches.named("message_content")
        view = get_view(context)
        if not mc or view is None:
            return False

        mc_text = view.text
        metadata_end = self._metadata_end(mc_text, matches, view)
        region = mc_text[:metadata_end]

        db_items, db_start, db_end = self._collect_section(
            region, _DRAFTED_HEADER
        )
        ab_items, ab_start, ab_end = self._collect_section(
            region, _APPROVED_HEADER
        )

        if not db_items:
            footer_start = self._structural_footer_start(mc_text, metadata_end)
            footer = mc_text[footer_start:metadata_end]
            items, start, end = self._collect_section(
                footer, _CANONICAL_DRAFTED_HEADER
            )
            # Fallback needs nearby APPROVED BY/metadata evidence, not
            # arbitrary prose: require an APPROVED header in the same
            # structural block.
            if items:
                _ab, _, _ = self._collect_section(footer, _APPROVED_HEADER)
                if _ab:
                    db_items, db_start, db_end = (
                        items,
                        start + footer_start,
                        end + footer_start,
                    )

        results = []
        for items, start, end, name in (
            (db_items, db_start, db_end, "drafted_by"),
            (ab_items, ab_start, ab_end, "approved_by"),
        ):
            if not items:
                continue
            bounding = view.clean_to_raw_bounding(start, end)
            if bounding is None:
                continue
            register_field_span(context, name, start, end)
            results.append(
                Match(
                    bounding[0],
                    bounding[1],
                    value=items,
                    name=name,
                    tags=["message_content", ZONE_PRE, TAG_STRIP, TAG_HEADER],
                )
            )

        return results if results else False

    def then(self, matches, when_response, context):
        for m in when_response:
            matches.append(m)
