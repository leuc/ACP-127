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

## POSIX Shell Loop Example (Parallel Processing)

Process each year individually in parallel using background jobs and save results to separate files:

```bash
mkdir -p results
for year in {1973..1979}; do
    echo "Starting processing for $year (background job)..."
    python3 -m src.extractor cables/$year/ 2>results/$year-coverage.json >results/$year-results.ndjson &
    echo "Background job started for $year with PID $!"
done

# Wait for all background jobs to complete
echo "Waiting for all years to finish processing..."
wait

echo "All years have finished processing."
for year in {1973..1979}; do
    if [ -f "results/$year-results.ndjson" ]; then
        count=$(wc -l < "results/$year-results.ndjson")
        echo "Finished $year: $count records"
    else
        echo "No results found for $year"
    fi
done
```

# LICENSE

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-white.svg)](https://www.gnu.org/licenses/gpl-3.0)