"""Extract raw REF/REFS/REFERENCE/REF :/REFTEL/RETELS line from message content.

Reference lines appear in the message body header, often after TAGS/E.O./SUBJECT.
They can span multiple lines with continuation lines, including lettered
enumerations (A. STATE ..., B. ...).

Output field:
  _reference — raw string from the REF header line through continuation
    lines until a blank line, next header label, section marker, or
    body-start evidence (line-based scanning; no character cap).

Reference splitting into individual MRNs is handled by
``src.reftel_normalize._split_refs``.
"""

from rebulk import AppendTags, Rebulk, Rule
from rebulk.match import Match
from rebulk.remodule import re

from ..rules.message_content import BuildMessageContent
from .tags_line import FindTagsCandidates

# NOTE: _BLANK_LINE_RE / _BODY_START_RE live in .subject_line, which
# imports ParseRef from this module -- so they are imported lazily
# inside _is_ref_stop_line, not at module top (circular import).

_REF_RE = re.compile(
    r"(?P<prefix>^[ \t]*|[ \t]+)"
    r"(?P<label>REFTEL\.?|RETELS?\.?|REF(?:ERENCE)?S?\.?|REF[A-Z]\.?)"
    r"(?=[ \t:;/.,-]|$)(?P<separator>[ \t]*:?[ \t]*)"
    r"(?P<value>(?:(?!\n[ \t]*\n).){0,200})",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)

# Continuation lines with lettered-enumeration shape ("(A) ...", "B. ...",
# "0) ...", "1. ..."). The letter slot is a single letter on purpose:
# two-letter abbreviations ("MR.", "DR.", "NO.", "ST.") are prose, not
# enumerators. Leading dashes are tolerated ("-- 0) ...").
_ENUM_CONT_RE = re.compile(
    r"^[ \t-]*(?:\([A-Z0-9]{1,3}\)|[A-Z][.\):\-]|\d{1,3}[.\):\-])[ \t]+\S"
)

# Reference tokens that mark a continuation as reference content rather
# than body prose: DTG filing-time fragments, MSG/DTG/NOTAL/LTR designators
# and STATION+number runs. Deliberately excluded: REFTEL/SEPTEL (common in
# prose about reftels), bare month dates ("AUGUST 6" is prose as often as
# reference), and short digit runs ("SEPT 11", "(365-1429)" fire on prose).
_REF_TOKEN_RE = re.compile(
    r"\(\s*[A-Z0-9]{1,3}\s*\)"
    r"|\b\d{6}Z\b"
    r"|\b(?:MSG|DTG|NOTAL|LTR)\b"
    r"|\b[A-Z][A-Z./-]{1,14} \d{3,6}\b"
)

# Wrap tails are short by nature (a wrapped fragment, not a new sentence);
# 40 splits the audited sample cleanly (genuine tails max 39, body
# sentences min 42). Used only under an explicit colon header with an
# unterminated block -- never alone as proof of reference shape.
_MAX_WRAP_TAIL = 40

# Lines that end a REF block: a blank line, another header label, a
# section marker, or body-start evidence. The REF value must not swallow
# a following E.O./TAGS/SUBJECT line into the reference string (that both
# corrupts _reference and hides the later header from its own parser).
_REF_STOP_RES = (
    re.compile(r"^(?:E\s*\.?\s*O\s*\.?|EO)\b", re.IGNORECASE),
    re.compile(r"^TAGS?\b", re.IGNORECASE),
    re.compile(r"^SUBJ", re.IGNORECASE),
    re.compile(r"^REFTEL\b|^RETELS?\b|^REF(?:S|ERENCE)?\b|^REF[A-Z]\b", re.IGNORECASE),
    re.compile(
        r"^(?:EXDIS|NODIS|LIMDIS|NOFORN|FOUO|NESCO|STADIS|ONLY|LOU)\b",
        re.IGNORECASE,
    ),
    re.compile(r"^(?:DRAFTED|APPROVED|EPPROVED)\b", re.IGNORECASE),
    re.compile(r"\bSECTION\s+\d+\s+OF\s+\d+\b", re.IGNORECASE),
)


def _is_ref_stop_line(stripped):
    """Return whether a stripped line ends the REF continuation block."""
    from .subject_line import _BODY_START_RE

    if _BODY_START_RE.match(stripped):
        return True
    return any(pattern.match(stripped) for pattern in _REF_STOP_RES)


