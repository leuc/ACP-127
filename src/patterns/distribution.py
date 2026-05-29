"""Parse the distribution section (ACTION/INFO addressee codes with copy counts).

Appears at the start of message content, before the dash counter line.
Parsed after page-break removal via dependency on MessageContentRegion.

Output fields:
  _distribution — {raw, ACTION: {CODE: count, ...}, INFO: {CODE: count, ...}}
"""

from rebulk import Rebulk, Rule, AppendMatch
from rebulk.match import Match
from rebulk.remodule import re

from ..rules.split import MessageContentRegion

_DASH_RE = re.compile(r"^\s{4,}\-{10,}\s*\d+", re.MULTILINE)
_CODE_RE = re.compile(r"(?P<code>\w+)-(?P<count>\d+)")
_SUM_RE = re.compile(r"/\s*(?P<expected>\d+)(?:\s+\w)?\s*$", re.MULTILINE)


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
            current_section = "ACTION"
            result["ACTION"] = {}
            for code, count in _CODE_RE.findall(stripped):
                result["ACTION"][code] = int(count)
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

    Runs after MessageContentRegion (page breaks stripped).
    Finds the dash counter and parses everything before it.
    """

    priority = 64
    dependency = MessageContentRegion
    consequence = AppendMatch

    def when(self, matches, context):
        mc = matches.named("message_content")
        if not mc:
            return False

        mc_text = mc[0].value
        mc_start = mc[0].start

        dash_m = _DASH_RE.search(mc_text)
        if not dash_m:
            return False

        dist_text = mc_text[: dash_m.start()]

        parsed = _parse_distribution(dist_text)
        if not parsed:
            return False

        return [
            Match(
                mc_start,
                mc_start + len(dist_text),
                value={"raw": dist_text, **parsed},
                name="distribution",
                tags=["message_content"],
            )
        ]
