"""Parse the distribution section (ACTION/INFO addressee codes with copy counts).

Appears at the start of message content, before the dash counter line.
Parsed after page-break removal via dependency on BuildMessageContent.

Output fields:
  _distribution — {raw, unknown_num, ACTION: {CODE: count, ...},
                   INFO: {CODE: count, ...}}
"""

from rebulk import Rebulk, Rule
from rebulk.match import Match
from rebulk.remodule import re

from ..content_view import (
    TAG_HEADER,
    TAG_STRIP,
    ZONE_PRE,
    get_view,
)
from ..rules.message_content import BuildMessageContent
from .from_line import ValidateFrom

_CODE_RE = re.compile(r"(?P<code>\w+)-(?P<count>\d+)")
_SUM_RE = re.compile(r"/\s*(?P<expected>\d+)(?:\s+[RW])?\s*$", re.MULTILINE)
_DASH_BOUNDARY_RE = re.compile(r"^\s{4,}\-{10,}", re.MULTILINE)
_DISTRIBUTION_START_RE = re.compile(
    r"^[ \t]*(?P<section>ACTION|ORIGIN)\b", re.MULTILINE
)
_UNKNOWN_NUM_RE = re.compile(
    r"^[ \t]*(?P<unknown_num>\d+)[ \t]*\r?\n(?:[ \t]*\r?\n)*\Z",
    re.MULTILINE,
)


def _validate_sum(parsed, text):
    """Validate that the expected sum (from /N suffix) matches actual total.

    Returns a dict with expected, actual, valid keys, or None if no sum marker found.
    """
    total = sum(c for section in parsed.values() for c in section.values())
    sum_m = _SUM_RE.search(text)
    if not sum_m:
        return None
    expected = int(sum_m.group("expected"))
    return {"expected": expected, "actual": total, "valid": expected == total}


def _parse_distribution(text):
    lines = text.split("\n")
    result = {}
    current_section = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        upper = stripped.upper()
        if upper.startswith("ACTION"):
            current_section = "ACTION"
            result["ACTION"] = {}
            for code, count in _CODE_RE.findall(stripped):
                result["ACTION"][code] = int(count)
        elif upper.startswith("ORIGIN"):
            current_section = "ORIGIN"
            result["ORIGIN"] = {}
            for code, count in _CODE_RE.findall(stripped):
                result["ORIGIN"][code] = int(count)
        elif upper.startswith("INFO"):
            current_section = "INFO"
            result["INFO"] = {}
            for code, count in _CODE_RE.findall(stripped):
                result["INFO"][code] = int(count)
        elif current_section == "INFO":
            for code, count in _CODE_RE.findall(stripped):
                result["INFO"][code] = int(count)

    if not result:
        return None

    sum_check = _validate_sum(result, text)
    if sum_check:
        result["_sum_check"] = sum_check

    return result


def distribution():
    """Build pattern that extracts addressee distribution information."""
    rebulk = Rebulk()
    rebulk.rules(ParseDistribution)
    return rebulk


