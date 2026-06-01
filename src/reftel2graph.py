#!/usr/bin/env python3
import sys
import json
import os
import igraph


def main():
    if len(sys.argv) != 3:
        sys.stderr.write(f"Usage: {sys.argv[0]} ref.json output.graphml\n")
        sys.exit(1)

    src = sys.argv[1]
    dest = sys.argv[2]

    if not os.path.exists(src):
        sys.stderr.write(f"Error: Input file not found: {src}\n")
        sys.exit(1)
    if os.path.exists(dest):
        sys.stderr.write(f"Error: Output file already exists: {dest}\n")
        sys.exit(1)

    vertices = set()
    primary_docs = set()  # Track IDs that exist as a document_number
    edges = set()
    node_dates = {}
    node_previews = {}
    count = 0

    with open(src, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            row = json.loads(line)
            doc = row.get("document_number")

            if not doc:
                continue

            refs = row.get("extracted_references")
            if not refs:
                continue

            # Mark this document as a known primary node
            primary_docs.add(doc)
            vertices.add(doc)

            doc_date = row.get("date")
            if doc_date:
                node_dates[doc] = doc_date

            doc_preview = row.get("message_preview")
            if doc_preview:
                node_previews[doc] = doc_preview

            for r in refs:
                edges.add((doc, r))
                vertices.add(r)

            count += 1
            if count % 500000 == 0:
                sys.stderr.write(f"  {count} lines...\n")

    sys.stderr.write(
        f"\nVertices: {len(vertices)} (Primary: {len(primary_docs)}), Edges: {len(edges)}\n"
    )

    ids = sorted(vertices)
    idx = {v: i for i, v in enumerate(ids)}

    edge_list = [(idx[f], idx[t]) for f, t in sorted(edges)]

    sys.stderr.write("Building graph...\n")
    g = igraph.Graph(edge_list, directed=True)

    # Map node properties
    g.vs["label"] = ids
    g.vs["date"] = [node_dates.get(vid, "") for vid in ids]
    g.vs["message_preview"] = [node_previews.get(vid, "") for vid in ids]

    # Flag missing documents: True if it ONLY appeared as a reference
    g.vs["missing"] = [vid not in primary_docs for vid in ids]

    sys.stderr.write(f"Saving {dest}...\n")
    g.write_graphml(dest)


if __name__ == "__main__":
    main()
