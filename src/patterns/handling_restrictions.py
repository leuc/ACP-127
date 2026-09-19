"""Extract handling-restriction designators from message headings.

Handling restrictions appear on standalone lines immediately after the
routing heading or a transmission-section marker.  Candidate lines are
tagged as ``header`` only when they occupy that position, preventing common
words such as ``ONLY`` and ``LOU`` in message prose from being extracted.

Output field:
  _handling_restrictions -- ordered list of designators; multiple may occur
"""

from rebulk import AppendTags, Rebulk, Rule
from rebulk.match import Match
from rebulk.remodule import re

from ..rules.message_content import BuildMessageContent
from .eo_line import ParseExecutiveOrder
from .routing import find_routing_header
from .subject_line import ParseSubject
from .tags_line import ParseTags

_VALUES = (
    "EXDIS",
    "NODIS",
    "LIMDIS",
    "NOFORN",
    "FOUO",
    "NESCO",
    "STADIS",
    "ONLY",
    "LOU",
)
_VALUE_ALT = "(?:" + "|".join(_VALUES) + ")"
_HANDLING_RE = re.compile(
    r"^[ \t]*(?P<handling_restrictions>"
    + _VALUE_ALT
    + r"(?:[ \t,;/+\-]+"
    + _VALUE_ALT
    + r")*)[ \t]*$",
    re.MULTILINE | re.IGNORECASE,
)


def _split_values(raw):
    """Split one validated designator line without re-matching it."""
    normalized = raw.upper()
    for separator in ",;/+-":
        normalized = normalized.replace(separator, " ")
    return normalized.split()


def handling_restrictions():
    """Build handling-restriction candidate, tagging, and collection rules."""
    rebulk = Rebulk()
    rebulk.rules(
        FindHandlingRestrictionCandidates,
        TagHeaderHandlingRestrictions,
        CollectHandlingRestrictions,
    )
    return rebulk


class FindHandlingRestrictionCandidates(Rule):
    """Create private candidates in cleaned message-content coordinates."""

    priority = 31
    dependency = BuildMessageContent

    def when(self, matches, context):
        mc = matches.named("message_content")
        if not mc:
            return False

        mc_text = mc[0].value
        mc_start = mc[0].start
        candidates = []
        for found in _HANDLING_RE.finditer(mc_text):
            candidates.append(
                Match(
                    mc_start + found.start(),
                    mc_start + found.end(),
                    value=_split_values(found.group("handling_restrictions")),
                    name="handling_restriction_marker",
                    tags=["handling_restriction_candidate", "message_content"],
                    private=True,
                )
            )
        return candidates or False

    def then(self, matches, when_response, context):
        for candidate in when_response:
            matches.append(candidate)


class TagHeaderHandlingRestrictions(Rule):
    """Tag only consecutive candidates following a known heading anchor."""

    priority = 31
    dependency = (
        FindHandlingRestrictionCandidates,
        ParseExecutiveOrder,
        ParseTags,
        ParseSubject,
    )
    consequence = AppendTags(["header"])

    def when(self, matches, context):
        mc = matches.named("message_content")
        if not mc:
            return False

        mc_text = mc[0].value
        mc_start = mc[0].start
        candidates = sorted(
            matches.tagged("handling_restriction_candidate"),
            key=lambda match: match.start,
        )
        if not candidates:
            return False

        anchors = []
        routing = find_routing_header(mc_text)
        if routing is not None:
            routing_start = mc_start + routing[0]
            routing_end = routing_start + routing[1]
            anchors.append(routing_end)
        else:
            routing_start = None
            routing_end = None

        header_ends = [
            match.start
            for match in matches.tagged("message_content")
            if match.name in {"executive_order", "tags", "subject"}
        ]
        if header_ends:
            upper_bound = min(header_ends)
            lower_bound = routing_start if routing_start is not None else mc_start
        else:
            upper_bound = None
            lower_bound = None

        search_start = 0
        for section_match in matches.named("section_marker"):
            if not isinstance(section_match.value, list):
                continue
            for section in section_match.value:
                raw = section.get("raw", "")
                if not raw:
                    continue
                position = mc_text.find(raw, search_start)
                if position < 0:
                    continue
                anchors.append(mc_start + position + len(raw))
                search_start = position + len(raw)

        tagged = []
        if upper_bound is not None:
            tagged.extend(
                candidate
                for candidate in candidates
                if lower_bound <= candidate.start < upper_bound
            )

        if routing_start is not None:
            cursor = routing_end
            for candidate in reversed(candidates):
                if not (routing_start <= candidate.start < cursor):
                    continue
                trailing = mc_text[candidate.end - mc_start : cursor - mc_start]
                if trailing.strip():
                    break
                tagged.append(candidate)
                cursor = candidate.start

        for anchor in anchors:
            cursor = anchor
            for candidate in candidates:
                if candidate.start < cursor:
                    continue
                gap = mc_text[cursor - mc_start : candidate.start - mc_start]
                if gap.strip():
                    break
                tagged.append(candidate)
                cursor = candidate.end

        unique = []
        seen = set()
        for candidate in tagged:
            key = (candidate.start, candidate.end)
            if key not in seen:
                seen.add(key)
                unique.append(candidate)
        return unique or False


class CollectHandlingRestrictions(Rule):
    """Collect header-tagged designators into one ordered list field."""

    priority = 31
    dependency = TagHeaderHandlingRestrictions

    def when(self, matches, context):
        markers = sorted(
            (
                match
                for match in matches.tagged("header")
                if match.name == "handling_restriction_marker"
            ),
            key=lambda match: match.start,
        )
        if not markers:
            return False

        mc = matches.named("message_content")
        if mc:
            mc_text = mc[0].value
            mc_start = mc[0].start
            routing_matches = [
                match for name in ("to", "info") for match in matches.named(name)
            ]
            for routing_match in routing_matches:
                for marker in reversed(markers):
                    raw = mc_text[
                        marker.start - mc_start : marker.end - mc_start
                    ].strip()
                    value = routing_match.value.rstrip(" \t,;/+-")
                    if value.upper().endswith(raw.upper()):
                        routing_match.value = value[: -len(raw)].rstrip(
                            " \t,;/+-"
                        )

        values = [value for marker in markers for value in marker.value]
        return Match(
            markers[0].start,
            markers[-1].end,
            value=values,
            name="handling_restrictions",
            tags=["message_content"],
        )

    def then(self, matches, when_response, context):
        matches.append(when_response)
