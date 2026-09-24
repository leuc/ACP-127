"""Byte and document coverage tracking.

Definitions (kept stable for comparability with stored reports):

- ``matched_bytes``: raw bytes covered by non-private match/marker spans.
- ``ignored_whitespace_bytes``: unmatched bytes that are whitespace.
- ``covered_bytes``: ``matched_bytes + ignored_whitespace_bytes`` — the
  "accounted for" total. ``byte_coverage_pct`` is ``covered / total``.
  - ``unmatched_non_whitespace_bytes``: ``total - covered``. Only substantive,
  unaccounted text keeps a document below 100%.

The spanning ``message_content`` match (``[text_end, attr_start)``) counts as
covering the whole content region: the body text is the primary extraction
output, so "accounted for" includes it by design. Pre-content strip ranges
(``context["_strip_ranges"]``) are therefore subsumed by that span and are not
added separately. Intentionally removed boilerplate outside the content region
(declass markings, reproduction artifacts) is counted via
``context["_coverage_ranges"]`` (absolute input coordinates).

Aggregate classification/page/section matches (list values spanning first to
last marker) are output carriers only: covering their outer bounds would
claim the gaps between disjoint markers as accounted for. Their
contribution is skipped here; the individual raw spans recorded in
``_coverage_ranges`` by their rules count instead.
"""

import re
import sys
from collections import Counter

from .serializer import is_empty_value, is_na_value

# Aggregate output carriers whose outer bounds must not count as coverage.
_AGGREGATE_NAMES = frozenset(
    {"classification_marker", "page_break", "section_marker"}
)


# Message Attributes supplied by NARA that have a direct counterpart extracted
# independently from the telegram body.  Keep this list deliberately narrow:
# related-but-different fields (for example Sent Date/DTG) are not valid
# extraction-completeness checks.
ATTRIBUTE_BODY_FIELDS = (
    ("Current Classification", "_classification_marker"),
    ("Drafter", "_drafted_by"),
    ("Executive Order", "_executive_order"),
    ("From", "_from"),
    ("Handling Restrictions", "_handling_restrictions"),
    ("Reference", "_reference"),
    ("Subject", "_subject"),
    ("TAGS", "_tags"),
    ("To", "_to"),
)


def _has_value(value):
    """Return whether a serialized field contains a substantive value."""
    return not is_empty_value(value)


# Matches "TEXT ON-LINE" plus NARA spacing variants ("TEXT ONLINE",
# "TEXT ON LINE"). Case-insensitive. MUST stay identical to
# patterns.locator.TEXT_ON_LINE_RE -- extraction eligibility and the
# quality report share this single predicate by value.
TEXT_ON_LINE_RE = re.compile(r"TEXT\s+ON[-\s]*LINE", re.IGNORECASE)


def has_retrievable_body(document):
    """Return whether a serialized document contains retrievable body text."""
    attributes = document.get("Message Attributes") or {}
    locator = attributes.get("Locator")
    return (
        isinstance(locator, str)
        and TEXT_ON_LINE_RE.search(locator) is not None
        and _has_value(document.get("_message_content"))
    )


def missing_body_extractions(document):
    """Return provided attributes whose direct body extraction is absent.

    Only documents whose Locator says ``TEXT ON-LINE`` and whose cleaned body
    is non-empty are eligible.  This excludes records containing an
    unretrievable-text error in place of a telegram body.
    """
    attributes = document.get("Message Attributes") or {}
    if not has_retrievable_body(document):
        return []

    return [
        {
            "attribute": attribute_name,
            "body_field": body_field,
            "provided_value": attributes[attribute_name],
        }
        for attribute_name, body_field in ATTRIBUTE_BODY_FIELDS
        if _has_value(attributes.get(attribute_name))
        and not _has_value(document.get(body_field))
    ]


