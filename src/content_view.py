"""Raw-to-clean content view and exact interval registry.

The central coordinate fix for the extraction pipeline (see
docs/EXTRACTION_IMPLEMENTATION_PLAN.md section 3.1).

Problem: ``BuildMessageContent`` strips pre-content ranges from the raw
input and stores the resulting string in one ``message_content`` match
whose ``start``/``end`` still cover the full original region. Later
rules parsed the cleaned string but built ``Match`` objects as
``mc_start(raw) + cleaned_offset`` -- phantom positions that are not
original source positions once any earlier strip occurred.

This module holds the monotone, invertible map between the two
coordinate systems:

* ``text``: cleaned content string after pre-content strips;
* ``raw_start``/``raw_end``: validated Message Text / Message Attributes bounds;
* ``retained``: ordered, non-overlapping ``(clean_start, clean_end,
  raw_start, raw_end)`` tuples with equal clean/raw lengths;
* conversion helpers for a raw position and a cleaned half-open interval.

No characters are ever added to the view; strips only remove. The map is
per document, internal, and never serialized.
"""

import bisect


class ContentView:
    """Monotone map between cleaned content offsets and raw input offsets."""

    def __init__(self, text, raw_start, retained):
        self.text = text
        self.raw_start = raw_start
        self.retained = list(retained)
        if self.retained:
            self.raw_end = self.retained[-1][3]
        else:
            self.raw_end = raw_start
        self._clean_starts = [segment[0] for segment in self.retained]
        self._raw_starts = [segment[2] for segment in self.retained]

    @classmethod
    def build(cls, raw_region, raw_start, strip_ranges):
        """Construct a view by applying merged raw-relative strip intervals.

        ``raw_region`` is ``input[text_end:attr_start]``; ``strip_ranges``
        are ``(start, end)`` half-open intervals in ``raw_region``
        coordinates. Returns ``(view, merged)`` where ``merged`` is the
        sorted, merged strip list (for audit/shadow logging).
        """
        merged = _merge_ranges(strip_ranges)
        pieces = []
        retained = []
        cursor = 0
        clean_cursor = 0
        for start, end in merged:
            if start < cursor:
                start = cursor
            if start >= end:
                continue
            if start > cursor:
                chunk = raw_region[cursor:start]
                pieces.append(chunk)
                retained.append(
                    (clean_cursor, clean_cursor + len(chunk),
                     raw_start + cursor, raw_start + start)
                )
                clean_cursor += len(chunk)
            cursor = max(cursor, end)
        if cursor < len(raw_region):
            chunk = raw_region[cursor:]
            pieces.append(chunk)
            retained.append(
                (clean_cursor, clean_cursor + len(chunk),
                 raw_start + cursor, raw_start + len(raw_region))
            )
        return cls("".join(pieces), raw_start, retained), merged

    def __len__(self):
        return len(self.text)

    def clean_to_raw(self, start, end):
        """Map a cleaned half-open interval to exact retained raw segments.

        Returns a list of ``(raw_start, raw_end)`` tuples covering exactly
        the retained source bytes for ``[start, end)``. Returns ``None``
        when the interval touches removed content or lies outside the view
        (a raw match crossing a removed span must be rejected for
        cleaned-body stripping, never widened to a bounding range).
        """
        if start < 0 or end > len(self.text) or start >= end:
            return None
        segments = []
        idx = bisect.bisect_right(self._clean_starts, start) - 1
        if idx < 0:
            idx = 0
        while idx < len(self.retained):
            clean_start, clean_end, raw_seg_start, _raw_seg_end = self.retained[idx]
            if clean_start >= end:
                break
            if clean_end <= start:
                idx += 1
                continue
            # The interval must be fully inside retained text; any part
            # overlapping a removed gap fails the projection.
            overlap_start = max(start, clean_start)
            overlap_end = min(end, clean_end)
            if overlap_start < overlap_end:
                segments.append(
                    (raw_seg_start + (overlap_start - clean_start),
                     raw_seg_start + (overlap_end - clean_start))
                )
            idx += 1
        if not segments:
            return None
        # Verify contiguity in clean space: total mapped length must equal
        # the requested length, otherwise a removed gap was crossed.
        mapped_len = sum(end_ - start_ for start_, end_ in segments)
        if mapped_len != end - start:
            return None
        return segments

    def clean_to_raw_bounding(self, start, end):
        """Return the bounding raw ``(start, end)`` for a clean interval.

        Used only for ``Match`` object placement (rebulk queries, JSON
        output carriers). Stripping must use :meth:`clean_to_raw` segments,
        never this bounding range.
        """
        segments = self.clean_to_raw(start, end)
        if not segments:
            return None
        return (segments[0][0], segments[-1][1])

    def raw_to_clean(self, raw_pos):
        """Map a raw input position to a cleaned offset, or ``None`` if removed."""
        idx = bisect.bisect_right(self._raw_starts, raw_pos) - 1
        if idx < 0:
            return None
        clean_start, clean_end, raw_seg_start, raw_seg_end = self.retained[idx]
        if raw_seg_start <= raw_pos < raw_seg_end:
            return clean_start + (raw_pos - raw_seg_start)
        return None


def _merge_ranges(ranges):
    """Sort and merge overlapping/adjacent ranges."""
    if not ranges:
        return []
    sorted_ranges = sorted(ranges, key=lambda r: r[0])
    merged = [list(sorted_ranges[0])]
    for start, end in sorted_ranges[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(s, e) for s, e in merged]


