"""Main extraction engine — iterates over txt/tel files and runs the rebulk pipeline."""

try:
    import orjson as json
except ImportError:
    import json

import os
import sys
import random
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed

from .builder import build_rebulk
from .coverage import CoverageTracker
from .serializer import result_to_dict, is_na_value

_REBULK_INSTANCE = None


def extract_from_text(text, context=None):
    global _REBULK_INSTANCE
    if _REBULK_INSTANCE is None:
        _REBULK_INSTANCE = build_rebulk()
    matches = _REBULK_INSTANCE.matches(text, context=context or {})
    return matches


_WORKER_REBULK = None


def process_file(filepath):
    """Worker function: parses a single file and returns (json_str, coverage_dict)."""
    global _WORKER_REBULK

    if _WORKER_REBULK is None:
        _WORKER_REBULK = build_rebulk()

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()

        matches = _WORKER_REBULK.matches(text)

        matched_positions = bytearray(len(text))
        for match in matches:
            if not match.private and not match.marker:
                for pos in range(match.start, match.end):
                    matched_positions[pos] = 1

        matched_bytes = sum(matched_positions)
        matched_doc = 1 if matches else 0

        field_counts = {}
        seen = set()
        for match in matches:
            if match.private or match.marker:
                continue
            name = match.name
            if name and name not in seen and not is_na_value(name, match.value):
                seen.add(name)
                field_counts[name] = 1

        coverage = {
            "total_documents": 1,
            "matched_documents": matched_doc,
            "total_bytes": len(text),
            "matched_bytes": matched_bytes,
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
        help="Limit number of files to process",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Randomly sample N files (overrides --limit)",
    )

    args = parser.parse_args()

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
                tracker.total_documents += coverage["total_documents"]
                tracker.matched_documents += coverage["matched_documents"]
                tracker.total_bytes += coverage["total_bytes"]
                tracker.matched_bytes += coverage["matched_bytes"]
                for name, count in coverage["field_counts"].items():
                    tracker.field_counts[name] += count

            if output:
                print(output)

    summary = tracker.summary()
    for key, value in summary.items():
        if key == "field_match_rates":
            sys.stderr.write(f"{key}:\n")
            for k, v in value.items():
                sys.stderr.write(f"    {k}: {v:.2f}\n")
        else:
            if isinstance(value, float):
                sys.stderr.write(f"{key}: {value:.2f}\n")
            else:
                sys.stderr.write(f"{key}: {value}\n")


if __name__ == "__main__":
    main()
