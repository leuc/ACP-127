"""Extract the TAGS line from message content as a raw string.

The TAGS line appears in the message body header, after the routing
header (FM/TO/INFO block) and E.O. line, and before SUBJECT. The line is
captured verbatim (whitespace-trimmed) -- no comma-splitting or other
parsing is done here; that is left to downstream consumers (e.g.
src/tags_normalize.py), since splitting on comma alone is lossy (it
breaks parenthetical text like "(SMITH, JACK)" into separate fragments).

The separator between "TAGS" and its value is inconsistent across the
corpus because of NARA reproduction/spacing artifacts. Besides the
well-formed "TAGS:", real
examples include "TAGS " (no punctuation), "TAGS  :" (whitespace before
the colon), "TAGS;", "TAGS/", "TAGS-", "TAGS.", and a single glued
reproduction-artifact letter before the colon ("TAGSC:", "TAGSS:",
"TAGSA:", etc. --
seen with many different letters, so any single uppercase letter
immediately followed by punctuation is accepted).

"TAGS" also appears as an ordinary English word in free-text body prose
("TAGS AND FLAGS...", "TAGS ARE PGOV..."). Rather than denylisting
connector words after "TAGS" (which is both incomplete and conflicts
with genuine reproduction artifacts like "TAGS A ORG OCON IAEA", where
"A" stands
in for a missing colon), candidates are filtered *positionally*, using
the "info" and "subject" matches already produced by ParseInfo and
ParseSubject (declared as dependencies below, so they are guaranteed to
have run first): a real TAGS line only ever appears after the INFO
routing block and before SUBJECT. No text is re-parsed here to find
those boundaries -- their positions are read directly off the existing
matches. Body prose is excluded structurally, since it only ever occurs
after SUBJECT.

Output field:
  _tags -- raw tag line text (string)
"""

from rebulk import Rebulk, Rule
from rebulk.match import Match
from rebulk.remodule import re

from ..rules.message_content import BuildMessageContent
from .info_line import ParseInfo

_GLUED_LETTER = r"[A-Z](?=[:;/.,-])"

_TAGS_RE = re.compile(
    r"^[ \t]*(?:TAGS|TAGA|TAG(?![SA]))(?:" + _GLUED_LETTER + r")?"
    r"[ \t]*[:;/.,-]?[ \t]*"
    r"(?P<value>\S.*)",
    re.MULTILINE | re.IGNORECASE,
)

_NA_VALUES = {"n/a", "na", ""}


def tags_line():
    """Build pattern that matches the TAGS line."""
    rebulk = Rebulk()
    rebulk.rules(FindTagsCandidates, ParseTags)
    return rebulk


class FindTagsCandidates(Rule):
    """Create private TAGS candidates in cleaned-content coordinates."""

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
        for found in _TAGS_RE.finditer(mc_text):
            bounding = view.clean_to_raw_bounding(found.start(), found.end())
            if bounding is None:
                continue
            candidates.append(
                Match(
                    bounding[0],
                    bounding[1],
                    value={
                        "clean_start": found.start(),
                        "clean_end": found.end(),
                        "value_clean_start": found.start("value"),
                    },
                    name="tags_marker",
                    tags=["tags_candidate", "message_content"],
                    private=True,
                )
            )
        return candidates or False

    def then(self, matches, when_response, context):
        for candidate in when_response:
            matches.append(candidate)


