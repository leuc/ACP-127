the app extracts structured json from 2081272 ACP-127 telegram messages using python rebulk lib

read docs/rebulk.md for documentation
use `pydoc3 rebulk` to lookup function calls
for examples of rebulk usage look at /usr/lib/python3/dist-packages/guessit

entry point: `python3 -m src.extractor [--limit N] [--sample N] <paths...>`

to tackle the large amount of messy data the app MUST:
- calculate byte coverage across the input document (percentage how much input text was matched)
- track the match coverage across all input documents (percentage how many documents had a match)

the data is extracted with chains of patterns that are combined in a depedency tree of rebulk Rules

for each extract field we define a pattern in a dedicated file
MOST matched fields are exported to JSON
MOST matched fields are removed from the input until only the primary body content remains
the order of removal matters!

# input structure

the details of acp-127 are described in docs/acp127g.txt

the following describes each field and step in order of dependency

---
the input is split into two parts with the strings

r"\s+Message Text"

r"\s+Message Attributes"

these strings MUST only match once per document and are the root of the dependency tree expressed as rebulk Rule (markers, not regular matches)
the acp-127 message content is located between "Message Text" and "Message Attributes"

---

"Message Attributes" follows a list of atrributes in "key: value" format.
SOME attribute values cross multiple lines (via `ExtendAttributeValue` + `MergeContinuationLines` rules)
Each attribute MUST be handled as indiviudal field for dependency checks
See ATTRIBUTES.md for possible values and counts of each attribute

---
r"^Locator:" attribute indicates if the content after "Message Text" contains a acp-127 message or errors
r"TEXT ON-LINE" MUST exist for acp-127 body extraction
---
all `declass_markings` (`marking_line`) and `content_footer_marker` are removed without output in JSON
---
the position of `page_break`, `classification_marker` and `end_marker` is identified.
`classification_marker` MUST be directly NEXT to `page_break` or `end_marker` or it does not MATCH
---
`classification_marker` gets output in JSON and removed from input
---
`page_break` gets output into JSON and removed from input. every empty line before and after gets removed (to merge continues text)
---
`end_marker` gets removed without output
---
`section_marker` (classification + "SECTION N OF M" + mrn) is extracted but NOT yet removed
---

content text (progressively cleaned via `_content` match) is now free of most markers
---
now the following header components are **independently extracted** from the cleaned content then **all removed at once** by `RemoveHeaders`:
---
distribution is parsed (via `ParseDistribution` — extracts ACTION/ORIGIN/INFO addressee codes)
---
dash counter is reduced to a single integer value (via `CollectDashCounters`)
---
dtg is parsed (via `ParseDTG` — extracts precedence, date)
---
FM from line is parsed (via `ValidateFrom`)
---
TO addressee lines are parsed (via `ParseTo`)
---
INFO addressee lines are parsed (via `ParseInfo`)
---
DRAFTED BY / APPROVED BY blocks are parsed (via `ParseDrafting`)
---
E.O. 11652 line is parsed (via `ParseExecutiveOrder`)
---
TAGS line is parsed into list (via `ParseTags`)
---
SUBJECT line is parsed with continuations (via `ParseSubject`)
---
REF/REFS/REFERENCE lines are parsed into list (via `ParseRef`)
---

# Rule dependency chain (implemented)

The extraction pipeline uses the following ordered rules, each handling ONE step:

```
ValidateSingleMessageText (256)              [src/rules/validate.py]
  └─ ValidateSingleMessageAttributes (256)   [src/rules/validate.py]
       └─ CollectMarkings (200)              [src/patterns/declass_markings.py]
       └─ RemoveDeclassMarkings (200)        [src/rules/declass_removal.py]

TagLocatorTextOnline (152)                   [src/patterns/locator.py]
  └─ ExtractClassificationMarker (144)       [src/rules/classification_extraction.py]
       └─ ExtractPageBreak (128)             [src/rules/page_break_extraction.py]
            └─ RemoveEndMarker (112)         [src/rules/end_marker_removal.py]
                 └─ BuildMessageContent (96) [src/rules/message_content.py]
                      └─ RemoveHeaders (16)  [src/rules/header_removal.py]

CollectDashCounters (32)                     [src/patterns/dash_counter.py]
ParseDTG (32)                                [src/patterns/dtg.py]
ParseDistribution (64)                       [src/patterns/distribution.py]
ValidateFrom (32)                            [src/patterns/from_line.py]
ParseTo (32)                                 [src/patterns/to_line.py]
ParseInfo (32)                               [src/patterns/info_line.py]
ParseDrafting (31)                           [src/patterns/drafting.py]
ParseExecutiveOrder (31)                     [src/patterns/eo_line.py]
ParseTags (31)                               [src/patterns/tags_line.py]
ParseSubject (31)                            [src/patterns/subject_line.py]
ParseRef (31)                                [src/patterns/ref_line.py]
ExtractSectionMarker (80)                    [src/patterns/section_marker.py]
```