def get_view(context):
    """Return the per-document :class:`ContentView`, or ``None``."""
    return context.get("_content_view")


def get_field_spans(context):
    """Return the mutable ``{field_name: [clean (start, end), ...]}`` registry."""
    return context.setdefault("_field_spans", {})


def register_field_span(context, field_name, clean_start, clean_end):
    """Register one exact cleaned-view interval for a strip-tagged field.

    Intervals are in :class:`ContentView` coordinates. Aggregated fields
    (section markers, handling restrictions, repeated distribution) register
    one interval per actual header line/block -- never the bounding span of
    an aggregate ``Match``. Validation (bounds, ordering) happens in
    ``RemoveHeaders``; here we only append.
    """
    if clean_start < 0 or clean_end <= clean_start:
        return False
    view = get_view(context)
    if view is not None and clean_end > len(view.text):
        return False
    spans = get_field_spans(context)
    spans.setdefault(field_name, []).append((clean_start, clean_end))
    return True


def content_region(matches):
    """Return ``(text_end, attr_start)`` or ``None`` when markers are ambiguous."""
    text_ms = matches.markers.named("message_text_marker")
    attr_ms = matches.markers.named("message_attributes_marker")
    if len(text_ms) != 1 or len(attr_ms) != 1:
        return None
    text_end, attr_start = text_ms[0].end, attr_ms[0].start
    if attr_start <= text_end:
        return None
    return text_end, attr_start


# Stable tag vocabulary for final body fields (section 3.2). The strip
# tag selects *which* fields to remove; the registered clean intervals
# determine *where*. ``KNOWN_TAGS`` backs a vocabulary test that fails
# on unknown tags.
ZONE_PRE = "zone:pre"
ZONE_ROUTING = "zone:routing"
ZONE_CLUSTER = "zone:cluster"
TAG_STRIP = "strip"
TAG_KEEP = "keep"
TAG_HEADER = "header"

KNOWN_TAGS = frozenset(
    {
        # new stable roles
        ZONE_PRE,
        ZONE_ROUTING,
        ZONE_CLUSTER,
        TAG_STRIP,
        TAG_KEEP,
        TAG_HEADER,
        # pre-existing tags kept during migration
        "message_content",
        "region",
        "section",
        "root",
        "attribute",
        "classification",
        "marking",
        "page_break",
        "end_marker",
        "content_footer",
        "dash_counter",
        "reproduction_artifact",
        "handling_restriction_candidate",
        "executive_order_candidate",
        "fallback_executive_order",
        "legacy_executive_order",
        "tags_candidate",
        "subject_candidate",
        "reference_candidate",
        "inline_subject",
        "punctuated_subject",
        "legacy_subject",
        "inline_reference",
        "legacy_reference",
        "header",
        "text-online",
    }
    | {f"subject_distance_{n}" for n in range(6)}
)


def field_tags(zone, strip_or_keep):
    """Return the tag list for a final body field.

    Keeps the legacy ``message_content`` tag during migration so old
    name-set selectors still agree while new tag selectors are compared
    on fixtures.
    """
    tags = ["message_content", zone, strip_or_keep]
    if strip_or_keep == TAG_STRIP:
        tags.append(TAG_HEADER)
    return tags


def make_field_match(context, field_name, clean_start, clean_end, value, tags):
    """Build a ``Match`` for a cleaned-view interval, registering its span.

    Projects ``[clean_start, clean_end)`` through the document's
    :class:`ContentView` to exact raw source positions. Returns ``None``
    (and registers nothing) when the interval crosses removed content --
    a failed projection is an extraction diagnostic, never a reason to
    delete an identical string elsewhere. On success the exact clean
    interval is registered via :func:`register_field_span` and the
    ``Match`` carries the bounding raw span as its placement.
    """
    from rebulk.match import Match

    view = get_view(context)
    if view is None:
        return None
    if clean_start < 0 or clean_end <= clean_start or clean_end > len(view.text):
        return None
    bounding = view.clean_to_raw_bounding(clean_start, clean_end)
    if bounding is None:
        return None
    register_field_span(context, field_name, clean_start, clean_end)
    return Match(bounding[0], bounding[1], value=value, name=field_name, tags=list(tags))


def scope_raw_matches(matches, context, names):
    """Project raw pattern matches into cleaned-view spans.

    For raw-coordinate patterns (dash, DTG, FM, section) whose matches
    live in original input coordinates: keep only matches inside the
    validated content region and return ``[(match, clean_start,
    clean_end)]`` for those fully inside retained text. Matches crossing
    removed spans are rejected (returned in the second list as
    diagnostics).
    """
    view = get_view(context)
    region = content_region(matches)
    if view is None or region is None:
        return [], []
    _text_end, _attr_start = region
    ok, rejected = [], []
    for name in names:
        for match in matches.named(name):
            if not (_text_end <= match.start < _attr_start):
                continue
            clean_start = view.raw_to_clean(match.start)
            clean_end = view.raw_to_clean(match.end - 1)
            if clean_start is None or clean_end is None:
                rejected.append(match)
                continue
            # Verify the whole raw span maps without gaps.
            segments = view.clean_to_raw(clean_start, clean_end + 1)
            if segments != [(match.start, match.end)]:
                # Tolerate only exact retained mapping; otherwise reject
                # for cleaned-body stripping (match itself is untouched).
                rejected.append(match)
                continue
            ok.append((match, clean_start, clean_end + 1))
    return ok, rejected
