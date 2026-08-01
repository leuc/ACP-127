the app extracts structured json from 2081272 ACP-127 telegram messages using python rebulk lib

# Data provenance — NOT OCR

The source text (`cables/`, `txtv2/`) is **NOT OCR output**. It is original plaintext pulled
from NARA's SAS databases (the digitized State Department Central Foreign Policy File),
with noise ADDED by NARA's own processing/reproduction (declassification-review reformatting,
stamps, spacing artifacts, etc.) — not by any OCR pass on this project's side. Never attribute
irregularities (dropped characters, odd spacing, garbled fields, unlabeled numeric fields) to
"OCR" — that is an unconfirmed and so far disproven explanation for such artifacts

use jq, rg, fdfind for exploration

entry point: `python3 -m src.extractor [--limit N] [--sample N] <paths...>`

to tackle the large amount of messy data the app MUST:
- calculate byte coverage across the input document (percentage how much input text was matched)
- track the match coverage across all input documents (percentage how many documents had a match)

the data is extracted with chains of patterns that are combined in a depedency tree of rebulk Rules
use rebulk skills to fully understands its features and use

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

`attributes.py` defines 69 known keys and 3 rules:
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
| `src/patterns/attributes.py` | 69 attribute key strings | `ExtendAttributeValue`, `RemoveAttributesBeforeMarker`, `MergeContinuationLines` | 160, 128, 96 | `Message Attributes` dict |
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

**"Message Attributes"** (dict) — all ACP-127 key:value fields from the Message Attributes section, nested under this single key. These are the 69 known attribute keys (see `_KEYS` in `attributes.py`). They never have a `_` prefix.

**Underscore-prefixed fields** — any match that is NOT a message attribute (e.g. `_message_content`, `_file`). These are computed or metadata fields, not directly from the attribute section. The `_` prefix distinguishes them from the raw input data.

| JSON field | Source | Description |
|---|---|---|
| `_file` | `extractor.py` | Absolute file path |
| `_message_content` | `message_content.py` | Cleaned body text with all markers/headers stripped |
| `_classification_marker` | `classification_extraction.py` | List of unique classification strings (near page breaks) |
| `_page_break` | `page_break_extraction.py` | List of `{line, page}` entries |
| `_dash_counters` | `dash_counter.py` | Integer from dash counter line |
| `_dtg` | `dtg.py` | Raw components dict `{raw, precedence_raw, dd, hh, mm, mon, yy}` — **not parsed**; rebulk only extracts, calendar parsing happens downstream in `src/date_utils.py::parse_dtg` (see `src/date_normalize.py`) |
| `_distribution` | `distribution.py` | Dict `{raw, ACTION: {CODE: count, ...}, ORIGIN, INFO, _sum_check}` |
| `_from` | `from_line.py` | Originator string (FM line body) |
| `_to` | `to_line.py` | TO addressee text (lines joined with spaces) |
| `_info` | `info_line.py` | INFO addressee text (lines joined with spaces) |
| `_drafted_by` | `drafting.py` | List of drafting officer lines |
| `_approved_by` | `drafting.py` | List of approving officer lines |
| `_executive_order` | `eo_line.py` | Raw E.O. 11652 line text |
| `_tags` | `tags_line.py` | Raw TAGS line text (string, unsplit) |
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

Always store plaintext coverage summary in results/coverage/ with a date based filename

# Date normalization

rebulk (`src/patterns/dtg.py`, `src/patterns/attributes.py`) only **extracts** date-shaped
text — it never parses a date to ISO or validates a calendar. All date parsing lives in
`src/date_utils.py`, invoked from `src/date_normalize.py`:

- `_dtg` (see JSON output table above) is a raw components dict — no century inference, no
  `datetime()` validation, no plausibility range applied at extraction time.
- The 9 date-bearing Message Attributes (`Capture Date`, `Decaption Date`, `Disposition Date`,
  `Disposition Approved on Date`, `Review Date`, `Review Release Date`, `Review Transfer Date`,
  `Draft Date`, `Sent Date`) stay raw strings in `"Message Attributes"`, same as every other
  attribute.

`src/date_utils.py` provides:
- `parse_date(raw: str) -> str | None` — parses an attribute date string (formats: `%d %b %Y`,
  `%d-%b-%Y %I:%M:%S %p`, `%d-%b-%Y`, `%d/%m/%Y`, plus already-ISO passthrough) into a bare ISO
  date (`YYYY-MM-DD`), or `None` if unparseable. Always date-only, even for formats with a time
  component — every Message-Attribute date's time-of-day, when present, is exactly midnight (NARA
  export padding, never real sub-day precision), so keeping it would just make output shape
  inconsistent across documents for no informational gain.
- `parse_dtg(components: dict) -> dict | None` — takes `_dtg`'s raw components and returns
  `{raw, precedence, datetime_iso}` (the shape `_dtg` used to have inline), applying the 2-digit→
  4-digit century heuristic, calendar validation, and the 1973-1979 plausibility clamp. Returns
  `None` if invalid. Named `datetime_iso` (not `date_iso`) because the DTG's `HH`/`MM` are genuine
  transmission-time precision from the message header itself — unlike attribute dates, this is not
  padding, so it isn't stripped.
- `reconstruct_filing_datetime(filing_time: str | None, dtg_components: dict | None) -> str | None`
  — `_dash_counters.filing_time` (see `src/patterns/dash_counter.py`) is a bare `DDHHMMZ` fragment
  with no month/year of its own. This borrows `mon`/`yy` from the same document's `_dtg`
  components (the filing event and the message DTG are the same transmission) to reconstruct a
  full `%Y-%m-%dT%H:%M:%SZ` datetime, applying the same bounds/calendar validation as `parse_dtg`.
  Returns `None` if either input is missing/invalid.