Rules with priority >= 96 accumulate strip ranges (in original input coordinates) into `context["_strip_ranges"]`. `BuildMessageContent` merges all ranges and applies them in one pass to produce `_message_content`.

Rules with priority < 96 operate on the already-extracted `_message_content` value. `RemoveHeaders` (the final rule) collects all header matches and strips their text from `_message_content` using a different mechanism: it searches for header match text within the cleaned value and removes it, leaving only the primary body text.

# Attribute parsing details

`attributes.py` defines 63 known keys and 3 rules:
- **`ExtendAttributeValue` (160)** — extends `key` matches to `key: value` on same line plus indented continuation lines
- **`RemoveAttributesBeforeMarker` (128)** — removes attribute matches appearing before `message_attributes_marker` (deps: `ExtendAttributeValue`)
- **`MergeContinuationLines` (96)** — extends attributes to include column-0 continuation lines (non-key, non-blank) between attributes (deps: `RemoveAttributesBeforeMarker`)

# Files layout

- `src/patterns/` — pattern modules that define raw regex/string matches + their rules
- `src/rules/` — rule modules that implement extraction, stripping, and output logic
- `src/builder.py` — composes all patterns + rules into a single `Rebulk` object
- `src/extractor.py` — CLI entry point, file discovery, pipeline runner
- `src/coverage.py` — `CoverageTracker` for byte and document coverage
- `src/serializer.py` — `result_to_dict()` converts rebulk matches to JSON dict
- `src/patterns/routing.py` — shared `find_routing_header()` utility used by `ParseTo` / `ParseInfo`

# All pattern/rule source files

| File | Pattern Name(s) | Rule(s) | Priority | Output field |
|---|---|---|---|---|
| `src/patterns/message_sections.py` | `message_text_marker`, `message_attributes_marker` | — | — (markers) | — |
| `src/patterns/attributes.py` | 63 attribute key strings | `ExtendAttributeValue`, `RemoveAttributesBeforeMarker`, `MergeContinuationLines` | 160, 128, 96 | `Message Attributes` dict |
| `src/patterns/locator.py` | — | `TagLocatorTextOnline` | 152 | — (tags only) |
| `src/patterns/classification.py` | `classification_marker` | — | — | `_classification_marker` |
| `src/patterns/declass_markings.py` | `marking_line` (6 strings) | `CollectMarkings` | 200 | — (removed) |
| `src/patterns/page_break.py` | `page_break`, `end_marker`, `content_footer_marker` | — | — | `_page_break` |
| `src/patterns/dash_counter.py` | `dash_counter` | `CollectDashCounters` | 32 | `_dash_counters` |
| `src/patterns/dtg.py` | `dtg` | `ParseDTG` | 32 | `_dtg` |
| `src/patterns/distribution.py` | — | `ParseDistribution` | 64 | `_distribution` |
| `src/patterns/from_line.py` | `from` (FM) | `ValidateFrom` | 32 | `_from` |
| `src/patterns/to_line.py` | — | `ParseTo` | 32 | `_to` |
| `src/patterns/info_line.py` | — | `ParseInfo` | 32 | `_info` |
| `src/patterns/drafting.py` | — | `ParseDrafting` | 31 | `_drafted_by`, `_approved_by` |
| `src/patterns/eo_line.py` | — | `ParseExecutiveOrder` | 31 | `_executive_order` |
| `src/patterns/tags_line.py` | — | `ParseTags` | 31 | `_tags` |
| `src/patterns/subject_line.py` | — | `ParseSubject` | 31 | `_subject` |
| `src/patterns/ref_line.py` | — | `ParseRef` | 31 | `_reference` |
| `src/patterns/section_marker.py` | `section_marker` | `ExtractSectionMarker` | 80 | `_section_marker` |
| `src/rules/validate.py` | — | `ValidateSingleMessageText`, `ValidateSingleMessageAttributes` | 256 | — |
| `src/rules/declass_removal.py` | — | `RemoveDeclassMarkings` | 200 | — |
| `src/rules/classification_extraction.py` | — | `ExtractClassificationMarker` | 144 | `_classification_marker` |
| `src/rules/page_break_extraction.py` | — | `ExtractPageBreak` | 128 | `_page_break` |
| `src/rules/end_marker_removal.py` | — | `RemoveEndMarker` | 112 | — |
| `src/rules/message_content.py` | — | `BuildMessageContent` | 96 | `_message_content` |
| `src/rules/header_removal.py` | — | `RemoveHeaders` | 16 | — (modifies `_message_content`) |

