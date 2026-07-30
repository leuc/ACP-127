#!/usr/bin/env python3
"""Test the hypothesis: cables that reference each other share the same or
similar combinations of TAGS.

Joins results/<year>.tags.norm.ndjson (document_number -> classified TAGS,
from src.tags_normalize) with results/<year>.reftel.norm.ndjson
(document_number -> extracted_references, from src.reftel_normalize) on the
shared, identically-normalized document_number key, then compares each
citing document's TAGS code set against each of its referenced documents'
TAGS code sets (Jaccard similarity), against a random-pair baseline drawn
from the same document pool.

Reports three code-set views per pair, since geographic overlap between two
cables about the same country is a much less interesting signal than subject
(aboutness) overlap:
  - all:     every TAGS code (subject, geographic, organization, person, ...)
  - subject: only permanent/temporary/wildcard-field subject codes
  - geo:     only confirmed geographic codes

    Usage::

        python3 -m src.tags_reference_similarity [--results-dir results]
            [--years 1973 1974 ...] [--sample N] [--seed S]
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

_SUBJECT_TYPES = {
    "permanent", "temporary", "economic", "military", "political", "social", "technology",
}

# Named views of the type taxonomy from tags_normalize.py, each checked both as
# an aggregate Jaccard-similarity view and as a per-code lift breakdown, so we
# can see exactly which kinds (and which individual codes) do NOT support the
# "referencing cables share TAGS" hypothesis.
_TYPE_GROUPS = {
    "subject": _SUBJECT_TYPES,
    "geo": {"geographic"},
    "organization": {"organization"},
    "person": {"person"},
    "annotation": {"annotation"},
    "unknown": {"unknown"},
    "other": {"other"},
}

_ALL_YEARS = [1973, 1974, 1975, 1976, 1977, 1978, 1979]


def load_tags(path: Path) -> dict[str, list[tuple[str, str, str | None]]]:
    """document_number -> list of (code, type, name) tuples."""
    result = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            doc = d.get("document_number")
            if not doc:
                continue
            entries = [
                (t["code"], t.get("type"), t.get("name"))
                for t in (d.get("tags") or [])
                if t.get("code")
            ]
            result[doc] = entries
    return result


def view_codes(entries: list[tuple[str, str, str | None]], view: str) -> set[str]:
    """Codes from `entries` belonging to `view` ("all" or a _TYPE_GROUPS key)."""
    if view == "all":
        return {code for code, _, _ in entries}
    types = _TYPE_GROUPS[view]
    return {code for code, ttype, _ in entries if ttype in types}


def load_references(path: Path) -> dict[str, list[str]]:
    """document_number -> list of referenced document_numbers."""
    result = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            doc = d.get("document_number")
            refs = d.get("extracted_references")
            if doc and refs:
                result[doc] = refs
    return result


def jaccard(a: set, b: set) -> float | None:
    """Jaccard similarity, or None if both sets are empty (undefined)."""
    if not a and not b:
        return None
    union = a | b
    if not union:
        return None
    return len(a & b) / len(union)


class PairStats:
    """Accumulates Jaccard scores for one code-set view (all/subject/geo)."""

    def __init__(self):
        self.scores: list[float] = []
        self.any_overlap = 0
        self.majority_overlap = 0  # jaccard >= 0.5
        self.identical = 0  # jaccard == 1.0
        self.both_empty = 0

    def add(self, a: set, b: set):
        score = jaccard(a, b)
        if score is None:
            self.both_empty += 1
            return
        self.scores.append(score)
        if score > 0:
            self.any_overlap += 1
        if score >= 0.5:
            self.majority_overlap += 1
        if score == 1.0:
            self.identical += 1

    def summary(self) -> dict:
        n = len(self.scores)
        if n == 0:
            return {"n": 0}
        return {
            "n": n,
            "both_empty": self.both_empty,
            "mean": statistics.mean(self.scores),
            "median": statistics.median(self.scores),
            "stdev": statistics.stdev(self.scores) if n > 1 else 0.0,
            "any_overlap_pct": self.any_overlap / n * 100,
            "majority_overlap_pct": self.majority_overlap / n * 100,
            "identical_pct": self.identical / n * 100,
        }


def main():
    parser = argparse.ArgumentParser(
        description="Test whether referencing cables share similar TAGS combinations."
    )
    parser.add_argument("--results-dir", default="results", help="Directory with *.tags.norm.ndjson and *.reftel.norm.ndjson")
    parser.add_argument("--years", nargs="+", type=int, default=_ALL_YEARS, help="Years to include")
    parser.add_argument("--sample", type=int, default=None, help="Sample this many citing documents (evenly across years); default: use all")
    parser.add_argument("--seed", type=int, default=0, help="Random seed for sampling and the baseline")
    parser.add_argument("--per-code", action="store_true", help="Also report per-individual-code lift (actual vs random co-occurrence), to find specific codes that carry no signal")
    parser.add_argument("--per-code-min-n", type=int, default=200, help="Minimum actual-pair occurrences for a code to be included in the per-code report")
    parser.add_argument("--per-code-top", type=int, default=25, help="How many lowest-lift codes to print")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    rng = random.Random(args.seed)

    sys.stderr.write(f"Loading tags for years {args.years} ...\n")
    tags_by_doc: dict[str, list[tuple[str, str]]] = {}
    for year in args.years:
        path = results_dir / f"{year}.tags.norm.ndjson"
        if not path.exists():
            sys.stderr.write(f"  WARNING: {path} not found, skipping\n")
            continue
        year_tags = load_tags(path)
        sys.stderr.write(f"  {path}: {len(year_tags):,} documents\n")
        tags_by_doc.update(year_tags)

    sys.stderr.write(f"Loading references for years {args.years} ...\n")
    refs_by_doc: dict[str, list[str]] = {}
    for year in args.years:
        path = results_dir / f"{year}.reftel.norm.ndjson"
        if not path.exists():
            sys.stderr.write(f"  WARNING: {path} not found, skipping\n")
            continue
        year_refs = load_references(path)
        sys.stderr.write(f"  {path}: {len(year_refs):,} documents with references\n")
        refs_by_doc.update(year_refs)

    sys.stderr.write(f"Total documents with tags: {len(tags_by_doc):,}\n")
    sys.stderr.write(f"Total documents with references: {len(refs_by_doc):,}\n")

    # Citing documents: have both tags of their own AND at least one reference.
    citing_docs = [d for d in refs_by_doc if d in tags_by_doc]
    sys.stderr.write(f"Citing documents with own tags: {len(citing_docs):,}\n")

    if args.sample is not None and args.sample < len(citing_docs):
        citing_docs = rng.sample(citing_docs, args.sample)
        sys.stderr.write(f"Sampled down to {len(citing_docs):,} citing documents\n")

    all_doc_keys = list(tags_by_doc.keys())

    views = ["all"] + list(_TYPE_GROUPS.keys())
    actual = {v: PairStats() for v in views}
    random_baseline = {v: PairStats() for v in views}

    # Per-code lift accounting (only used with --per-code): for each code,
    # how often does the cited/random document ALSO carry that code, given
    # the citing document does?
    code_name: dict[str, str] = {}
    actual_code_total: dict[str, int] = {}
    actual_code_hit: dict[str, int] = {}
    random_code_total: dict[str, int] = {}
    random_code_hit: dict[str, int] = {}

    resolved_ref_pairs = 0
    total_ref_pairs = 0
    citing_docs_with_resolved_ref = 0

    for doc in citing_docs:
        doc_entries = tags_by_doc[doc]
        doc_views = {v: view_codes(doc_entries, v) for v in views}
        if args.per_code:
            for code, _, name in doc_entries:
                if name:
                    code_name[code] = name
                else:
                    code_name.setdefault(code, code)
        refs = refs_by_doc[doc]
        had_resolved = False
        for ref in refs:
            total_ref_pairs += 1
            ref_entries = tags_by_doc.get(ref)
            if ref_entries is None:
                continue  # referenced doc not in our tagged corpus
            resolved_ref_pairs += 1
            had_resolved = True
            ref_all = view_codes(ref_entries, "all")
            for view in views:
                actual[view].add(doc_views[view], view_codes(ref_entries, view))

            # Random baseline: one random other document per resolved reference,
            # compared against the SAME citing document, for a fair comparison.
            random_doc = rng.choice(all_doc_keys)
            random_entries = tags_by_doc[random_doc]
            random_all = view_codes(random_entries, "all")
            for view in views:
                random_baseline[view].add(doc_views[view], view_codes(random_entries, view))

            if args.per_code:
                for code in doc_views["all"]:
                    actual_code_total[code] = actual_code_total.get(code, 0) + 1
                    if code in ref_all:
                        actual_code_hit[code] = actual_code_hit.get(code, 0) + 1
                    random_code_total[code] = random_code_total.get(code, 0) + 1
                    if code in random_all:
                        random_code_hit[code] = random_code_hit.get(code, 0) + 1
        if had_resolved:
            citing_docs_with_resolved_ref += 1

    print("=== TAGS Reference-Similarity Test ===")
    print(f"Years: {args.years}")
    print(f"Citing documents considered: {len(citing_docs):,}")
    print(
        f"Citing documents with >=1 in-corpus resolved reference: "
        f"{citing_docs_with_resolved_ref:,} "
        f"({citing_docs_with_resolved_ref / len(citing_docs) * 100:.2f}%)"
    )
    print(
        f"Reference pairs: {total_ref_pairs:,} total, "
        f"{resolved_ref_pairs:,} resolved to an in-corpus tagged document "
        f"({resolved_ref_pairs / total_ref_pairs * 100:.2f}%)"
    )
    print()

    for view in views:
        a = actual[view].summary()
        r = random_baseline[view].summary()
        print(f"--- {view} codes ---")
        if a["n"] == 0:
            print("  no data")
            continue
        print(f"  {'':20s} {'actual references':>20s} {'random baseline':>20s}")
        print(f"  {'n pairs':20s} {a['n']:>20,} {r['n']:>20,}")
        print(f"  {'mean Jaccard':20s} {a['mean']:>20.4f} {r['mean']:>20.4f}")
        print(f"  {'median Jaccard':20s} {a['median']:>20.4f} {r['median']:>20.4f}")
        print(f"  {'stdev':20s} {a['stdev']:>20.4f} {r['stdev']:>20.4f}")
        print(f"  {'any overlap %':20s} {a['any_overlap_pct']:>19.2f}% {r['any_overlap_pct']:>19.2f}%")
        print(f"  {'>=50% overlap %':20s} {a['majority_overlap_pct']:>19.2f}% {r['majority_overlap_pct']:>19.2f}%")
        print(f"  {'identical %':20s} {a['identical_pct']:>19.2f}% {r['identical_pct']:>19.2f}%")
        lift = (a["mean"] / r["mean"]) if r["mean"] > 0 else float("inf")
        print(f"  mean Jaccard lift (actual / random): {lift:.2f}x")
        print()

    if args.per_code:
        rows = []
        for code, total in actual_code_total.items():
            if total < args.per_code_min_n:
                continue
            actual_rate = actual_code_hit.get(code, 0) / total
            rtotal = random_code_total.get(code, 0)
            random_rate = (random_code_hit.get(code, 0) / rtotal) if rtotal else 0.0
            lift = (actual_rate / random_rate) if random_rate > 0 else float("inf")
            rows.append((lift, code, code_name.get(code, code), total, actual_rate, random_rate))
        rows.sort(key=lambda row: row[0])

        print(f"=== Per-code lift: P(cited also has code | citing has code), actual vs random ===")
        print(f"(codes with >= {args.per_code_min_n} actual-pair occurrences; showing {args.per_code_top} LOWEST-lift codes = weakest support for the hypothesis)")
        print(f"  {'code':10s} {'n':>8s} {'actual P':>10s} {'random P':>10s} {'lift':>8s}  name")
        for lift, code, name, total, actual_rate, random_rate in rows[: args.per_code_top]:
            lift_str = "inf" if lift == float("inf") else f"{lift:.2f}x"
            print(f"  {code:10s} {total:>8,} {actual_rate:>10.3f} {random_rate:>10.3f} {lift_str:>8s}  {name}")
        print()
        print(f"  ({len(rows):,} codes met the minimum-n threshold out of {len(actual_code_total):,} total distinct codes seen)")


if __name__ == "__main__":
    main()
