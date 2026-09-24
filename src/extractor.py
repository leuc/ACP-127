"""Main extraction engine — iterates over txt/tel files and runs the rebulk pipeline."""

try:
    import orjson as json
except ImportError:
    import json

import datetime
import io
import os
import sys
import random
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed

from .builder import build_rebulk
from .coverage import (
    CoverageTracker,
    calculate_coverage,
    count_fields,
    has_substantive_match,
)
from .serializer import result_to_dict

# One process-local cached provider for both extract_from_text (in-process
# callers: tests/REPL) and process_file (forked ProcessPoolExecutor
# workers inherit the parent's instance; spawn workers build their own on
# first use). Never construct one Rebulk per file.
_REBULK = None


def _get_rebulk():
    global _REBULK
    if _REBULK is None:
        _REBULK = build_rebulk()
    return _REBULK


def extract_from_text(text, context=None):
    matches = _get_rebulk().matches(text, context=context or {})
    return matches


def process_file(filepath):
    """Worker function: parses a single file and returns (json_str, coverage_dict)."""
    rebulk = _get_rebulk()

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()

        context = {}
        matches = rebulk.matches(text, context=context)

        byte_stats = calculate_coverage(
            text, matches, context.get("_coverage_ranges", ())
        )
        # Same substantive-match definition as CoverageTracker.record, so the
        # worker/parent numbers cannot drift apart.
        matched_doc = 1 if has_substantive_match(matches) else 0
        field_counts = count_fields(matches)

        coverage = {
            "total_documents": 1,
            "matched_documents": matched_doc,
            **byte_stats,
            "fully_covered_documents": int(
                byte_stats["unmatched_non_whitespace_bytes"] == 0
            ),
            "file": filepath,
            "field_counts": field_counts,
        }

        result = result_to_dict(matches)

        if result:
            result["_file"] = filepath
            output = json.dumps(result)
            if isinstance(output, bytes):
                output = output.decode("utf-8")
            return output, coverage

        return None, coverage

    except Exception as e:
        return f"ERROR: {filepath} - {str(e)}", None


def _discover_files(paths):
    """Yield all .txt and .tel files under given paths (files or directories)."""
    for path in paths:
        if not os.path.exists(path):
            sys.stderr.write(f"WARNING: {path} does not exist, skipping\n")
            continue
        if os.path.isfile(path):
            if path.endswith((".txt", ".tel")):
                yield path
        elif os.path.isdir(path):
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in sorted(filenames):
                    if filename.endswith((".txt", ".tel")):
                        yield os.path.join(dirpath, filename)
        else:
            sys.stderr.write(f"WARNING: {path} is not a file or directory, skipping\n")


def _write_dated_coverage_report(tracker):
    """Store the plaintext coverage summary under results/coverage/.

    Date-based filename per project convention; never fails the run.
    """
    try:
        buffer = io.StringIO()
        tracker.print_report(stream=buffer)
        report = buffer.getvalue()
        directory = os.path.join("results", "coverage")
        os.makedirs(directory, exist_ok=True)
        filename = "extraction-{}.txt".format(
            datetime.date.today().strftime("%Y%m%d")
        )
        with open(os.path.join(directory, filename), "w", encoding="utf-8") as f:
            f.write(report)
    except OSError as e:
        sys.stderr.write(f"WARNING: could not write coverage report: {e}\n")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract ACP-127 fields from telegram text/tel files"
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="Files or directories to process (directories are walked for *.txt/*.tel)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of files to process (applied after --sample; "
        "must be >= 0)",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Randomly sample N files with seed 0 (applied before --limit; "
        "must be >= 0)",
    )

    args = parser.parse_args()

    if args.limit is not None and args.limit < 0:
        parser.error("--limit must be >= 0")
    if args.sample is not None and args.sample < 0:
        parser.error("--sample must be >= 0")

    all_files = list(_discover_files(args.inputs))
    if not all_files:
        sys.stderr.write("No .txt or .tel files found.\n")
        sys.exit(1)

    if args.sample is not None:
        random.seed(0)
        if args.sample >= len(all_files):
            selected = all_files
        else:
            selected = random.sample(all_files, args.sample)
        files_to_process = selected
    else:
        files_to_process = all_files

    if args.limit is not None:
        files_to_process = files_to_process[: args.limit]

    cores = multiprocessing.cpu_count()
    sys.stderr.write(f"Processing {len(files_to_process)} files on {cores} cores...\n")

    tracker = CoverageTracker()

    with ProcessPoolExecutor(max_workers=cores) as executor:
        futures = [executor.submit(process_file, fp) for fp in files_to_process]
        for future in as_completed(futures):
            output, coverage = future.result()
            if isinstance(output, str) and output.startswith("ERROR:"):
                sys.stderr.write(output + "\n")
                continue

            if coverage:
                tracker.record_summary(coverage)

            if output:
                print(output)

    tracker.print_report()
    # Persist the plaintext summary only for full runs (no --limit/--sample
    # slicing); sampled smoke tests must not clobber the dated baseline.
    if args.limit is None and args.sample is None:
        _write_dated_coverage_report(tracker)


if __name__ == "__main__":
    main()
