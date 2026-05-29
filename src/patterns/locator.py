"""Tag Locator matches that contain TEXT ON-LINE."""

from rebulk import Rebulk, Rule
from rebulk.remodule import re


def locator():
    """Return a Rebulk that tags Locator matches containing TEXT ON-LINE.

    The Locator key is already matched by attributes.py via string
    matching.  This module adds a rule that tags those matches with
    "text-online" when the value indicates the message text is
    available.
    """
    rebulk = Rebulk()
    rebulk.rules(TagLocatorTextOnline)
    return rebulk


class TagLocatorTextOnline(Rule):
    """Tag locator matches that contain TEXT ON-LINE."""

    priority = 64

    def when(self, matches, context):
        for match in matches.named("Locator"):
            if re.search(r"\bTEXT\s+ON-LINE\b", match.value, re.IGNORECASE):
                match.tags.append("text-online")
        return False
