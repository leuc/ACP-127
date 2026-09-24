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

_LEGACY_LABELS = {
    "SUBJECT",
    "SUBJT",
    "SUBJ8",
    "SUBJ4",
    "SUBJ",
    "SUB",
    "SUJ",
}
_LABEL_CHARACTER = r"[A-Z0-9]"
_MAX_LABEL_DISTANCE = 4
_MIN_DISTANCE_FOUR_LABEL_LENGTH = 6


def _label_distance(label):
    """Return the edit distance from the two canonical SUBJECT labels."""

    def distance(left, right):
        previous = list(range(len(right) + 1))
        for left_index, left_character in enumerate(left, 1):
            current = [left_index]
            for right_index, right_character in enumerate(right, 1):
                current.append(
                    min(
                        current[-1] + 1,
                        previous[right_index] + 1,
                        previous[right_index - 1]
                        + (left_character != right_character),
                    )
                )
            previous = current
        return previous[-1]

    return min(distance(label, "SUBJECT"), distance(label, "SUBJ"))


def _is_adjacent_swap(label, canonical):
    """Return whether ``label`` is one adjacent swap from ``canonical``."""
    if len(label) != len(canonical):
        return False
    differences = [
        index
        for index, characters in enumerate(zip(label, canonical))
        if characters[0] != characters[1]
    ]
    return (
        len(differences) == 2
        and differences[1] == differences[0] + 1
        and label[differences[0]] == canonical[differences[1]]
        and label[differences[1]] == canonical[differences[0]]
    )


def _label_confidence(label):
    """Return the marker's edit tier, counting an adjacent swap as one edit."""
    distance = _label_distance(label)
    if distance <= 1 or any(
        _is_adjacent_swap(label, canonical)
        for canonical in ("SUBJECT", "SUBJ")
    ):
        return min(distance, 1)
    return distance


def _subject_matches(text):
    """Yield valid candidates without letting a rejected token hide a later one."""
    position = 0
    while position < len(text):
        found = _SUBJECT_RE.search(text, position)
        if found is None:
            return
        raw_label = found.group("label")
        separator = found.group("separator")
        label_parts = raw_label.upper().split()
        if len(label_parts) > 1 and label_parts[-1].startswith("SUBJ"):
            position = found.start() + 1
            continue
        label = raw_label.upper()
        if separator.startswith("-") and label not in {
            "SUBJECT",
            "SUBJ",
        }:
            position = found.start() + 1
            continue
        if found.group("canonical_label") is not None:
            confidence = 0
        elif found.group("suffix_label") is not None:
            confidence = 2
        else:
            confidence = _label_confidence(label)
        if confidence <= _MAX_LABEL_DISTANCE and (
            confidence < 4 or len(label) >= _MIN_DISTANCE_FOUR_LABEL_LENGTH
        ):
            yield found, label, confidence
            position = found.end()
        else:
            position = found.start() + 1


def _candidate_distance(candidate):
    """Read a candidate's confidence tier from its ReBulk tags."""
    for distance in range(_MAX_LABEL_DISTANCE + 1):
        if f"subject_distance_{distance}" in candidate.tags:
            return distance
    return _MAX_LABEL_DISTANCE + 1


def _projected_candidate(view, found, tags):
    """Project a cleaned-view candidate to raw positions (or None)."""
    from rebulk.match import Match as _Match

    bounding = view.clean_to_raw_bounding(found.start(), found.end())
    if bounding is None:
        return None
    return _Match(
        bounding[0],
        bounding[1],
        value=found.group("value").strip(),
        name="subject_marker",
        tags=tags,
        private=True,
    )


def _label_patterns(label):
    """Return regex fragments one edit or adjacent swap from ``label``."""
    patterns = {label}
    for index in range(len(label)):
        patterns.add(label[:index] + label[index + 1 :])
        patterns.add(label[:index] + _LABEL_CHARACTER + label[index + 1 :])
    for index in range(len(label)):
        patterns.add(label[:index] + _LABEL_CHARACTER + label[index:])
    patterns.add(label + _LABEL_CHARACTER + r"(?=[ \t]*[:.;])")
    for index in range(len(label) - 1):
        patterns.add(
            label[:index]
            + label[index + 1]
            + label[index]
            + label[index + 2 :]
        )
    return patterns


