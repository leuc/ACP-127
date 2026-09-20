"""Report provided Message Attributes missing from body extraction.

This is a semantic complement to byte coverage: a document can have complete
byte coverage while a header field supplied in Message Attributes failed to
produce its independently extracted body field.
"""

import argparse
from collections import Counter
import sys

try:
    import orjson as json
except ImportError:
    import json

from .coverage import (
    ATTRIBUTE_BODY_FIELDS,
    has_retrievable_body,
    missing_body_extractions,
)


def _loads(line):
    return json.loads(line)


def _dumps(value):
    output = json.dumps(value)
    if isinstance(output, bytes):
        return output.decode("utf-8")
    return output


def _documents(paths):
    for path in paths:
        if path == "-":
            for line_number, line in enumerate(sys.stdin.buffer, 1):
                if line.strip():
                    yield "<stdin>", line_number, _loads(line)
            continue

        with open(path, "rb") as source:
            for line_number, line in enumerate(source, 1):
                if line.strip():
                    yield path, line_number, _loads(line)


def _write_report(stream, inputs, documents, eligible, counts, cable_count):
    field_map = dict(ATTRIBUTE_BODY_FIELDS)
    lines = [
        "Attribute/body extraction completeness",
        f"inputs: {', '.join(inputs)}",
        f"documents_processed: {documents}",
        f"documents_with_retrievable_body: {eligible}",
        f"cables_with_missing_body_extractions: {cable_count}",
        f"missing_body_extractions: {sum(counts.values())}",
        "missing_by_field:",
    ]
    for attribute_name, _body_field in ATTRIBUTE_BODY_FIELDS:
        lines.append(
            f"    {attribute_name} -> {field_map[attribute_name]}: "
            f"{counts[attribute_name]}"
        )
    stream.write("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Find retrievable telegrams where a supplied Message Attribute "
            "has no corresponding body-extracted field"
        )
    )
    parser.add_argument("inputs", nargs="+", help="Extractor NDJSON files, or -")
    args = parser.parse_args()

    documents = 0
    eligible = 0
    counts = Counter()
    cable_count = 0

    for input_path, line_number, document in _documents(args.inputs):
        documents += 1
        attributes = document.get("Message Attributes") or {}
        if has_retrievable_body(document):
            eligible += 1

        missing = missing_body_extractions(document)
        if not missing:
            continue

        filepath = document.get("_file")
        cable_count += 1
        for issue in missing:
            counts[issue["attribute"]] += 1
        sys.stdout.write(
            _dumps(
                {
                    "file": filepath or f"{input_path}:{line_number}",
                    "document_number": attributes.get("Document Number"),
                    "missing": missing,
                }
            )
            + "\n"
        )

    _write_report(
        sys.stderr,
        args.inputs,
        documents,
        eligible,
        counts,
        cable_count,
    )


if __name__ == "__main__":
    main()
