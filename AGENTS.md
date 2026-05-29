the app extracts structured json from 2081272 ACP-127 telegram messages using python rebulk lib

read docs/rebulk.md for documentation
use `pydoc3 rebulk` to lookup function calls
for examples of rebulk usage look at /usr/lib/python3/dist-packages/guessit

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

these strings MUST only match once per document and are the root of the dependency tree expressed as rebulk Rule
the acp-127 message content is located between "Message Text" and "Message Attributes"

---

"Message Attributes" follows a list of atrributes in "key: value" format.
SOME attribute values cross multiple lines
Each attribute MUST be handled as indiviudal field for dependency checks
See ATTRIBUTES.md for possible values and counts of each attribute

---
r"^Locator:" attribute indicates if the content after "Message Text" contains a acp-127 message or errors
r"TEXT ON-LINE" MUST exist for acp-127 body extraction
---
all `declass_markings` and `content_footer_marker`  are removed without output in JSON
---
the position of `page_break`, `classification_marker`  and `end_marker` is identified.
`classification_marker` MUST be directly NEXT to `page_break` or `end_marker` or it does not MATCH
---
`classification_marker` gets output in JSON and removed from input
---
`page_break` gets output into JSON and removed from input. every empty line before and after gets removed (to merge continues text)
---
`end_marker` gets removed without output
---

content text (progressively cleaned via `_content` match) is now free of most markers
---
now in order from top to bottom following header components are extracted and removed on the cleaned input
---
distribution is extracted and removed (via ParseDistribution)
---
dash counter is extracted and removed (via CollectDashCounters)
---
dtg is extracted and removed (via ParseDTG)
---

TODO next fields

# Rule dependency chain (implemented)

The extraction pipeline uses the following ordered rules, each handling ONE stripping/output step:

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
                      └─ ParseDistribution (64) [src/patterns/distribution.py]

CollectDashCounters (32)                     [src/patterns/dash_counter.py]
ParseDTG (32)                                [src/patterns/dtg.py]
```

Each rule accumulates strip ranges (in original input coordinates) into `context["_strip_ranges"]`.
`BuildMessageContent` merges all ranges and applies them to the original input in one pass to produce `_message_content`.

# Files layout

- `src/patterns/` — pattern modules that define raw regex/string matches
- `src/rules/` — rule modules that implement extraction, stripping, and output logic


# JSON output structure

Every extracted document produces a flat JSON object with two kinds of fields:

**"Message Attributes"** (dict) — all ACP-127 key:value fields from the Message Attributes section, nested under this single key. These are the 63 known attribute keys (see `_KEYS` in `attributes.py`). They never have a `_` prefix.

**Underscore-prefixed fields** — any match that is NOT a message attribute (e.g. `_message_content`, `_file`). These are computed or metadata fields, not directly from the attribute section. The `_` prefix distinguishes them from the raw input data.

Example output:
```json
{
  "_file": "txtv2/1973/04/1973LIMA02545.txt",
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

Classification is done via match tags: a match with `"attribute"` in `match.tags` is placed under `"Message Attributes"`; everything else gets a `_` prefix.

# Critical restrictions

NEVER execute git commands. Do not touch git at all. You may read git output that already exists, but do not run git status, git add, git commit, git diff, git log, or any other git command. The user handles all version control manually.

# Code conventions

All regex capturing groups MUST use named group syntax (`(?P<name>...)`). Unnamed groups `(...)` are prohibited. This applies to both `re.compile()` and `rebulk.regex()` calls across the entire codebase. Named groups improve readability when accessing match values via `groupdict()` and make refactoring safer.
