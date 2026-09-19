"""Byte and document coverage tracking."""

from collections import Counter

from .serializer import is_na_value


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
        "matched_bytes": covered_bytes,
        "ignored_whitespace_bytes": ignored_whitespace_bytes,
        "unmatched_non_whitespace_bytes": unmatched_non_whitespace_bytes,
    }


class CoverageTracker:
    """Tracks byte coverage across documents and document-level match coverage."""

    def __init__(self):
        self.total_documents = 0
        self.matched_documents = 0
        self.total_bytes = 0
        self.matched_bytes = 0
        self.ignored_whitespace_bytes = 0
        self.unmatched_non_whitespace_bytes = 0
        self.fully_covered_documents = 0
        self.incomplete_documents = []
        self.field_counts = Counter()

    def record(self, input_text, matches, source=None, extra_ranges=()):
        self.total_documents += 1

        if matches:
            self.matched_documents += 1

        stats = calculate_coverage(input_text, matches, extra_ranges)
        self.total_bytes += stats["total_bytes"]
        self.matched_bytes += stats["matched_bytes"]
        self.ignored_whitespace_bytes += stats["ignored_whitespace_bytes"]
        unmatched = stats["unmatched_non_whitespace_bytes"]
        self.unmatched_non_whitespace_bytes += unmatched
        if unmatched == 0:
            self.fully_covered_documents += 1
        elif source is not None:
            total = stats["total_bytes"]
            coverage_pct = (stats["matched_bytes"] / total * 100) if total else 0.0
            self.incomplete_documents.append((coverage_pct, unmatched, source))

        seen = set()
        for match in matches:
            if match.private or match.marker:
                continue
            name = match.name
            if name and name not in seen and not is_na_value(name, match.value):
                seen.add(name)
                self.field_counts[name] += 1

    @property
    def byte_coverage(self):
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
