#!/usr/bin/env python3
"""MRN normalizer for ACP-127 reference data using rebulk functional pattern.

Reads ``results/197?.reftel.ndjson`` files, normalizes each reference
string into canonical MRN format using a single rebulk functional pattern
with O(1) dict-lookup station matching, and outputs NDJSON.

    Usage::

        python3 -m src.reftel_normalize [results/197?.reftel.ndjson ...] > all-mrns.ndjson

Output format (one JSON line per document)::

    {"document_number": "1973AMMAN03057", "date": "07 JUN 1973",
     "extracted_references": ["73STATE93410"]}
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime

from rebulk import Rebulk

_src_dir = os.path.dirname(os.path.abspath(__file__))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from station_data import STATIONS, _VARIANT_TO_TARGET

# ── Pre-processing constants ────────────────────────────────────────────────

_PREFIX_STRIP = re.compile(
    r"^(?:REF(?:ERENCE)?S?\s*:|REF\s*:|REFTEL:|RETELS?\s*:)\s*", re.I
)
_LETTER_PREFIX = re.compile(r"^\s*(?:\(\s*[A-Z]\s*\)\s*|[A-Z]\.\s*|[A-Z]\)\s*)+")
_NOTAL_CLEAN = re.compile(r"\s*\(?\s*NOTAL\b\s*\)?\s*", re.I)
_UNCLAS = re.compile(r"\bUNCLAS\s+", re.I)
_POSSESSIVE = re.compile(r"\b' S\s+")
_AIRGRAM_STRIP = re.compile(r"\bAIRGRAM\s+", re.I)
_NA_RE = re.compile(r"^(?:\s*n/a\s*|\s*N/A\s*|\s*none\s*)$", re.I)
_4DIGIT_YEAR = re.compile(r"\b(?P<y>\d{4})(?P<rest>[A-Z])")
_RETENTION_STRIP = re.compile(r"\n\s*Retention:\s*\d+\s*$")
_DATE_FORMATS = [
    "%d %b %Y",
    "%d-%b-%Y %I:%M:%S %p",
    "%d-%b-%Y",
]

_TOP_FAILED = 500

# ── Station lookup (O(1), no regex alternation) ────────────────────────────

_STATIONS: dict[str, str] = {}
for canon in STATIONS:
    _STATIONS[canon.upper()] = canon
for variant, canon in _VARIANT_TO_TARGET.items():
    _STATIONS[variant.upper()] = canon

_STOP_STATIONS = frozenset(
    s.upper()
    for s in [
        "DATED",
        "DATE",
        "NUMBER",
        "NBR",
        "REFERENCE",
        "REF",
        "REFTEL",
        "PAGE",
        "PAGES",
        "SECTION",
        "CLASSIFIED",
        "UNCLASSIFIED",
        "SECRET",
        "CONFIDENTIAL",
        "SENSITIVE",
        "NOTAL",
        "EXDIS",
        "NODIS",
        "STADIS",
        "PART",
        "SECT",
        "ITEM",
        "NOTE",
        "JANUARY",
        "FEBRUARY",
        "MARCH",
        "APRIL",
        "MAY",
        "JUNE",
        "JULY",
        "AUGUST",
        "SEPTEMBER",
        "OCTOBER",
        "NOVEMBER",
        "DECEMBER",
        "JAN",
        "FEB",
        "MAR",
        "APR",
        "JUN",
        "JUL",
        "AUG",
        "SEP",
        "OCT",
        "NOV",
        "DEC",
        "MONDAY",
        "TUESDAY",
        "WEDNESDAY",
        "THURSDAY",
        "FRIDAY",
        "SATURDAY",
        "SUNDAY",
    ]
)

# ── Utility functions ──────────────────────────────────────────────────────


def _clean_year(y: str) -> str:
    return y[-2:]


def _extract_year_from_date(date_str: str) -> str:
    text = date_str.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime("%y")
        except ValueError:
            continue
    return ""


def _clean_number(n: str) -> str:
    n = n.lstrip("0")
    return n if n else "0"


def _format_canonical(year: str, station: str, number: str, is_airgram: bool) -> str:
    if is_airgram:
        return f"{year}{station}-A{number}"
    return f"{year}{station}{number}"


def _preprocess(ref: str) -> str | None:
    if not ref:
        return None
    text = ref.strip()
    if not text:
        return None
    if _NA_RE.match(text):
        return None
    text = _PREFIX_STRIP.sub("", text).strip()
    text = _NOTAL_CLEAN.sub("", text).strip()
    text = _UNCLAS.sub("", text).strip()
    text = _LETTER_PREFIX.sub("", text).strip()
    text = _POSSESSIVE.sub(" ", text)
    text = _AIRGRAM_STRIP.sub("", text).strip()
    text = _4DIGIT_YEAR.sub(lambda m: m.group("y")[2:] + m.group("rest"), text)
    return text.strip() or None


def _preprocess_attr(attr_ref: str) -> str | None:
    """Preprocess an attr_reference string (single ref, no splitting)."""
    if not attr_ref:
        return None
    text = attr_ref.strip()
    if not text:
        return None
    if _NA_RE.match(text):
        return None
    text = _RETENTION_STRIP.sub("", text)
    text = text.strip()
    if not text:
        return None
    return _preprocess(text)


# ── MRN parsing (no regex station matching) ────────────────────────────────


def _parse_single_ref(text: str, doc_year: str) -> tuple[str, bool] | None:
    """Parse a cleaned reference string into (mrn, is_airgram)."""
    tlen = len(text)
    if tlen < 4:
        return None

    year = ""
    idx = 0
    if tlen >= 2 and text[0:2].isdigit():
        if tlen == 2 or not text[2].isdigit():
            year = text[0:2]
            idx = 2
            while idx < tlen and text[idx] in " \t":
                idx += 1

    if not year:
        year = doc_year

    num_end = tlen
    while num_end > 0 and not text[num_end - 1].isdigit():
        num_end -= 1
    if num_end == 0:
        return None
    num_start = num_end
    while (
        num_start > 0 and text[num_start - 1].isdigit() and (num_end - num_start) < 10
    ):
        num_start -= 1
    if num_end - num_start < 1:
        return None

    raw_number = text[num_start:num_end]

    is_airgram = False
    station_end = num_start
    if station_end >= 2 and text[station_end - 1] == "-":
        station_end -= 1
        if station_end >= 1 and text[station_end - 1].upper() == "A":
            station_end -= 1
            is_airgram = True
    elif station_end >= 1 and text[station_end - 1].upper() == "A":
        if station_end >= 2 and text[station_end - 2] in " \t":
            station_end -= 1
            is_airgram = True

    raw_station = text[idx:station_end].strip()
    while raw_station and not raw_station[-1].isalpha():
        raw_station = raw_station[:-1]
    if not raw_station or len(raw_station) < 3:
        return None
    if not all(c.isalpha() or c in " \t" for c in raw_station):
        return None

    raw_station_upper = raw_station.upper()

    if raw_station_upper in _STOP_STATIONS:
        return None

    canonical = _STATIONS.get(raw_station_upper)
    if canonical is None:
        return None

    number = _clean_number(raw_number)
    mrn = _format_canonical(year, canonical, number, is_airgram)
    return (mrn, is_airgram)


# ── Rebulk functional pattern ──────────────────────────────────────────────


def _batch_match(input_string: str, context: dict) -> list[dict] | None:
    """Rebulk functional pattern: extract MRNs from batched ref strings.

    Each line in the batch has format::

        doc_idx<tab>doc_year<tab>single_ref_text

    Each line represents exactly one pre-split reference.
    """
    results = []
    for raw_line in input_string.split("\n"):
        stripped = raw_line.strip()
        if not stripped:
            continue
        parts = stripped.split("\t", 2)
        if len(parts) < 3:
            continue
        doc_idx, doc_year, text = parts[0], parts[1], parts[2]

        text = _NOTAL_CLEAN.sub("", text).strip()
        if not text:
            continue
        result = _parse_single_ref(text, doc_year)
        if result:
            mrn, is_airgram = result
            results.append(
                {
                    "start": 0,
                    "end": 1,
                    "name": "mrn",
                    "value": mrn,
                    "tags": [
                        f"doc={doc_idx}",
                        "airgram" if is_airgram else "cable",
                    ],
                }
            )
        elif context and "_failed_refs" in context:
            context["_failed_refs"].append(text[:120])
    return results if results else None


def _build_rebulk() -> Rebulk:
    r = Rebulk(default_rules=False)
    r.functional(_batch_match, name="mrn", properties={"mrn": [None]})
    return r


# ── Document number normalization (simple regex, no rebulk) ────────────────

_RE_DOC_NUMBER = re.compile(r"(?P<year>\d{2})(?P<station>[A-Z]{3,80})0*(?P<number>\d+)")


def _normalize_doc_number(doc_number: str) -> str | None:
    if not doc_number:
        return None
    cleaned = _preprocess(doc_number)
    if not cleaned:
        return None
    m = _RE_DOC_NUMBER.search(cleaned)
    if not m:
        return None
    raw_station = m.group("station")
    canonical = _STATIONS.get(raw_station.upper())
    if not canonical:
        return None
    year = _clean_year(m.group("year"))
    number = _clean_number(m.group("number"))
    return f"{year}{canonical}{number}"


# ── Coverage tracking ──────────────────────────────────────────────────────


class CoverageTracker:
    """Tracks normalization coverage and collects failure samples."""

    def __init__(self):
        self.total_docs = 0
        self.total_refs = 0
        self.matched_refs = 0
        self.skipped_docs = 0
        self.failed_refs: list[str] = []
        self.cable_count = 0
        self.airgram_count = 0
        self.docs_with_refs = 0
        self.docs_with_matches = 0

    def record_doc(self, ref_count: int, match_count: int):
        self.total_docs += 1
        if ref_count > 0:
            self.docs_with_refs += 1
        if match_count > 0:
            self.docs_with_matches += 1

    def record_refs(
        self, total: int, matched: int, skipped_docs: int, cables: int, airgrams: int
    ):
        self.total_refs += total
        self.matched_refs += matched
        self.skipped_docs += skipped_docs
        self.cable_count += cables
        self.airgram_count += airgrams

    def record_failed(self, ref_text: str):
        if len(self.failed_refs) < _TOP_FAILED:
            self.failed_refs.append(ref_text[:120])

    def print_report(self, source_files: list[str], output_path: str | None):
        def pct(n):
            return (n / self.total_refs * 100) if self.total_refs else 0.0

        def pct_doc(n):
            return (n / self.total_docs * 100) if self.total_docs else 0.0

        sys.stderr.write("=== Reference Normalization Coverage ===\n")
        sys.stderr.write(f"Source files:            {' '.join(source_files)}\n")
        sys.stderr.write(f"Output:                  {output_path or 'stdout'}\n")
        sys.stderr.write(f"Total documents:         {self.total_docs:,}\n")
        sys.stderr.write(
            f"  with refs:             {self.docs_with_refs:,}  ({pct_doc(self.docs_with_refs):.2f}%)\n"
        )
        sys.stderr.write(
            f"  with matches:          {self.docs_with_matches:,}  ({pct_doc(self.docs_with_matches):.2f}%)\n"
        )
        sys.stderr.write(
            f"  no ref (null/NA):      {self.skipped_docs:,}  ({pct_doc(self.skipped_docs):.2f}%)\n"
        )
        sys.stderr.write(f"Total ref parts:         {self.total_refs:,}\n")
        sys.stderr.write(
            f"  matched:               {self.matched_refs:,}  ({pct(self.matched_refs):.2f}%)\n"
        )
        failed = self.total_refs - self.matched_refs
        sys.stderr.write(f"  failed (no match):     {failed:,}  ({pct(failed):.2f}%)\n")
        sys.stderr.write(
            f"  cables:                {self.cable_count:,}  ({pct(self.cable_count):.2f}%)\n"
        )
        sys.stderr.write(
            f"  airgrams:              {self.airgram_count:,}  ({pct(self.airgram_count):.2f}%)\n"
        )

        if self.failed_refs:
            sys.stderr.write(
                f"\nTop {len(self.failed_refs)} failing reference strings:\n"
            )
            for i, fr in enumerate(self.failed_refs):
                sys.stderr.write(f"  {i + 1:>6,}  {fr!r}\n")


# ── Input reading ──────────────────────────────────────────────────────────


def read_reftel(path: str):
    """Yield (doc_number, date, attr_reference, ref_list) from a .reftel.ndjson file.

    ``ref_list`` is the pre-split ``reference`` field (list of strings, or None).
    ``attr_reference`` is the raw attribute string (fallback).
    """
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            doc = obj.get("document_number") or ""
            date = obj.get("date") or ""
            attr_ref = obj.get("attr_reference") or ""
            ref_list = obj.get("reference")
            yield doc, date, attr_ref, ref_list


# ── Main ───────────────────────────────────────────────────────────────────


def main():
    paths = sys.argv[1:] if len(sys.argv) > 1 else []
    if not paths:
        results_dir = os.path.join(os.path.dirname(__file__), "..", "results")
        if os.path.isdir(results_dir):
            paths = sorted(
                os.path.join(results_dir, f)
                for f in os.listdir(results_dir)
                if f.endswith(".reftel.ndjson")
            )
    if not paths:
        sys.stderr.write(
            "Usage: python3 -m src.reftel-normalize [results/197?.reftel.ndjson ...]\n"
        )
        sys.exit(1)

    out_path = None
    if sys.stdout.isatty():
        out_path = os.path.join(
            os.path.dirname(__file__), "..", "results", "all-mrns.ndjson"
        )
        out = open(out_path, "w", encoding="utf-8")
    else:
        out = sys.stdout

    rebulk = _build_rebulk()
    coverage = CoverageTracker()

    for path in paths:
        sys.stderr.write(f"Processing {path} ...\n")

        docs: list[tuple[str, str]] = []
        batch_lines: list[str] = []
        batch_ref_counts: list[int] = []

        for doc_number, doc_date, attr_ref, ref_list in read_reftel(path):
            doc_idx = len(docs)
            docs.append((doc_number, doc_date))

            doc_year = _extract_year_from_date(doc_date)

            if ref_list and isinstance(ref_list, list):
                cleaned = [_preprocess(str(r)) for r in ref_list]
                cleaned = [c for c in cleaned if c]
                if cleaned:
                    for c in cleaned:
                        batch_lines.append(f"{doc_idx}\t{doc_year}\t{c}")
                    batch_ref_counts.append(len(cleaned))
                    continue

            cleaned = _preprocess_attr(attr_ref)
            if cleaned:
                batch_lines.append(f"{doc_idx}\t{doc_year}\t{cleaned}")
                batch_ref_counts.append(1)
            else:
                batch_ref_counts.append(0)

        failed_refs: list[str] = []

        if batch_lines:
            batch_text = "\n".join(batch_lines)
            context = {"_failed_refs": failed_refs}
            all_matches = rebulk.matches(batch_text, context=context)

            # Group matches by document index
            doc_mrns: dict[int, list[str]] = defaultdict(list)
            doc_cables: dict[int, int] = defaultdict(int)
            doc_airgrams: dict[int, int] = defaultdict(int)
            for m in all_matches:
                doc_idx = -1
                for tag in m.tags:
                    if tag.startswith("doc="):
                        doc_idx = int(tag[4:])
                    elif tag == "cable":
                        doc_cables[doc_idx] += 1
                    elif tag == "airgram":
                        doc_airgrams[doc_idx] += 1
                if doc_idx >= 0:
                    doc_mrns[doc_idx].append(m.value)
        else:
            doc_mrns = {}
            doc_cables = {}
            doc_airgrams = {}

        # Output per document
        total_ref_parts = 0
        total_matched = 0
        total_skipped_docs = 0
        total_cables = 0
        total_airgrams = 0

        for i, (doc_number, doc_date) in enumerate(docs):
            normalized = doc_mrns.get(i, [])
            ref_parts = batch_ref_counts[i]

            if ref_parts > 0:
                total_ref_parts += ref_parts
            else:
                total_skipped_docs += 1

            total_matched += len(normalized)
            total_cables += doc_cables.get(i, 0)
            total_airgrams += doc_airgrams.get(i, 0)

            coverage.record_doc(ref_parts, len(normalized))

            doc_number_norm = _normalize_doc_number(doc_number)
            result = {
                "document_number": doc_number_norm or doc_number,
                "date": doc_date,
                "extracted_references": normalized if normalized else None,
            }
            out.write(json.dumps(result, ensure_ascii=False) + "\n")

        for fr in failed_refs:
            coverage.record_failed(fr)

        coverage.record_refs(
            total_ref_parts,
            total_matched,
            total_skipped_docs,
            total_cables,
            total_airgrams,
        )

    if out is not sys.stdout:
        out.close()

    coverage.print_report(paths, out_path)


if __name__ == "__main__":
    main()
