"""Generic attribute key:value pattern for all Message Attributes."""

from rebulk import Rebulk, Rule, RemoveMatch, AppendMatch
from rebulk.match import Match
from rebulk.remodule import re


def attributes():
    """Build pattern that matches all 'Key: value' attribute lines.

    Each full-line match is parsed by a rule that creates named matches
    with the attribute key as name and the value as .value.
    """
    rebulk = Rebulk()

    rebulk.regex(
        r"(?m)^[A-Za-z][A-Za-z0-9 ]+?:\s*[^\n]*(?:\n[ \t]+[^\n]*)*",
        name="attribute",
        tags=["attribute"],
        flags=re.IGNORECASE,
    )

    rebulk.rules(
        RemoveAttributesBeforeMarker,
        ConvertAttributesToNamed,
    )

    return rebulk


_ATTR_RE = re.compile(
    r"^(?P<key>[A-Za-z][A-Za-z0-9 ]+?):\s*(?P<value>.*)",
    re.MULTILINE | re.IGNORECASE,
)


class RemoveAttributesBeforeMarker(Rule):
    """Remove attribute matches that occur before the Message Attributes marker."""

    priority = 128
    consequence = RemoveMatch

    def when(self, matches, context):
        attr_ms = matches.markers.named("message_attributes_marker")
        if not attr_ms:
            return list(matches.named("attribute"))

        marker_start = attr_ms[0].start
        ret = []
        for match in matches.named("attribute"):
            if match.start < marker_start:
                ret.append(match)
        return ret or False


class ConvertAttributesToNamed(Rule):
    """Convert generic 'attribute' matches into named matches with key/value."""

    priority = 64
    dependency = RemoveAttributesBeforeMarker
    consequence = [RemoveMatch, AppendMatch]

    def when(self, matches, context):
        existing = {
            m.name.lower() for m in matches if not m.private and not m.marker and m.name
        }

        to_remove = []
        to_append = []
        for match in matches.named("attribute"):
            m = _ATTR_RE.match(match.value)
            if m:
                key = m.group("key").strip()
                val = m.group("value").strip()
                if key:
                    if key.lower() in existing:
                        to_remove.append(match)
                        continue
                    to_remove.append(match)
                    to_append.append(
                        Match(
                            match.start,
                            match.end,
                            value=val,
                            name=key,
                            tags=["attribute"],
                        )
                    )
        return to_remove, to_append
