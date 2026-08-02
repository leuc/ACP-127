#!/usr/bin/env python3
"""Date estimator for MRNs that are cited in results/all-mrns.ndjson but never
appear as any document_number anywhere in the corpus ("missing" MRNs) --
estimates each one's date by interpolating from the nearest known documents
at the same station/year, ordered by MRN sequence number.

Reads BOTH results/all-mrns.ndjson (document_number, document_number_raw,
date, extracted_references) AND the raw per-year extractor output
results/<year>.ndjson (Message Attributes."Document Number" -- the same
value as document_number_raw, no re-normalization needed -- and
_dash_counters.counter). File role is auto-detected per line ("Message
Attributes" present -> raw extractor line; otherwise -> all-mrns line), so
both file sets can be passed on one command line with no new flags. Unlike
its sibling normalizers, this script needs a GLOBAL view of the whole corpus
before it can emit a single line -- resolving one missing MRN may need any
station's data, and references may cite any station regardless of which
input file is currently being read -- so ALL input is loaded into memory
before any output is produced.

    Usage::

        python3 -m src.missing_mrn_estimate results/all-mrns.ndjson results/{1973..1979}.ndjson > results/missing-mrn-dates.ndjson

    Output format (one JSON line per missing MRN)::

        {"mrn": "73ACCRA2180", "station": "ACCRA", "year": "73", "is_airgram": false,
         "sequence": 2180, "estimated_date": "1973-04-05", "estimate_type": "interpolated_refined",
         "accuracy_days": 12, "date_order_inverted": false,
         "prev_known": {"document_number": "73ACCRA1284", "sequence": 1284, "date": "1973-02-08"},
         "next_known": {"document_number": "73ACCRA4187", "sequence": 4187, "date": "1973-07-02"}}

A station's MRN sequence number is validated (independently, in the sibling
cable-insights repo's already-answered dash-counter-meaning investigation --
see results/dash_counter_stats.md there) to correlate with the corpus-wide
shared tape-relay transmission counter, which itself tracks real
chronological order within a reset cycle. That's the basis for the
interpolation here: same-station/year neighbors, ordered by sequence number,
bracket a missing MRN's likely date.

Two estimate tiers, distinguished by ``estimate_type``:

- ``"interpolated"`` -- both a same-station/year document below and above
  the missing MRN's sequence number are known. Linear interpolation by
  sequence-number position between their dates. ``accuracy_days`` is the
  bracket width (days between the two known dates) -- not an error estimate,
  but a guarantee (the true date must fall inside it), so smaller is tighter.
  ``accuracy_days`` is always non-negative (an absolute distance); a small
  fraction of same-station neighbor pairs disagree on chronological order
  (the "prev"/lower-sequence document's own resolved date is actually later
  than "next"'s -- real upstream date-resolution noise, e.g. a DTG/Draft
  Date/Sent Date mis-parse on one of the two, not a bug here) -- when that
  happens ``date_order_inverted`` is true and the estimate for that MRN
  should be treated as low-confidence regardless of how small
  ``accuracy_days`` looks.
- ``"interpolated_refined"`` -- same bracket, but additionally refined using
  OTHER stations' cables that share the relay counter window between the two
  same-station anchors. This only engages when both anchors have a known
  ``_dash_counters.counter`` value AND the next anchor's counter is cleanly
  greater than the previous one's (the counter resets every ~129,000-131,000
  ticks, sometimes more than once a day, so a same-station gap that's wide
  in sequence-number terms can straddle a reset -- when it does, or when
  either anchor lacks a counter at all, this script falls back to the plain
  ``"interpolated"`` estimate for that MRN rather than risk a corrupted
  window). The counter is NOT globally unique across the whole 7-year span
  (values repeat every reset cycle), so a bare numeric range query over the
  entire corpus would pull in unrelated documents from different reset
  generations that just happen to share counter numbers -- the candidate
  pool is therefore bounded by BOTH counter range AND date range (already
  known documents whose own date falls within [prev_date, next_date]), not
  counter range alone. ``accuracy_days`` here is the (necessarily tighter)
  bracket between the nearest bounded candidates on either side of the
  missing MRN's estimated counter position, which can be much narrower than
  the plain same-station bracket when other stations' traffic filled the gap.
- ``"extrapolated"`` -- only one side (prev or next) is known; that side's
  date is used as-is. ``accuracy_days`` is null (no bracket exists).
- ``"unresolvable"`` -- no dated document exists at this station/year/
  is_airgram combination at all. Emitted (not omitted) so a consumer can
  compute exact resolution rates directly from the output, matching this
  codebase's coverage-first philosophy of always surfacing failure/unresolved
  counts rather than silently dropping rows.

Airgrams and cables use independent serial-number sequences at a station, so
they are never interpolated against each other (grouped by
``(station, year, is_airgram)``). Critically, ``document_number`` never
takes the airgram (``-A``) form ANYWHERE in this corpus (0 of ~1.9M
canonical document numbers) -- this corpus contains only telegrams; airgrams
were physical pouch mail with no corresponding record here. That means every
airgram-format missing MRN's group is permanently empty and resolves to
``"unresolvable"`` -- a structural fact of the corpus, not a bug, which is
why the coverage report below breaks airgram vs. cable out separately.

"Missing" is defined by exact document_number STRING membership, not
re-parseability: ~7.5% of document_number values fail canonical
normalization upstream (in src.reftel_normalize) and stay as raw fallback
strings -- those still count as "known" for membership purposes (a citation
matching that exact raw string is not missing), they just cannot be
reverse-parsed into (station, year, sequence) for the interpolation index.

A small fraction of canonical document_number values (~0.17%) appear more
than once with different resolved dates (fuzzy station matching or OCR
merging distinct messages onto the same MRN upstream). When building the
per-(station, year, is_airgram) sequence index, duplicates at the same
sequence number are collapsed to one representative by sorting the tied
entries by date and taking the middle one by position -- deterministic,
and avoids both order-dependent "first wins" and a fabricated mean-of-dates
that may not correspond to either real document.
"""

