"""Locator attribute pattern."""

from rebulk import Rebulk, Rule
from rebulk.remodule import re


def locator():
    """Build Locator attribute pattern.

    Matches "Locator: value" where value may span multiple indented
    continuation lines.  The "Locator:" prefix is stripped in formatter.
    """
    rebulk = Rebulk()

    rebulk.regex(
        r"(?m)^Locator:\s*.*(?:\n[ \t]+.*)*",
        name="locator",
        tags=["attribute"],
        flags=re.IGNORECASE,
        formatter=lambda s: s[len("Locator:") :].strip()
        if s.startswith("Locator:")
        else s,
    )

    rebulk.rules(TagLocatorTextOnline)

    return rebulk


class TagLocatorTextOnline(Rule):
    """Tag locator matches that contain TEXT ON-LINE."""

    priority = 64

    def when(self, matches, context):
        for match in matches.named("locator"):
            if re.search(r"\bTEXT\s+ON-LINE\b", match.value, re.IGNORECASE):
                match.tags.append("text-online")
        return False
