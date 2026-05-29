"""Main extraction engine — iterates over txt files and runs the rebulk pipeline."""

try:
    import orjson as json
except ImportError:
    import json

import os
import sys

from .builder import build_rebulk
from .coverage import CoverageTracker
from .serializer import result_to_dict


def extract_from_text(text, context=None):
    rebulk = build_rebulk()
    matches = rebulk.matches(text, context=context or {})
    return matches


def extract_file(filepath):
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    matches = extract_from_text(text)
    tracker = CoverageTracker()
    tracker.record(text, matches)
    return {
        "path": filepath,
        "matches": matches,
        "result": result_to_dict(matches),
        "coverage": tracker.summary(),
    }


def process_documents(root_dir, limit=None):
    rebulk = build_rebulk()
    tracker = CoverageTracker()
    results = []
    count = 0

    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in sorted(filenames):
            if not filename.endswith(".txt"):
                continue

            filepath = os.path.join(dirpath, filename)
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()

            matches = rebulk.matches(text)
            tracker.record(text, matches)
            result = result_to_dict(matches)
            if result:
                result["_file"] = filepath
                results.append(result)

            count += 1
            if limit and count >= limit:
                break
        if limit and count >= limit:
            break

    return {
        "coverage": tracker.summary(),
        "results": results,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract ACP-127 fields from telegram text files"
    )
    parser.add_argument("root_dir", help="Root directory of txtv2 files")
    parser.add_argument(
        "--limit", type=int, default=None, help="Limit number of files to process"
    )
    parser.add_argument("--output", default="-", help="Output file (default: stdout)")
    parser.add_argument("--single", help="Process a single file")
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Use index.csv for file discovery with NDJSON output",
    )
    parser.add_argument(
        "--checkpoint",
        default=None,
        help="Checkpoint file for batch resume",
    )
    parser.add_argument(
        "--progress",
        type=int,
        default=10000,
        help="Progress report interval (default: 10000)",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Randomly sample N files (overrides --limit)",
    )
    args = parser.parse_args()

    if args.single:
        result = extract_file(args.single)
        result["result"]["_file"] = args.single
        output = json.dumps(
            {
                "coverage": result["coverage"],
                "results": [result["result"]],
            }
        ).decode("utf-8")
        if args.output == "-":
            print(output)
        else:
            with open(args.output, "w") as f:
                f.write(output)
        return

    if args.batch or args.sample:
        if args.output == "-":
            print("--batch/--sample requires --output FILE", file=sys.stderr)
            sys.exit(1)
        from .batch import process_batch

        summary = process_batch(
            args.root_dir,
            output_path=args.output,
            checkpoint_path=args.checkpoint,
            limit=args.limit,
            progress_interval=args.progress,
            sample=args.sample,
        )
        summary_path = args.checkpoint or (args.output + ".summary.json")
        output = json.dumps(
            {
                "coverage": {
                    "documents_processed": summary.get("files_processed", 0),
                    "documents_matched": summary.get("documents_matched", 0),
                    "document_coverage_pct": summary.get("document_coverage_pct", 0.0),
                    "byte_coverage_pct": summary.get("byte_coverage_pct", 0.0),
                    "field_match_rates": summary.get("field_match_rates", {}),
                },
                "results": [],
            }
        ).decode("utf-8")
        with open(summary_path, "w") as f:
            f.write(output)
        print(output)
        return

    data = process_documents(args.root_dir, limit=args.limit)
    output = json.dumps(
        {
            "coverage": data["coverage"],
            "results": data["results"][:100]
            if len(data["results"]) > 100
            else data["results"],
        }
    ).decode("utf-8")

    if args.output == "-":
        print(output)
    else:
        with open(args.output, "w") as f:
            f.write(output)


if __name__ == "__main__":
    main()