from __future__ import annotations

import bisect
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta

_src_dir = os.path.dirname(os.path.abspath(__file__))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from station_data import STATIONS

# ── Canonical MRN parsing (the reverse of reftel_normalize.py's
#    _format_canonical -- no such reverse-parser exists anywhere else, since
#    only ALREADY-canonical strings ever need this, never messy raw text) ──

_VALID_STATIONS = sorted(STATIONS.keys(), key=len, reverse=True)
_MRN_RE = re.compile(
    r"^(?P<year>\d{2})"
    r"(?P<station>" + "|".join(re.escape(s) for s in _VALID_STATIONS) + r")"
    r"(?P<airgram>-A)?"
    r"(?P<seq>\d+)$"
)

_MAX_UNRESOLVABLE_EXAMPLES = 30


def parse_canonical_mrn(mrn: str) -> tuple[str, str, bool, int] | None:
    """canonical MRN string -> (year, station, is_airgram, sequence), or None."""
    if not mrn:
        return None
    m = _MRN_RE.match(mrn)
    if not m:
        return None
    return m.group("year"), m.group("station"), m.group("airgram") is not None, int(m.group("seq"))


# ── Coverage Tracking ────────────────────────────────────────────────────


class CoverageTracker:
    def __init__(self):
        self.known_docnums = 0
        self.referenced_mrns = 0
        self.total_missing = 0
        self.by_type: Counter[str] = Counter()
        self.by_type_airgram: Counter[tuple[str, bool]] = Counter()
        self.accuracy_days: dict[str, list[int]] = {"interpolated": [], "interpolated_refined": []}
        self.collisions_resolved = 0
        self.out_of_range_year = 0
        self.date_order_inverted: Counter[str] = Counter()
        self.unresolvable_examples: list[str] = []

    def record_index(self, known_docnums: int, referenced_mrns: int, collisions_resolved: int):
        self.known_docnums = known_docnums
        self.referenced_mrns = referenced_mrns
        self.collisions_resolved = collisions_resolved

    def record_estimate(
        self, mrn: str, year: str, is_airgram: bool, estimate_type: str,
        accuracy_days: int | None, date_order_inverted: bool,
    ):
        self.total_missing += 1
        self.by_type[estimate_type] += 1
        self.by_type_airgram[(estimate_type, is_airgram)] += 1
        if year not in ("73", "74", "75", "76", "77", "78", "79"):
            self.out_of_range_year += 1
        if accuracy_days is not None and estimate_type in self.accuracy_days:
            self.accuracy_days[estimate_type].append(accuracy_days)
        if date_order_inverted:
            self.date_order_inverted[estimate_type] += 1
        if estimate_type == "unresolvable" and len(self.unresolvable_examples) < _MAX_UNRESOLVABLE_EXAMPLES:
            self.unresolvable_examples.append(mrn)

    def print_report(self, source_files: list[str], output_path: str | None):
        def pct(n, d):
            return (n / d * 100) if d else 0.0

        w = sys.stderr.write
        w("=== Missing MRN Date Estimation Coverage ===\n")
        w(f"Source files:            {' '.join(source_files)}\n")
        w(f"Output:                  {output_path or 'stdout'}\n")
        w(f"Known document_numbers:  {self.known_docnums:,}\n")
        w(f"Unique referenced MRNs:  {self.referenced_mrns:,}\n")
        w(f"Total missing MRNs:      {self.total_missing:,}\n\n")

        w("By estimate type:\n")
        for t in ("interpolated_refined", "interpolated", "extrapolated", "unresolvable"):
            n = self.by_type[t]
            w(f"  {t:22s} {n:>10,}  ({pct(n, self.total_missing):5.2f}%)\n")

        w("\nBy type x airgram (airgram groups are structurally always empty -- see docstring):\n")
        for is_airgram in (False, True):
            label = "airgram" if is_airgram else "cable"
            w(f"  {label}:\n")
            for t in ("interpolated_refined", "interpolated", "extrapolated", "unresolvable"):
                n = self.by_type_airgram[(t, is_airgram)]
                w(f"    {t:22s} {n:>10,}\n")

        for t in ("interpolated", "interpolated_refined"):
            vals = sorted(self.accuracy_days[t])
            if not vals:
                continue
            n = len(vals)

            def pctile(p):
                return vals[min(n - 1, int(n * p))]

            w(f"\naccuracy_days distribution ({t}, N={n:,}, all non-negative -- see date_order_inverted):\n")
            w(
                f"  min={vals[0]}  p25={pctile(0.25)}  median={pctile(0.50)}  "
                f"p75={pctile(0.75)}  p90={pctile(0.90)}  max={vals[-1]}\n"
            )
            inv = self.date_order_inverted[t]
            w(f"  date_order_inverted (prev/next dates disagree on chronological order -- upstream date noise, treat as low-confidence): {inv:,}  ({pct(inv, n):.2f}%)\n")

        w(f"\nKnown-document sequence collisions collapsed (tie-break): {self.collisions_resolved:,}\n")
        w(f"Missing MRNs with year prefix outside 73-79 (likely false-positive ref matches): {self.out_of_range_year:,}\n")

        if self.unresolvable_examples:
            w(f"\nFirst {len(self.unresolvable_examples)} unresolvable examples:\n")
            for mrn in self.unresolvable_examples:
                w(f"  {mrn!r}\n")