# JSON output structure

Every extracted document produces a flat JSON object with two kinds of fields:

**"Message Attributes"** (dict) — all ACP-127 key:value fields from the Message Attributes section, nested under this single key. These are the 63 known attribute keys (see `_KEYS` in `attributes.py`). They never have a `_` prefix.

**Underscore-prefixed fields** — any match that is NOT a message attribute (e.g. `_message_content`, `_file`). These are computed or metadata fields, not directly from the attribute section. The `_` prefix distinguishes them from the raw input data.

| JSON field | Source | Description |
|---|---|---|
| `_file` | `extractor.py` | Absolute file path |
| `_message_content` | `message_content.py` | Cleaned body text with all markers/headers stripped |
| `_classification_marker` | `classification_extraction.py` | List of unique classification strings (near page breaks) |
| `_page_break` | `page_break_extraction.py` | List of `{line, page}` entries |
| `_dash_counters` | `dash_counter.py` | Integer from dash counter line |
| `_dtg` | `dtg.py` | Dict `{raw, precedence, date_iso}` |
| `_distribution` | `distribution.py` | Dict `{raw, ACTION: {CODE: count, ...}, ORIGIN, INFO, _sum_check}` |
| `_from` | `from_line.py` | Originator string (FM line body) |
| `_to` | `to_line.py` | TO addressee text (lines joined with spaces) |
| `_info` | `info_line.py` | INFO addressee text (lines joined with spaces) |
| `_drafted_by` | `drafting.py` | List of drafting officer lines |
| `_approved_by` | `drafting.py` | List of approving officer lines |
| `_executive_order` | `eo_line.py` | Raw E.O. 11652 line text |
| `_tags` | `tags_line.py` | List of tag strings |
| `_subject` | `subject_line.py` | Subject text (joined) |
| `_reference` | `ref_line.py` | List of reference strings |
| `_section_marker` | `section_marker.py` | List of `{raw, classification, section, total, mrn}` |

**NOT output to JSON** (stripped/removed without output):
- `marking_line` — declassification marking lines
- `content_footer_marker` — `*** Current Handling Restrictions/Classification` lines
- `end_marker` — `NNN`, `NNNN`, `NNNNMAFVVZCZ`, `<< END OF DOCUMENT >>` (`_page_break` IS output, `end_marker` is NOT)

Example output:
```json
{
  "_file": "cables/1973/04/1973LIMA02545.txt",
  "_message_content": "...",
  "Message Attributes": {
    "Automatic Decaptioning": "X",
    "Capture Date": "01 JAN 1994",
    "Document Number": "1973LIMA02545",
    "Locator": "TEXT ON-LINE",
    ...
  }
}
```

Classification is done via match tags: a match with `"attribute"` in `match.tags` is placed under `"Message Attributes"`; everything else gets a `_` prefix. Attribute values matching `N/A` or `NA` are normalized to `null`.

# Coverage tracking

`CoverageTracker` (`src/coverage.py`) tracks:
- **byte coverage**: percentage of input characters matched by non-private, non-marker matches
- **document coverage**: percentage of documents with at least one match
- **field match rates**: per-field percentage of documents that have a non-NA match

Output: JSON lines to stdout, coverage summary to stderr.

# Reference Normalization Pipeline

The reference normalization pipeline converts raw ACP-127 reference strings into canonical MRN format and builds a directed reference graph.

## Pipeline steps

1. **Extract structured JSON** from ACP-127 messages:

        python3 -m src.extractor [--limit N] [--sample N] <paths...>

2. **Flatten to reftel NDJSON** (extracts only relevant fields for faster loading):

        for year in {1973..1979}; do
          jq -Mc '{"references": ._reference, "attr_reference": ."Message Attributes"."Reference", "document_number": ."Message Attributes"."Document Number", "date": ."Message Attributes"."Draft Date" // ."Message Attributes"."Sent Date"}' results/${year}.ndjson > results/${year}.reftel.ndjson
        done

   This produces per-year NDJSON files (e.g. `1973.reftel.ndjson`) with `document_number`, `date`, `attr_reference`, and `references` fields.

