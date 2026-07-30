# Hypothesis: cables that reference each other share similar TAGS

**Question:** when one cable cites another (a `REF:` line resolving to another
document's MRN), do the two cables tend to carry the same or similar TAGS
codes, more than two unrelated cables would?

**Answer: yes, strongly and consistently**, across the full 1973-1979 corpus
and across every TAGS type (subject, geographic, organization, person, and
the unclassified buckets). The effect is not driven by any single type —
subject-code overlap (topical "aboutness") is if anything the *strongest*
signal, not an artifact of shared dateline geography.

Script: [`src/tags_reference_similarity.py`](../src/tags_reference_similarity.py).

## Method

1. **Join.** `results/<year>.tags.norm.ndjson` (from `src.tags_normalize`,
   `document_number -> classified TAGS codes`) is joined with
   `results/<year>.reftel.norm.ndjson` (from `src.reftel_normalize`,
   `document_number -> extracted_references`, a list of normalized MRNs cited
   by that cable) on the shared, identically-normalized `document_number`
   key. Both are loaded for all 7 years combined, since references can and do
   cross year boundaries.
2. **Citing/cited pairs.** For every document with at least one reference and
   its own TAGS ("citing" doc), each resolved reference ("cited" doc, i.e.
   one that itself has a TAGS record) forms one pair.
3. **Similarity metric.** Jaccard similarity of TAGS code sets:
   `|A ∩ B| / |A ∪ B|`. Computed on the full code set ("all") and on
   type-restricted subsets: `subject` (permanent/temporary/wildcard-field
   subject codes), `geo` (confirmed geographic codes), `organization`,
   `person`, `annotation`, `unknown`, `other` — the same type taxonomy
   `tags_normalize.py` assigns.
4. **Null baseline.** For every resolved actual reference, a random other
   document is drawn from the same pool and compared to the same citing
   document with the same metric. This gives a same-size, same-citing-doc
   control group with no assumed relationship, so "actual vs. random" is an
   apples-to-apples comparison, not actual-vs-corpus-average.
5. **Per-code lift.** For each individual code seen often enough
   (`--per-code-min-n`, default 300 in the run below), `P(cited doc also has
   code X | citing doc has code X)` is computed for actual reference pairs
   and for random pairs; `lift = actual P / random P`.

Run: `python3 -m src.tags_reference_similarity [--sample N] [--per-code]`.

## Small-sample validation (per the initial ask: check before a full run)

`--sample 2000 --seed 42`, drawn from all 7 years:

| view | mean Jaccard (actual) | mean Jaccard (random) | lift |
|---|---|---|---|
| all | 0.626 | 0.019 | 32.4x |
| subject | 0.774 | 0.028 | 27.3x |
| geo | 0.614 | 0.029 | 21.2x |

79.0% of references resolved to an in-corpus tagged document. The small
sample already showed the effect clearly, so the same run was repeated on
the full corpus.

## Full-corpus result (all 2,081,272 documents, 1973-1979)

- 1,136,872 citing documents (have ≥1 reference and their own TAGS).
- 924,312 (81.3%) have at least one reference that resolves to an in-corpus
  tagged document.
- 2,650,126 total reference pairs; 2,056,127 (77.6%) resolved. The remaining
  ~22% cite a document number not present in our tagged corpus (e.g. cited
  cable fell outside 1973-1979, was never captured, or the reference itself
  didn't normalize to a real MRN) — an availability gap, not a hypothesis
  failure.

### Aggregate similarity by TAGS type

| view | n pairs | mean Jaccard (actual) | mean Jaccard (random) | any overlap (actual) | any overlap (random) | identical (actual) | lift |
|---|---|---|---|---|---|---|---|
| all | 2,056,124 | 0.615 | 0.019 | 97.4% | 12.5% | 25.2% | 33.1x |
| subject | 2,056,068 | 0.762 | 0.024 | 91.8% | 5.1% | 61.8% | 31.4x |
| organization | 529,345 | 0.669 | 0.005 | 70.9% | 0.6% | 63.0% | 137.3x |
| geographic | 1,790,200 | 0.607 | 0.027 | 77.1% | 8.2% | 45.7% | 22.2x |
| person | 632,762 | 0.386 | 0.0004 | 42.6% | 0.05% | 35.3% | 1070.5x |
| unknown | 93,498 | 0.317 | 0.001 | 32.2% | 0.09% | 31.2% | 354.9x |
| other | 568,071 | 0.295 | 0.0002 | 32.0% | 0.02% | 27.4% | 1448.5x |
| annotation | 153,701 | 0.194 | 0.0000 | 20.9% | 0.00% | 18.2% | 9250.5x |

`n pairs` per view excludes pairs where both docs have an empty code set for
that view (Jaccard undefined), which is why counts differ across rows —
e.g. only ~529K of the 2.06M pairs have an organization code on either side
at all.

Full "all codes" run output (`--seed 42`, no sampling):

```
Citing documents considered: 1,136,872
Citing documents with >=1 in-corpus resolved reference: 924,312 (81.30%)
Reference pairs: 2,650,126 total, 2,056,127 resolved to an in-corpus tagged document (77.59%)
```

### Per-code lift: where the hypothesis holds weakest

Lift ratios above look huge across the board, but two effects can each make
a *specific* code or type look weak — worth separating:

**(a) Codes too common to be informative.** A handful of very broad codes
have a random baseline that's already high, so even strong absolute
co-occurrence produces modest lift. Lowest-lift codes with ≥300 actual-pair
occurrences (full corpus, `--per-code --per-code-min-n 300`):

| code | n | actual P | random P | lift | name |
|---|---|---|---|---|---|
| US | 571,255 | 0.648 | 0.240 | 2.70x | United States |
| PFOR | 241,711 | 0.853 | 0.121 | 7.03x | Foreign Policy and Relations |
| OVIP | 114,930 | 0.807 | 0.057 | 14.20x | Visits and Travel of Prominent Individuals and Leaders |
| PINT | 99,356 | 0.777 | 0.052 | 14.93x | Internal Political Affairs |
| OTRA | 78,879 | 0.632 | 0.038 | 16.42x | Travel and Visits |
| ETRD | 127,254 | 0.836 | 0.049 | 17.04x | Foreign Trade |
| UR | 112,772 | 0.835 | 0.048 | 17.34x | Soviet Union |
| BEXP | 85,804 | 0.855 | 0.048 | 18.00x | Trade Expansion and Promotion |
| ASEC | 84,361 | 0.906 | 0.046 | 19.48x | Security |
| EFIN | 96,897 | 0.803 | 0.040 | 20.08x | Financial and Monetary Affairs |

(next ~30 codes climb steadily from ~20x to ~40x — see script output for the
full list; 754 of 189,703 distinct codes observed met the 300-occurrence
threshold). `US` stands out as a clear outlier: it's mentioned in roughly a
quarter of *random* cable pairs simultaneously, so sharing it is weak
evidence of an actual citation relationship, unlike a specific code such as
`NARC` or a less-central country.

**(b) Types where the random baseline is so close to zero that the lift
ratio is dramatic but the absolute hit rate is still modest.** `annotation`
(9250x lift) and `other`/`unknown` (1449x/355x) look like the strongest
signal by lift, but in absolute terms only 18-32% of real reference pairs
actually share a specific code in those buckets — most pairs simply don't
carry a matching annotation or unclassified code at all, they just do so
*far* more often than the near-zero random rate. `person` names sit in
between: 42.6% of real reference pairs share a named individual, versus
0.05% at random.

**Ranked by absolute reliability** (how often the shared-tag pattern
actually shows up when a real reference exists), subject codes (91.8% any
overlap) and organization codes (70.9%) are the most dependable evidence of
a citation relationship; person names, unknown, other, and annotation codes
are real but much noisier signals, present in a minority of pairs.

## Conclusion

The hypothesis holds: cables that cite each other share TAGS at rates 20x to
over 1000x above chance, depending on the code type, and no type or
individual code contradicts it. The strongest and most reliable signal is
the *subject* code set (topical aboutness), not geography — 92% of real
reference pairs share at least one subject code, and 62% share the *exact
same* subject-TAGS set. Geography and organization codes also carry strong
signal. The weakest evidence comes from a small number of extremely common
codes (chiefly `US` and broad subject buckets like `PFOR`/`PINT`/`OVIP`)
whose high baseline frequency erodes their discriminating power, and from
the noisier person/annotation/unknown/other buckets, where the signal is
real but only present in a minority of pairs.

## Reproducing

```bash
# quick sanity check
python3 -m src.tags_reference_similarity --sample 2000 --seed 42

# full corpus, all views
python3 -m src.tags_reference_similarity --seed 42

# full corpus + per-code lift table
python3 -m src.tags_reference_similarity --seed 42 --per-code \
    --per-code-min-n 300 --per-code-top 40
```
