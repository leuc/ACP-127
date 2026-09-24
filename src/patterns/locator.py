"""Tag Locator matches that contain TEXT ON-LINE."""

import re as _re

from rebulk import Rebulk, Rule

# Same tolerant predicate as coverage.has_retrievable_body: NARA spacing
# variants ("TEXT ONLINE", "TEXT ON LINE") must count. Only a Locator in
# the validated Message Attributes region may set eligibility -- an
# identical word in the telegram body must not do so.
TEXT_ON_LINE_RE = _re.compile(r"TEXT\s+ON[-\s]*LINE", _re.IGNORECASE)


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


def is_text_online(value):
    """Return whether a Locator value carries a TEXT ON-LINE form."""
    return isinstance(value, str) and TEXT_ON_LINE_RE.search(value) is not None


class TagLocatorTextOnline(Rule):
    """Tag scoped locator matches that contain TEXT ON-LINE."""

    priority = 152

    def when(self, matches, context):
        attr_ms = matches.markers.named("message_attributes_marker")
        scoped_start = attr_ms[0].start if len(attr_ms) == 1 else None
        for match in matches.named("Locator"):
            if scoped_start is not None and match.start < scoped_start:
                continue
            if is_text_online(match.value) and "text-online" not in match.tags:
                match.tags.append("text-online")
        return False
