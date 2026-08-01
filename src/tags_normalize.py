#!/usr/bin/env python3
"""TAGS normalizer for ACP-127 messages: resolves raw TAGS tokens against
src/tags_mapping.py and classifies each by type.

Reads per-document NDJSON files (the full extractor output, e.g.
results/<year>.ndjson) and outputs NDJSON, one line per document.

    Usage::

        python3 -m src.tags_normalize <file.ndjson> [...] > output.ndjson

    Output format (one JSON line per document)::

        {"document_number": "75ABIDJAN4622", "document_number_raw": "1975ABIDJAN04622",
         "date": "1975-06-04",
         "tags": [{"code": "ASEC", "type": "permanent", "name": "Security",
                    "sources": ["attr", "body"]}, ...]}

``document_number_raw`` is the un-normalized value straight from the input's
``document_number`` field (pre-``_normalize_doc_number()``), kept so callers
can back-reference the source document even after ``document_number`` has
been rewritten to canonical MRN form.

Two independent sources are read per document -- ``Message Attributes.TAGS``
(the raw attribute string) and ``_tags`` (the raw TAGS line captured from the
message body by src/patterns/tags_line.py) -- classified separately, then
merged into a single deduplicated ``tags`` list keyed by resolved code, with
a ``sources`` field recording which side(s) produced each entry. This keeps
one simple array for consumers while preserving the per-source signal that
docs/tags_coverage.md found informative (a code appearing on only one side
is visible via ``sources`` rather than silently lost).

document_number is produced via src.reftel_normalize._normalize_doc_number
(imported, not reimplemented) so it is join-ready against
*.reftel.norm.ndjson output by the same key.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter

_src_dir = os.path.dirname(os.path.abspath(__file__))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from reftel_normalize import _normalize_doc_number, _parse_document_date
from tags_mapping import classify_subject_tag, lookup_organization_tag, lookup_geographic_tag

# ── Token splitting (paren-aware -- do not split inside "(LASTNAME, FIRST)") ─

def _split_tags(raw: str) -> list[str]:
    """Split a raw TAGS line on commas, without splitting inside parentheses."""
    tokens = []
    current = []
    depth = 0
    for ch in raw:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth = max(0, depth - 1)
            current.append(ch)
        elif ch == "," and depth == 0:
            tokens.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    tokens.append("".join(current).strip())
    return [t for t in tokens if t]


# ── Token classification ─────────────────────────────────────────────────

_NA_VALUES = {"n/a", "na", "none", ""}

_WILDCARD_TYPE_NAMES = {
    "E": "economic",
    "M": "military",
    "P": "political",
    "S": "social",
    "T": "technology",
}

_TAG_TYPES = [
    "permanent", "temporary", "economic", "military", "political", "social",
    "technology", "organization", "geographic", "person", "annotation",
    "unknown", "other",
]


def _classify_person_or_annotation(token: str) -> tuple[str, str]:
    """Classify a parenthetical fragment as a person name or a free-text note.

    Best-effort heuristic, not a guarantee: "(LASTNAME, FIRST[ MIDDLE])" with
    a single-word first part and a digit-free remainder is treated as a
    person name; everything else is a generic annotation. See
    docs/tags_coverage.md for the same "documented vs guessed" honesty
    standard this mirrors.
    """
    inner = token
    if inner.startswith("(") and inner.endswith(")"):
        inner = inner[1:-1]
    else:
        inner = inner.lstrip("(")
    inner = inner.strip()

    parts = inner.split(",", 1)
    if len(parts) == 2:
        last, rest = parts[0].strip(), parts[1].strip()
        if last and " " not in last and not any(c.isdigit() for c in inner):
            return "person", inner
    return "annotation", inner


def _classify_token(token: str) -> tuple[str, str | None]:
    """Classify one already-split TAGS token.

    Returns (type, name); type is one of _TAG_TYPES plus "na" for
    placeholder/empty tokens (never emitted in output, only counted).
    """
    cleaned = token.strip().rstrip(".").strip()

    if not cleaned or cleaned.lower() in _NA_VALUES:
        return "na", None

    if cleaned.startswith("("):
        return _classify_person_or_annotation(cleaned)

    code = cleaned.upper()

    if code.isalpha():
        # Organization TAGS aren't all 4 letters (EEC, OAS, WHO, IMF, ILO,
        # COCOM, ECOSOC, UNESCO, ...), so check the mapping regardless of
        # length before falling back to the length-gated Subject/geographic
        # checks below. ORGANIZATION_TAGS and the Subject TAGS dicts are
        # disjoint (verified when tags_mapping.py was built), so this can't
        # shadow a real Subject TAGS code.
        org_name = lookup_organization_tag(code)
        if org_name:
            return "organization", org_name

        if len(code) == 4:
            status, title = classify_subject_tag(code)
            if status == "permanent":
                return "permanent", title
            if status == "temporary":
                return "temporary", title
            if status == "permanent-wildcard":
                return _WILDCARD_TYPE_NAMES[code[0]], title
            return "unknown", title

    if len(code) == 2:
        # Region TAGS are 2-character *alphanumeric* (e.g. "2M" = Middle
        # East), not pure alpha, so this check is deliberately outside the
        # code.isalpha() branch above. "geographic" is only ever asserted
        # when confirmed against COUNTRY_TAGS/REGION_TAGS (5 FAH-3
        # H-414/H-416) -- an unconfirmed 2-char code (very commonly a
        # pre-1990s legacy code not in the current reference, see
        # tags_mapping.py's module docstring) stays "unknown" rather than
        # being guessed as geographic from shape alone.
        geo_name = lookup_geographic_tag(code)
        if geo_name:
            return "geographic", geo_name
        return "unknown", None

    return "other", None


def _classify_source(raw, source: str, coverage: "CoverageTracker") -> list[tuple[str, str, str | None]]:
    """Split + classify one source's raw TAGS string.

    Returns a deduplicated list of (code, type, name) for this source only
    -- deduplication and cross-source merging happens in _merge_entries.
    """
    if not raw or not isinstance(raw, str):
        return []

    tokens = _split_tags(raw)
    coverage.record_raw_tokens(source, len(tokens))

    seen: dict[str, tuple[str, str, str | None]] = {}
    for tok in tokens:
        ttype, name = _classify_token(tok)
        if ttype == "na":
            coverage.record_na(source)
            continue

        if ttype == "other":
            # Known corpus issue (see docs/tags_coverage.md): some body TAGS
            # lines are missing commas entirely ("PFOR IZ BU" instead of
            # "PFOR, IZ, BU"), so the whole run lands here as one token. If
            # every whitespace-separated piece independently classifies to
            # something recognized, use that split instead of giving up.
            pieces = tok.strip().rstrip(".").strip().split()
            if len(pieces) > 1:
                sub = [_classify_token(p) for p in pieces]
                if all(t not in ("other", "na") for t, _ in sub):
                    coverage.record_whitespace_split(source)
                    for piece, (ptype, pname) in zip(pieces, sub):
                        pcode = pname if ptype in ("person", "annotation") else piece.upper()
                        if pcode not in seen:
                            seen[pcode] = (pcode, ptype, pname)
                    continue

        code = name if ttype in ("person", "annotation") else tok.strip().rstrip(".").strip().upper()
        if code not in seen:
            seen[code] = (code, ttype, name)
    return list(seen.values())


def _merge_entries(
    attr_entries: list[tuple[str, str, str | None]],
    body_entries: list[tuple[str, str, str | None]],
) -> list[dict] | None:
    """Merge attr/body classified entries into one list, tracking sources."""
    merged: dict[str, dict] = {}
    for code, ttype, name in attr_entries:
        merged[code] = {"code": code, "type": ttype, "name": name, "sources": ["attr"]}
    for code, ttype, name in body_entries:
        existing = merged.get(code)
        if existing:
            if "body" not in existing["sources"]:
                existing["sources"].append("body")
        else:
            merged[code] = {"code": code, "type": ttype, "name": name, "sources": ["body"]}
    return list(merged.values()) or None


# ── Coverage Tracking ────────────────────────────────────────────────────

_UNKNOWN_TOP_N = 30


class CoverageTracker:
    def __init__(self):
        self.total_docs = 0
        self.docs_with_attr = 0
        self.docs_with_body = 0
        self.raw_tokens = {"attr": 0, "body": 0}
        self.na_tokens = {"attr": 0, "body": 0}
        self.whitespace_splits = {"attr": 0, "body": 0}
        self.merged_total = 0
        self.named_total = 0
        self.type_counts = Counter()
        self.single_source = 0
        self.unknown_codes = Counter()

    def record_raw_tokens(self, source: str, n: int):
        self.raw_tokens[source] += n

    def record_na(self, source: str):
        self.na_tokens[source] += 1

    def record_whitespace_split(self, source: str):
        self.whitespace_splits[source] += 1

    def record_doc(self, tags_attr, tags_body, merged: list[dict] | None):
        self.total_docs += 1
        if tags_attr:
            self.docs_with_attr += 1
        if tags_body:
            self.docs_with_body += 1
        if not merged:
            return
        for entry in merged:
            self.merged_total += 1
            self.type_counts[entry["type"]] += 1
            if entry["name"] is not None:
                self.named_total += 1
            if len(entry["sources"]) == 1:
                self.single_source += 1
            if entry["type"] == "unknown" and entry["name"] is None:
                self.unknown_codes[entry["code"]] += 1

    def print_report(self, source_files: list[str], output_path: str | None):
        def pct(n, d):
            return (n / d * 100) if d else 0.0

        w = sys.stderr.write
        w("=== TAGS Normalization Coverage ===\n")
        w(f"Source files:            {' '.join(source_files)}\n")
        w(f"Output:                  {output_path or 'stdout'}\n")
        w(f"Total documents:         {self.total_docs:,}\n")
        w(
            f"  with Message Attributes.TAGS: {self.docs_with_attr:,} "
            f"({pct(self.docs_with_attr, self.total_docs):.2f}%)\n"
        )
        w(
            f"  with _tags (body):            {self.docs_with_body:,} "
            f"({pct(self.docs_with_body, self.total_docs):.2f}%)\n"
        )
        w(
            f"Raw tokens -- attr: {self.raw_tokens['attr']:,} "
            f"(na: {self.na_tokens['attr']:,}, whitespace-split recovered: {self.whitespace_splits['attr']:,})   "
            f"body: {self.raw_tokens['body']:,} "
            f"(na: {self.na_tokens['body']:,}, whitespace-split recovered: {self.whitespace_splits['body']:,})\n"
        )
        w(f"Merged (code, doc) entries: {self.merged_total:,}\n")
        w(
            f"  single-source-only:      {self.single_source:,} "
            f"({pct(self.single_source, self.merged_total):.2f}%)\n"
        )

        classified = self.merged_total - self.type_counts["unknown"] - self.type_counts["other"]
        w(
            f"  named rate (has a resolved meaning):        {self.named_total:,} "
            f"({pct(self.named_total, self.merged_total):.2f}%)\n"
        )
        w(
            f"  classified rate (categorized, name may be null): {classified:,} "
            f"({pct(classified, self.merged_total):.2f}%)\n"
        )

        w("Type breakdown:\n")
        for t in _TAG_TYPES:
            c = self.type_counts.get(t, 0)
            w(f"    {t:12s} {c:>10,}  ({pct(c, self.merged_total):5.2f}%)\n")

        if self.unknown_codes:
            top = self.unknown_codes.most_common(_UNKNOWN_TOP_N)
            w(f"\nTop {len(top)} unknown codes by frequency:\n")
            for code, n in top:
                w(f"  {n:>8,}  {code}\n")


# ── Input Handling & Main ────────────────────────────────────────────────

def read_tags(path: str):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            attrs = obj.get("Message Attributes") or {}
            doc_number = attrs.get("Document Number") or ""
            date = attrs.get("Draft Date") or attrs.get("Sent Date") or ""
            tags_attr = attrs.get("TAGS")
            tags_body = obj.get("_tags")
            yield doc_number, date, tags_attr, tags_body


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: python3 -m src.tags_normalize <file.ndjson> [...] > output.ndjson\n")
        sys.exit(1)

    paths = sys.argv[1:]
    if sys.stdout.isatty():
        sys.stderr.write("ERROR: redirect stdout to a file (e.g. ... > output.ndjson)\n")
        sys.exit(1)

    out = sys.stdout
    coverage = CoverageTracker()

    for path in paths:
        sys.stderr.write(f"Processing {path} ...\n")
        for doc_number, doc_date, tags_attr, tags_body in read_tags(path):
            iso_date, _ = _parse_document_date(doc_date)
            doc_number_norm = _normalize_doc_number(doc_number)

            attr_entries = _classify_source(tags_attr, "attr", coverage)
            body_entries = _classify_source(tags_body, "body", coverage)
            merged = _merge_entries(attr_entries, body_entries)

            coverage.record_doc(tags_attr, tags_body, merged)

            result_doc = {
                "document_number": doc_number_norm or doc_number,
                "document_number_raw": doc_number or None,
                "date": iso_date,
                "tags": merged,
            }
            out.write(json.dumps(result_doc, ensure_ascii=False) + "\n")

    coverage.print_report(paths, None)


if __name__ == "__main__":
    main()
