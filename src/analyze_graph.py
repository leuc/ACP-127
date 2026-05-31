#!/usr/bin/env python3
"""Analyze the reference graph: connectivity, clustering, giant component."""

import sys
import os
import igraph as ig
import pandas as pd
import numpy as np
import json


def main():
    if len(sys.argv) < 2:
        sys.stderr.write(f"Usage: {sys.argv[0]} <graph.graphml>\n")
        sys.exit(1)

    path = sys.argv[1]

    if not os.path.exists(path):
        sys.stderr.write(f"GraphML not found: {path}\n")
        sys.exit(1)

    sys.stderr.write(f"Loading {path} ...\n")
    g = ig.Graph.Read_GraphML(path)
    sys.stderr.write(
        f"Vertices: {g.vcount():,}, Edges: {g.ecount():,}, Directed: {g.is_directed()}\n\n"
    )

    results = {}

    # ── Basic stats ──
    results["nodes"] = g.vcount()
    results["edges"] = g.ecount()
    results["directed"] = g.is_directed()

    # ── Weakly Connected Components ──
    sys.stderr.write("Computing WCC ...\n")
    components = g.connected_components(mode="weak")
    comp_sizes = components.sizes()
    giant_size = max(comp_sizes)
    results["total_components"] = len(comp_sizes)
    results["giant_component_size"] = giant_size
    results["giant_component_pct"] = round(giant_size / g.vcount() * 100, 2)
    results["component_size_percentiles"] = {
        "50": int(np.percentile(comp_sizes, 50)),
        "75": int(np.percentile(comp_sizes, 75)),
        "90": int(np.percentile(comp_sizes, 90)),
        "99": int(np.percentile(comp_sizes, 99)),
        "99.9": int(np.percentile(comp_sizes, 99.9)),
    }

    sys.stderr.write(f"  Components: {len(comp_sizes):,}\n")
    sys.stderr.write(f"  Giant: {giant_size:,} ({results['giant_component_pct']}%)\n")

    # ── Degree Analysis ──
    sys.stderr.write("Computing degrees ...\n")
    in_deg = g.degree(mode="in")
    out_deg = g.degree(mode="out")
    results["degree_summary"] = {
        "in": {
            "mean": round(np.mean(in_deg), 2),
            "max": int(max(in_deg)),
            "p99": int(np.percentile(in_deg, 99)),
        },
        "out": {
            "mean": round(np.mean(out_deg), 2),
            "max": int(max(out_deg)),
            "p99": int(np.percentile(out_deg, 99)),
        },
    }

    # ── Reciprocity, Transitivity, Assortativity ──
    sys.stderr.write("Computing reciprocity ...\n")
    results["reciprocity"] = round(g.reciprocity(), 4)

    sys.stderr.write("Computing transitivity ...\n")
    results["transitivity"] = round(g.transitivity_undirected(), 4)

    sys.stderr.write("Computing assortativity ...\n")
    results["assortativity"] = round(g.assortativity_degree(), 4)

    # ── K-Core ──
    sys.stderr.write("Computing k-core ...\n")
    coreness = g.coreness(mode="all")
    max_core = max(coreness)
    results["max_k_core"] = max_core

    core_dist = pd.Series(coreness).value_counts().sort_index()
    results["k_core_distribution"] = {str(k): int(v) for k, v in core_dist.items()}

    sys.stderr.write(f"  Max K-core: {max_core}\n")

    # ── PageRank ──
    sys.stderr.write("Computing PageRank ...\n")
    pr = g.pagerank(directed=True)
    labels = g.vs["label"] if "label" in g.vs.attributes() else list(range(g.vcount()))
    actors = pd.DataFrame(
        {
            "label": labels,
            "in_degree": in_deg,
            "out_degree": out_deg,
            "pagerank": pr,
            "k_core": coreness,
        }
    )

    top_broadcasters = actors.sort_values("out_degree", ascending=False).head(10)
    top_authorities = actors.sort_values("pagerank", ascending=False).head(10)

    results["top_broadcasters"] = [
        {
            "label": r["label"],
            "out_degree": int(r["out_degree"]),
            "in_degree": int(r["in_degree"]),
        }
        for _, r in top_broadcasters.iterrows()
    ]
    results["top_authorities"] = [
        {
            "label": r["label"],
            "pagerank": round(r["pagerank"], 6),
            "in_degree": int(r["in_degree"]),
        }
        for _, r in top_authorities.iterrows()
    ]

    # ── Save giant component subgraph ──
    giant_path = path.replace(".graphml", ".giant.graphml")
    sys.stderr.write(f"Saving giant component to {giant_path} ...\n")
    giant_comp_idx = int(np.argmax(comp_sizes))
    gc = g.induced_subgraph(components[giant_comp_idx])
    gc.write_graphml(giant_path)

    # ── Community detection on 3-core ──
    core3_nodes = [v.index for v in g.vs if coreness[v.index] >= 3]
    sys.stderr.write(f"3-core: {len(core3_nodes):,} nodes\n")
    results["core3_nodes"] = len(core3_nodes)

    if len(core3_nodes) >= 3:
        core3 = g.induced_subgraph(core3_nodes)
        core3.to_undirected()
        sys.stderr.write("  Leiden community detection on 3-core ...\n")
        communities = core3.community_leiden(objective_function="modularity")
        results["core3_communities"] = len(communities)
        results["core3_modularity"] = round(communities.modularity, 4)
        results["core3_community_sizes"] = {
            "min": int(min(communities.sizes())),
            "max": int(max(communities.sizes())),
            "mean": round(np.mean(communities.sizes()), 1),
            "median": int(np.median(communities.sizes())),
        }
        sys.stderr.write(
            f"  Communities: {len(communities)}, Modularity: {results['core3_modularity']}\n"
        )
    else:
        results["core3_communities"] = 0
        results["core3_modularity"] = 0
        results["core3_community_sizes"] = {}

    # ── Shatter giant component to find embedded chains ──
    sys.stderr.write("Shattering giant component for chain analysis ...\n")
    MAX_DEG = 6
    hubs = [v.index for v in gc.vs if gc.degree(v, mode="all") > MAX_DEG]
    results["giant_hubs_removed"] = len(hubs)

    if len(hubs) < gc.vcount():
        shattered = gc.copy()
        shattered.delete_vertices(hubs)
        shatter_comp = shattered.connected_components(mode="weak")
        results["shattered_components"] = len(shatter_comp)
        results["shattered_nodes"] = shattered.vcount()
        results["shattered_edges"] = shattered.ecount()

        chain_scores = []
        for comp_nodes in shatter_comp:
            n = len(comp_nodes)
            if 5 <= n <= 50:
                sub = shattered.induced_subgraph(comp_nodes)
                d = sub.diameter(directed=True)
                chain_scores.append(
                    {
                        "nodes": n,
                        "edges": sub.ecount(),
                        "diameter": d,
                        "score": round(d / (n - 1), 2) if n > 1 else 0,
                    }
                )

        chain_df = pd.DataFrame(chain_scores)
        top_chains = (
            chain_df[chain_df["diameter"] >= 5]
            .sort_values(["score", "diameter"], ascending=[False, False])
            .head(10)
        )
        results["embedded_chains"] = top_chains.to_dict("records")
    else:
        results["shattered_components"] = 0
        results["shattered_nodes"] = 0
        results["shattered_edges"] = 0
        results["embedded_chains"] = []

    # ── Print report ──
    sys.stdout.write(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
