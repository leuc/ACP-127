#!/usr/bin/env python3
"""Multi-stage MRN normalizer for ACP-127 reference data.

Reads ``results/197?.reftel.ndjson`` files (pretty-printed JSON objects),
normalizes each reference string into canonical MRN format using
rebulk-based multi-stage pattern matching, and outputs NDJSON.

Usage::

    python3 src/reftel-normalize.py [results/197?.reftel.ndjson ...] > all-mrns.ndjson

Output format (one JSON line per document)::

    {"document_number": "1973AMMAN03057", "date": "07 JUN 1973",
     "extracted_references": ["73STATE93410"]}
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field

from rebulk import Rebulk

from station_index import StationIndex

# ── Pre-processing constants ────────────────────────────────────────────────

_PREFIX_STRIP = re.compile(
    r"^(?:REF(?:ERENCE)?S?\s*:|REF\s*:|REFTEL:|RETELS?\s*:)\s*", re.I
)
_LETTER_PREFIX = re.compile(r"^\s*(?:\(\s*[A-Z]\s*\)\s*|[A-Z]\.\s*|[A-Z]\)\s*)+")
_NOTAL_CLEAN = re.compile(r"\s*\(?\s*NOTAL\b\s*\)?\s*", re.I)
_UNCLAS = re.compile(r"\bUNCLAS\s+", re.I)
_POSSESSIVE = re.compile(r"\b' S\s+")
_NA_RE = re.compile(r"^(?:\s*n/a\s*|\s*N/A\s*|\s*none\s*)$", re.I)
_4DIGIT_YEAR = re.compile(r"\b(?P<y>\d{4})(?P<rest>[A-Z])")

_MIN_STATION_LEN = 3
_TOP_FAILED = 20


@dataclass
class StageDef:
    name: str
    regex_template: str
    is_airgram: bool
    priority: int


_STAGES: list[StageDef] = [
    # ── Airgram stages (higher priority) ────────────────────────────────
    StageDef(
        "airgram_spaced_known",
        r"\b(?P<year>\d{{2}})\s+(?P<station>{stations})\s+A-?(?P<number>\d{{1,10}})\b",
        is_airgram=True,
        priority=1400,
    ),
    StageDef(
        "airgram_compact_known",
        r"\b(?P<year>\d{{2}})(?P<station>{stations})A-?(?P<number>\d{{1,10}})\b",
        is_airgram=True,
        priority=1300,
    ),
    StageDef(
        "airgram_A_prefix",
        r"\b(?P<year>\d{{2}})[A-Z]:(?P<station>{stations})\s*A-?(?P<number>\d{{1,10}})\b",
        is_airgram=True,
        priority=1200,
    ),
    StageDef(
        "airgram_spaced_generic",
        r"\b(?P<year>\d{{2}})\s+(?P<station>[A-Z]{{3,}}(?:\s+[A-Z]{{3,}})*)\s+A-?(?P<number>\d{{1,10}})\b",
        is_airgram=True,
        priority=1150,
    ),
    StageDef(
        "airgram_compact_generic_80",
        r"\b(?P<year>\d{{2}})(?P<station>[A-Z]{{4,80}})A-?(?P<number>\d{{1,10}})\b",
        is_airgram=True,
        priority=1140,
    ),
    StageDef(
        "airgram_mixed_case_generic",
        r"\b(?P<year>\d{{2}})(?P<station>[A-Za-z]{{4,80}})A-?(?P<number>\d{{1,10}})\b",
        is_airgram=True,
        priority=1130,
    ),
    StageDef(
        "airgram_fallback",
        r"\b(?P<station>{stations})\s+A-?\s*(?P<number>\d{{1,10}})\b",
        is_airgram=True,
        priority=1100,
    ),
    StageDef(
        "airgram_fallback_compact",
        r"\b(?P<station>{stations})A\s+(?P<number>\d{{1,10}})\b",
        is_airgram=True,
        priority=1085,
    ),
    # ── Cable stages ────────────────────────────────────────────────────
    StageDef(
        "cable_spaced_known",
        r"\b(?P<year>\d{{2}})\s+(?P<station>{stations})\s+(?P<number>\d{{1,10}})\b",
        is_airgram=False,
        priority=1000,
    ),
    StageDef(
        "cable_A_prefix",
        r"\b(?P<year>\d{{2}})[A-Z]:(?P<station>{stations})\s*(?P<number>\d{{1,10}})\b",
        is_airgram=False,
        priority=950,
    ),
    StageDef(
        "cable_compact_known",
        r"\b(?P<year>\d{{2}})(?P<station>{stations})\s*(?P<number>\d{{1,10}})\b",
        is_airgram=False,
        priority=900,
    ),
    StageDef(
        "cable_spaced_generic",
        r"\b(?P<year>\d{{2}})\s+(?P<station>[A-Z]{{3,}}(?:\s+[A-Z]{{3,}})*)\s+(?P<number>\d{{1,10}})\b",
        is_airgram=False,
        priority=850,
    ),
    StageDef(
        "cable_compact_uppercase",
        r"\b(?P<year>\d{{2}})(?P<station>[A-Z]{{4,80}})\s*(?P<number>\d{{1,10}})\b",
        is_airgram=False,
        priority=800,
    ),
    StageDef(
        "cable_mixed_case",
        r"\b(?P<year>\d{{2}})(?P<station>[A-Za-z]{{4,80}})\s*(?P<number>\d{{1,10}})\b",
        is_airgram=False,
        priority=750,
    ),
    StageDef(
        "cable_fallback",
        r"\b(?P<station>{stations})\s+(?P<number>\d{{1,10}})\b",
        is_airgram=False,
        priority=700,
    ),
    # ── Generic fallback (catches typos / unknown stations via fuzzy) ──
    StageDef(
        "cable_fallback_generic",
        r"\b(?P<station>[A-Z]{{3,80}}(?:\s+[A-Z]{{3,}})*)\s+(?P<number>\d{{1,10}})\b",
        is_airgram=False,
        priority=690,
    ),
    StageDef(
        "airgram_fallback_generic",
        r"\b(?P<station>[A-Z]{{3,80}}(?:\s+[A-Z]{{3,}})*)\s+A-?(?P<number>\d{{1,10}})\b",
        is_airgram=True,
        priority=1090,
    ),
]


def _extract_groups(match):
    """Extract named groups from a rebulk Match as a plain dict."""
    return {c.name: c.value for c in match.children}


def _clean_year(y: str) -> str:
    return y[-2:]


def _clean_number(n: str) -> str:
    n = n.lstrip("0")
    return n if n else "0"


def _format_canonical(year: str, station: str, number: str, is_airgram: bool) -> str:
    if is_airgram:
        return f"{year}{station}-A{number}"
    return f"{year}{station}{number}"


def _preprocess(ref: str) -> str | None:
    """Clean a reference string before matching.

    Returns cleaned string or None if the reference should be skipped
    (null, NA, empty).
    """
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
    text = _4DIGIT_YEAR.sub(lambda m: m.group("y")[2:] + m.group("rest"), text)
    return text.strip() or None


def _normalize_doc_number(
    doc_number: str, station_index: StationIndex, rebulk: Rebulk
) -> str | None:
    cleaned = _preprocess(doc_number)
    if not cleaned:
        return None
    matches = rebulk.matches(cleaned)
    for stage in _STAGES:
        for m in matches.named(stage.name):
            groups = _extract_groups(m)
            raw_station = groups.get("station", "").strip()
            raw_number = groups.get("number", "").strip()
            if not raw_station or not raw_number:
                continue
            if len(raw_station) < _MIN_STATION_LEN:
                continue
            if station_index.is_stop_station(raw_station):
                continue
            if stage.name == "airgram_fallback_compact":
                if (
                    station_index.resolve(raw_station + "A", allow_fuzzy=False)
                    is not None
                ):
                    continue
            canonical = station_index.resolve(
                raw_station, allow_fuzzy=not stage.is_airgram
            )
            if not canonical:
                continue
            year = groups.get("year", "")
            year = _clean_year(year) if year else ""
            number = _clean_number(raw_number)
            return _format_canonical(year, canonical, number, stage.is_airgram)
    return None


def _build_rebulk(station_index: StationIndex) -> Rebulk:
    r = Rebulk()
    stations_alt = station_index.alternation_pattern()
    for stage in _STAGES:
        pattern = stage.regex_template.format(stations=stations_alt)
        r.regex(
            pattern,
            name=stage.name,
            priority=stage.priority,
            tags=["reference_stage"],
            flags=re.IGNORECASE,
        )
    return r


class CoverageTracker:
    """Tracks normalization coverage per-stage and collects failure samples."""

    def __init__(self):
        self.total_docs = 0
        self.total_refs = 0
        self.stage_counts: Counter = Counter()
        self.failed_refs: list[str] = []
        self.station_exact_variant = 0
        self.station_exact_joined = 0
        self.station_fuzzy = 0
        self.station_failed = 0
        # Per-document tracking
        self.docs_with_refs = 0
        self.docs_with_matches = 0

    def record_ref(self, stage: str | None, ref_text: str):
        self.total_refs += 1
        if stage:
            self.stage_counts[stage] += 1
        else:
            self.stage_counts["failed"] += 1
            if len(self.failed_refs) < _TOP_FAILED:
                self.failed_refs.append(ref_text[:120])

    def record_station_resolution(self, result: str):
        if result == "exact_variant":
            self.station_exact_variant += 1
        elif result == "exact_joined":
            self.station_exact_joined += 1
        elif result == "fuzzy":
            self.station_fuzzy += 1
        elif result == "failed":
            self.station_failed += 1

    def record_doc(self, ref_count: int, match_count: int):
        self.total_docs += 1
        if ref_count > 0:
            self.docs_with_refs += 1
        if match_count > 0:
            self.docs_with_matches += 1

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
        sys.stderr.write(f"Total ref strings:       {self.total_refs:,}\n")
        sys.stderr.write("\n")

        sys.stderr.write("Per-stage match rates:\n")
        for stage in _STAGES:
            cnt = self.stage_counts.get(stage.name, 0)
            sys.stderr.write(f"  {stage.name:40s} {cnt:>8,}  ({pct(cnt):.2f}%)\n")

        cnt = self.stage_counts.get("skipped", 0)
        sys.stderr.write(f"  {'skipped (null/NA)':40s} {cnt:>8,}  ({pct(cnt):.2f}%)\n")
        cnt = self.stage_counts.get("failed", 0)
        sys.stderr.write(f"  {'failed (no match)':40s} {cnt:>8,}  ({pct(cnt):.2f}%)\n")
        sys.stderr.write("\n")

        sys.stderr.write("Station resolution:\n")
        total_station = (
            self.station_exact_variant
            + self.station_exact_joined
            + self.station_fuzzy
            + self.station_failed
        )
        if total_station:

            def spct(n):
                return n / total_station * 100

            sys.stderr.write(
                f"  exact (variant dict):  {self.station_exact_variant:>10,}  ({spct(self.station_exact_variant):.2f}%)\n"
            )
            sys.stderr.write(
                f"  exact (joined multi):  {self.station_exact_joined:>10,}  ({spct(self.station_exact_joined):.2f}%)\n"
            )
            sys.stderr.write(
                f"  fuzzy (Levenshtein):   {self.station_fuzzy:>10,}  ({spct(self.station_fuzzy):.2f}%)\n"
            )
            sys.stderr.write(
                f"  failed to resolve:     {self.station_failed:>10,}  ({spct(self.station_failed):.2f}%)\n"
            )
        else:
            sys.stderr.write("  (no station resolutions tracked)\n")

        if self.failed_refs:
            sys.stderr.write(
                f"\nTop {len(self.failed_refs)} failing reference strings:\n"
            )
            for i, fr in enumerate(self.failed_refs):
                sys.stderr.write(f"  {i + 1:>6,}  {fr!r}\n")


def read_reftel(path: str):
    """Yield (doc_number, date, refs_list) from a .reftel.ndjson file.

    Handles pretty-printed JSON objects separated by ``}\\n{`` boundaries.
    """
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    chunks = content.split("}\n{")
    for i, chunk in enumerate(chunks):
        if i == 0:
            text = chunk + "}"
        elif i == len(chunks) - 1:
            text = "{" + chunk
        else:
            text = "{" + chunk + "}"
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            continue
        doc = obj.get("document_number") or ""
        date = obj.get("date") or ""
        refs = obj.get("references") or []
        if isinstance(refs, list):
            yield doc, date, refs


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

    station_index = StationIndex()
    rebulk = _build_rebulk(station_index)
    coverage = CoverageTracker()

    for path in paths:
        sys.stderr.write(f"Processing {path} ...\n")
        for doc_number, doc_date, refs in read_reftel(path):
            doc_year = doc_number[2:4] if len(doc_number) >= 4 else ""
            normalized = []
            for ref_text in refs:
                cleaned = _preprocess(str(ref_text)) if ref_text else None
                if not cleaned:
                    coverage.record_ref("skipped", ref_text or "")
                    continue

                matches = rebulk.matches(cleaned)
                matched = False
                for stage in _STAGES:
                    for m in matches.named(stage.name):
                        groups = _extract_groups(m)
                        raw_station = groups.get("station", "").strip()
                        raw_number = groups.get("number", "").strip()

                        if not raw_station or not raw_number:
                            continue
                        if len(raw_station) < _MIN_STATION_LEN:
                            continue
                        if station_index.is_stop_station(raw_station):
                            continue

                        # airgram_fallback_compact: reject if raw_station+"A"
                        # is itself a known station (would be false positive)
                        if stage.name == "airgram_fallback_compact":
                            if (
                                station_index.resolve(
                                    raw_station + "A", allow_fuzzy=False
                                )
                                is not None
                            ):
                                continue

                        canonical_station = station_index.resolve(
                            raw_station,
                            allow_fuzzy=not stage.is_airgram,
                        )
                        if canonical_station is None:
                            coverage.record_station_resolution("failed")
                            continue

                        # Track station resolution method
                        norm_station = raw_station.strip().upper()
                        if norm_station in station_index._canonical_set:
                            coverage.record_station_resolution("exact_joined")
                        else:
                            coverage.record_station_resolution("exact_variant")

                        year = groups.get("year", doc_year)
                        if not year:
                            year = doc_year
                        year = _clean_year(year)
                        number = _clean_number(raw_number)

                        mrn = _format_canonical(
                            year, canonical_station, number, stage.is_airgram
                        )
                        normalized.append(mrn)
                        coverage.record_ref(stage.name, ref_text)
                        matched = True
                        break

                    if matched:
                        break

                if not matched:
                    coverage.record_ref(None, ref_text)

            coverage.record_doc(len(refs), len(normalized))

            doc_number_norm = _normalize_doc_number(doc_number, station_index, rebulk)
            result = {
                "document_number": doc_number_norm or doc_number,
                "date": doc_date,
                "extracted_references": normalized if normalized else None,
            }
            out.write(json.dumps(result, ensure_ascii=False) + "\n")

    if out is not sys.stdout:
        out.close()

    coverage.print_report(paths, out_path)


if __name__ == "__main__":
    main()
