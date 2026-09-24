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
        from ..content_view import get_view

        mc = matches.named("message_content")
        view = get_view(context)
        if not mc or view is None:
            return False

        mc_text = view.text
        candidates = []
        for found in _HANDLING_RE.finditer(mc_text):
            bounding = view.clean_to_raw_bounding(found.start(), found.end())
            if bounding is None:
                continue
            candidates.append(
                Match(
                    bounding[0],
                    bounding[1],
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
        from ..content_view import get_view
        from .routing import walk_routing

        mc = matches.named("message_content")
        view = get_view(context)
        if not mc or view is None:
            return False

        mc_text = view.text

        def _clean_of(raw_start, raw_end):
            clean_start = view.raw_to_clean(raw_start)
            clean_end = view.raw_to_clean(raw_end - 1)
            if clean_start is None or clean_end is None:
                return None
            return (clean_start, clean_end + 1)

        candidates = sorted(
            matches.tagged("handling_restriction_candidate"),
            key=lambda match: match.start,
        )
        if not candidates:
            return False
        # Candidate positions in clean coordinates (None when unmappable).
        clean_pos = {}
        for candidate in candidates:
            clean_pos[id(candidate)] = _clean_of(candidate.start, candidate.end)

        anchors = []
        walked = walk_routing(mc_text)
        if walked is not None:
            routing_end = walked["header_end"]
            anchors.append(routing_end)
            routing_start = walked["header_start"]
        else:
            routing_start = None
            routing_end = None

        header_ends = []
        for match in matches.tagged("message_content"):
            if match.name in {"executive_order", "tags", "subject"}:
                projected = _clean_of(match.start, match.end)
                if projected is not None:
                    header_ends.append(projected[0])
        if header_ends:
            upper_bound = min(header_ends)
            lower_bound = routing_start if routing_start is not None else 0
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
                marker_line = next(
                    (line for line in raw.splitlines() if line), ""
                )
                if not marker_line:
                    continue
                position = mc_text.find(marker_line, search_start)
                if position < 0:
                    continue
                anchors.append(position + len(marker_line))
                search_start = position + len(marker_line)

        tagged = []
        if upper_bound is not None:
            tagged.extend(
                candidate
                for candidate in candidates
                if clean_pos[id(candidate)] is not None
                and lower_bound <= clean_pos[id(candidate)][0] < upper_bound
            )

        if routing_start is not None:
            cursor = routing_end
            for candidate in reversed(candidates):
                pos = clean_pos[id(candidate)]
                if pos is None or not (routing_start <= pos[0] < cursor):
                    continue
                trailing = mc_text[pos[1]:cursor]
                if trailing.strip():
                    break
                tagged.append(candidate)
                cursor = pos[0]

        for anchor in anchors:
            cursor = anchor
            for candidate in candidates:
                pos = clean_pos[id(candidate)]
                if pos is None or pos[0] < cursor:
                    continue
                gap = mc_text[cursor:pos[0]]
                if gap.strip():
                    break
                tagged.append(candidate)
                cursor = pos[1]

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
        from ..content_view import (
            TAG_HEADER,
            TAG_STRIP,
            ZONE_CLUSTER,
            get_view,
            register_field_span,
        )

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
        view = get_view(context)
        if mc and view is not None:
            mc_text = view.text
            routing_matches = [
                match for name in ("to", "info") for match in matches.named(name)
            ]
            for routing_match in routing_matches:
                routing_clean = view.raw_to_clean(routing_match.start)
                for marker in reversed(markers):
                    marker_clean_start = view.raw_to_clean(marker.start)
                    marker_clean_end = view.raw_to_clean(marker.end - 1)
                    if marker_clean_start is None or marker_clean_end is None:
                        continue
                    raw = mc_text[
                        marker_clean_start : marker_clean_end + 1
                    ].strip()
                    value = routing_match.value.rstrip(" \t,;/+-")
                    if value.upper().endswith(raw.upper()):
                        routing_match.value = value[: -len(raw)].rstrip(
                            " \t,;/+-"
                        )
            # Register one exact interval per accepted designator line.
            for marker in markers:
                clean_start = view.raw_to_clean(marker.start)
                clean_end = view.raw_to_clean(marker.end - 1)
                if clean_start is not None and clean_end is not None:
                    register_field_span(
                        context, "handling_restrictions", clean_start, clean_end + 1
                    )

        values = [value for marker in markers for value in marker.value]
        return Match(
            markers[0].start,
            markers[-1].end,
            value=values,
            name="handling_restrictions",
            tags=["message_content", ZONE_CLUSTER, TAG_STRIP, TAG_HEADER],
        )

    def then(self, matches, when_response, context):
        matches.append(when_response)
