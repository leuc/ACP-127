"""Parse the distribution section (ACTION/INFO addressee codes with copy counts).

Appears at the start of message content, before the dash counter line.
Parsed after page-break removal via dependency on BuildMessageContent.

Output fields:
  _distribution — {raw, ACTION: {CODE: count, ...}, INFO: {CODE: count, ...}}
"""

from rebulk import Rebulk, Rule
from rebulk.match import Match
from rebulk.remodule import re

from ..rules.message_content import BuildMessageContent

_CODE_RE = re.compile(r"(?P<code>\w+)-(?P<count>\d+)")
_SUM_RE = re.compile(r"/\s*(?P<expected>\d+)(?:\s+[RW])?\s*$", re.MULTILINE)


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
    """

    priority = 64
    dependency = BuildMessageContent

    def when(self, matches, context):
        mc = matches.named("message_content")
        if not mc:
            return False

        mc_text = mc[0].value
        mc_start = mc[0].start

        # Find first ACTION or ORIGIN line — distribution starts there
        act = re.search(r"^ACTION\b", mc_text, re.MULTILINE)
        org = re.search(r"^ORIGIN\b", mc_text, re.MULTILINE)
        dist_start = None
        if act and org:
            dist_start = min(act.start(), org.start())
        elif act:
            dist_start = act.start()
        elif org:
            dist_start = org.start()
        else:
            return False

        # Find /N sum line to determine distribution end
        sum_m = _SUM_RE.search(mc_text, dist_start)
        if not sum_m:
            return False

        sum_end = mc_text.find("\n", sum_m.end())
        dist_end = sum_end + 1 if sum_end >= 0 else len(mc_text)

        dist_text = mc_text[dist_start:dist_end]

        parsed = _parse_distribution(dist_text)
        if not parsed:
            return False

        dist_match = Match(
            mc_start + dist_start,
            mc_start + dist_end,
            value={"raw": dist_text, **parsed},
            name="distribution",
            tags=["message_content"],
        )
        return dist_match

    def then(self, matches, when_response, context):
        matches.append(when_response)
