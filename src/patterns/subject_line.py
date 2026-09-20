"""Extract the SUBJECT/SUBJ line from message content.

The subject line appears in the message body header after TAGS/E.O.
and before REF. It may use a colon, other punctuation, or whitespace as
the label separator and may span multiple continuation lines.  Broader
separator forms are accepted only after an existing tagged header match.

Output field:
  _subject — the subject text, continuation lines joined with spaces
"""

from rebulk import AppendTags, Rebulk, Rule
from rebulk.match import Match
from rebulk.remodule import re

from ..rules.message_content import BuildMessageContent
from .eo_line import ParseExecutiveOrder
from .ref_line import ParseRef
from .tags_line import FindTagsCandidates

_SUBJECT_RE = re.compile(
    r"(?P<prefix>^[ \t]*|[ \t]+|(?<=:)|(?<=TAGS))"
    r"(?P<label>SUBJECT|SUBJT|SUBJ4|SUBJ|SUB|SUJ)"
    r"(?P<separator>[ \t]*[:;/.,][ \t]*|[ \t]+)"
    r"(?P<value>\S.*?)$",
    re.MULTILINE | re.IGNORECASE,
)

_BLANK_LINE_RE = re.compile(r"\r?\n[ \t]*\r?\n")
_BODY_START_RE = re.compile(
    r"^[ \t]*(?P<body_start>\d+[.)]|SUMMARY(?:[ \t]*[:.;]|$))",
    re.IGNORECASE,
)
_MAX_RELAXED_HEADER_GAP = 256
_MAX_CONTINUATION_BYTES = 500
_MAX_CONTINUATION_LINES = 5

_PRE_SUBJECT_HEADERS = {
    "distribution",
    "dtg",
    "from",
    "to",
    "info",
    "drafted_by",
    "approved_by",
    "executive_order",
}


def subject_line():
    """Build pattern that matches the SUBJECT line."""
    rebulk = Rebulk()
    rebulk.rules(FindSubjectCandidates, TagHeaderSubject, ParseSubject)
    return rebulk


class FindSubjectCandidates(Rule):
    """Create private SUBJECT candidates in cleaned-content coordinates."""

    priority = 31
    dependency = BuildMessageContent

    def when(self, matches, context):
        mc = matches.named("message_content")
        if not mc:
            return False

        mc_text = mc[0].value
        mc_start = mc[0].start
        candidates = []
        for found in _SUBJECT_RE.finditer(mc_text):
            separator = found.group("separator")
            tags = ["subject_candidate", "message_content"]
            raw = found.group(0)
            label_start = found.start("label")
            line_start = mc_text.rfind("\n", 0, label_start) + 1
            inline = bool(mc_text[line_start:label_start].strip())
            if inline:
                tags.append("inline_subject")
                if any(mark in separator for mark in ":;/.,"):
                    tags.append("punctuated_subject")
            elif ":" in separator and raw == raw.lstrip(" \t"):
                tags.append("legacy_subject")
            candidates.append(
                Match(
                    mc_start + found.start(),
                    mc_start + found.end(),
                    value=found.group("value").strip(),
                    name="subject_marker",
                    tags=tags,
                    private=True,
                )
            )
        return candidates or False

    def then(self, matches, when_response, context):
        for candidate in when_response:
            matches.append(candidate)


