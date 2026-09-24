"""Strip extracted header fields from message_content.

Runs as the final cleaning step after all extraction is complete.
Gathers only registered clean intervals from final strip-tagged fields
and applies a single merged reverse-order removal to the content view.
Never calls find() on a field value or Match.raw; never removes private
candidates or the bounding span of an aggregate. SUBJECT and REF are
keep fields: a validated kept field protects its exact bytes, and a
strip interval intersecting it logs an invariant failure for review
instead of deleting kept text.
"""

from rebulk import Rule
from rebulk.match import Match
from rebulk.rules import Consequence

from ..content_view import get_field_spans, get_view
from ..rules.message_content import BuildMessageContent

# Final strip-tagged fields removed from the body. SUBJECT and REF are
# keep fields and are never stripped. Aggregate output carriers
# (section_marker, handling_restrictions, distribution) contribute their
# registered per-line intervals, never their bounding Match span.
_STRIP_FIELDS = frozenset(
    {
        "distribution",
        "dtg",
        "from",
        "to",
        "info",
        "drafted_by",
        "approved_by",
        "handling_restrictions",
        "executive_order",
        "tags",
        "section_marker",
        "dash_counters",
    }
)

_KEEP_FIELDS = frozenset({"subject", "reference"})


def _merged_spans(spans):
    """Sort and merge overlapping/adjacent clean intervals."""
    if not spans:
        return []
    ordered = sorted(spans, key=lambda span: span[0])
    merged = [list(ordered[0])]
    for start, end in ordered[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


class StripHeaders(Consequence):
    """Strip registered header intervals from the content view text."""

    def then(self, matches, when_response, context):
        text_end, attr_start, strip_spans, keep_spans = when_response
        mc = matches.named("message_content")
        if not mc:
            return True
        current_value = mc[0].value
        view = get_view(context)
        if view is not None and view.text != current_value:
            # A rule mutated message_content after the view was built;
            # re-anchor on the view text (the positional authority).
            current_value = view.text

        merged_strip = _merged_spans(strip_spans)
        merged_keep = _merged_spans(keep_spans)

        # Overlap precedence: a validated kept field protects its exact
        # bytes. Intersecting strip intervals are clipped (not deleted
        # through the kept range); the invariant failure is logged.
        effective = []
        for strip_start, strip_end in merged_strip:
            cursor = strip_start
            for keep_start, keep_end in merged_keep:
                if keep_end <= cursor or keep_start >= strip_end:
                    continue
                context.setdefault("_invariant_failures", []).append(
                    {
                        "type": "strip_keep_overlap",
                        "strip": [strip_start, strip_end],
                        "keep": [keep_start, keep_end],
                    }
                )
                if keep_start > cursor:
                    effective.append((cursor, keep_start))
                cursor = max(cursor, keep_end)
            if cursor < strip_end:
                effective.append((cursor, strip_end))
        effective = _merged_spans(effective)

        cleaned = current_value
        for start, end in reversed(effective):
            start = max(0, start)
            end = min(len(cleaned), end)
            if start < end:
                cleaned = cleaned[:start] + cleaned[end:]

        for old in matches.named("message_content"):
            if old in matches:
                matches.remove(old)

        matches.append(
            Match(
                text_end,
                attr_start,
                value=cleaned,
                name="message_content",
                tags=["region"],
            )
        )
        return True


class RemoveHeaders(Rule):
    """Remove extracted header fields from message_content.

    Strips distribution, dtg, from, to, info, drafted_by, approved_by,
    section_marker, dash_counters, handling_restrictions, executive_order
    and tags using their registered clean intervals. Reference and
    subject are NOT stripped.
    """

    priority = 16
    dependency = BuildMessageContent
    consequence = StripHeaders()

    def when(self, matches, context):
        from ..content_view import content_region

        region = content_region(matches)
        if region is None:
            return False
        text_end, attr_start = region
        mc = matches.named("message_content")
        if not mc:
            return False

        spans = get_field_spans(context)
        strip_spans = []
        for field in _STRIP_FIELDS:
            strip_spans.extend(spans.get(field, ()))
        if not strip_spans:
            return False

        view = get_view(context)
        view_len = len(view.text) if view is not None else len(mc[0].value)
        validated_strip = [
            (start, end)
            for start, end in strip_spans
            if 0 <= start < end <= view_len
        ]
        if not validated_strip:
            return False

        keep_spans = []
        for field in _KEEP_FIELDS:
            keep_spans.extend(spans.get(field, ()))
        # Keep spans are also recoverable from final keep matches when a
        # rule did not register them (SUBJECT/REF register nothing by
        # design today): project their raw bounds back to clean.
        if view is not None:
            for name in ("subject", "reference"):
                for m in matches.named(name):
                    clean_start = view.raw_to_clean(m.start)
                    clean_end = view.raw_to_clean(m.end - 1)
                    if clean_start is not None and clean_end is not None:
                        keep_spans.append((clean_start, clean_end + 1))

        return text_end, attr_start, validated_strip, keep_spans
