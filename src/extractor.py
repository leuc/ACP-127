"""Main extraction engine — iterates over txt/tel files and runs the rebulk pipeline."""

try:
    import orjson as json
except ImportError:
    import json

import os
import sys
import random

from .builder import build_rebulk
from .coverage import CoverageTracker
from .serializer import result_to_dict


def extract_from_text(text, context=None):
    rebulk = build_rebulk()
    matches = rebulk.matches(text, context=context or {})
    return matches


def _discover_files(paths):
    """Yield all .txt and .tel files under given paths (files or directories)."""
    for path in paths:
        if os.path.isfile(path):
            if path.endswith((".txt", ".tel")):
                yield path
        elif os.path.isdir(path):
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in sorted(filenames):
                    if filename.endswith((".txt", ".tel")):
                        yield os.path.join(dirpath, filename)
        # If the path does not exist, we simply skip it (no warning)


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

    # Discover all candidate files
    all_files = list(_discover_files(args.inputs))
    if not all_files:
        sys.stderr.write("No .txt or .tel files found.\n")
        sys.exit(1)

    # Discover all candidate files
    all_files = list(_discover_files(args.inputs))
    if not all_files:
        sys.stderr.write("No .txt or .tel files found.\n")
        sys.exit(1)

    # Apply sampling if requested
    if args.sample is not None:
        random.seed(0)  # deterministic sampling
        if args.sample >= len(all_files):
            selected = all_files
        else:
            selected = random.sample(all_files, args.sample)
        files_to_process = selected
    else:
        files_to_process = all_files

    # Apply limit if requested (after sampling)
    if args.limit is not None:
        files_to_process = files_to_process[: args.limit]

    rebulk = build_rebulk()
    tracker = CoverageTracker()
    processed = 0

    for filepath in files_to_process:
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except Exception as e:
            # Skip file on read error
            continue

        try:
            matches = rebulk.matches(text)
        except Exception as e:
            # Skip file on match error
            continue

        tracker.record(text, matches)
        result = result_to_dict(matches)
        if result:
            result["_file"] = filepath
            # Output result as JSON line to stdout
            output = json.dumps(result)
            if isinstance(output, bytes):
                output = output.decode("utf-8")
            print(output)

        processed += 1

    # Final coverage to stderr
    summary = tracker.summary()
    coverage_output = json.dumps({"coverage": summary})
    if isinstance(coverage_output, bytes):
        coverage_output = coverage_output.decode("utf-8")
    sys.stderr.write(coverage_output + "\n")


if __name__ == "__main__":
    main()