def _ref_block_end(mc_text, label_line_start, colon_header):
    """Return the end of the REF continuation block (single structural walk).

    Replaces the old 200-character cap. The label line always belongs to
    the block; a following line joins while it is non-blank, is not a
    next-header label, section marker, or body-start evidence, and either
    has lettered-enumeration shape or -- under an explicit colon header
    with an unterminated block -- is a short wrap tail or carries a
    reference token (see _join_continuation). Colon-less ``REFERENCE TO
    ...`` prose keeps the strict enumeration gate, so body sentences
    accepted as candidates by the legacy line-start rule stop at the
    label line instead of absorbing whole paragraphs. The walk returns
    the end of the last kept line (no trailing newline).
    """
    end = label_line_start
    offset = label_line_start
    first = True
    while True:
        line_end = mc_text.find("\n", offset)
        if line_end < 0:
            line_end = len(mc_text)
            last = True
        else:
            last = False
        line = mc_text[offset:line_end]
        stripped = line.strip()
        if first:
            first = False
        elif _is_block_stop(line, stripped, mc_text[label_line_start:end], colon_header):
            break
        elif not _join_continuation(
            line, mc_text[label_line_start:end], colon_header
        ):
            break
        end = line_end
        if last:
            break
        offset = line_end + 1
    return end


def _is_block_stop(line, stripped, block_so_far, colon_header):
    """Return whether a line ends the REF continuation block."""
    if not stripped:
        return True
    if (
        colon_header
        and _NUMBER_FRAGMENT_RE.match(line)
        and _BLOCK_TERMINATOR_RE.search(block_so_far) is None
    ):
        # Wrapped MRN number ("(C) LONDON" / "6071."): not a body-start
        # numbered paragraph, even though it matches the body-start shape.
        return False
    return _is_ref_stop_line(stripped)


# A bare short number line (digits plus optional trailing period/paren):
# the wrapped tail of an MRN, not body prose.
_NUMBER_FRAGMENT_RE = re.compile(r"^\s*\d{1,6}[.)]?\s*$")


def _join_continuation(line, block_so_far, colon_header):
    """Return whether a continuation line joins the REF block."""
    if _ENUM_CONT_RE.match(line):
        return True
    if (
        not colon_header
        or _BLOCK_TERMINATOR_RE.search(block_so_far) is not None
    ):
        return False
    stripped = line.strip()
    # An explicit colon header continues an unterminated block with a
    # short wrap tail ("... COORDINATING" / "COMMISSION TO JONES, NIH/FIC")
    # or a reference-token line (wrapped MRN/DTG/enumeration detail).
    # Full-width body sentences without reference tokens stop the block.
    return len(stripped) < _MAX_WRAP_TAIL or _REF_TOKEN_RE.search(line) is not None


_BLOCK_TERMINATOR_RE = re.compile(r'[.!?]["\']?\s*$')


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
        from ..content_view import get_view

        mc = matches.named("message_content")
        view = get_view(context)
        if not mc or view is None:
            return False

        mc_text = view.text

        candidates = []
        for found in _REF_RE.finditer(mc_text):
            label_start = found.start("label")
            line_start = mc_text.rfind("\n", 0, label_start) + 1
            inline = bool(mc_text[line_start:label_start].strip())
            candidate_end = found.end()
            if inline:
                # Mid-body prose guard: an inline REF (e.g. "REF A,
                # PARA 4") stays a single line, never a block.
                line_end = mc_text.find("\n", label_start)
                if line_end >= 0:
                    candidate_end = min(candidate_end, line_end)
            else:
                colon_header = ":" in found.group("separator")
                candidate_end = _ref_block_end(mc_text, line_start, colon_header)
            tags = ["reference_candidate", "message_content"]
            tags.append("inline_reference" if inline else "legacy_reference")
            bounding = view.clean_to_raw_bounding(found.start(), candidate_end)
            if bounding is None:
                continue
            candidates.append(
                Match(
                    bounding[0],
                    bounding[1],
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
    """Export the header-tagged REF candidate.

    REF text is preserved in the body (keep tag): explicit REF header
    lines are parsed with lettered enumerations until a blank, next
    header, section marker, or body-start evidence. The mid-body prose
    guard holds -- a phrase such as REF A, PARA 4 is not a header.
    """

    priority = 31
    dependency = TagHeaderRef

    def when(self, matches, context):
        from ..content_view import TAG_KEEP, ZONE_CLUSTER, get_view

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
        view = get_view(context)
        if view is not None:
            # REF is a keep field: no strip span is registered.
            pass
        return Match(
            marker.start,
            marker.end,
            value=marker.value,
            name="reference",
            tags=["message_content", ZONE_CLUSTER, TAG_KEEP],
        )

    def then(self, matches, when_response, context):
        matches.append(when_response)
