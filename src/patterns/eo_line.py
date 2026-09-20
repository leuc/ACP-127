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
    r"^[ \t]*(?P<label>E[ \t]*\.?[ \t]*O[ \t]*\.?)[ \t]*"
    r"(?P<prefix_colon>:[ \t]*)?"
    r"(?P<order>11652|11653|12065)"
    r"(?P<separator>[ \t]*[:;,/.'$-]?[ \t]*)"
    r"(?P<value>[^\r\n]*?)[ \t]*$",
    re.MULTILINE | re.IGNORECASE,
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
            tags = ["executive_order_candidate", "message_content"]
            if (
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
        if not anchors:
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
            if not preceding:
                continue
            lower_bound = max(anchor.end for anchor in preceding)
            if candidate.start - lower_bound > _MAX_HEADER_GAP:
                continue
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
