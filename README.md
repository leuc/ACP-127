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

Extract structured reference data from ACP-127 messages and normalize it to a canonical MRN format.

## Pipeline

```bash
# 1. Extract structured JSON from ACP-127 messages
python3 -m src.extractor <paths...>

# 2. Flatten to reftel NDJSON (extract relevant fields for faster loading)
#    "date" stays raw here (Draft Date // Sent Date, unparsed) -- see step 3a
for year in {1973..1979}; do
  jq -Mc '{"references": ._reference, "attr_reference": ."Message Attributes"."Reference",
           "document_number": ."Message Attributes"."Document Number",
           "date": ."Message Attributes"."Draft Date" // ."Message Attributes"."Sent Date",
           "message_preview": (._message_content | if . then split("\n")[:100] | join("\n") else null end)}' \
    ${year}.ndjson > ${year}.reftel.ndjson
done

# 3a. Normalize every date-bearing field (body DTG + all Message Attribute
#     dates) into ISO 8601, with its own coverage report on stderr
python3 -m src.date_normalize *.ndjson > all-dates.ndjson

# 3b. Normalize references to canonical MRN format
python3 -m src.reftel_normalize *.reftel.ndjson > all-mrns.ndjson

# 3c. Normalize TAGS the same way
python3 -m src.tags_normalize *.new5.ndjson > all-tags.ndjson
```

This repo's pipeline stops at extraction + normalization. Graph-building and
other corpus-level research analysis (citation graphs, statistical cross-checks,
investigative writeups) now live in the sibling `cable-insights` repo, which
consumes the NDJSON produced above as its data source.

## Key Files

| File | Description |
|---|---|
| `src/date_utils.py` | Shared date parsing: attribute date strings + DTG components -> ISO 8601 |
| `src/date_normalize.py` | Date normalizer: all date-bearing fields, with per-field coverage |
| `src/reftel_normalize.py` | Reference normalizer: rebulk functional pattern, O(1) station dict |
| `src/tags_normalize.py` | TAGS normalizer/classifier |
| `src/station_data.py` | 558 canonical stations + 686 variant mappings |

See `AGENTS.md` and `docs/REFTEL.md` for detailed architecture and failure analysis.

# LICENSE

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-white.svg)](https://www.gnu.org/licenses/gpl-3.0)
