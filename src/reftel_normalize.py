#!/usr/bin/env python3
"""MRN normalizer for ACP-127 reference data using strict deterministic regex pipeline.

Reads per-document NDJSON files, normalizes each reference string into canonical 
MRN format, and outputs NDJSON. Date fields are converted to ISO 8601.

    Usage::

        python3 -m src.reftel_normalize <file.ndjson> [...] > output.ndjson

    Output format (one JSON line per document)::

        {"document_number": "1973AMMAN03057", "date": "1973-06-07",
         "extracted_references": ["73STATE93410"],
         "message_preview": "..."}
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime

_src_dir = os.path.dirname(os.path.abspath(__file__))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from station_data import STATIONS, _STOP_STATIONS, _SENDER_DATE_STATIONS

# ── Station Compilation (No Wildcards, Longest Match First) ─────────────────

_STATIONS_MAPPING: dict[str, str] = {}
for canonical, variants in STATIONS.items():
    _STATIONS_MAPPING[canonical.upper()] = canonical
    for variant in variants:
        _STATIONS_MAPPING[variant.upper()] = canonical

_VALID_STATIONS = sorted(
    [s for s in _STATIONS_MAPPING.keys() if s not in _STOP_STATIONS], 
    key=len, 
    reverse=True
)

_STATIONS_REGEX_STR = r"(?P<station>" + r"|".join(re.escape(s) for s in _VALID_STATIONS) + r")"


# ── Pipeline Stage 1: Ordered Pre-Splitting Cleanup ─────────────────────────

_PREFIX_STRIP_RE = re.compile(r"^(?P<prefix>(?:REFTEL|RETELS?|REF(?:ERENCE)?S?)\.?\s*:?\s*)", re.IGNORECASE)

_CLEANUP_REGEXES = [
    # Strip list-style prefixes (e.g., "B. ", "(C) ", "D) ") and numbered lists
    (re.compile(r"^(?P<letter_prefix>\s*(?:\(\s*[A-Za-z]\s*\)\s*|[A-Za-z]\.\s*|[A-Za-z]\)\s*)+)", re.IGNORECASE), ""),
    (re.compile(r"^(?P<num_prefix>\d+[\).]\s*)", re.IGNORECASE), ""),
    # Keyword/flag removal
    (re.compile(r"(?P<na>^(?:\s*n/a\s*|\s*N/A\s*|\s*none\s*)$)", re.IGNORECASE), ""),
    (re.compile(r"(?P<notal>\s*\(?\s*NOTAL\b\s*\)?\s*)", re.IGNORECASE), ""),
    (re.compile(r"(?P<unclas>\bUNCLAS(?:SIFIED)?\s+)", re.IGNORECASE), ""),
    (re.compile(r"(?P<airgram_word>\bAIRGRAM\s+)", re.IGNORECASE), ""),
    (re.compile(r"(?P<possessive>\b'\sS\s+)", re.IGNORECASE), " "),
    (re.compile(r"(?P<retention>\n\s*Retention:\s*\d+\s*$)", re.IGNORECASE), ""),
    # Convert YY century variants
    (re.compile(r"\b(?P<century>\d{2})(?P<year>\d{2})(?P<rest>[A-Z])", re.IGNORECASE), r"\g<year>\g<rest>"),
    # Strip trailing dates, paragraph marks, and parentheticals
    (re.compile(
        r"(?P<trailing_misc>\s*"
        r"(?:"
        r"\([^()]*\)"  
        r"|"
        r"[,:]?\s*(?:\d{1,2}\s+)?(?:"
        r"JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER"
        r"|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC"
        r")"
        r"(?:\.?)\s+(?:\d{1,2},?\s*)?(?:\d{2,4})?"  
        r"|"
        r"\d{6}\s*Z(?:\s+(?:"
        r"JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER"
        r"|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC"
        r")"
        r"(?:\.?)\s+(?:\d{1,2},?\s+)?\d{2,4})?"  
        r"|"
        r"\d{1,2}/\d{1,2}/(?:\d{2}|\d{4})" 
        r"|"
        r"PARA(?:GRAPH)?\s+\d+"
        r"|"
        r"ITEM\s+\d+"
        r"|"
        r"PART\s+\d+"
        r")*[,.:;/()]*\s*$)",
        re.IGNORECASE,
    ), ""),
    # Extra explicit prefix/suffix punctuation cleanup
    (re.compile(r"^(?P<leading_punct>[,.:;/()]\s*)", re.IGNORECASE), ""),
    (re.compile(r"(?P<trailing_punct>[,.:;/()]\s*$)", re.IGNORECASE), ""),
]


# ── Pipeline Stage 2: Splitting Delimiters ──────────────────────────────────

_REF_NON_SEP_WORDS = (
    "JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|"
    "JANUARY|FEBRUARY|MARCH|APRIL|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER|"
    "DATED|PARA|ITEM|SECTION|PAGE|SUBJECT|AND|THE|OF|FOR|TO|IN|BY|WITH|NOT|PREVIOUS|"
    "SUMMARY|BEGIN|END|PART|NOTE"
)

# Every regex MUST have exactly 1 named capture group so we can reliably slice 
# the re.split array using [::2] to ignore delimiters entirely.
_SPLIT_REGEXES = [
    re.compile(r"(?P<sep_semi>;\s*)", re.IGNORECASE),
    re.compile(r"(?P<sep_and>\s+(?:AND|&)\s+)", re.IGNORECASE),
    # Splits "B. STATE 105386" ensuring at least a 2-char station follows
    re.compile(r"(?P<sep_letter>[,:;.]?\s+(?:[A-Z]\.\s*|[A-Z]\s*\.\s*|[A-Z]\)\s+|\([A-Z]\)\s+)(?=[A-Z]{2,}))", re.IGNORECASE),
    re.compile(r"(?P<sep_colon>:\s+(?=(?:\d{2}\s+)?[A-Z]{3}))", re.IGNORECASE),
    re.compile(r"(?P<sep_comma>,\s+(?=(?:\d{2}\s+)?(?!(?:" + _REF_NON_SEP_WORDS + r"))[A-Z]{3}))", re.IGNORECASE),
]

_CONT_TEXT_RE = re.compile(r"^\s{2,}\S")
_NEW_REF_RE = re.compile(r"^\s{2,}(?:(?:[A-Z][\).]|\([A-Z]\))\s|[A-Z]\.\s)")


# ── Pipeline Stage 3: Precise Final Matches (^...$) ─────────────────────────

_DOC_PATTERN = re.compile(r"^(?P<year>\d{2})[\s-]*" + _STATIONS_REGEX_STR + r"[\s-]*0*(?P<number>\d+)$", re.IGNORECASE)

# Uses [\s-]* to cleanly accommodate missing spaces or hyphens (e.g. "BA-4301" or "BAMAKO A-50")
_MRN_PATTERNS = [
    # 1. Full MRN with Year and Airgram indicator
    re.compile(r"^(?P<year>\d{2})[\s-]*" + _STATIONS_REGEX_STR + r"[\s-]*(?P<airgram>-?A|AIRGRAM)[\s-]*(?P<number>\d{1,10})$", re.IGNORECASE),
    # 2. Full MRN with Year, no Airgram
    re.compile(r"^(?P<year>\d{2})[\s-]*" + _STATIONS_REGEX_STR + r"[\s-]*(?P<number>\d{1,10})$", re.IGNORECASE),
    # 3. No Year, Airgram indicator
    re.compile(r"^" + _STATIONS_REGEX_STR + r"[\s-]*(?P<airgram>-?A|AIRGRAM)[\s-]*(?P<number>\d{1,10})$", re.IGNORECASE),
    # 4. No Year, no Airgram
    re.compile(r"^" + _STATIONS_REGEX_STR + r"[\s-]*(?P<number>\d{1,10})$", re.IGNORECASE),
]


# ── Core Functions ─────────────────────────────────────────────────────────

def _parse_document_date(date_str: str) -> tuple[str, str]:
    text = date_str.strip()
    if not text:
        return "", ""
    
    formats = [
        "%d %b %Y",
        "%d-%b-%Y %I:%M:%S %p",
        "%d-%b-%Y"
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(text, fmt)
            iso_date = dt.strftime("%Y-%m-%dT%H:%M:%S") if "%I" in fmt else dt.strftime("%Y-%m-%d")
            doc_year = dt.strftime("%y")
            return iso_date, doc_year
        except ValueError:
            continue
            
    return text, ""

def _clean_number(n: str) -> str:
    n = n.lstrip("0")
    return n if n else "0"

def _format_canonical(year: str, station: str, number: str, is_airgram: bool) -> str:
    if is_airgram:
        return f"{year}{station}-A{number}"
    return f"{year}{station}{number}"

def _preprocess_text(text: str) -> str | None:
    if not text:
        return None
    cleaned = text.strip()
    for pattern, substitution in _CLEANUP_REGEXES:
        cleaned = pattern.sub(substitution, cleaned)
    return cleaned.strip() or None

def _split_refs(text: str) -> list[str]:
    """Split raw reference text into discrete, fully cleaned tokens."""
    if not text:
        return []
    
    # Run the general REFTEL strip before line continuations
    cleaned_initial = _PREFIX_STRIP_RE.sub("", text).strip()
    if not cleaned_initial:
        return []

    lines = cleaned_initial.split("\n")
    initial: list[str] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if i == 0 or not _CONT_TEXT_RE.match(line):
            initial.append(stripped)
        elif _NEW_REF_RE.match(line):
            initial.append(stripped)
        elif initial:
            initial[-1] += " " + stripped
        else:
            initial.append(stripped)

    items: list[str] = initial
    for pattern in _SPLIT_REGEXES:
        new_items = []
        for item in items:
            pieces = pattern.split(item)
            # Re.split with 1 capturing group returns [val, delimiter, val]
            # [::2] securely extracts ONLY the values, eliminating delimiter leakage
            for sub_item in pieces[::2]:
                sub_item = sub_item.strip()
                if sub_item:
                    new_items.append(sub_item)
        items = new_items

    # Process all parsed splits through the rigorous cleanup stage
    final_items = []
    for item in items:
        cleaned = _preprocess_text(item)
        if cleaned:
            final_items.append(cleaned)

    return final_items

def _match_mrn(text: str, doc_year: str) -> tuple[str, bool] | None:
    """Run text against precision MRN patterns."""
    for pattern in _MRN_PATTERNS:
        match = pattern.match(text)
        if match:
            group_dict = match.groupdict()
            year = group_dict.get("year") or doc_year
            raw_station = group_dict.get("station", "").upper()
            number = _clean_number(group_dict.get("number", ""))
            is_airgram = "airgram" in group_dict and group_dict["airgram"] is not None

            if len(group_dict.get("number", "")) >= 6 and raw_station in _SENDER_DATE_STATIONS:
                return None
            
            canonical_station = _STATIONS_MAPPING.get(raw_station)
            if not canonical_station:
                return None
                
            mrn = _format_canonical(year, canonical_station, number, is_airgram)
            return (mrn, is_airgram)
    return None

def _normalize_doc_number(doc_number: str) -> str | None:
    if not doc_number:
        return None
    cleaned = _preprocess_text(doc_number)
    if not cleaned:
        return None
        
    match = _DOC_PATTERN.match(cleaned)
    if not match:
        return None
    
    canonical = _STATIONS_MAPPING.get(match.group("station").upper())
    if not canonical:
        return None
        
    return f"{match.group('year')}{canonical}{_clean_number(match.group('number'))}"

# ── Coverage Tracking ──────────────────────────────────────────────────────

_TOP_FAILED = 500

class CoverageTracker:
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

    def record_refs(self, total: int, matched: int, skipped_docs: int, cables: int, airgrams: int):
        self.total_refs += total
        self.matched_refs += matched
        self.skipped_docs += skipped_docs
        self.cable_count += cables
        self.airgram_count += airgrams

    def record_failed(self, ref_text: str):
        if len(self.failed_refs) < _TOP_FAILED:
            self.failed_refs.append(ref_text[:120])

    def print_report(self, source_files: list[str], output_path: str | None):
        def pct(n): return (n / self.total_refs * 100) if self.total_refs else 0.0
        def pct_doc(n): return (n / self.total_docs * 100) if self.total_docs else 0.0

        sys.stderr.write("=== Reference Normalization Coverage ===\n")
        sys.stderr.write(f"Source files:            {' '.join(source_files)}\n")
        sys.stderr.write(f"Output:                  {output_path or 'stdout'}\n")
        sys.stderr.write(f"Total documents:         {self.total_docs:,}\n")
        sys.stderr.write(f"  with refs:             {self.docs_with_refs:,}  ({pct_doc(self.docs_with_refs):.2f}%)\n")
        sys.stderr.write(f"  with matches:          {self.docs_with_matches:,}  ({pct_doc(self.docs_with_matches):.2f}%)\n")
        sys.stderr.write(f"  no ref (null/NA):      {self.skipped_docs:,}  ({pct_doc(self.skipped_docs):.2f}%)\n")
        sys.stderr.write(f"Total ref parts:         {self.total_refs:,}\n")
        sys.stderr.write(f"  matched:               {self.matched_refs:,}  ({pct(self.matched_refs):.2f}%)\n")
        
        failed = self.total_refs - self.matched_refs
        sys.stderr.write(f"  failed (no match):     {failed:,}  ({pct(failed):.2f}%)\n")
        sys.stderr.write(f"  cables:                {self.cable_count:,}  ({pct(self.cable_count):.2f}%)\n")
        sys.stderr.write(f"  airgrams:              {self.airgram_count:,}  ({pct(self.airgram_count):.2f}%)\n")

        if self.failed_refs:
            sys.stderr.write(f"\nTop {len(self.failed_refs)} failing reference strings:\n")
            for i, fr in enumerate(self.failed_refs):
                sys.stderr.write(f"  {i + 1:>6,}  {fr!r}\n")

# ── Input Handling & Main ──────────────────────────────────────────────────

def read_reftel(path: str):
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
            ref_list = obj.get("references")
            message_preview = obj.get("message_preview")
            yield doc, date, attr_ref, ref_list, message_preview

def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: python3 -m src.reftel_normalize <file.ndjson> [...] > output.ndjson\n")
        sys.exit(1)

    paths = sys.argv[1:]
    if sys.stdout.isatty():
        sys.stderr.write("ERROR: redirect stdout to a file (e.g. ... > output.ndjson)\n")
        sys.exit(1)
    
    out = sys.stdout
    coverage = CoverageTracker()

    for path in paths:
        sys.stderr.write(f"Processing {path} ...\n")
        
        total_ref_parts = 0
        total_matched = 0
        total_skipped_docs = 0
        total_cables = 0
        total_airgrams = 0

        for doc_number, doc_date, attr_ref, ref_list, message_preview in read_reftel(path):
            iso_date, doc_year = _parse_document_date(doc_date)
            
            # Stage 1: Gather EVERYTHING for rigorous splitting
            raw_tokens = []
            if ref_list:
                if isinstance(ref_list, list):
                    for r in ref_list:
                        raw_tokens.extend(_split_refs(str(r)))
                elif isinstance(ref_list, str):
                    raw_tokens.extend(_split_refs(ref_list))
                    
            if attr_ref:
                raw_tokens.extend(_split_refs(str(attr_ref)))

            # Stage 2: Deduplicate cleanly parsed tokens to match against
            seen = set()
            tokens_to_match = []
            for token in raw_tokens:
                if token and token not in seen:
                    seen.add(token)
                    tokens_to_match.append(token)

            ref_count = len(tokens_to_match)
            if ref_count == 0:
                total_skipped_docs += 1
            else:
                total_ref_parts += ref_count

            # Stage 3: Match against Anchored Pattern
            extracted_mrns = []
            doc_cable_count = 0
            doc_airgram_count = 0
            
            for token in tokens_to_match:
                result = _match_mrn(token, doc_year)
                if result:
                    mrn, is_airgram = result
                    extracted_mrns.append(mrn)
                    if is_airgram:
                        doc_airgram_count += 1
                    else:
                        doc_cable_count += 1
                else:
                    coverage.record_failed(token)

            total_matched += len(extracted_mrns)
            total_cables += doc_cable_count
            total_airgrams += doc_airgram_count
            
            coverage.record_doc(ref_count, len(extracted_mrns))
            doc_number_norm = _normalize_doc_number(doc_number)
            
            result_doc = {
                "document_number": doc_number_norm or doc_number,
                "date": iso_date,
                "extracted_references": extracted_mrns if extracted_mrns else None,
            }
            if message_preview:
                result_doc["message_preview"] = message_preview
            out.write(json.dumps(result_doc, ensure_ascii=False) + "\n")

        coverage.record_refs(
            total_ref_parts, total_matched, total_skipped_docs, total_cables, total_airgrams
        )

    coverage.print_report(paths, None)

if __name__ == "__main__":
    main()