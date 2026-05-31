# MRN / Reference Normalization

## MRN Format

```
YYSTATIONNNNNN
```

| Part | Description | Example |
|------|-------------|---------|
| `YY` | 2-digit year | `72`, `06` |
| `STATION` | Canonical station name (uppercase) | `STATE`, `TEHRAN` |
| `NNNNN` | Sequential number, leading zeros stripped | `5822` (not `05822`) |

Airgram variant: `YYSTATION-ANNNNN` (e.g. `73BANGKOK-A50`).

## Implementation

`src/reftel_normalize.py` — single rebulk functional pattern, O(1) dict-lookup station matching, batch processing.

### Pipeline

1. **Read** per-year NDJSON files (e.g. `1973.reftel.ndjson`) — yields `(doc_number, date, attr_ref, ref_list)`
2. **Prefer** `ref_list` (pre-split `reference` field) over raw `attr_reference` string
3. **Clean** each ref string:
   - Strip `REF:/REFTEL:/RETELS:` prefix
   - Strip `NOTAL`, `UNCLAS`
   - Strip letter prefixes (`A.`, `(B)`, `C)`)
   - Strip `AIRGRAM` marker
   - Convert 4-digit years to 2-digit
4. **Batch** all refs into one string: `doc_idx\tdoc_year\tcleaned_ref\n`
5. **Parse** with one `rebulk.matches()` call per file — each line becomes one MRN or failure

### Parsing Logic (`_parse_single_ref`)

Extracts:
- **Year**: optional 2-digit prefix at start, or falls back to document year
- **Number**: rightmost run of digits (1-10 chars)
- **Airgram**: `A[-]` before number
- **Station**: text between year and number/airgram, looked up in `_STATIONS` dict (O(1))

### Station Matching

- 558 canonical stations + 686 variant-to-canonical mappings
- Flat `_STATIONS` dict: all variants and canonics point to canonical name
- `_STOP_STATIONS` blocklist: months, dates, classification words, common non-stations

### No Splitting

The normalizer does **no splitting** of multi-ref strings. Each ref enters `_parse_single_ref` as-is. Upstream `reference` field is expected to provide pre-split individual refs. The `attr_reference` fallback (raw attribute string) will fail for comma-separated or multi-ref strings.

## Coverage (2,081,272 documents)

| Year | Docs | Refs | Matched | Rate | Time |
|---|---|---|---|---|---|
| 1973 | 155,278 | 94,515 | 58,973 | 62.4% | 2.96s |
| 1974 | 239,348 | 148,589 | 97,256 | 65.5% | — |
| 1975 | 275,335 | 168,064 | 113,932 | 67.8% | — |
| 1976 | 288,088 | 172,145 | 118,507 | 68.8% | — |
| 1977 | 296,299 | 175,218 | 121,230 | 69.2% | — |
| 1978 | 304,641 | 176,060 | 121,846 | 69.2% | — |
| 1979 | 522,283 | 293,443 | 195,863 | 66.7% | — |
| **Total** | **2,081,272** | **1,228,034** | **827,607** | **67.4%** | **43.0s** |

## Failure Categories (400,427 total)

| Category | Share | Example |
|---|---|---|
| Multi-ref with commas | ~75% | `STATE 093410, B.STATE 105386` |
| Sender-date format | ~5% | `USCINCRED 311345 Z MAY 73` |
| Non-station sender codes | ~5% | `EMBTEL`, `IAEA VIENNA`, `EC BRUSSELS` |
| `AND` / `;` / letter-dot separators | ~5% | `73 STATE 115778 AND COPENHAGEN 130` |
| Genuine garbage | ~5% | `PARA 2`, `MILLS LETTER TO BLAKE MAY 25` |
| OCR issues | ~5% | `73 STATE 1 O1684`, `73 STATE 2118984` |

## Usage

```bash
# Normalize all years
python3 -m src.reftel_normalize *.reftel.ndjson > all-mrns.ndjson

# Build reference graph
python3 src/reftel2graph.py all-mrns.ndjson reference-graph.graphml
```
