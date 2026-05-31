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

1. **Extract** structured JSON from ACP-127 messages via `src.extractor`
2. **Flatten** to reftel NDJSON:

        jq -Mc '{"references": ._reference, "attr_reference": ."Message Attributes"."Reference", "document_number": ."Message Attributes"."Document Number", "date": ."Message Attributes"."Draft Date" // ."Message Attributes"."Sent Date"}' input.ndjson > year.reftel.ndjson

3. **Read** per-year NDJSON files — yields `(doc_number, date, attr_ref, ref_list)`
4. **Prefer** `ref_list` (pre-split `references` field) over raw `attr_reference` string
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
| 1973 | 155,278 | 210,904 | 156,091 | 74.0% | 7.2s |
| 1974 | 239,348 | 236,280 | 181,294 | 76.7% | — |
| 1975 | 275,335 | 266,178 | 207,490 | 78.0% | — |
| 1976 | 288,088 | 232,871 | 180,691 | 77.6% | — |
| 1977 | 296,299 | 243,413 | 189,847 | 78.0% | — |
| 1978 | 304,641 | 231,370 | 181,697 | 78.5% | — |
| 1979 | 522,283 | 252,831 | 179,372 | 70.9% | — |
| **Total** | **2,081,272** | **1,673,847** | **1,276,482** | **76.3%** | **51.0s** |

## Failure Categories (397,365 total)

| Category | Share | Example |
|---|---|---|
| Multi-ref with commas | ~25% | `STATE 093410, B.STATE 105386` |
| Sender-date format | ~15% | `USCINCRED 311345 Z MAY 73` |
| Non-station sender codes | ~15% | `EMBTEL`, `IAEA VIENNA`, `EC BRUSSELS`, `BA` |
| Standalone numbers / fragments | ~10% | `3164`, `125535`, `115785` |
| `AND` / `;` / letter-dot separators | ~10% | `STATE 115778 AND COPENHAGEN 130` |
| Genuine garbage | ~10% | `PARA 2`, `MILLS LETTER TO BLAKE MAY 25` |
| OCR issues | ~5% | `73 STATE 1 O1684`, `73 STATE 2118984` |

## Usage

```bash
# Normalize all years
python3 -m src.reftel_normalize *.reftel.ndjson > all-mrns.ndjson

# Build reference graph
python3 src/reftel2graph.py all-mrns.ndjson reference-graph.graphml
```
