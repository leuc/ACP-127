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
    r"^TAGS(?:" + _GLUED_LETTER + r")?"
    r"[ \t]*[:;/.,-]?[ \t]*"
    r"(?P<value>\S.*)",
    re.MULTILINE | re.IGNORECASE,
)

_NA_VALUES = {"n/a", "na", ""}


def tags_line():
    """Build pattern that matches the TAGS line."""
    from .subject_line import ParseSubject

    ParseTags.dependency = (FindTagsCandidates, ParseInfo, ParseSubject)
    rebulk = Rebulk()
    rebulk.rules(FindTagsCandidates, ParseTags)
    return rebulk


class FindTagsCandidates(Rule):
    """Create private TAGS candidates in cleaned-content coordinates."""

    priority = 31
    dependency = BuildMessageContent

    def when(self, matches, context):
        mc = matches.named("message_content")
        if not mc:
            return False

        mc_text = mc[0].value
        mc_start = mc[0].start
        candidates = []
        for found in _TAGS_RE.finditer(mc_text):
            candidates.append(
                Match(
                    mc_start + found.start(),
                    mc_start + found.end(),
                    value={
                        "value_start": mc_start + found.start("value"),
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
    dependency = (FindTagsCandidates, ParseInfo)

    def when(self, matches, context):
        mc = matches.named("message_content")
        if not mc:
            return False

        mc_text = mc[0].value
        mc_start = mc[0].start
        mc_end = mc_start + len(mc_text)

        info_matches = matches.named("info")
        lower_bound = max((m.end for m in info_matches), default=mc_start)

        subject_matches = matches.named("subject")
        upper_bound = min((m.start for m in subject_matches), default=mc_end)
        inline_boundaries = [
            match.start
            for name in ("subject", "reference")
            for match in matches.named(name)
        ]

        routing_matches = [
            match
            for match in matches.tagged("message_content")
            if match.name in {"to", "info"}
        ]

        # ParseInfo's continuation-line collection can run past the actual
        # INFO addressee block when no blank line separates it from the
        # following header lines, inflating info.end past subject.start.
        # Rather than trust an inverted window, fall back to not
        # restricting from below in that case (still bounded above by
        # SUBJECT, which is unaffected).
        if lower_bound >= upper_bound:
            lower_bound = mc_start

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
            abs_start = candidate.start
            inside_routing = any(
                routing.start <= abs_start < routing.end
                for routing in routing_matches
            )
            in_header_window = lower_bound <= abs_start < upper_bound
            if not (inside_routing or in_header_window):
                continue
            if abs_start >= upper_bound:
                continue

            candidate_boundaries = [
                boundary
                for boundary in inline_boundaries
                if candidate.start < boundary < candidate.end
            ]
            candidate_end = min(
                candidate.end,
                upper_bound,
                *candidate_boundaries,
            )
            value_start = candidate.value["value_start"]
            if candidate_end <= value_start:
                continue
            candidate_value = mc_text[
                value_start - mc_start : candidate_end - mc_start
            ].strip()
            if candidate_end < candidate.end:
                candidate_value = candidate_value.rstrip(" ,:;/.-\t")
            if not candidate_value:
                continue
            if first_m is None:
                first_m = candidate
                first_value = candidate_value
                first_end = candidate_end
            if candidate_value.lower() not in _NA_VALUES:
                t_m = candidate
                t_value = candidate_value
                t_end = candidate_end
                break

        t_m = t_m or first_m
        if t_m is None:
            return False

        value = t_value if t_value is not None else first_value
        match_end = t_end if t_end is not None else first_end

        return Match(
            t_m.start,
            match_end,
            value=value,
            name="tags",
            tags=["message_content"],
        )

    def then(self, matches, when_response, context):
        matches.append(when_response)
