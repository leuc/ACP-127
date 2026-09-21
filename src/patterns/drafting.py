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
_MAX_FOOTER_DISTANCE = 512


class ParseDrafting(Rule):
    """Parse DRAFTED BY and APPROVED BY blocks from the metadata region.

    The metadata region is bounded below by the dash counter line
    (or FM line if no dash counter). Only lines within this region
    are considered — this avoids false positives from body text.
    """

    priority = 31
    dependency = (BuildMessageContent, CollectDashCounters, ValidateFrom)

    @staticmethod
    def _find_metadata_region(mc_text, matches):
        """Return the region before existing dash-counter/from matches."""
        boundaries = []
        for name in ("dash_counters", "from"):
            for match in matches.named(name):
                if name == "dash_counters" and isinstance(match.value, dict):
                    raw = match.value.get("raw")
                else:
                    raw = match.raw
                if not raw:
                    continue
                position = mc_text.find(raw)
                if position >= 0:
                    boundaries.append(position)
        end = min(boundaries) if boundaries else len(mc_text)
        return mc_text[:end], 0

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
        if not mc:
            return False

        mc_text = mc[0].value
        mc_start = mc[0].start
        region, base = self._find_metadata_region(mc_text, matches)

        db_items, db_start, db_end = self._collect_section(
            region, _DRAFTED_HEADER
        )
        ab_items, ab_start, ab_end = self._collect_section(
            region, _APPROVED_HEADER
        )

        if not db_items:
            footer_start = max(0, len(mc_text) - _MAX_FOOTER_DISTANCE)
            footer = mc_text[footer_start:]
            db_items, db_start, db_end = self._collect_section(
                footer, _CANONICAL_DRAFTED_HEADER
            )
            if db_items:
                db_start += footer_start
                db_end += footer_start

        results = []
        if db_items:
            results.append(
                Match(
                    mc_start + base + db_start,
                    mc_start + base + db_end,
                    value=db_items,
                    name="drafted_by",
                    tags=["message_content"],
                )
            )
        if ab_items:
            results.append(
                Match(
                    mc_start + base + ab_start,
                    mc_start + base + ab_end,
                    value=ab_items,
                    name="approved_by",
                    tags=["message_content"],
                )
            )

        return results if results else False

    def then(self, matches, when_response, context):
        for m in when_response:
            matches.append(m)