class ParseDistribution(Rule):
    """Parse distribution (ACTION/INFO addressee codes) from message content.

    Uses the /N sum line (e.g. "/050 W") to find where distribution ends.
    Runs after ValidateFrom so the no-sum/no-dash FM fallback can use an
    accepted ``from`` match.
    """

    priority = 32
    dependency = (BuildMessageContent, ValidateFrom)

    @staticmethod
    def _section_ranges(matches, mc_text):
        """Locate already-extracted section-marker lines in cleaned content."""
        ranges = []
        search_start = 0
        for section_match in matches.named("section_marker"):
            if not isinstance(section_match.value, list):
                continue
            for section in section_match.value:
                raw = section.get("raw", "")
                if not raw:
                    continue
                marker_line = next(
                    (line for line in raw.splitlines() if line), ""
                )
                if not marker_line:
                    continue
                position = mc_text.find(marker_line, search_start)
                if position < 0:
                    continue
                marker_end = position + len(marker_line)
                ranges.append((position, marker_end))
                search_start = marker_end
        return ranges

    @classmethod
    def _repeated_headers(cls, matches, mc_text, view, search_start, context):
        """Build private removal matches for later transmission headers."""
        from ..content_view import register_field_span

        section_ranges = cls._section_ranges(matches, mc_text)
        if not section_ranges:
            return []

        repeated = []
        for header in _DISTRIBUTION_START_RE.finditer(mc_text, search_start):
            section_range = next(
                (section for section in section_ranges if section[0] > header.end()),
                None,
            )
            if section_range is None:
                break
            section_start, section_end = section_range

            dash_m = _DASH_BOUNDARY_RE.search(
                mc_text, header.end(), section_start
            )
            if not dash_m:
                continue

            sum_m = _SUM_RE.search(mc_text, header.end(), dash_m.start())
            dist_end = sum_m.end() if sum_m else dash_m.start()
            dist_text = mc_text[header.start() : dist_end]
            if not _parse_distribution(dist_text):
                continue

            repeat_start = header.start()
            if header.group("section") == "ACTION":
                unknown_num_m = _UNKNOWN_NUM_RE.search(mc_text[:repeat_start])
                if unknown_num_m:
                    repeat_start = unknown_num_m.start()

            # Register one interval per repeated block; the private Match
            # below is only a coverage/output carrier.
            register_field_span(context, "distribution", repeat_start, section_end)
            bounding = view.clean_to_raw_bounding(repeat_start, section_end)
            if bounding is None:
                continue
            repeated.append(
                Match(
                    bounding[0],
                    bounding[1],
                    name="distribution",
                    tags=["message_content"],
                    private=True,
                )
            )
        return repeated

    def when(self, matches, context):
        from ..content_view import register_field_span

        mc = matches.named("message_content")
        view = get_view(context)
        if not mc or view is None:
            return False

        mc_text = view.text

        # Find first ACTION or ORIGIN line — distribution starts there.
        # Leading whitespace before the keyword (a NARA reproduction
        # spacing artifact, same class as the DTG issue) is tolerated.
        header = _DISTRIBUTION_START_RE.search(mc_text)
        if not header:
            return False
        dist_start = header.start()

        # Some distributions have an unlabeled numeric line immediately before
        # ACTION. Include it only when no other substantive text separates the
        # complete numeric line from the selected distribution header. ORIGIN is
        # deliberately excluded because document numbers can directly precede it.
        unknown_num = None
        if header.group("section") == "ACTION":
            unknown_num_m = _UNKNOWN_NUM_RE.search(mc_text[:dist_start])
            if unknown_num_m:
                unknown_num = int(unknown_num_m.group("unknown_num"))
                dist_start = unknown_num_m.start()

        # Find /N sum line to determine distribution end. Some documents
        # replace the numeric "/NNN" copy count with a non-numeric token
        # (e.g. "( ISO )") — when no sum marker is found, fall back to the
        # dash counter line (or the accepted FM line) as the end boundary
        # instead, same fallback order as drafting.py's metadata-region search.
        dash_m = _DASH_BOUNDARY_RE.search(mc_text, dist_start)
        sum_m = _SUM_RE.search(
            mc_text,
            dist_start,
            dash_m.start() if dash_m else len(mc_text),
        )
        if sum_m:
            sum_end = mc_text.find("\n", sum_m.end())
            dist_end = sum_end + 1 if sum_end >= 0 else len(mc_text)
        else:
            if dash_m:
                dist_end = dash_m.start()
            else:
                from_ms = [
                    m
                    for m in matches.named("from")
                    if "message_content" in (m.tags or [])
                ]
                if not from_ms:
                    return False
                # Project the accepted FM match back to clean coordinates
                # for the bound (it is already validated in-region).
                fm_clean = None
                for m in from_ms:
                    candidate = view.raw_to_clean(m.start)
                    if candidate is not None:
                        fm_clean = candidate
                        break
                if fm_clean is None or fm_clean <= dist_start:
                    return False
                dist_end = fm_clean

        dist_text = mc_text[dist_start:dist_end]

        parsed = _parse_distribution(dist_text)
        if not parsed:
            return False
        distribution_value = {"raw": dist_text}
        if unknown_num is not None:
            distribution_value["unknown_num"] = unknown_num
        distribution_value.update(parsed)

        bounding = view.clean_to_raw_bounding(dist_start, dist_end)
        if bounding is None:
            return False
        register_field_span(context, "distribution", dist_start, dist_end)
        dist_match = Match(
            bounding[0],
            bounding[1],
            value=distribution_value,
            name="distribution",
            tags=["message_content", ZONE_PRE, TAG_STRIP, TAG_HEADER],
        )
        repeated = self._repeated_headers(
            matches, mc_text, view, dist_end, context
        )
        return dist_match, repeated

    def then(self, matches, when_response, context):
        dist_match, repeated = when_response
        matches.append(dist_match)
        for repeated_header in repeated:
            matches.append(repeated_header)
