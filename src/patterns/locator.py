"""Tag Locator matches that contain TEXT ON-LINE."""

from rebulk import Rebulk, Rule


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

    priority = 152

    def when(self, matches, context):
        for match in matches.named("Locator"):
            if "TEXT ON-LINE" in match.value.upper():
                match.tags.append("text-online")
        return False