def is_substantive_match(match):
    """Return whether a match counts as a real extracted field.

    Mirrors ``serializer.result_to_dict`` filtering (skips private, markers and
    child matches with a parent) plus NA normalization, so ``field_counts`` and
    ``matched_documents`` agree with the JSON output instead of counting
    placeholders.
    """
    if match.private or match.marker or match.parent:
        return False
    if not match.name:
        return False
    return not is_na_value(match.name, match.value)


def iter_substantive_matches(matches):
    """Yield ``(name, match)`` once per field name with a substantive value."""
    seen = set()
    for match in matches:
        if not is_substantive_match(match):
            continue
        if match.name in seen:
            continue
        seen.add(match.name)
        yield match.name, match


def count_fields(matches):
    """Return ``{field_name: 1}`` for each substantive field in one document."""
    return {name: 1 for name, _ in iter_substantive_matches(matches)}


def has_substantive_match(matches):
    """Return whether a document has at least one substantive field match."""
    return any(True for _ in iter_substantive_matches(matches))


def calculate_coverage(input_text, matches, extra_ranges=()):
    """Return effective coverage statistics for one input document.

    Structural markers and intentionally removed ranges count as covered.
    Unmatched whitespace is ignored so only substantive, unmatched text keeps
    a document below 100 percent coverage.
    """
    matched_positions = bytearray(len(input_text))

    def cover(start, end):
        start = max(0, start)
        end = min(len(input_text), end)
        if start < end:
            matched_positions[start:end] = b"\1" * (end - start)

    for match in matches:
        if not match.private:
            if match.name in _AGGREGATE_NAMES and isinstance(match.value, list):
                continue
            cover(match.start, match.end)

    for marker in matches.markers:
        if not marker.private:
            cover(marker.start, marker.end)

    for start, end in extra_ranges:
        cover(start, end)

    matched_bytes = sum(matched_positions)
    ignored_whitespace_bytes = sum(
        1
        for position, character in enumerate(input_text)
        if not matched_positions[position] and character.isspace()
    )
    covered_bytes = matched_bytes + ignored_whitespace_bytes
    unmatched_non_whitespace_bytes = len(input_text) - covered_bytes

    return {
        "total_bytes": len(input_text),
        "matched_bytes": matched_bytes,
        "ignored_whitespace_bytes": ignored_whitespace_bytes,
        "covered_bytes": covered_bytes,
        "unmatched_non_whitespace_bytes": unmatched_non_whitespace_bytes,
    }


