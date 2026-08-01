#!/usr/bin/env python3
"""Date normalizer for ACP-127 messages: parses every date-bearing field --
the body DTG line, the dash-counter filing time, and all Message-Attribute
date keys -- into ISO 8601.

Reads per-document NDJSON files (the full extractor output, e.g.
results/<year>.ndjson) and outputs NDJSON, one line per document. rebulk
(src/patterns/dtg.py, src/patterns/attributes.py, src/patterns/dash_counter.py)
only extracts raw date text/components; all parsing lives in
src/date_utils.py, invoked from here, so it can be audited and covered in one
place instead of scattered across the pipeline.

    Usage::

        python3 -m src.date_normalize <file.ndjson> [...] > output.ndjson

    Output format (one JSON line per document)::

        {"document_number": "1973ABUDH00866", "document_number_raw": "1973ABUDH00866",
         "dtg": {"raw": "...", "precedence": ["PRIORITY"], "datetime_iso": "..."},
         "filing_time_raw": "201212Z",
         "filing_datetime_iso": "1973-06-20T12:12:00Z",
         "dates": {"capture_date": "1994-01-01", "draft_date": "1973-06-27", ...}}

This module deliberately does NOT pick a single "document date" -- every
field is exposed independently, 1:1 named to its source, so a downstream
consumer decides its own priority (see src/reftel_normalize.py, which has a
genuine internal need for one resolved date and makes that choice itself,
explicitly, off these same raw fields). ``filing_time_raw`` is the bare
day/hour/minute/Z fragment from ``_dash_counters.filing_time`` (it has no
month/year of its own); ``filing_datetime_iso`` reconstructs a full datetime
by borrowing month/year from the same document's DTG. ``document_number_raw``
is the un-normalized value straight from ``Message Attributes.Document
Number`` (pre-``_normalize_doc_number()``), kept so callers can
back-reference the source document even after ``document_number`` has been
rewritten to canonical MRN form.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter

_src_dir = os.path.dirname(os.path.abspath(__file__))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from date_utils import parse_date, parse_dtg, reconstruct_filing_datetime
from reftel_normalize import _normalize_doc_number

_DATE_ATTRS = [
    "Capture Date",
    "Decaption Date",
    "Disposition Date",
    "Disposition Approved on Date",
    "Review Date",
    "Review Release Date",
    "Review Transfer Date",
    "Draft Date",
    "Sent Date",
]

# 1:1 map from the verbatim Message Attributes key to the output field name --
# attrs.get(name) below still uses the space-form key; only the JSON output
# key is snake_case.
_ATTR_OUTPUT_KEYS = {name: name.lower().replace(" ", "_") for name in _DATE_ATTRS}

_ALL_FIELDS = _DATE_ATTRS + ["dtg", "filing_time"]

_MAX_EXAMPLES = 10


# ── Coverage Tracking ────────────────────────────────────────────────────


class CoverageTracker:
    def __init__(self):
        self.total_docs = 0
        self.raw_present = Counter()
        self.parsed_ok = Counter()
        self.failed_examples: dict[str, list[str]] = {name: [] for name in _ALL_FIELDS}

    def record_doc(self):
        self.total_docs += 1

    def record_attr(self, name: str, raw, iso):
        if not raw:
            return
        self.raw_present[name] += 1
        if iso:
            self.parsed_ok[name] += 1
        elif len(self.failed_examples[name]) < _MAX_EXAMPLES:
            self.failed_examples[name].append(str(raw)[:120])

    def record_dtg(self, raw_components, parsed_value):
        if not raw_components:
            return
        self.raw_present["dtg"] += 1
        if parsed_value:
            self.parsed_ok["dtg"] += 1
        elif len(self.failed_examples["dtg"]) < _MAX_EXAMPLES:
            self.failed_examples["dtg"].append(str(raw_components)[:120])

    def record_filing_time(self, raw, parsed_value):
        if not raw:
            return
        self.raw_present["filing_time"] += 1
        if parsed_value:
            self.parsed_ok["filing_time"] += 1
        elif len(self.failed_examples["filing_time"]) < _MAX_EXAMPLES:
            self.failed_examples["filing_time"].append(str(raw)[:120])

    def print_report(self, source_files: list[str], output_path: str | None):
        def pct(n, d):
            return (n / d * 100) if d else 0.0

        w = sys.stderr.write
        w("=== Date Normalization Coverage ===\n")
        w(f"Source files:            {' '.join(source_files)}\n")
        w(f"Output:                  {output_path or 'stdout'}\n")
        w(f"Total documents:         {self.total_docs:,}\n\n")

        w(f"{'Field':32s} {'raw present':>14s} {'parsed':>14s} {'parse rate':>11s}\n")
        for name in _ALL_FIELDS:
            raw = self.raw_present[name]
            ok = self.parsed_ok[name]
            w(f"{name:32s} {raw:>14,} {ok:>14,} {pct(ok, raw):>10.2f}%\n")

        for name in _ALL_FIELDS:
            examples = self.failed_examples[name]
            if examples:
                w(f"\nUnparsed {name} examples:\n")
                for ex in examples:
                    w(f"  {ex!r}\n")


# ── Input Handling & Main ────────────────────────────────────────────────


def read_dates(path: str):
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
            raw_dates = {name: attrs.get(name) for name in _DATE_ATTRS}
            dtg_raw = obj.get("_dtg")
            filing_time_raw = (obj.get("_dash_counters") or {}).get("filing_time")
            yield doc_number, raw_dates, dtg_raw, filing_time_raw


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: python3 -m src.date_normalize <file.ndjson> [...] > output.ndjson\n")
        sys.exit(1)

    paths = sys.argv[1:]
    if sys.stdout.isatty():
        sys.stderr.write("ERROR: redirect stdout to a file (e.g. ... > output.ndjson)\n")
        sys.exit(1)

    out = sys.stdout
    coverage = CoverageTracker()

    for path in paths:
        sys.stderr.write(f"Processing {path} ...\n")
        for doc_number, raw_dates, dtg_raw, filing_time_raw in read_dates(path):
            coverage.record_doc()

            parsed_dates = {}
            for name, raw in raw_dates.items():
                iso = parse_date(raw) if raw else None
                parsed_dates[_ATTR_OUTPUT_KEYS[name]] = iso
                coverage.record_attr(name, raw, iso)

            dtg_parsed = parse_dtg(dtg_raw) if dtg_raw else None
            coverage.record_dtg(dtg_raw, dtg_parsed)

            filing_datetime_iso = reconstruct_filing_datetime(filing_time_raw, dtg_raw)
            coverage.record_filing_time(filing_time_raw, filing_datetime_iso)

            doc_number_norm = _normalize_doc_number(doc_number)

            result_doc = {
                "document_number": doc_number_norm or doc_number,
                "document_number_raw": doc_number or None,
                "dtg": dtg_parsed,
                "filing_time_raw": filing_time_raw,
                "filing_datetime_iso": filing_datetime_iso,
                "dates": parsed_dates,
            }
            out.write(json.dumps(result_doc, ensure_ascii=False) + "\n")

    coverage.print_report(paths, None)


if __name__ == "__main__":
    main()
