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
mkdir -p results results/coverage
for year in {1973..1979}; do
    echo "Processing $year ..."
    python3 -m src.extractor "cables/us-diplomatic-cables-txt-$year/" 2>"results/coverage/coverage-$year.txt" >"results/$year.ndjson"
    count=$(wc -l < "results/$year.ndjson")
    echo "Finished $year: $count records"
done
```

# Reference Normalization Pipeline

Extract structured reference data from ACP-127 messages and normalize it to a canonical MRN format.

## Pipeline

```bash
# 1. Extract structured JSON from ACP-127 messages
python3 -m src.extractor <paths...>

# 2. Flatten to reftel NDJSON (extract relevant fields for faster loading)
#    draft_date/sent_date/dtg all stay raw here -- see step 3a. reftel_normalize.py
#    reads these three fields independently and resolves its own single date (step 3b).
for year in {1973..1979}; do
  jq -Mc '{"references": ._reference, "attr_reference": ."Message Attributes"."Reference",
           "document_number": ."Message Attributes"."Document Number",
           "draft_date": ."Message Attributes"."Draft Date",
           "sent_date": ."Message Attributes"."Sent Date",
           "dtg": ._dtg,
           "message_preview": (._message_content | if . then split("\n")[:100] | join("\n") else null end)}' \
    results/${year}.ndjson > results/${year}.reftel.ndjson
done

# 3a. Normalize every date-bearing field (body DTG + all Message Attribute
#     dates) into ISO 8601, with its own coverage report on stderr.
#     Reads the raw per-year files -- list them explicitly, not `*.ndjson`,
#     or a rerun will also sweep up *.reftel.ndjson/*.dates.ndjson/etc.
python3 -m src.date_normalize results/{1973..1979}.ndjson > results/all-dates.ndjson

# 3b. Normalize references to canonical MRN format
python3 -m src.reftel_normalize results/*.reftel.ndjson > results/all-mrns.ndjson

# 3c. Normalize TAGS the same way (reads the raw per-year files -- TAGS lives
#     in "Message Attributes"/_tags, not in the flattened reftel NDJSON)
python3 -m src.tags_normalize results/{1973..1979}.ndjson > results/all-tags.ndjson

# 4. Combine references + TAGS into one joined NDJSON, keyed by document_number.
#    This is what `cable-insights/questions/reference-graph-structure/code/reftel2graph.py`
#    expects as its single input -- jq only, two passes so the tags file is
#    indexed once rather than re-scanned per mrns record:
jq -n '[inputs | {(.document_number): .tags}] | add' results/all-tags.ndjson > results/all-tags.index.json
jq -c --slurpfile idx results/all-tags.index.json '
  $idx[0] as $tags
  | {document_number, date, extracted_references, message_preview, tags: $tags[.document_number]}
' results/all-mrns.ndjson > results/all-mrns-tags.ndjson

# 6. Estimate dates for MRNs that are cited but never appear as a document,
#    by interpolating same-station/year sequence-number neighbors, refined
#    where possible using cross-station cables sharing the relay counter
#    window between those neighbors (see src/missing_mrn_estimate.py docstring).
python3 -m src.missing_mrn_estimate results/all-mrns.ndjson results/{1973..1979}.ndjson \
  > results/missing-mrn-dates.ndjson \
  2> results/coverage/missing-mrn-dates.$(date +%Y%m%d).txt
```

This repo's pipeline stops at extraction + normalization (through
`all-mrns-tags.ndjson` and `missing-mrn-dates.ndjson`). Graph-building and
other corpus-level research analysis (citation graphs, statistical cross-checks,
investigative writeups) live in the sibling `cable-insights` repo, which
consumes the NDJSON produced above as its data source.

## Optional: merge estimated dates into all-mrns-tags.ndjson

Not part of the required pipeline -- `all-mrns-tags.ndjson` and
`missing-mrn-dates.ndjson` are already complete, independently useful
artifacts on their own. This step only helps a consumer that wants one file
with a `date` for as many nodes as possible, including MRNs that only exist
as citations. Resolved missing-MRN estimates are appended as extra records
(`document_number` = the MRN, `date` = `estimated_date`,
`extracted_references`/`message_preview`/`tags` all `null` since the
document itself doesn't exist -- only its estimated date is known -- plus
`estimate_type`/`accuracy_days`/`date_order_inverted` carried through so a
consumer can tell an estimated row from a real one and judge its
confidence):

```bash
jq -c 'select(.estimated_date != null) | {document_number: .mrn, date: .estimated_date, extracted_references: null, message_preview: null, tags: null, estimate_type, accuracy_days, date_order_inverted}' \
  results/missing-mrn-dates.ndjson \
  | cat results/all-mrns-tags.ndjson - > results/all-mrns-tags.estimated.ndjson
```

**Caveat**: `reftel2graph.py`'s current loop skips any record whose
`extracted_references` is falsy, so these merged rows won't populate node
dates there without a corresponding change on that side -- this step
produces the data, it doesn't change how existing downstream code consumes
it.

## Key Files

| File | Description |
|---|---|
| `src/date_utils.py` | Shared date parsing: attribute date strings + DTG components -> ISO 8601 |
| `src/date_normalize.py` | Date normalizer: all date-bearing fields, with per-field coverage |
| `src/reftel_normalize.py` | Reference normalizer: rebulk functional pattern, O(1) station dict |
| `src/tags_normalize.py` | TAGS normalizer/classifier |
| `src/missing_mrn_estimate.py` | Estimates dates for cited-but-missing MRNs via same-station/year sequence interpolation, refined with cross-station relay-counter data |
| `src/station_data.py` | 558 canonical stations + 686 variant mappings |

See `AGENTS.md` and `docs/REFTEL.md` for detailed architecture and failure analysis.

# LICENSE

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-white.svg)](https://www.gnu.org/licenses/gpl-3.0)