`src/date_normalize.py` is the CLI that runs this over a corpus, mirroring
`src/reftel_normalize.py`/`src/tags_normalize.py`'s shape exactly (same `CoverageTracker` +
`print_report()` pattern, reads `results/<year>.ndjson` directly):

    python3 -m src.date_normalize <file.ndjson> [...] > output.ndjson

Per document, output is `{document_number, document_number_raw, dtg, filing_time_raw,
filing_datetime_iso, dates}`. This module deliberately does **not** pick a single "document date" —
`Draft Date` and `Sent Date` are two semantically distinct fields (one administrative, one often
absent entirely) and blending them into one opaque field hid which one won and produced
inconsistent output shape. Instead every field is exposed independently, 1:1 named to its source
(`dates` keys are the snake_case form of the attribute name — `draft_date`, `sent_date`, etc.), and
a downstream consumer decides its own priority — see `src/reftel_normalize.py` below, which has a
genuine internal need for one resolved date and makes that choice itself, explicitly. Its stderr
report gives per-field raw-presence and parse-success/failure rates — the audit surface for "is
this date field actually parseable."

`document_number_raw` is the un-normalized `Document Number` attribute value, straight from the
input, before `_normalize_doc_number()` rewrites `document_number` to canonical MRN form. All
three normalizers (`date_normalize.py`, `reftel_normalize.py`, `tags_normalize.py`) emit this
field so a caller can always trace a normalized `document_number` back to its exact source
document.

`src/reftel_normalize.py::_parse_document_date` is the one place a single resolved date is still
computed — MRN station-year matching genuinely needs exactly one year. It prefers the message's
own DTG (via `date_utils.parse_dtg`, truncated to `YYYY-MM-DD`) over `Draft Date`/`Sent Date` (via
`date_utils.parse_date`), since the DTG is the message's actual date while the two attributes are
NARA administrative metadata dates that are frequently absent. It records which source won as
`date_source` (`"dtg"`, `"draft"`, `"sent"`, or `""`) for auditability. `src/tags_normalize.py`
doesn't need a document date at all and has no date handling.

# Reference Normalization Pipeline

The reference normalization pipeline converts raw ACP-127 reference strings into canonical MRN format and builds a directed reference graph.

## Pipeline steps

1. **Extract structured JSON** from ACP-127 messages:

        python3 -m src.extractor [--limit N] [--sample N] <paths...>

2. **Flatten to reftel NDJSON** (extracts only relevant fields for faster loading):

        for year in {1973..1979}; do
          jq -Mc '{"references": ._reference, "attr_reference": ."Message Attributes"."Reference", "document_number": ."Message Attributes"."Document Number", "draft_date": ."Message Attributes"."Draft Date", "sent_date": ."Message Attributes"."Sent Date", "dtg": ._dtg, "message_preview": (._message_content | if . then split("\n")[:100] | join("\n") else null end)}' results/${year}.ndjson > results/${year}.reftel.ndjson
        done

   This produces per-year NDJSON files (e.g. `1973.reftel.ndjson`) with `document_number`, `draft_date`, `sent_date`, `dtg`, `attr_reference`, `references`, and `message_preview` (first 100 lines of the cleaned body text) fields. Note: `draft_date`/`sent_date` here are still **raw** attribute strings and `dtg` is still raw components — no `//` fallback and no parsing happens in jq; see the "Date normalization" section above for where `src/reftel_normalize.py` resolves these into a single date.

3. **Normalize references** to canonical MRN format:

        python3 -m src.reftel_normalize *.reftel.ndjson > all-mrns.ndjson

   Reads per-document NDJSON files, normalizes each reference string to `YYSTATIONNNNNN` format using a single rebulk functional pattern with O(1) dict-lookup station matching. Outputs NDJSON with `date`, `date_source`, `extracted_references` array, and `message_preview` (first 100 lines of body text).

   **Data source priority:**
   - Primary: the `references` field (pre-split list of individual references from the message body)
   - Fallback: the `attr_reference` field (raw attribute string, unsplit — will fail for multi-ref strings)

   **No splitting** is done in the normalizer — each ref string enters the parser as-is.

   **Station matching:** 558 canonical stations, 686 variant-to-canonical mappings, all loaded into a flat `_STATIONS` dict for O(1) lookup. ~900 entries total.

4. **Normalize TAGS** the same way:

        python3 -m src.tags_normalize *.new5.ndjson > all-tags.ndjson

This repo's pipeline stops here. Joining reftel + TAGS output, building the
citation graph, and analyzing it are now part of the sibling `cable-insights`
repo, which consumes this repo's NDJSON output as its data source (not a code
dependency).

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
| `src/date_utils.py` | — | Shared date parsing: `parse_date()` (attribute strings), `parse_dtg()` (DTG components) |
| `src/date_normalize.py` | — | Date normalizer: all date-bearing fields, `CoverageTracker`, same CLI style |
| `src/reftel_normalize.py` | 567 | Main normalizer: rebulk functional pattern, `_parse_single_ref()`, `CoverageTracker`, CLI |
| `src/tags_normalize.py` | 379 | TAGS normalizer/classifier, same CLI style |
| `src/station_data.py` | 1844 | 558 canonical stations + 686 variant mappings |
| `*.reftel.ndjson` | input | Per-year NDJSON with `document_number`, `date`, `attr_reference`, `reference`, `message_preview` |

# Normalizer architecture

```
read_reftel(path)
  └─ yields (doc_number, date, attr_ref, ref_list, message_preview)

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
