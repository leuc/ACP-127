"""Main extraction engine — iterates over txt files and runs the rebulk pipeline."""

import json
import os
import sys

from .builder import build_rebulk
from .coverage import CoverageTracker


def extract_from_text(text, context=None):
    rebulk = build_rebulk()
    matches = rebulk.matches(text, context=context or {})
    return matches


def extract_file(filepath):
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    matches = extract_from_text(text)
    return {"path": filepath, "matches": matches, "result": result_to_dict(matches)}


def result_to_dict(matches):
    attributes = {}
    others = {}
    for match in matches:
        if match.private or match.marker or match.parent:
            continue
        name = match.name
        if not name:
            continue
        value = match.value
        if value is not None and isinstance(value, str):
            value = value.strip()
            if value.startswith(name + ":"):
                value = value[len(name) + 1 :].strip()
        if match.tags and "attribute" in match.tags:
            attributes[name] = value
        else:
            others["_" + name] = value
    result = {"Message Attributes": attributes}
    result.update(others)
    return result


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
    args = parser.parse_args()

    if args.single:
        result = extract_file(args.single)
        output = json.dumps(result["result"], indent=2)
        if args.output == "-":
            print(output)
        else:
            with open(args.output, "w") as f:
                f.write(output)
        return

    if args.batch:
        if args.output == "-":
            print("--batch requires --output FILE", file=sys.stderr)
            sys.exit(1)
        from .batch import process_batch

        summary = process_batch(
            args.root_dir,
            output_path=args.output,
            checkpoint_path=args.checkpoint,
            limit=args.limit,
            progress_interval=args.progress,
        )
        summary_path = args.checkpoint or (args.output + ".summary.json")
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)
        print(json.dumps(summary, indent=2))
        return

    data = process_documents(args.root_dir, limit=args.limit)
    output = json.dumps(
        {
            "coverage": data["coverage"],
            "count": len(data["results"]),
            "results": data["results"][:100]
            if len(data["results"]) > 100
            else data["results"],
        },
        indent=2,
    )

    if args.output == "-":
        print(output)
    else:
        with open(args.output, "w") as f:
            f.write(output)


if __name__ == "__main__":
    main()