class TagHeaderSubject(Rule):
    """Tag the first positionally valid SUBJECT candidate as a header."""

    priority = 31
    dependency = (
        FindSubjectCandidates,
        FindTagsCandidates,
        ParseExecutiveOrder,
        ParseRef,
    )
    consequence = AppendTags(["header"])

    def when(self, matches, context):
        candidates = sorted(
            matches.tagged("subject_candidate"), key=lambda match: match.start
        )
        if not candidates:
            return False

        legacy = [
            candidate
            for candidate in candidates
            if "legacy_subject" in candidate.tags
        ]
        if legacy:
            return legacy[0]

        anchors = [
            match
            for match in matches.tagged("message_content")
            if match.name in _PRE_SUBJECT_HEADERS
        ]
        if not anchors:
            return False

        routing_matches = [
            match for match in anchors if match.name in {"to", "info"}
        ]
        tags_candidates = matches.tagged("tags_candidate")

        references = sorted(matches.named("reference"), key=lambda match: match.start)
        for candidate in candidates:
            if "inline_subject" in candidate.tags:
                inside_routing = any(
                    routing.start <= candidate.start < routing.end
                    for routing in routing_matches
                )
                inside_tags = any(
                    tags.start <= candidate.start < tags.end
                    for tags in tags_candidates
                )
                if (
                    inside_routing
                    and inside_tags
                    and "punctuated_subject" in candidate.tags
                ):
                    return candidate
                continue

            preceding = [anchor for anchor in anchors if anchor.end <= candidate.start]
            if not preceding:
                continue
            lower_bound = max(anchor.end for anchor in preceding)
            if candidate.start - lower_bound > _MAX_RELAXED_HEADER_GAP:
                continue
            upper_bound = next(
                (
                    reference.start
                    for reference in references
                    if reference.start >= lower_bound
                ),
                None,
            )
            if upper_bound is None or candidate.start < upper_bound:
                return candidate
        return False


class ParseSubject(Rule):
    """Collect the header-tagged SUBJECT candidate and its continuations."""

    priority = 31
    dependency = TagHeaderSubject

    def when(self, matches, context):
        mc = matches.named("message_content")
        if not mc:
            return False

        markers = sorted(
            (
                match
                for match in matches.tagged("header")
                if match.name == "subject_marker"
            ),
            key=lambda match: match.start,
        )
        if not markers:
            return False

        marker = markers[0]
        mc_text = mc[0].value
        mc_start = mc[0].start
        start = marker.start - mc_start
        marker_end = marker.end - mc_start
        first_val = marker.value

        rest = mc_text[marker_end:]
        boundaries = []
        blank_line = _BLANK_LINE_RE.search(rest)
        if blank_line:
            boundaries.append(blank_line.start())
        boundaries.extend(
            reference.start - marker.end
            for reference in matches.named("reference")
            if reference.start >= marker.end
        )
        block_end = min(boundaries) if boundaries else 0
        block_text = mc_text[marker_end : marker_end + block_end]
        block_lines = [line for line in block_text.splitlines() if line.strip()]
        if (
            len(block_text) <= _MAX_CONTINUATION_BYTES
            and len(block_lines) <= _MAX_CONTINUATION_LINES
        ):
            continuation_lines = [line.strip() for line in block_lines]
            continuation_end = len(block_text)
        else:
            continuation_lines = []
            continuation_end = 0
            possible_lines = []
            body_start_found = False
            offset = 0
            for line_with_end in rest.splitlines(keepends=True):
                line = line_with_end.rstrip("\r\n")
                if not line.strip():
                    offset += len(line_with_end)
                    if possible_lines:
                        break
                    continue
                if _BODY_START_RE.match(line):
                    body_start_found = True
                    break
                possible_lines.append((line, offset + len(line_with_end)))
                if len(possible_lines) >= _MAX_CONTINUATION_LINES:
                    break
                offset += len(line_with_end)

            if body_start_found:
                continuation_lines = [line.strip() for line, _end in possible_lines]
                if possible_lines:
                    continuation_end = possible_lines[-1][1]
            else:
                for line, line_end in possible_lines:
                    if not line.startswith(("  ", "\t")):
                        break
                    continuation_lines.append(line.strip())
                    continuation_end = line_end

        parts = [first_val, *continuation_lines]
        end_offset = continuation_end

        value = " ".join(parts)

        return Match(
            mc_start + start,
            mc_start + marker_end + end_offset,
            value=value,
            name="subject",
            tags=["message_content"],
        )

    def then(self, matches, when_response, context):
        matches.append(when_response)
