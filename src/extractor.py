"""Main extraction engine — iterates over txt files and runs the rebulk pipeline."""

import json
import os

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
    result = {}
    for match in matches:
        if match.private or match.marker or match.parent:
            continue
        name = match.name
        if not name or name in ("attribute", "message_content"):
            continue
        value = match.value
        if value is not None and isinstance(value, str):
            value = value.strip()
        result[name] = value
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
    parser.add_argument(
        "--output", default="-", help="Output JSON file (default: stdout)"
    )
    parser.add_argument("--single", help="Process a single file")
    args = parser.parse_args()

    if args.single:
        result = extract_file(args.single)
        output = json.dumps(result["result"], indent=2)
    else:
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
