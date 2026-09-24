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

# Continuation lines with lettered-enumeration shape: the only sanctioned
# multi-line reference form ("(A) ...", "A. ...", "B) ...", "1. ...").
_ENUM_CONT_RE = re.compile(r"^[ \t]*(?:\([A-Z0-9]{1,3}\)|[A-Z0-9]{1,3}[.\):\-])[ \t]+")

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


def _ref_block_end(mc_text, label_line_start):
    """Return the end of the REF continuation block (single structural walk).

    Replaces the old 200-character cap: the label line always belongs to
    the block; a following line joins only while it is non-blank, is not
    a next-header label, section marker, or body-start evidence, AND has
    lettered-enumeration shape (``(A)``/``A.``/``B)``/``1.`` ... -- the
    sanctioned multi-line reference form). Plain prose continuations
    (``REFERENCE TO X...`` sentences in body text, which the legacy
    line-start rule accepts as candidates) stop the block at the label
    line instead of absorbing whole paragraphs. The walk returns the end
    of the last kept line (no trailing newline).
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
        elif (
            not stripped
            or _is_ref_stop_line(stripped)
            or not _ENUM_CONT_RE.match(line)
        ):
            break
        end = line_end
        if last:
            break
        offset = line_end + 1
    return end


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
                candidate_end = _ref_block_end(mc_text, line_start)
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