_SPACED_SUBJECT = r"S[ \t]*U[ \t]*B[ \t]*J[ \t]*E[ \t]*C[ \t]*T"
_SPACED_SUBJ = r"S[ \t]*U[ \t]*B[ \t]*J"
_SUBJECT_LABEL_PATTERN = (
    r"(?:"
    + r"(?P<canonical_label>"
    + _SPACED_SUBJECT
    + "|"
    + _SPACED_SUBJ
    + r")|(?P<generated_label>"
    + "|".join(
        sorted(
            _label_patterns("SUBJECT")
            | _label_patterns("SUBJ")
            | _LEGACY_LABELS,
            key=lambda pattern: (-len(pattern), pattern),
        )
    )
    + r")|(?P<suffix_label>S[A-Z0-9/'*?$-]{2,8}:5(?=[ \t]*:))"
    + r"|(?P<alphanumeric_label>[A-Z0-9]{3,10}(?=[ \t]*:))"
    + r"|(?P<punctuated_label>S[A-Z0-9 \t/'*?$-]{1,13}?[A-Z0-9](?=[ \t]*:))"
    + r")"
)

_SUBJECT_RE = re.compile(
    r"(?P<prefix>^[ \t]*|[ \t]+|(?<=:)|(?<=TAGS))"
    r"(?P<label>" + _SUBJECT_LABEL_PATTERN + r")"
    r"(?P<separator>[ \t]*[:;/.,][ \t]*|-[ \t]*|[ \t]+|(?=W/W))"
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
        from ..content_view import get_view

        mc = matches.named("message_content")
        view = get_view(context)
        if not mc or view is None:
            return False

        mc_text = view.text
        candidates = []
        for found, label, confidence in _subject_matches(mc_text):
            separator = found.group("separator")
            tags = ["subject_candidate", "message_content"]
            tags.append(f"subject_distance_{confidence}")
            raw = found.group(0)
            label_start = found.start("label")
            line_start = mc_text.rfind("\n", 0, label_start) + 1
            inline = bool(mc_text[line_start:label_start].strip())
            if inline:
                tags.append("inline_subject")
                if any(mark in separator for mark in ":;/.,"):
                    tags.append("punctuated_subject")
            elif (
                label in _LEGACY_LABELS
                and ":" in separator
                and raw == raw.lstrip(" \t")
            ):
                tags.append("legacy_subject")
            candidate = _projected_candidate(view, found, tags)
            if candidate is not None:
                candidates.append(candidate)
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

        candidates.sort(
            key=lambda candidate: (
                _candidate_distance(candidate) < 2,
                candidate.start,
            )
        )

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
        relaxed_anchors = [
            *tags_candidates,
            *matches.named("executive_order"),
        ]

        references = sorted(matches.named("reference"), key=lambda match: match.start)
        for candidate in candidates:
            relaxed = _candidate_distance(candidate) >= 2
            if "inline_subject" in candidate.tags:
                if relaxed:
                    continue
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

            if relaxed:
                preceding_relaxed = [
                    anchor
                    for anchor in relaxed_anchors
                    if anchor.end <= candidate.start
                ]
                if not preceding_relaxed:
                    continue
                lower_bound = max(anchor.end for anchor in preceding_relaxed)
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
        from ..content_view import TAG_KEEP, ZONE_CLUSTER, get_view

        mc = matches.named("message_content")
        view = get_view(context)
        if not mc or view is None:
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
        mc_text = view.text
        clean_marker_start = view.raw_to_clean(marker.start)
        clean_marker_end = view.raw_to_clean(marker.end - 1)
        if clean_marker_start is None or clean_marker_end is None:
            return False
        start = clean_marker_start
        marker_end = clean_marker_end + 1
        first_val = marker.value

        rest = mc_text[marker_end:]
        boundaries = []
        blank_line = _BLANK_LINE_RE.search(rest)
        if blank_line:
            boundaries.append(blank_line.start())
        for reference in matches.named("reference"):
            ref_clean = view.raw_to_clean(reference.start)
            if ref_clean is not None and ref_clean >= marker_end:
                boundaries.append(ref_clean - marker_end)
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

        bounding = view.clean_to_raw_bounding(start, marker_end + end_offset)
        if bounding is None:
            return False
        return Match(
            bounding[0],
            bounding[1],
            value=value,
            name="subject",
            tags=["message_content", ZONE_CLUSTER, TAG_KEEP],
        )

    def then(self, matches, when_response, context):
        matches.append(when_response)
