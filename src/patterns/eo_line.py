"""Extract the Executive Order line from message content.

The Executive Order line appears in the message header after routing and
drafting fields, sometimes before and sometimes after REF. Its punctuation
varies, but the order number comes from a small known set. Separator variants
are accepted only when an existing extracted header field places the
candidate in that header position.

Output field:
  _executive_order — the raw Executive Order line
"""

from rebulk import AppendTags, Rebulk, Rule
from rebulk.match import Match
from rebulk.remodule import re

from ..rules.message_content import BuildMessageContent
from .ref_line import ParseRef

_EO_RE = re.compile(
    r"^[ \t]*(?P<label>E[ \t]*\.{0,2}[ \t]*O[ \t]*\.?)[ \t]*"
    r"(?:"
    r"(?P<prefix_colon>:[ \t]*)?"
    r"(?P<order>11652|11653|12065)"
    r"(?P<separator>[ \t]*[:;,/.'$-]?[ \t]*)"
    r"(?P<value>[^\r\n]*?)"
    r"|(?P<fallback_value>\S[^\r\n]*?)"
    r")[ \t]*$",
    re.MULTILINE | re.IGNORECASE,
)
_FALLBACK_VALUE_RE = re.compile(
    r"(?<![A-Z])(?P<value_token>N/?A|[XN]?GDS(?:-[A-Z0-9]+)?|"
    r"RDS(?:-[A-Z0-9]+)?|XDS(?:-[A-Z0-9]+)?|GS|GDA|DECLAS)(?![A-Z])",
    re.IGNORECASE,
)

_PRE_EO_HEADERS = {
    "distribution",
    "dtg",
    "from",
    "to",
    "info",
    "drafted_by",
    "approved_by",
    "reference",
}
_MAX_HEADER_GAP = 512
_MAX_FALLBACK_HEADER_GAP = 128


def eo_line():
    """Build Executive Order candidate, tagging, and collection rules."""
    rebulk = Rebulk()
    rebulk.rules(
        FindExecutiveOrderCandidates,
        TagHeaderExecutiveOrder,
        ParseExecutiveOrder,
    )
    return rebulk


class FindExecutiveOrderCandidates(Rule):
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
        for found in _EO_RE.finditer(mc_text):
            fallback_value = found.group("fallback_value")
            if fallback_value is not None and not _FALLBACK_VALUE_RE.search(
                fallback_value
            ):
                continue
            tags = ["executive_order_candidate", "message_content"]
            if fallback_value is not None:
                tags.append("fallback_executive_order")
            elif (
                found.group("prefix_colon") is None
                and ":" in found.group("separator")
                and found.group("value").strip()
            ):
                tags.append("legacy_executive_order")
            candidates.append(
                Match(
                    mc_start + found.start(),
                    mc_start + found.end(),
                    value=found.group(0).strip(),
                    name="executive_order_marker",
                    tags=tags,
                    private=True,
                )
            )
        return candidates or False

    def then(self, matches, when_response, context):
        for candidate in when_response:
            matches.append(candidate)


class TagHeaderExecutiveOrder(Rule):
    """Tag the first positionally valid Executive Order candidate."""

    priority = 31
    dependency = (FindExecutiveOrderCandidates, ParseRef)
    consequence = AppendTags(["header"])

    def when(self, matches, context):
        candidates = sorted(
            matches.tagged("executive_order_candidate"),
            key=lambda match: match.start,
        )
        if not candidates:
            return False

        legacy = [
            candidate
            for candidate in candidates
            if "legacy_executive_order" in candidate.tags
        ]
        if legacy:
            return legacy[0]

        anchors = [
            match
            for match in matches.tagged("message_content")
            if match.name in _PRE_EO_HEADERS
        ]
        following_anchors = [
            *matches.tagged("tags_candidate"),
            *matches.named("reference"),
        ]
        if not anchors and not following_anchors:
            return False

        for candidate in candidates:
            containing_routing = [
                match
                for match in anchors
                if match.name in {"to", "info"}
                and match.start <= candidate.start < match.end
            ]
            if containing_routing:
                return candidate

            preceding = [
                anchor for anchor in anchors if anchor.end <= candidate.start
            ]
            max_gap = (
                _MAX_FALLBACK_HEADER_GAP
                if "fallback_executive_order" in candidate.tags
                else _MAX_HEADER_GAP
            )
            if preceding:
                lower_bound = max(anchor.end for anchor in preceding)
                if candidate.start - lower_bound <= max_gap:
                    return candidate

            if "fallback_executive_order" in candidate.tags:
                following = [
                    anchor
                    for anchor in following_anchors
                    if candidate.end <= anchor.start
                ]
                if following:
                    upper_bound = min(anchor.start for anchor in following)
                    if upper_bound - candidate.end <= max_gap:
                        return candidate
        return False


class ParseExecutiveOrder(Rule):
    """Export the header-tagged Executive Order candidate."""

    priority = 31
    dependency = TagHeaderExecutiveOrder

    def when(self, matches, context):
        markers = sorted(
            (
                match
                for match in matches.tagged("header")
                if match.name == "executive_order_marker"
            ),
            key=lambda match: match.start,
        )
        if not markers:
            return False

        marker = markers[0]
        return Match(
            marker.start,
            marker.end,
            value=marker.value,
            name="executive_order",
            tags=["message_content"],
        )

    def then(self, matches, when_response, context):
        matches.append(when_response)
