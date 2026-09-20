"""Extract raw REF/REFS/REFERENCE/REF :/REFTEL/RETELS line from message content.

Reference lines appear in the message body header, often after TAGS/E.O./SUBJECT.
They can span multiple lines with continuation lines.

Output field:
  _reference — raw string from REF: line through continuation lines until
    next empty line or 200 characters (whichever comes first).

Reference splitting into individual MRNs is handled by
``src.reftel_normalize._split_refs``.
"""

from rebulk import AppendTags, Rebulk, Rule
from rebulk.match import Match
from rebulk.remodule import re

from ..rules.message_content import BuildMessageContent
from .tags_line import FindTagsCandidates

_REF_RE = re.compile(
    r"(?P<prefix>^[ \t]*|[ \t]+)"
    r"(?P<label>REFTEL\.?|RETELS?\.?|REF(?:ERENCE)?S?\.?|REF[A-Z]\.?)"
    r"(?=[ \t:;/.,-]|$)(?P<separator>[ \t]*:?[ \t]*)"
    r"(?P<value>(?:(?!\n[ \t]*\n).){0,200})",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)


def ref_line():
    """Build pattern that matches REF lines."""
    rebulk = Rebulk()
    rebulk.rules(FindRefCandidates, TagHeaderRef, ParseRef)
    return rebulk


class FindRefCandidates(Rule):
    """Create private REF candidates in cleaned-content coordinates."""

    priority = 31
    dependency = BuildMessageContent

    def when(self, matches, context):
        mc = matches.named("message_content")
        if not mc:
            return False

        mc_text = mc[0].value
        mc_start = mc[0].start

        candidates = []
        for found in _REF_RE.finditer(mc_text):
            label_start = found.start("label")
            line_start = mc_text.rfind("\n", 0, label_start) + 1
            inline = bool(mc_text[line_start:label_start].strip())
            candidate_end = found.end()
            if inline:
                line_end = mc_text.find("\n", label_start)
                if line_end >= 0:
                    candidate_end = min(candidate_end, line_end)
            tags = ["reference_candidate", "message_content"]
            tags.append("inline_reference" if inline else "legacy_reference")
            candidates.append(
                Match(
                    mc_start + found.start(),
                    mc_start + candidate_end,
                    value=mc_text[found.start() : candidate_end],
                    name="reference_marker",
                    tags=tags,
                    private=True,
                )
            )
        return candidates or False

    def then(self, matches, when_response, context):
        for candidate in when_response:
            matches.append(candidate)


class TagHeaderRef(Rule):
    """Tag the first positionally valid REF candidate as a header."""

    priority = 31
    dependency = (FindRefCandidates, FindTagsCandidates)
    consequence = AppendTags(["header"])

    def when(self, matches, context):
        candidates = sorted(
            matches.tagged("reference_candidate"),
            key=lambda match: match.start,
        )
        if not candidates:
            return False

        legacy = [
            candidate
            for candidate in candidates
            if "legacy_reference" in candidate.tags
        ]
        if legacy:
            return legacy[0]

        routing_matches = [
            match
            for match in matches.tagged("message_content")
            if match.name in {"to", "info"}
        ]
        tags_candidates = matches.tagged("tags_candidate")
        for candidate in candidates:
            inside_routing = any(
                routing.start <= candidate.start < routing.end
                for routing in routing_matches
            )
            inside_tags = any(
                tags.start <= candidate.start < tags.end
                for tags in tags_candidates
            )
            if inside_routing and inside_tags:
                return candidate
        return False


class ParseRef(Rule):
    """Export the header-tagged REF candidate."""

    priority = 31
    dependency = TagHeaderRef

    def when(self, matches, context):
        markers = sorted(
            (
                match
                for match in matches.tagged("header")
                if match.name == "reference_marker"
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
            name="reference",
            tags=["message_content"],
        )

    def then(self, matches, when_response, context):
        matches.append(when_response)