# ── Input Handling ─────────────────────────────────────────────────────────


def _iter_json_lines(path: str):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


# ── Index Building ───────────────────────────────────────────────────────


def _finalize_group(entries: list[tuple[int, str, str, str]]) -> tuple[list[int], list[tuple[str, str, str]]]:
    """entries: list of (seq, document_number, document_number_raw, date).

    Sorts by (seq, date), then collapses duplicate seq values by taking the
    middle entry by position among ties (deterministic tie-break, see
    module docstring). Returns parallel (seqs, reps) lists for bisect.
    """
    entries.sort(key=lambda e: (e[0], e[3]))
    seqs: list[int] = []
    reps: list[tuple[str, str, str]] = []
    i, n = 0, len(entries)
    collisions = 0
    while i < n:
        j = i
        while j < n and entries[j][0] == entries[i][0]:
            j += 1
        tied = entries[i:j]
        if len(tied) > 1:
            collisions += 1
        mid = tied[len(tied) // 2]
        seqs.append(mid[0])
        reps.append((mid[1], mid[2], mid[3]))
        i = j
    return seqs, reps, collisions


def _lookup_neighbors(by_group, key, target_seq: int):
    grp = by_group.get(key)
    if not grp:
        return None, None
    seqs, reps = grp
    i = bisect.bisect_left(seqs, target_seq)
    prev = None
    nxt = None
    if i > 0:
        doc, raw, d = reps[i - 1]
        prev = {"document_number": doc, "document_number_raw": raw, "sequence": seqs[i - 1], "date": d}
    if i < len(seqs):
        doc, raw, d = reps[i]
        nxt = {"document_number": doc, "document_number_raw": raw, "sequence": seqs[i], "date": d}
    return prev, nxt


# ── Estimation ─────────────────────────────────────────────────────────────


def _refine_with_counter(prev, nxt, seq_frac, counter_by_raw, all_dated_docs, dates_sorted):
    """Attempt the cross-station counter-window refinement. Returns
    (local_prev, local_next, target_counter_est) or None if unavailable/unsafe.
    local_prev/local_next are (date, counter, document_number) tuples.
    """
    prev_counter = counter_by_raw.get(prev["document_number_raw"])
    next_counter = counter_by_raw.get(nxt["document_number_raw"])
    if prev_counter is None or next_counter is None or next_counter <= prev_counter:
        return None

    target_counter_est = prev_counter + (next_counter - prev_counter) * seq_frac

    lo = bisect.bisect_left(dates_sorted, prev["date"])
    hi = bisect.bisect_right(dates_sorted, nxt["date"])
    candidates = [
        rec for rec in all_dated_docs[lo:hi]
        if prev_counter <= rec[1] <= next_counter
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda rec: rec[1])
    counters = [rec[1] for rec in candidates]

    j = bisect.bisect_left(counters, target_counter_est)
    if j == 0 or j == len(candidates):
        # target estimate falls outside the bounded candidate pool's own
        # counter range -- can't properly bracket it, don't fabricate one
        return None
    return candidates[j - 1], candidates[j], target_counter_est


def _estimate(prev, nxt, target_seq: int, counter_by_raw, all_dated_docs, dates_sorted):
    if prev and nxt:
        seq_span = nxt["sequence"] - prev["sequence"]
        seq_frac = (target_seq - prev["sequence"]) / seq_span if seq_span else 0.5
        prev_d = date.fromisoformat(prev["date"])
        next_d = date.fromisoformat(nxt["date"])

        refined = _refine_with_counter(prev, nxt, seq_frac, counter_by_raw, all_dated_docs, dates_sorted)
        if refined:
            local_prev, local_next, target_counter_est = refined
            lp_date, lp_counter, _ = local_prev
            ln_date, ln_counter, _ = local_next
            lp_d = date.fromisoformat(lp_date)
            ln_d = date.fromisoformat(ln_date)
            counter_span = ln_counter - lp_counter
            local_frac = (target_counter_est - lp_counter) / counter_span if counter_span else 0.5
            local_frac = min(1.0, max(0.0, local_frac))
            bracket_days = (ln_d - lp_d).days
            estimated = lp_d + timedelta(days=round(bracket_days * local_frac))
            return estimated.isoformat(), "interpolated_refined", abs(bracket_days), bracket_days < 0

        bracket_days = (next_d - prev_d).days
        estimated = prev_d + timedelta(days=round(bracket_days * seq_frac))
        return estimated.isoformat(), "interpolated", abs(bracket_days), bracket_days < 0

    if prev or nxt:
        only = prev or nxt
        return only["date"], "extrapolated", None, False

    return None, "unresolvable", None, False


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: python3 -m src.missing_mrn_estimate <file.ndjson> [...] > output.ndjson\n")
        sys.exit(1)

    paths = sys.argv[1:]
    if sys.stdout.isatty():
        sys.stderr.write("ERROR: redirect stdout to a file (e.g. ... > output.ndjson)\n")
        sys.exit(1)

    out = sys.stdout

    known_docnums: set[str] = set()
    referenced_mrns: set[str] = set()
    raw_index: dict[tuple[str, str, bool], list[tuple[int, str, str, str]]] = defaultdict(list)
    date_by_raw: dict[str, str] = {}
    canonical_by_raw: dict[str, str] = {}
    counter_by_raw: dict[str, int] = {}

    for path in paths:
        sys.stderr.write(f"Processing {path} ...\n")
        for obj in _iter_json_lines(path):
            if "Message Attributes" in obj:
                # raw extractor line -- only source of _dash_counters.counter
                attrs = obj.get("Message Attributes") or {}
                doc_raw = attrs.get("Document Number")
                dash = obj.get("_dash_counters") or {}
                counter = dash.get("counter")
                if doc_raw and counter is not None:
                    counter_by_raw[doc_raw] = counter
                continue

            # all-mrns-shaped line
            doc = obj.get("document_number") or ""
            doc_raw = obj.get("document_number_raw") or ""
            date_str = obj.get("date") or ""
            refs = obj.get("extracted_references") or []

            if doc:
                known_docnums.add(doc)
            if refs:
                referenced_mrns.update(refs)
            if doc_raw and date_str:
                date_by_raw[doc_raw] = date_str
                canonical_by_raw[doc_raw] = doc

            if date_str:
                parsed = parse_canonical_mrn(doc)
                if parsed:
                    year, station, is_airgram, seq = parsed
                    raw_index[(station, year, is_airgram)].append((seq, doc, doc_raw, date_str))

    sys.stderr.write("Finalizing station/year sequence index ...\n")
    by_group: dict[tuple[str, str, bool], tuple[list[int], list[tuple[str, str, str]]]] = {}
    total_collisions = 0
    for key, entries in raw_index.items():
        seqs, reps, collisions = _finalize_group(entries)
        by_group[key] = (seqs, reps)
        total_collisions += collisions

    all_dated_docs = [
        (d, counter_by_raw[raw], canonical_by_raw.get(raw, raw))
        for raw, d in date_by_raw.items()
        if raw in counter_by_raw
    ]
    all_dated_docs.sort(key=lambda rec: rec[0])
    dates_sorted = [rec[0] for rec in all_dated_docs]

    missing = referenced_mrns - known_docnums
    sys.stderr.write(f"Resolving {len(missing):,} missing MRNs ...\n")

    coverage = CoverageTracker()
    coverage.record_index(len(known_docnums), len(referenced_mrns), total_collisions)

    def sort_key(mrn: str):
        parsed = parse_canonical_mrn(mrn)
        if parsed:
            year, station, is_airgram, seq = parsed
            return (0, station, year, is_airgram, seq)
        return (1, mrn)

    for mrn in sorted(missing, key=sort_key):
        parsed = parse_canonical_mrn(mrn)
        if not parsed:
            # Not expected against real corpus data (validated against 100%
            # of extracted_references tokens) -- handled defensively rather
            # than raising, since a malformed reference should degrade
            # gracefully, not crash a multi-hour-adjacent pipeline run.
            result = {
                "mrn": mrn, "station": None, "year": None, "is_airgram": None,
                "sequence": None, "estimated_date": None, "estimate_type": "unparseable",
                "accuracy_days": None, "date_order_inverted": False, "prev_known": None, "next_known": None,
            }
            out.write(json.dumps(result, ensure_ascii=False) + "\n")
            continue

        year, station, is_airgram, seq = parsed
        prev, nxt = _lookup_neighbors(by_group, (station, year, is_airgram), seq)
        estimated_date, estimate_type, accuracy_days, date_order_inverted = _estimate(
            prev, nxt, seq, counter_by_raw, all_dated_docs, dates_sorted
        )
        coverage.record_estimate(mrn, year, is_airgram, estimate_type, accuracy_days, date_order_inverted)

        result = {
            "mrn": mrn,
            "station": station,
            "year": year,
            "is_airgram": is_airgram,
            "sequence": seq,
            "estimated_date": estimated_date,
            "estimate_type": estimate_type,
            "accuracy_days": accuracy_days,
            "date_order_inverted": date_order_inverted,
            "prev_known": (
                {"document_number": prev["document_number"], "sequence": prev["sequence"], "date": prev["date"]}
                if prev else None
            ),
            "next_known": (
                {"document_number": nxt["document_number"], "sequence": nxt["sequence"], "date": nxt["date"]}
                if nxt else None
            ),
        }
        out.write(json.dumps(result, ensure_ascii=False) + "\n")

    coverage.print_report(paths, None)


if __name__ == "__main__":
    main()
