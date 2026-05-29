"""Batch processor with checkpoint/resume and NDJSON output."""

import json
import os
import sys

from .builder import build_rebulk
from .coverage import CoverageTracker


def _discover_files(root_dir):
    files = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in sorted(filenames):
            if filename.endswith(".txt"):
                files.append(os.path.join(dirpath, filename))
    return sorted(files)


def _load_checkpoint(checkpoint_path):
    if not checkpoint_path or not os.path.isfile(checkpoint_path):
        return -1, CoverageTracker()
    with open(checkpoint_path, "r") as f:
        data = json.load(f)
    tracker = CoverageTracker()
    state = data.get("coverage", {})
    tracker.total_documents = state.get("documents_processed", 0)
    tracker.matched_documents = state.get("documents_matched", 0)
    tracker.total_bytes = state.get("total_bytes", 0)
    tracker.matched_bytes = state.get("matched_bytes", 0)
    from collections import Counter

    tracker.field_counts = Counter(state.get("field_counts", {}))
    return data.get("file_index", -1), tracker


def _save_checkpoint(checkpoint_path, file_index, tracker):
    if not checkpoint_path:
        return
    data = {
        "file_index": file_index,
        "coverage": {
            "documents_processed": tracker.total_documents,
            "documents_matched": tracker.matched_documents,
            "total_bytes": tracker.total_bytes,
            "matched_bytes": tracker.matched_bytes,
            "field_counts": dict(tracker.field_counts),
        },
    }
    tmp = checkpoint_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, checkpoint_path)


def process_batch(
    root_dir,
    output_path,
    checkpoint_path=None,
    limit=None,
    progress_interval=10000,
):
    """Process .txt files under root_dir, writing NDJSON to output_path.

    Walks root_dir to discover all .txt files in sorted order.
    Supports checkpoint/resume — skips already-processed files
    when checkpoint_path points to a prior checkpoint file.
    """
    start_index, tracker = _load_checkpoint(checkpoint_path)
    rebulk = build_rebulk()

    sys.stderr.write(f"Discovering .txt files under {root_dir}...\n")
    all_files = _discover_files(root_dir)
    sys.stderr.write(f"Found {len(all_files)} .txt files\n")

    resume = start_index >= 0
    if resume:
        sys.stderr.write(
            f"Resuming from file index {start_index} "
            f"({len(all_files) - start_index - 1} remaining)\n"
        )

    out_file = open(output_path, "a" if resume else "w")
    count = 0

    for i, filepath in enumerate(all_files):
        if resume and i <= start_index:
            continue

        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except Exception as e:
            sys.stderr.write(f"ERROR reading {filepath}: {e}\n")
            continue

        try:
            matches = rebulk.matches(text)
        except Exception as e:
            sys.stderr.write(f"ERROR matching {filepath}: {e}\n")
            continue

        tracker.record(text, matches)
        result = _result_to_dict(matches)
        result["_file"] = filepath
        out_file.write(json.dumps(result, default=str) + "\n")

        count += 1
        if count % progress_interval == 0:
            summary = tracker.summary()
            elapsed = i + 1 - (start_index + 1 if resume else 0)
            total = len(all_files) - (start_index + 1 if resume else 0)
            pct = (elapsed / total * 100) if total > 0 else 0
            sys.stderr.write(
                f"[{elapsed}/{total} ({pct:.0f}%)] "
                f"doc_cov={summary['document_coverage_pct']}% "
                f"byte_cov={summary['byte_coverage_pct']}%\n"
            )

        if checkpoint_path:
            _save_checkpoint(checkpoint_path, i, tracker)

        if limit and count >= limit:
            break

    out_file.close()

    summary = tracker.summary()
    summary["files_found"] = len(all_files)
    summary["files_processed"] = count
    return summary


def _result_to_dict(matches):
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
