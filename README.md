A Python rebulk parser for Allied Communications Publications (ACPs) 127 (G),
"TAPE RELAY PROCEDURES" Telegrams from the Central Foreign Policy Files,
1973-1779, Released Telegrams.
Record Group 59: General Records of the Department of State, National Archives.

# Data Source:

```
https://archive.org/download/U.s.DiplomaticCablesYear1973/us-diplomatic-cables-txt-1973.7z
https://archive.org/download/U.s.DiplomaticCablesYear1974/us-diplomatic-cables-txt-1974.7z
https://archive.org/download/U.s.DiplomaticCablesYear1975/us-diplomatic-cables-txt-1975.7z
https://archive.org/download/U.s.DiplomaticCablesYear1976/us-diplomatic-cables-txt-1976.7z
https://archive.org/download/U.s.DiplomaticCablesYear1977/us-diplomatic-cables-txt-1977.7z
https://archive.org/download/U.s.DiplomaticCablesYear1978/us-diplomatic-cables-txt-1978.7z
https://archive.org/download/U.s.DiplomaticCablesYear1979/us-diplomatic-cables-txt-1979.7z
```

# Installation

## Ubuntu Dependencies

```bash
sudo apt-get update
sudo apt-get install python3-orjson python3-rebulk
```

## Using pip (alternative or supplement)

```bash
pip install -r requirements.txt
```

# Downloading and Extracting Data

```bash
# Create a directory for the data
mkdir -p cables
cd cables

# Download and extract each year (1973-1979)
for year in {1973..1979}; do
    echo "Downloading $year..."
    curl -LO "https://archive.org/download/U.s.DiplomaticCablesYear$year/us-diplomatic-cables-txt-$year.7z"
    echo "Extracting $year..."
    7z x us-diplomatic-cables-txt-$year.7z
    # Optional: remove the archive to save space
    rm us-diplomatic-cables-txt-$year.7z
done
```

# Usage

## Basic Usage

Process all .txt and .tel files in a directory (recursively):

```bash
python3 -m src.extractor cables/
```

## With Limits

Limit the number of files processed (useful for testing):

```bash
python3 -m src.extractor cables/ --limit 100
```

## Random Sampling

Process a random sample of files (overrides --limit if both are given):

```bash
python3 -m src.extractor cables/ --sample 1000
```

## Output Format

- **STDOUT**: Each processed file's extraction result is output as a separate JSON line (streaming)
- **STDERR**: Progress messages and final coverage statistics (as a JSON object)

Example of processing a single file and viewing the output:

```bash
# Process one file, capture stdout and stderr separately
python3 -m src.extractor cables/1973/01/1973LIMA00001.txt 2>coverage.json >result.json

# View the extraction result
cat result.json | jq .

# View the coverage statistics
cat coverage.json | jq .
```

## Batch Processing (Multiple Years)

The script uses multiprocessing internally (`ProcessPoolExecutor`), so a simple sequential loop is all that's needed:

```bash
mkdir -p results
for year in {1973..1979}; do
    echo "Processing $year ..."
    python3 -m src.extractor cables/$year/ 2>results/$year-coverage.json >results/$year-results.ndjson
    count=$(wc -l < "results/$year-results.ndjson")
    echo "Finished $year: $count records"
done
```

# Reference Normalization Pipeline

Extract structured reference data from ACP-127 messages and build a directed reference graph for network analysis.

## Pipeline

```bash
# 1. Extract structured JSON from ACP-127 messages
python3 -m src.extractor <paths...>

# 2. Flatten to reftel NDJSON (extract relevant fields for faster loading)
for year in {1973..1979}; do
  jq -Mc '{"references": ._reference, "attr_reference": ."Message Attributes"."Reference",
           "document_number": ."Message Attributes"."Document Number",
           "date": ."Message Attributes"."Draft Date" // ."Message Attributes"."Sent Date",
           "message_preview": (._message_content | if . then split("\n")[:100] | join("\n") else null end)}' \
    ${year}.ndjson > ${year}.reftel.ndjson
done

# 3. Normalize references to canonical MRN format
python3 -m src.reftel_normalize *.reftel.ndjson > all-mrns.ndjson

# 4. Build reference graph (GraphML)
python3 src/reftel2graph.py all-mrns.ndjson reference-graph.graphml

# 5. Analyze graph connectivity
python3 src/analyze_graph.py reference-graph.graphml
```

## Coverage

| Year | Docs | Refs | Matched | Rate |
|---|---|---|---|---|
| 1973 | 155,278 | 210,904 | 156,091 | 74.0% |
| 1974 | 239,348 | 236,280 | 181,294 | 76.7% |
| 1975 | 275,335 | 266,178 | 207,490 | 78.0% |
| 1976 | 288,088 | 232,871 | 180,691 | 77.6% |
| 1977 | 296,299 | 243,413 | 189,847 | 78.0% |
| 1978 | 304,641 | 231,370 | 181,697 | 78.5% |
| 1979 | 522,283 | 252,831 | 179,372 | 70.9% |
| **Total** | **2,081,272** | **1,673,847** | **1,276,482** | **76.3%** |

## Graph Properties

| Metric | Value |
|---|---|
| Vertices | 1,619,261 (1,010,077 primary) |
| Edges | 1,274,070 |
| Weakly connected components | 450,463 |
| WCC size distribution (p50/p90/p99/p99.9) | 2 / 5 / 18 / 68 |
| Giant component | 119,431 (7.38% of nodes) |
| Reciprocity | 0.0003 |
| Transitivity | 0.0636 |
| Assortativity | -0.036 |
| Max k-core | 6 |
| 3-core nodes | 16,245 |
| 3-core communities | 2,793 (modularity 0.998) |
| Giant hubs removed (deg > 6) | 3,593 |
| Shattered components (after hub removal) | 44,086 |

Top authorities (by PageRank) are all `STATE` messages. Top broadcasters (by out-degree) are embassy stations across multiple years. The high modularity of the 3-core (0.998) indicates strong community structure — the network consists of tightly clustered groups of documents that reference each other, with very little cross-community linking.

## Key Files

| File | Description |
|---|---|
| `src/reftel_normalize.py` | Reference normalizer: rebulk functional pattern, O(1) station dict |
| `src/reftel2graph.py` | GraphML builder from normalized NDJSON |
| `src/analyze_graph.py` | Graph analysis: WCC, k-core, PageRank, communities |
| `src/station_data.py` | 558 canonical stations + 686 variant mappings |

See `AGENTS.md` and `docs/REFTEL.md` for detailed architecture and failure analysis.

# LICENSE

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-white.svg)](https://www.gnu.org/licenses/gpl-3.0)