class CoverageTracker:
    """Tracks byte coverage across documents and document-level match coverage."""

    def __init__(self):
        self.total_documents = 0
        self.matched_documents = 0
        self.total_bytes = 0
        self.matched_bytes = 0
        self.covered_bytes = 0
        self.ignored_whitespace_bytes = 0
        self.unmatched_non_whitespace_bytes = 0
        self.fully_covered_documents = 0
        self.incomplete_documents = []
        self.field_counts = Counter()

    def record(self, input_text, matches, source=None, extra_ranges=()):
        self.total_documents += 1

        if has_substantive_match(matches):
            self.matched_documents += 1

        stats = calculate_coverage(input_text, matches, extra_ranges)
        self.total_bytes += stats["total_bytes"]
        self.matched_bytes += stats["matched_bytes"]
        self.covered_bytes += stats["covered_bytes"]
        self.ignored_whitespace_bytes += stats["ignored_whitespace_bytes"]
        unmatched = stats["unmatched_non_whitespace_bytes"]
        self.unmatched_non_whitespace_bytes += unmatched
        if unmatched == 0:
            self.fully_covered_documents += 1
        elif source is not None:
            total = stats["total_bytes"]
            coverage_pct = (stats["covered_bytes"] / total * 100) if total else 0.0
            self.incomplete_documents.append((coverage_pct, unmatched, source))

        for name in count_fields(matches):
            self.field_counts[name] += 1

    def record_summary(self, coverage):
        """Merge one compact worker coverage summary (no Matches cross IPC).

        The worker computes its own ``calculate_coverage`` /
        ``count_fields`` and returns only JSON plus this small
        serializable dict; the parent merges it here instead of
        duplicating the arithmetic.
        """
        self.total_documents += coverage["total_documents"]
        self.matched_documents += coverage["matched_documents"]
        self.total_bytes += coverage["total_bytes"]
        self.matched_bytes += coverage["matched_bytes"]
        # Old workers emit only "matched_bytes" holding the covered
        # total; new workers emit both keys. Prefer covered_bytes.
        self.covered_bytes += coverage.get(
            "covered_bytes", coverage["matched_bytes"]
        )
        self.ignored_whitespace_bytes += coverage["ignored_whitespace_bytes"]
        self.unmatched_non_whitespace_bytes += coverage[
            "unmatched_non_whitespace_bytes"
        ]
        self.fully_covered_documents += coverage["fully_covered_documents"]
        if coverage["unmatched_non_whitespace_bytes"]:
            total = coverage["total_bytes"]
            covered = coverage.get("covered_bytes", coverage["matched_bytes"])
            coverage_pct = covered / total * 100 if total else 0.0
            self.incomplete_documents.append(
                (
                    coverage_pct,
                    coverage["unmatched_non_whitespace_bytes"],
                    coverage["file"],
                )
            )
        for name, count in coverage["field_counts"].items():
            self.field_counts[name] += count

    # Backwards-compatible alias for the worker-merge entry point.
    merge_stats = record_summary

    @property
    def byte_coverage(self):
        if self.total_bytes == 0:
            return 0.0
        return (self.covered_bytes / self.total_bytes) * 100

    @property
    def matched_byte_pct(self):
        """Raw span coverage without whitespace forgiveness (diagnostic)."""
        if self.total_bytes == 0:
            return 0.0
        return (self.matched_bytes / self.total_bytes) * 100

    @property
    def document_coverage(self):
        if self.total_documents == 0:
            return 0.0
        return (self.matched_documents / self.total_documents) * 100

    def field_rates(self):
        if self.total_documents == 0:
            return {}
        return {
            name: (count / self.total_documents) * 100
            for name, count in self.field_counts.items()
        }

    def summary(self):
        return {
            "documents_processed": self.total_documents,
            "documents_matched": self.matched_documents,
            "document_coverage_pct": round(self.document_coverage, 2),
            "byte_coverage_pct": round(self.byte_coverage, 2),
            "matched_bytes": self.matched_bytes,
            "covered_bytes": self.covered_bytes,
            "whitespace_bytes_ignored": self.ignored_whitespace_bytes,
            "unmatched_non_whitespace_bytes": self.unmatched_non_whitespace_bytes,
            "documents_fully_covered": self.fully_covered_documents,
            "documents_not_fully_covered": (
                self.total_documents - self.fully_covered_documents
            ),
            "field_match_rates": {
                k: round(v, 2) for k, v in self.field_rates().items()
            },
        }

    def print_report(self, stream=None):
        """Write the plaintext coverage summary (extractor stderr format)."""
        stream = sys.stderr if stream is None else stream
        summary = self.summary()
        for key, value in summary.items():
            if key == "field_match_rates":
                stream.write(f"{key}:\n")
                for name, rate in value.items():
                    stream.write(f"    {name}: {rate:.2f}\n")
            else:
                if isinstance(value, float):
                    stream.write(f"{key}: {value:.2f}\n")
                else:
                    stream.write(f"{key}: {value}\n")

        if self.incomplete_documents:
            stream.write("documents_below_100_pct:\n")
            for coverage_pct, unmatched, filepath in sorted(
                self.incomplete_documents, key=lambda entry: (entry[0], entry[2])
            ):
                stream.write(
                    f"    {coverage_pct:.2f}% ({unmatched} unmatched bytes)"
                    f" {filepath}\n"
                )
