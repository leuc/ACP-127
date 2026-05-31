# MRN / Reference Extraction


## MRN Format

```
YYSTATIONNNNNN
```

| Part | Description | Example |
|------|-------------|---------|
| `YY` | 2-digit year | `72`, `06` |
| `STATION` | Uppercase embassy/city/agency name (4+ chars) | `STATE`, `TEHRAN` |
| `NNNNN` | Sequential number, leading zeros stripped | `5822` (not `05822`) |

Variants: compact (`72STATE12345`), space-separated (`75 STATE 194199`),
comma-separated lists (`78 RANGOON 1287, 78 STATE 90518`),
letter-prefixed (`A. STATE 113893`, `02A:STATE79760`).

## Multi-Stage Matching Strategy

Patterns are tried in order — most precise first. Each uses `\b` boundaries
and requires **minimum 4 characters** for station names.

### Pre-processing

1. Strip `REFTEL:`, `REF:`, `REFS:`, `RETEL:`, `REF/TEL:`, `REFERENCE:`
   (case-insensitive, no `\b` — follows digits)
2. Split on `|`, `,`, `;`, and `A. B. C.` patterns
3. Normalise 4-digit years: `1974STATE9201` → `74STATE9201`
4. Normalise zero-padded numbers: `76FRANKF05822` → `76FRANKF5822`

### Stage 1 — Known Station, Space-Separated (most precise)

```
\b(?P<year>\d{2})\s+(?P<station>STATION_LIST)\s+(?P<number>\d{1,10})\b
```

Matches `79 STATE 113893`, `74 TEHRAN 2481`. Zero false positives.

### Stage 2 — Known Station, A: Prefix

```
\b(?P<year>\d{2})[A-Z]:(?P<station>STATION_LIST)\s*(?P<number>\d{1,10})\b
```

Matches `02A:STATE79760`.

### Stage 3 — Known Station, Compact

```
\b(?P<year>\d{2})(?P<station>STATION_LIST)\s*(?P<number>\d{1,10})\b
```

Matches `72STATE12345`, `76LAGOS12828`.

### Stage 4 — Generic Multi-Word (4+ chars per word)

```
\b(?P<year>\d{2})\s+(?P<station>[A-Z]{4,}(?:\s+[A-Z]{4,})*)\s+(?P<number>\d{1,10})\b
```

Matches unknown multi-word stations like `78 USUN NEW YORK 1030`.
Rejects 3-letter tokens (`DTG`, `MAY`).

### Stage 5 — Generic Compact Uppercase

```
\b(?P<year>\d{2})(?P<station>[A-Z]{4,20})\s*(?P<number>\d{1,10})\b
```

### Stage 6 — Mixed/Lower Case

```
\b(?P<year>\d{2})(?P<station>[A-Za-z]{4,20})\s*(?P<number>\d{1,10})\b
```

Matches `02Kathmandu209`, `02secstate201932`.

### STOP_STATIONS Filter

All Stage 4–6 matches are checked against a blocklist of words that are
never valid station names:

```
JANUARY, FEBRUARY, MARCH, APRIL, MAY, JUNE, JULY, AUGUST,
SEPTEMBER, OCTOBER, NOVEMBER, DECEMBER,
JAN, FEB, MAR, APR, MAY, JUN, JUL, AUG, SEP, OCT, NOV, DEC,
DATED, DATE, NUMBER, NBR, REFERENCE, REF, REFTEL,
PAGE, PAGES, SECTION,
CLASSIFIED, UNCLASSIFIED, SECRET, CONFIDENTIAL, SENSITIVE,
NOTAL, EXDIS, NODIS, STADIS,
MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY
```

### Fallback — Year Injection

When no pattern matches but a known station + number is found anywhere in
the part, the document's year is prepended (using pre-compiled `RE_S_FALLBACK`):

```
STATE 113893 + doc_year=79 → 79STATE113893
```

Example: `A. STATE 113893 DTG 042237Z MAY 79` extracts `79STATE113893`.

## Coverage

Measured against `reftel.json` (all reference fields from both sources):

| Metric | CSV | Tel |
|--------|-----|-----|
| Total documents | 251,287 | 1,878,933 |
| Unique referenced MRNs | 130,194 | 868,303 |
| In dataset | 76,666 | 468,540 |
| **Not in dataset** | **53,528** | **399,763** |
| Exist but no text | 0 | 22,055 |

The 250K reduction in tel missing refs (from 650K to 400K) is attributed to
the `STOP_STATIONS` filter eliminating month names, date labels, and
classification words that were incorrectly matched as station names.

## Edge Cases

| # | Case | Handling |
|---|------|----------|
| 1 | `REFTEL:` prefix | Strip before matching |
| 2 | `|`, `,`, `;` separators | Split on all three |
| 3 | `A. B. C.` letter prefixes | Split on `\b[A-Z]\.\s*` |
| 4 | Space-separated | Stage 1 |
| 5 | Mixed case | Stage 6 |
| 6 | 4-digit year `0100HARARE7134` | Normalise to `00HARARE7134` |
| 7 | `A:` separator `02A:STATE79760` | Stage 2 |
| 8 | Zero-padded number `76FRANKF05822` | `mrn()` strips leading zeros |
| 9 | 3-letter tokens `DTG`, `MAY` | Rejected (4-char minimum) |
| 10 | Month names `JANUARY`, `DATED` | Rejected by `STOP_STATIONS` |
| 11 | FBIS `00FBIS2813114ZFEB00` | Not an MRN, correctly skipped |
| 12 | No year prefix `STATE 113893` | Year injected via fallback |
| 13 | `n/a` / `N/A` / `NONE` | Skipped (772K entries, 36%) |

## False Positive Prevention

A false positive (`93DTG0437`) was discovered and fixed:

```
Input:  A. STATE 113893 DTG 042237Z MAY 79 - B. STATE 127051 DTG 182320Z MAY 79
Before: → ["93DTG0437"]   ← WRONG (DTG is not a station)
After:  → ["79STATE113893", "79STATE127051"]   ← CORRECT
```

**Root cause:** `[A-Z]+` matched 3-letter `DTG` as a station name. Fixed by:
1. Requiring minimum 4 characters for station names in all patterns
2. Adding `\b` boundaries to prevent matching digits embedded in larger numbers
3. Adding `STOP_STATIONS` blocklist for months, dates, and classification words

## Station Whitelist

Compiled from `old-extract`'s `re_emb` pattern, `from.stations` (the `From:`
field distribution from .tel Message Attributes), and stations observed in
reference data. Includes common OCR typos and multi-word embassy names.

Single-word stations embed in `SINGLE_STATIONS`; multi-word stations
(USUN NEW YORK, HONG KONG, etc.) embed in `MULTI_STATIONS` with `\s+`
for regex alternation.

## Graph Tool

`src/reftel2graph.py` builds a **directed** igraph from `reftel.json`:

```
python3 src/reftel2graph.py reftel.json output.graphml
```

Vertices: every unique `document_number` + every unique `extracted_reference`.
Edges: each `(document_number → ref)` pair (directed for correct PageRank).
Vertex attributes: `label`, `degree`, `pagerank`. No parsing or normalization.
