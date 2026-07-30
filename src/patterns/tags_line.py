"""Extract the TAGS line from message content as a raw string.

The TAGS line appears in the message body header, after the routing
header (FM/TO/INFO block) and E.O. line, and before SUBJECT. The line is
captured verbatim (whitespace-trimmed) -- no comma-splitting or other
parsing is done here; that is left to downstream consumers (e.g.
src/tags_normalize.py), since splitting on comma alone is lossy (it
breaks parenthetical text like "(SMITH, JACK)" into separate fragments).

The separator between "TAGS" and its value is inconsistent across the
corpus (OCR/transcription noise): besides the well-formed "TAGS:", real
examples include "TAGS " (no punctuation), "TAGS  :" (whitespace before
the colon), "TAGS;", "TAGS/", "TAGS-", "TAGS.", and a single glued OCR
letter standing in for the colon ("TAGSC:", "TAGSS:", "TAGSA:", etc. --
seen with many different letters, so any single uppercase letter
immediately followed by punctuation is accepted).

"TAGS" also appears as an ordinary English word in free-text body prose
("TAGS AND FLAGS...", "TAGS ARE PGOV..."). Rather than denylisting
connector words after "TAGS" (which is both incomplete and conflicts
with genuine OCR artifacts like "TAGS A ORG OCON IAEA", where "A" stands
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
from .subject_line import ParseSubject

_GLUED_LETTER = r"[A-Z](?=[:;/.,-])"

_TAGS_RE = re.compile(
    r"^TAGS(?:" + _GLUED_LETTER + r")?"
    r"\s*[:;/.,-]?\s*"
    r"(?P<value>\S.*)",
    re.MULTILINE | re.IGNORECASE,
)

_NA_VALUES = {"n/a", "na", ""}


def tags_line():
    """Build pattern that matches the TAGS line."""
    rebulk = Rebulk()
    rebulk.rules(ParseTags)
    return rebulk


class ParseTags(Rule):
    """Extract the TAGS line from message content as a raw string.

    Candidates are restricted to the window between the "info" match
    (end) and the "subject" match (start) -- see module docstring. This
    requires ParseInfo and ParseSubject to have already run; ParseInfo
    is a higher-priority rule (32 vs 31) so that is automatic, but
    ParseSubject is the same priority (31), so it is declared as an
    explicit dependency to force rebulk's toposort to order it first
    within that priority tier.

    Some documents declare a placeholder "TAGS: N/A" line immediately
    followed by a second, real TAGS line (a "declare N/A then restate"
    drafting convention seen consistently across the corpus). When the
    first TAGS-shaped line in the window is a bare N/A placeholder and a
    later one in the same window has real content, the later one is used
    instead.
    """

    priority = 31
    dependency = (BuildMessageContent, ParseInfo, ParseSubject)

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

        # ParseInfo's continuation-line collection can run past the actual
        # INFO addressee block when no blank line separates it from the
        # following header lines, inflating info.end past subject.start.
        # Rather than trust an inverted window, fall back to not
        # restricting from below in that case (still bounded above by
        # SUBJECT, which is unaffected).
        if lower_bound >= upper_bound:
            lower_bound = mc_start

        first_m = None
        t_m = None
        for candidate in _TAGS_RE.finditer(mc_text):
            abs_start = mc_start + candidate.start()
            if abs_start < lower_bound or abs_start >= upper_bound:
                continue
            if first_m is None:
                first_m = candidate
            if candidate.group("value").strip().lower() not in _NA_VALUES:
                t_m = candidate
                break

        t_m = t_m or first_m
        if t_m is None:
            return False

        value = t_m.group("value").strip()

        return Match(
            mc_start + t_m.start(),
            mc_start + t_m.end(),
            value=value,
            name="tags",
            tags=["message_content"],
        )

    def then(self, matches, when_response, context):
        matches.append(when_response)