class ParseTags(Rule):
    """Extract the TAGS line from message content as a raw string.

    Candidates are restricted to the header position established by existing
    matches: either between INFO and SUBJECT, or inside a message-content
    tagged TO/INFO match whose continuation has swallowed later header lines.
    This requires ParseInfo and ParseSubject to have already run; ParseInfo is
    a higher-priority rule (32 vs 31) so that is automatic, but ParseSubject is
    the same priority (31), so it is declared as an explicit dependency to
    force rebulk's toposort to order it first within that priority tier.

    Some documents declare a placeholder "TAGS: N/A" line immediately
    followed by a second, real TAGS line (a "declare N/A then restate"
    drafting convention seen consistently across the corpus). When the
    first TAGS-shaped line in the window is a bare N/A placeholder and a
    later one in the same window has real content, the later one is used
    instead.
    """

    priority = 31
    # Needs ParseSubject's upper bound; the full triple is set once in
    # builder.py (avoids a circular import here -- subject_line imports
    # FindTagsCandidates from this module).
    dependency = (FindTagsCandidates, ParseInfo)

    def when(self, matches, context):
        from ..content_view import (
            TAG_HEADER,
            TAG_STRIP,
            ZONE_CLUSTER,
            get_view,
            register_field_span,
        )

        mc = matches.named("message_content")
        view = get_view(context)
        if not mc or view is None:
            return False

        mc_text = view.text

        info_matches = list(matches.named("info"))
        if info_matches:
            info_ends = []
            for m in info_matches:
                clean = view.raw_to_clean(m.end - 1)
                if clean is not None:
                    info_ends.append(clean + 1)
            lower_bound = max(info_ends) if info_ends else 0
        else:
            lower_bound = 0

        subject_matches = list(matches.named("subject"))
        if subject_matches:
            subject_starts = []
            for m in subject_matches:
                clean = view.raw_to_clean(m.start)
                if clean is not None:
                    subject_starts.append(clean)
            upper_bound = min(subject_starts) if subject_starts else len(mc_text)
        else:
            upper_bound = len(mc_text)
        inline_boundaries = []
        for name in ("subject", "reference"):
            for match in matches.named(name):
                clean = view.raw_to_clean(match.start)
                if clean is not None:
                    inline_boundaries.append(clean)

        # Clean intervals of routing matches for the inside-routing check.
        routing_intervals = []
        for match in matches.tagged("message_content"):
            if match.name in {"to", "info"}:
                clean_start = view.raw_to_clean(match.start)
                clean_end = view.raw_to_clean(match.end - 1)
                if clean_start is not None and clean_end is not None:
                    routing_intervals.append((clean_start, clean_end + 1))

        # ParseInfo's continuation-line collection can run past the actual
        # INFO addressee block when no blank line separates it from the
        # following header lines, inflating info.end past subject.start.
        # An inverted window is a diagnostic, not a reason to reset the
        # lower bound to the beginning of the body: fall back to the end
        # of the joint routing window (the structurally exact FM-block
        # end) instead.
        if lower_bound >= upper_bound:
            from .routing import walk_routing as _walk

            walked = _walk(mc_text)
            lower_bound = walked["header_end"] if walked is not None else 0
            if lower_bound >= upper_bound:
                context.setdefault("_diagnostics", []).append(
                    {
                        "field": "tags",
                        "type": "inverted_window",
                        "lower_bound": lower_bound,
                        "upper_bound": upper_bound,
                    }
                )
                return False

        first_m = None
        first_value = None
        first_end = None
        t_m = None
        t_value = None
        t_end = None
        candidates = sorted(
            matches.tagged("tags_candidate"), key=lambda match: match.start
        )
        for candidate in candidates:
            value = candidate.value
            if isinstance(value, dict) and "clean_start" in value:
                clean_start = value["clean_start"]
                clean_end = value["clean_end"]
                value_clean_start = value["value_clean_start"]
            else:
                # Legacy candidate without clean offsets: project endpoints.
                clean_start = view.raw_to_clean(candidate.start)
                clean_end = (
                    view.raw_to_clean(candidate.end - 1) + 1
                    if view.raw_to_clean(candidate.end - 1) is not None
                    else None
                )
                value_clean_start = None
                if clean_start is None or clean_end is None:
                    continue
            abs_start = clean_start
            inside_routing = any(
                start <= abs_start < end for start, end in routing_intervals
            )
            in_header_window = lower_bound <= abs_start < upper_bound
            if not (inside_routing or in_header_window):
                continue
            if abs_start >= upper_bound:
                continue

            candidate_boundaries = [
                boundary
                for boundary in inline_boundaries
                if clean_start < boundary < clean_end
            ]
            clean_candidate_end = min(
                clean_end,
                upper_bound,
                *candidate_boundaries,
            )
            if value_clean_start is None:
                continue
            if clean_candidate_end <= value_clean_start:
                continue
            candidate_value = mc_text[
                value_clean_start:clean_candidate_end
            ].strip()
            # Reject bare punctuation, zero-token values and values
            # beginning with another header label.
            if not candidate_value:
                continue
            if not any(ch.isalnum() for ch in candidate_value):
                continue
            if first_m is None:
                first_m = candidate
                first_value = candidate_value
                first_end = clean_candidate_end
            if candidate_value.lower() not in _NA_VALUES:
                t_m = candidate
                t_value = candidate_value
                t_end = clean_candidate_end
                break

        t_m = t_m or first_m
        if t_m is None:
            return False

        value = t_value if t_value is not None else first_value
        clean_match_end = t_end if t_end is not None else first_end
        t_clean = (
            t_m.value["clean_start"]
            if isinstance(t_m.value, dict) and "clean_start" in t_m.value
            else None
        )
        if t_clean is None:
            t_clean = view.raw_to_clean(t_m.start)
            if t_clean is None:
                return False
        bounding = view.clean_to_raw_bounding(t_clean, clean_match_end)
        if bounding is None:
            return False
        register_field_span(context, "tags", t_clean, clean_match_end)
        return Match(
            bounding[0],
            bounding[1],
            value=value,
            name="tags",
            tags=["message_content", ZONE_CLUSTER, TAG_STRIP, TAG_HEADER],
        )

    def then(self, matches, when_response, context):
        matches.append(when_response)
