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


def drafting():
    """Build pattern that extracts drafting metadata."""
    rebulk = Rebulk()
    rebulk.rules(ParseDrafting)
    return rebulk


_DASH_RE = re.compile(r"^\s{4,}\-{10,}", re.MULTILINE)


class ParseDrafting(Rule):
    """Parse DRAFTED BY and APPROVED BY blocks from the metadata region.

    The metadata region is bounded below by the dash counter line
    (or FM line if no dash counter). Only lines within this region
    are considered — this avoids false positives from body text.
    """

    priority = 31
    dependency = BuildMessageContent

    @staticmethod
    def _find_metadata_region(mc_text):
        """Return (region_text, base_offset) bounded by dash counter or FM."""
        dc_m = _DASH_RE.search(mc_text)
        if dc_m:
            end = dc_m.start()
        else:
            fm_m = re.search(r"^FM\s+", mc_text, re.MULTILINE)
            end = fm_m.start() if fm_m else len(mc_text)
        return mc_text[:end], 0

    @staticmethod
    def _collect_section(region_text, header_prefix):
        """Collect lines for a section starting with header_prefix.

        Returns (items, start_offset, end_offset) or (None, None, None).
        Lines after the header that don't start with another header
        keyword are treated as continuations.
        """
        _END_PAT = re.compile(
            r"^(?:DRAFTED BY|APPROVED BY|DESIRED DISTRIBUTION|\s{4,}\-{10})",
            re.MULTILINE,
        )

        pat = re.compile(
            r"^" + header_prefix + r"\s*(.*)", re.MULTILINE | re.IGNORECASE
        )
        matches = list(pat.finditer(region_text))
        if not matches:
            return None, None, None

        first = matches[0]
        header_start = first.start()
        header_end = first.end()

        items = [first.group(1)]

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
        region, base = self._find_metadata_region(mc_text)

        db_items, db_start, db_end = self._collect_section(region, "DRAFTED BY")
        ab_items, ab_start, ab_end = self._collect_section(region, "APPROVED BY")

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