3. **Normalize references** to canonical MRN format:

        python3 -m src.reftel_normalize *.reftel.ndjson > all-mrns.ndjson

   Reads per-document NDJSON files, normalizes each reference string to `YYSTATIONNNNNN` format using a single rebulk functional pattern with O(1) dict-lookup station matching. Outputs NDJSON with `extracted_references` array.

   **Data source priority:**
   - Primary: the `references` field (pre-split list of individual references from the message body)
   - Fallback: the `attr_reference` field (raw attribute string, unsplit — will fail for multi-ref strings)

   **No splitting** is done in the normalizer — each ref string enters the parser as-is.

   **Station matching:** 558 canonical stations, 686 variant-to-canonical mappings, all loaded into a flat `_STATIONS` dict for O(1) lookup. ~900 entries total.

4. **Build reference graph** (GraphML):

        python3 src/reftel2graph.py all-mrns.ndjson reference-graph.graphml

   Reads the normalized NDJSON, builds a directed iGraph where vertices are document numbers and edges point from a document to its references. Missing documents (referenced but not in the dataset) are flagged with `missing=True`.

## Normalizer performance

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

## Reference graph properties

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

Top authorities (by PageRank) are all `STATE` messages. Top broadcasters (by out-degree) are embassy stations across multiple years. The high modularity of the 3-core (0.998) indicates strong community structure — tightly clustered groups with very little cross-community linking. At 7.38%, the giant component is small; 91.5% of vertices are isolated or in tiny clusters, consistent with the 76.3% match rate and many referenced documents missing from the dataset.

## Failure categories (top 500 from 397,365 total)

| Category | Share | Example |
|---|---|---|
| Multi-ref with commas | ~25% | `STATE 093410, B.STATE 105386` |
| Sender-date format | ~15% | `USCINCRED 311345 Z MAY 73` |
| Non-station sender codes | ~15% | `EMBTEL`, `FBIS BANGKOK`, `IAEA VIENNA`, `EC BRUSSELS`, `BA` |
| Standalone numbers / fragments | ~10% | `3164`, `125535`, `115785` |
| `AND` / `;` / letter-dot separators | ~10% | `STATE 115778 AND COPENHAGEN 130` |
| Genuine garbage | ~10% | `PARA 2`, `MILLS LETTER TO BLAKE MAY 25` |
| OCR issues | ~5% | `73 STATE 1 O1684`, `73 STATE 2118984` |

## Normalizer files

| Path | Lines | Description |
|---|---|---|
| `src/reftel_normalize.py` | 567 | Main normalizer: rebulk functional pattern, `_parse_single_ref()`, `CoverageTracker`, CLI |
| `src/reftel2graph.py` | 83 | GraphML builder from normalized NDJSON |
| `src/station_data.py` | 1844 | 558 canonical stations + 686 variant mappings |
| `src/station_index.py` | — | StationIndex class (not used by normalizer; uses `_STATIONS` dict directly) |
| `*.reftel.ndjson` | input | Per-year NDJSON with `document_number`, `date`, `attr_reference`, `reference` |

# Normalizer architecture

```
read_reftel(path)
  └─ yields (doc_number, date, attr_ref, ref_list)

main loop per file:
  ├─ prefers `references` list over attr_ref (raw string)
  ├─ builds batch_lines: doc_idx<tab>doc_year<tab>cleaned_ref
  ├─ calls rebulk.matches() ONCE per file (not per-ref)
  └─ groups results by doc_idx, outputs one JSON line per doc

_batch_match() — rebulk functional pattern
  └─ _parse_single_ref(text, doc_year)
       ├─ extracts optional 2-digit year prefix (or uses doc_year)
       ├─ finds rightmost digit run as number
       ├─ detects airgram marker (A[-] before number)
       ├─ station = text between year and number
       └─ O(1) dict lookup in _STATIONS

_preprocess(ref) — cleans a single ref string
  ├─ strips REF:/REFTEL:/RETELS: prefix
  ├─ strips NOTAL, UNCLAS
  ├─ strips letter prefixes (A., B., (A), etc.)
  ├─ strips AIRGRAM marker
  └─ converts 4-digit years to 2-digit
```

# Critical restrictions

NEVER execute git commands. Do not touch git at all. You may read git output that already exists, but do not run git status, git add, git commit, git diff, git log, or any other git command. The user handles all version control manually.

# Code conventions

All regex capturing groups MUST use named group syntax (`(?P<name>...)`). Unnamed groups `(...)` are prohibited. This applies to both `re.compile()` and `rebulk.regex()` calls across the entire codebase. Named groups improve readability when accessing match values via `groupdict()` and make refactoring safer.
