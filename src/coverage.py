"""Byte and document coverage tracking."""

from collections import Counter


class CoverageTracker:
    """Tracks byte coverage across documents and document-level match coverage."""

    def __init__(self):
        self.total_documents = 0
        self.matched_documents = 0
        self.total_bytes = 0
        self.matched_bytes = 0
        self.field_counts = Counter()

    def record(self, input_text, matches):
        self.total_documents += 1
        self.total_bytes += len(input_text)

        if matches:
            self.matched_documents += 1

        matched_positions = bytearray(len(input_text))
        for match in matches:
            if not match.private and not match.marker:
                for pos in range(match.start, match.end):
                    matched_positions[pos] = 1

        self.matched_bytes += sum(matched_positions)

        seen = set()
        for match in matches:
            if match.private or match.marker:
                continue
            name = match.name
            if name and name not in seen:
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
            "field_match_rates": {
                k: round(v, 2) for k, v in self.field_rates().items()
            },
        }
