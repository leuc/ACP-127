# TAGS coverage: FAQ mapping vs. extracted data

Companion to `docs/ATTRIBUTES.md`. This is a snapshot analysis of how much of the
real TAGS data across all 7 years (1973-1979, `results/*.ndjson`) is covered by
the Subject TAGS mapping in `src/tags_mapping.py` (itself transcribed from
`docs/faqs.txt` Appendix I / Appendix II).

## Methodology

`docs/faqs.txt` only documents **Subject TAGS**: ~35 explicit permanent codes
(Appendix I), ~36 explicit temporary codes (Appendix II), and a wildcard rule
that any code in the `E`/`M`/`P`/`S`/`T` fields is permanent (the FAQ doesn't
enumerate those — only the on-line TAGS handbooks do). It does **not** define
Geographic or Organization TAGS codes at all. So "unknown" below does not mean
"missing from the FAQ mapping by mistake" — for most codes it means "the FAQ
never covered this category of code in the first place" (see the NATO/OECD/UNGA
example below).

Two independent extractions of TAGS exist in the data and were analyzed
**separately** because they can and do differ:

- **`Message Attributes.TAGS`** — raw attribute string, comma-delimited,
  captured from the "Message Attributes" section (`src/patterns/attributes.py`).
- **`_tags`** — list extracted by this codebase's `ParseTags` rule
  (`src/patterns/tags_line.py`) from the `TAGS:` line in the message **body**.
  It only splits on commas, so when the body copy of the TAGS line is missing
  commas (common OCR/transcription artifact — the body and the attributes
  section are independently transcribed copies of the same underlying message),
  a single `_tags` list entry can contain multiple space-separated codes, e.g.
  for one 1973 document: `_tags = ["PFOR IZ US UR"]` while
  `Message Attributes.TAGS = "PFOR, IZ, UR, US, n/a"` for the *same* document.

For each source, tokens were split on commas (and, for `_tags`, also on
whitespace, to catch the un-split case above), trimmed, upper-cased, and
filtered to those shaped like a 4-letter subject code (`^[A-Z]{4}$`) — this
drops 2-letter geographic codes, literal `N/A` tokens, free-text/parenthetical
fragments (e.g. `(KISSINGER, HENRY A.)`), and OCR garbage, none of which are
in scope for a Subject TAGS mapping.

```bash
# Message Attributes.TAGS
jq -r '."Message Attributes".TAGS // empty' results/19{73..79}.ndjson \
  | tr ',' '\n' \
  | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/\.$//' \
  | tr 'a-z' 'A-Z' | grep -E '^[A-Z]{4}$' | sort | uniq -c | sort -rn

# _tags (body)
jq -r '._tags // empty | .[]' results/19{73..79}.ndjson \
  | tr ',' '\n' | tr ' ' '\n' \
  | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/\.$//' \
  | tr 'a-z' 'A-Z' | grep -E '^[A-Z]{4}$' | sort | uniq -c | sort -rn
```

Each resulting frequency list was then classified with
`src/tags_mapping.classify_subject_tag()`.

## Coverage summary

| Source | Unique codes | Total occurrences |
|---|---:|---:|
| `Message Attributes.TAGS` | 2,805 | 3,394,533 |
| `_tags` (body) | 7,546 | 2,678,005 |

| Status | Attr: unique (%) | Attr: occurrences (%) | Body: unique (%) | Body: occurrences (%) |
|---|---:|---:|---:|---:|
| `permanent` (explicit, Appendix I) | 35 (1.2%) | 792,891 (23.4%) | 35 (0.5%) | 628,848 (23.5%) |
| `temporary` (explicit, Appendix II) | 36 (1.3%) | 358,557 (10.6%) | 36 (0.5%) | 255,754 (9.6%) |
| `permanent-wildcard` (E/M/P/S/T field) | 808 (28.8%) | 2,010,210 (59.2%) | 2,818 (37.3%) | 1,596,018 (59.6%) |
| `unknown` (no FAQ coverage) | 1,926 (68.7%) | 232,875 (6.9%) | 4,657 (61.7%) | 197,385 (7.4%) |

Takeaways:
- By **occurrence count** (i.e. how much of the real data is explained), the
  FAQ-derived mapping accounts for **~93%** of both sources once the E/M/P/S/T
  wildcard rule is included (permanent + temporary + wildcard). Only the
  Appendix-explicit codes have known titles though — the wildcard bucket
  (59% of occurrences) is classified as permanent but has no title, since the
  FAQ doesn't enumerate those codes.
- By **unique code count**, most of the long tail is `unknown` — but this is
  overwhelmingly single-digit/low-frequency noise (OCR fragments, rare
  organization acronyms), not systematic gaps. See below.
- `_tags` (body) has ~2.7x more unique codes than the attribute source for the
  same ~93% occurrence coverage — consistent with it being the noisier,
  independently-OCR'd copy of the same TAGS line.

## Top 40 `unknown` codes (Message Attributes.TAGS source)

These are legitimate **Organization TAGS** (international bodies, alliances,
foreign parties) — a category the FAQ never defines codes for, not a gap in
the Appendix I/II transcription:

| Code | Occurrences |
|---|---:|
| `NATO` | 61,718 |
| `UNGA` | 25,678 |
| `OECD` | 24,860 |
| `IAEA` | 15,578 |
| `CSCE` | 13,283 |
| `UNSC` | 11,393 |
| `GATT` | 11,158 |
| `OPIC` | 6,851 |
| `CCMS` | 5,851 |
| `ICAO` | 4,659 |
| `IBRD` | 4,283 |
| `ICRC` | 3,516 |
| `OPEC` | 3,398 |
| `UNDP` | 3,329 |
| `IMCO` | 3,190 |
| `UNEP` | 2,901 |
| `CIEC` | 1,886 |
| `NASA` | 1,734 |
| `BTOP` | 1,658 |
| `WARC` | 1,523 |
| `ICEM` | 1,156 |
| `UNEF` | 1,048 |
| `WIPO` | 859 |
| `ICCS` | 798 |
| `IFAD` | 774 |
| `FSLN` | 719 |
| `FNLA` | 572 |
| `AFDB` | 567 |
| `USIA` | 562 |
| `NACB` | 479 |
| `IATA` | 478 |
| `AFDF` | 475 |
| `GULF` | 414 |
| `NOAA` | 407 |
| `UNTC` | 330 |
| `ZANU` | 318 |
| `ZAPU` | 307 |
| `CEMA` | 248 |
| `AALC` | 243 |
| `ICAF` | 215 |

## `A`/`B`/`C`/`O`-prefixed unknown codes (the actual gap candidates)

Unlike `E`/`M`/`P`/`S`/`T`, the FAQ does **not** apply a wildcard rule to the
`A` (Administration), `B` (Business Services), `C` (Consular Affairs), or `O`
(Operations) fields — Appendix I/II instead present themselves as complete
lists of Subject TAGS for those four fields. Any `A*`/`B*`/`C*`/`O*` code
classified `unknown` is therefore worth a second look, since it's either (a) a
genuine Organization TAGS code that happens to start with one of those
letters (the common case — `OECD`, `OPIC`, `CCMS`, `OPEC`, `ACDA`, `CACM`,
etc. below are all real international-organization acronyms, not Subject
TAGS), or (b) an actual Subject TAGS omission from the FAQ appendices.

719 unique `A`/`B`/`C`/`O` codes fell into `unknown` (attribute source); the
top 20 by frequency, all of which are recognizable as Organization TAGS or
OCR/parenthetical-name fragments rather than missing Subject TAGS:

| Code | Occurrences |
|---|---:|
| `OECD` | 24,860 |
| `CSCE` | 13,283 |
| `OPIC` | 6,851 |
| `CCMS` | 5,851 |
| `OPEC` | 3,398 |
| `CIEC` | 1,886 |
| `BTOP` | 1,658 |
| `AFDB` | 567 |
| `AFDF` | 475 |
| `CEMA` | 248 |
| `AALC` | 243 |
| `ACDA` | 166 |
| `CCIR` | 159 |
| `ORIT` | 152 |
| `AORC` | 125 |
| `CACM` | 103 |
| `AADP` | 101 |
| `CIME` | 97 |
| `BWIA` | 96 |
| `APAG` | 95 |

No high-frequency `A`/`B`/`C`/`O` code in this list looks like a plausible
missed Subject TAGS entry (all match known international organizations,
alliances, or agencies) — the Appendix I/II transcription appears complete
for these four fields relative to what actually shows up in the data.

## Source divergence (`Message Attributes.TAGS` vs. `_tags`)

Codes with ≥200 occurrences in one source and **zero** in the other (9 found):

| Code | Attr occurrences | Body occurrences | Likely explanation |
|---|---:|---:|---|
| `FSLN` | 719 | 0 | Organization code (Sandinista National Liberation Front); apparently not present verbatim in the body TAGS line for these docs |
| `ZAPU` | 307 | 0 | Organization code (Zimbabwe African People's Union) |
| `BCRP` | 0 | 479 | Body-only; likely a name/org fragment not carried into the attribute copy |
| `EARL` | 0 | 437 | Looks like a personal-name fragment leaking from an unparenthesized `(SMITH, EARL)`-style entry in the body TAGS line |
| `AGEN` | 0 | 407 | Possibly an OCR variant of a genuine code, unique to body transcription |
| `PGEN` | 0 | 366 | Same pattern as `AGEN` |
| `JACK` | 0 | 334 | Personal-name fragment (same mechanism as `EARL`) |
| `RUTH` | 0 | 258 | Personal-name fragment |
| `GARY` | 0 | 245 | Personal-name fragment |

The body-only names (`EARL`, `JACK`, `RUTH`, `GARY`) confirm the known
`_tags` extraction quirk: `ParseTags` only splits on commas
(`src/patterns/tags_line.py`), so a body TAGS line like `OVIP (SMITH, JACK)`
splits into `["OVIP", "(SMITH", "JACK)"]` rather than keeping the parenthetical
name intact — the leaked first-name tokens then pass the 4-letter filter here.
This is a known extraction limitation, not new data quality information, but
it explains why `_tags` has a longer unknown tail than the attribute source.

## Investigated meanings of the top 100 undocumented (Organization) TAGS codes

**This section is independent research, not part of `docs/faqs.txt`.** It is
*not* reflected in `src/tags_mapping.py`, which intentionally stays scoped to
what the FAQ itself documents (Subject TAGS only). The findings below were
derived by sampling real messages and are classified into two confidence
tiers — treat "documented" as *evidenced by this dataset*, not as an official
NARA/State Department source; it is not equivalent to the FAQ appendices.

**Method:** for each of the top 100 `unknown`-classified codes (by
`Message Attributes.TAGS` frequency), up to 6 documents carrying that code
were sampled (spread across the full match list, not just the first hits).
For each sampled document, both the `_subject` field and the `_message_content`
body text (which has the `TAGS:` header itself stripped out, but often
mentions the same organization in running prose — per the tip that prompted
this investigation) were searched for a word-boundary mention of the code,
and the surrounding text was captured as evidence:

```bash
# Stage 1: fast pass — which sampled docs carry which target code (hash-set
# lookup against Message Attributes.TAGS, single pass over all 7 years)
jq -c --argjson codeset '{"NATO":true, "UNGA":true, ...}' '
  (.["Message Attributes"].TAGS // "") as $t
  | ($t | split(",") | map(gsub("^[[:space:]]+|[[:space:]]+$";"") | ascii_upcase)) as $tags
  | ($tags | map(select($codeset[.]))) as $matched
  | select(($matched|length) > 0)
  | {matched: $matched, subject: (._subject // null),
     docnum: (.["Message Attributes"]."Document Number" // null)}
' results/19{73..79}.ndjson

# Stage 2: targeted pass — pull subject + body (._message_content, the
# post-header-removal body text) for exactly the ~600 sampled docnums
jq -c --argjson docset '{"1973BONN08260":true, ...}' '
  (.["Message Attributes"]."Document Number" // null) as $dn
  | select($dn != null and $docset[$dn])
  | {docnum: $dn, subject: (._subject // null),
     body: (._message_content // "" | .[0:3000])}
' results/19{73..79}.ndjson
```

A grep-style word-boundary search (`\bCODE\b`) was then run in Python over
each sampled document's subject (checked first) and body (checked second) to
extract ~130 characters of surrounding context.

### Documented (spelled out in the sampled text, or an unambiguous standard institution confirmed by matching context)

| Code | Meaning | Evidence (doc / snippet) |
|---|---|---|
| `NATO` | North Atlantic Treaty Organization | 1973BONN08260: "...OBSERVERS AT EXPERT MEETING...AT NATO HEADQUARTERS..." |
| `UNGA` | UN General Assembly | 1976SEOUL03106: "...KOREAN QUESTION AT 31ST UNGA..." |
| `OECD` | Organisation for Economic Co-operation and Development | 1973BONN08829: "...OECD EXAMINATION OF FOREIGN INVESTMENT..." |
| `IAEA` | International Atomic Energy Agency | 1973BANGKO09696 body: "...TAGS IAEA, TECH, TH..."; 1976IAEAV07279: "UNCLAS IAEA VIENNA 7279" |
| `CSCE` | Conference on Security and Co-operation in Europe | 1973BONN08597: "...DISCLAIMER ON GERMANY IN CSCE..." |
| `UNSC` | UN Security Council | 1973CAIRO01604: "...GOE PLANS FOR UNSC DEBATE ON ME..." |
| `GATT` | General Agreement on Tariffs and Trade | 1977MTNGE01382 body: "...TAS: ETRD, MTN, GATT..." |
| `OPIC` | Overseas Private Investment Corporation | 1975STATE191056: "...POLITICAL RISK CONVERTIBILITY INSURANCE (OPIC)..." |
| `CCMS` | NATO Committee on the Challenges of Modern Society | 1974BONN14669: "...CCMS: ROAD SAFETY IMPLEMENTING RESOLUTION..."; USNATO/NATOB origin cables |
| `ICAO` | International Civil Aviation Organization | 1973MONTRE01242: "...ICAO - COMMITTEE ON AIRCRAFT NOISE III..." |
| `IBRD` | International Bank for Reconstruction and Development (World Bank) | 1974USUNN02171: "...LINK BETWEEN IMF/IBRD C-20 DEVELOPMENT COUNCIL..." |
| `ICRC` | International Committee of the Red Cross | 1978STATE260274: "...INTERNATIONAL COMMITTEE OF THE RED CROSS (ICRC)..." |
| `OPEC` | Organization of the Petroleum Exporting Countries | 1977ABUDH02190: "...OPEC PRICES IN 1978..." |
| `UNDP` | UN Development Programme | 1977STATE123184 body: "...DEVELOPMENT PROGRAM (UNDP), GOVERNING COUNCIL..." |
| `IMCO` | Inter-Governmental Maritime Consultative Organization (predecessor of IMO) | 1974MOSCOW02912: "...IMCO PANEL OF EXPERTS ON MARITIME SATELLITES..." |
| `UNEP` | UN Environment Programme | 1973GENEVA02921: "...UNEP: GOVERNING COUNCIL MEETING..." |
| `CIEC` | Conference on International Economic Cooperation ("North-South Dialogue") | 1977OECDP14338: "...CIEC RAW MATERIALS COMMISSION: G-19 TEXT..." |
| `NASA` | National Aeronautics and Space Administration | 1973TANANA00878: "...NASA TRACKING STATION IN MADAGASCAR..." |
| `WARC` | World Administrative Radio Conference | 1979SANSA04575: "...1979 WORLD ADMINISTRATIVE RADIO CONFERENCE (WARC)..." |
| `ICEM` | Intergovernmental Committee for European Migration | 1973GENEVA02892 body: "...TRIPARTITE ICEM/UNHCR/USRP MEETING..." |
| `UNEF` | UN Emergency Force | 1975USUNN03422 body: "...SC CONSULTATIONS ON UNEF..." (Sinai) |
| `WIPO` | World Intellectual Property Organization | 1978BONN13685 body: "...INTELLECTUAL PROPERTY ORGANIZATION (WIPO)..." |
| `ICCS` | International Commission of Control and Supervision (Vietnam ceasefire body) | 1973SAIGON11473: "...SUCCESSOR TO CANADA ON ICCS..." |
| `IFAD` | International Fund for Agricultural Development | 1976BRUSSE00277: "...INTERNATIONAL FUND FOR AGRICULTURAL DEVELOPMENT (IFAD)..." |
| `FSLN` | Frente Sandinista de Liberación Nacional (Sandinista National Liberation Front, Nicaragua) | 1978MANAGU01364 body: "...THE FSLN HAS DECLARED A TRUCE FOR EASTER WEEK..." |
| `FNLA` | Frente Nacional de Libertação de Angola | 1975LUANDA00695: "...MPLA TAKES OVER CABINDA CITY, FNLA FLEEING..." |
| `AFDB` | African Development Bank | 1978NAIROB06654: "...AFRICAN DEVELOPMENT BANK/FUND ANNUAL MEETINGS..." |
| `USIA` | United States Information Agency | 1974STATE143909 body: "...ADVISORY COMMISSIONS OF STATE CU AND USIA..." |
| `NACB` | Non-Aligned Coordinating Bureau | 1978COLOMB02616 body: "...[NON-]ALIGNED COORDINATING BUREAU (NACB) AT HAVANA..." |
| `NACC` | Non-Aligned Coordinating Committee | 1978JAKART05157 tagged doc subject: "NON-ALIGNED COORDINATING COMMITTEE MEETING IN KABUL" |
| `IATA` | International Air Transport Association | 1973LONDON13220 body: "...SUPPORTING APPROVAL IATA PROPOSED PACKAGE..." |
| `AFDF` | African Development Fund | 1978OUAGAD05603: "...VISIT OF TREASURY OFFICIALS TO IDA/AFDF..." |
| `NOAA` | National Oceanic and Atmospheric Administration | 1976STATE090146 body: "...NATIONAL MARINE FISHERIES SERVICE (NMFS), NOAA..." |
| `UNTC` | UN Trusteeship Council | 1973YAOUND03898 body (OCR-degraded): "...ZATIO, (UNTC) WHICH WAS FORMED BY AMALGAMATING..."; corroborated by adjacent "TRUSTEESHIP COUNCIL (TC)" subjects on other Micronesia-related docs |
| `ZANU` | Zimbabwe African National Union | 1978MAPUTO01436: "...RHODESIA: ZANU PRESIDENT MUGABE..." |
| `ZAPU` | Zimbabwe African People's Union | 1979LUSAKA00564: "...RHODESIA: ZAPU SUSPICIONS OF THE UK..." (Joshua Nkomo's party) |
| `CEMA` | Council for Mutual Economic Assistance (COMECON) | 1977BONN00815 body: "...IN THE CONTEXT OF THE EC-CEMA NEGOTIATIONS..." |
| `AALC` | African-American Labor Center | 1977STATE151079 body: "...AFRICAN-AMERICAN LABOR CENTER (AALC), INSTITUTE OF AFL-CIO..." |
| `ICAF` | Industrial College of the Armed Forces | 1977STATE067986 body: "...COLLEGE OF THE ARMED FORCES(ICAF)..." |
| `ACDA` | US Arms Control and Disarmament Agency | 1978STATE284342: "...ACDA SAFEGUARDS RESEARCH IN SUPPORT OF IAEA..." |
| `CCIR` | International Radio Consultative Committee | 1974STATE110390: "...US CANDIDATE FOR DIRECTOR OF CCIR OF THE ITU..." |
| `ORIT` | Inter-American Regional Organization of Workers (AFL-CIO-affiliated) | 1973MEXICO07847: "...AFL-CIO/ORIT RELATIONS..." |
| `INCB` | International Narcotics Control Board | 1976BRUSSE04007 body: "...CONTROL BOARD (INCB)..." |
| `WFTU` | World Federation of Trade Unions | 1975HELSIN00275 body: "...WORLD FEDERATION OF TRADE UNIONS (WFTU)..." |
| `IRSG` | International Rubber Study Group | 1976LONDON17322 body: "...INTERNATIONAL RUBBER STUDY GROUP (IRSG)..." |
| `USGS` | US Geological Survey | 1976STATE228037 body: "...U.S. GEOLOGICAL SURVEY (USGS), DEPARTMENT OF INTERIOR..." |
| `FHWA` | Federal Highway Administration | 1973KUWAIT01977 body: "...FOR: KRUSER US DEPT OF TRANSP, FHWA..." |
| `USAF` | US Air Force | 1973NOUAKC01083 body: "...TRIBUTE TO EFFICIENCY OF USAF OPERATION..." |
| `USIS` | US Information Service (overseas arm of USIA) | 1976ANKARA03731: "...COMMENDATION OF USIS ANKARA..." |
| `USDA` | US Department of Agriculture | 1979STATE111241 body: "...USDA/FAS PLANNING FOR..." |
| `UJNR` | US-Japan Cooperative Program in Natural Resources | 1974STATE011857: "...JOINT UJNR AQUACULTURE PANEL MEETING..." |
| `NIOC` | National Iranian Oil Company | 1973TEHRAN07507: "...NIOC-CONSORTIUM MEMBERS MEET ON 1974 BUDGET..." |
| `FCIA` | Foreign Credit Insurance Association | 1974STATE000342: "...FCIA CREDIT INSURANCE REQUEST FOR SALE OF CATERPILLAR..." |
| `CACM` | Central American Common Market | 1973GUATEM05367: "...CACM: IS APATHY THE PREVAILING MOOD?..." |
| `KCIA` | Korean Central Intelligence Agency | 1976STATE051178: "...CONGRESSIONAL HEARING ON KCIA ACTIVITIES..." |
| `ICCO` | International Cocoa Organization | 1974LONDON14838: "...COCOA: TRAVEL OF ICCO EXECUTIVE DIRECTOR..." |
| `CIME` | OECD Committee on International Investment and Multinational Enterprises | 1977OECDP07647 body: "...MULTINATIONAL ENTERPRISES (CIME), NEXT MEETING..." |
| `BWIA` | British West Indian Airways | 1976PORTO03018: "...BWIA PROMOTIONAL FARES..." |
| `ICES` | International Council for the Exploration of the Sea | 1978STATE229332: "...ICES - INTERNATIONAL COUNCIL FOR EXPLOITATION..." |
| `FNCB` | First National City Bank (Citibank's former name) | 1973KARACH02406 body: "...BRANCHES IN PAKISTAN (FNCB, AMEX AND BANK OF AMERICA)..." |
| `ISVS` | International Secretariat for Volunteer Service | 1974GENEVA00150 body: "...SUBJ ISVS/UNV MERGER..." |
| `IAJC` | Inter-American Juridical Committee | 1973PANAMA04647: "...ISSUE BEFORE INTER-AMERICAN JURIDICAL COMMITTEE (IAJC)..." |
| `FIAT` | Fabbrica Italiana Automobili Torino (Italian automaker) | 1974ROME13567: "...FIAT TALKS BREAK DOWN..." (Rome/Turin auto-industry cables) |
| `CSTP` | OECD Committee for Scientific and Technological Policy | 1975OECDP05129: "...OECD/CSTP MEETING ON ENERGY R & D..." |
| `ABCC` | Atomic Bomb Casualty Commission (Tokyo, US-Japan joint body) | 1974STATE239891: "...ERDA AND ABCC..." (ERDA = Energy Research & Development Administration, its funding successor to AEC) |
| `CPSU` | Communist Party of the Soviet Union | 1974LENING00526 body: "...CPSU POLITBURO MEMBER M.A. SUSLOV..." |
| `CISL` | Confederazione Italiana Sindacati Lavoratori (Italian trade union confederation) | 1974LONDON04226 body: "...COMMUNIST-DOMINATED ITALIAN CGIL TO THE EUROPEAN..." context; 1975ROME12723 "...CISL MINORITY LEADER..." |
| `NTSB` | National Transportation Safety Board | 1974WELLIN00773: "...NTSB HEARING ON PAN AM CRASH PAGO PAGO..." |
| `IFRB` | International Frequency Registration Board (ITU) | 1976GENEVA06938: "...ITU: IFRB: PROVISIONAL NOTICES OF FREQUENCY ASSIGNMENTS..." |
| `ICAC` | International Cotton Advisory Committee | 1976SANSA04656 body: "...COTTON ADVISORY COMMITTEE (ICAC) SAN FRANCISCO..." |
| `FLEC` | Frente de Libertação do Enclave de Cabinda | 1974LUANDA00819 body: "...(FRENTE DE LIBERACAO DO ENCLAVE DE CABINDA - "FLEC")..." |
| `NMFS` | National Marine Fisheries Service | 1976STATE090146 body: "...NATIONAL MARINE FISHERIES SERVICE (NMFS)..." |
| `CEAO` | Communauté Économique de l'Afrique de l'Ouest (West African Economic Community) | 1975OUAGAD00649: "...CEAO SUMMIT MEETING..." |
| `CNAD` | NATO Conference of National Armaments Directors | 1975STATE251419 body: "...CONFERENCE OF NATIONAL ARMAMENTS DIRECTORS (CNAD)..." |
| `CEPE` | Corporación Estatal Petrolera Ecuatoriana (Ecuador state oil company) | 1974QUITO06939: "...PETROLEUM: CEPE ACTIONS..." |
| `OCAM` | Organisation Commune Africaine et Malgache | 1974BANGUI00881: "...EIGHTH OCAM SUMMIT CONFERENCE..." |
| `LPDR` | Lao People's Democratic Republic (official name post-1975) | 1976VIENTI01813: "...CONGRATULATORY MESSAGE FROM LPDR TO CUBAN LEADERS..." |
| `IGGI` | Inter-Governmental Group on Indonesia (aid consortium) | 1974STATE024589: "...GOI IGGI REQUEST..." (GOI = Government of Indonesia) |
| `IESC` | International Executive Service Corps | 1976NAIROB00748 body: "...CORPS (IESC) IN AFRICA..." |
| `FEOF` | Foreign Exchange Operations Fund (Laos monetary stabilization fund) | 1975VIENTI05418: "...FEOF: POSITIONS OF DONORS AND PGNU ON IMF REVIEW..." |
| `QUAI` | Quai d'Orsay (metonym for the French Foreign Ministry) | 1973PARIS30079 body: "...QUAI OFFICIAL SAID BREZHNEV-POMPIDOU SUMMIT..." |
| `CGIL` | Confederazione Generale Italiana del Lavoro (Italian communist-aligned union federation) | 1974LONDON04226 body: "...COMMUNIST-DOMINATED ITALIAN CGIL TO THE EUROPEAN..." |
| `CNEA` | Comisión Nacional de Energía Atómica (Argentina's atomic energy commission) | 1976BUENOS01462 body: "...CNEA HAS NUCLEAR RESPONSIBILITY AND SCIENCE&TECHNOLOGY..." |
| `AIIC` | American International Insurance Company (in this dataset's usage — not to be confused with the interpreters' association of the same acronym) | 1974LAGOS04576: "...AMERICAN INTERNATIONAL INSURANCE COMPANY (AIIC)..." |
| `APRA` | Alianza Popular Revolucionaria Americana (Peruvian political party) | 1974LIMA01570: "...APRA CELEBRATES HAYA'S 79TH BIRTHDAY..." (Haya de la Torre, APRA founder) |
| `FARC` | Fuerzas Armadas Revolucionarias de Colombia | 1974BOGOTA05106: "...THE REVOLUTIONARY ARMED FORCES OF COLOMBIA (FARC)..." |
| `ALIA` | Alia — The Royal Jordanian Airline | 1974AMMAN01711 body: "...DESIGNATES ALIA - ROYAL JORDANIAN AIRLINE..." |
| `USTS` | United States Travel Service | 1978SYDNEY02647: "...U.S. TRAVEL SERVICE STAFF VISIT..." |

### Guessed / unclear (contextual correlation only, or genuinely ambiguous — do not treat as reliable)

| Code | Best guess | Why it's uncertain |
|---|---|---|
| `BTOP` | Business Services: some kind of "Trade Opportunity" posting (near `BEXP`/`BFOL`-adjacent territory) | All 6 samples are generic "PRIVATE TRADE OPPORTUNITY" / "TRADE INQUIRY" subjects with no acronym spelled out anywhere — purely thematic correlation, no direct evidence of what "TOP" stands for |
| `AADP` | Possibly "Automated/Automatic Data Processing" (Administration field) | All 6 samples involve computers/commercial systems (Prague, Kampala, Seoul minicomputer installs) but the code itself never appears spelled out in any sample |
| `XCSS` | Possibly an OECD "Executive Committee in Special Session"-type body on East-West economic relations | All samples are "OECD MEETING OF XCSS" with no expansion; one adjacent unrelated doc mentions "OECD DISCUSSION OF EAST/WEST ECONOMIC RELATIONS", suggestive but not conclusive |
| `AORC` | Possibly a NATO committee | 5 of 6 samples originate from NATO/USNATO/NATOB posts, but none mention the code in subject/body text — pure posting-location correlation |
| `APAG` | Possibly a NATO advisory/planning group | All samples are "APAG MEETING" cables from NATOB (NATO Brussels); no expansion found in any sample |
| `FORD` | Ambiguous — mostly appears to mean **Ford Motor Company** (auto manufacturing/strikes/investment contexts: South Africa, UK, Egypt), but "FORD OFFICIALS" and "FORD INVESTMENT PROPOSAL" samples could instead mean the Ford Foundation | Multiple plausible referents, no sample disambiguates which |
| `GULF` | Ambiguous — most samples pair `GULF` with `BP`/`Texaco` as an oil company (**Gulf Oil Corporation**), in Kuwait/Ecuador/Peru petroleum-negotiation cables | Could also be misread as a geographic "Persian Gulf" reference in other docs; this may not be a genuine TAGS code at all (could be a company name leaking into the TAGS line, similar to the personal-name leak pattern documented above) |
| `OPDC` | Unclear — samples cluster around the Egypt-Israel peace process (Cairo, Jerusalem, SECTO channel, Sadat/Begin correspondence) | No code expansion found in any of the 6 samples; thematic cluster only |
| `ODIP` | Unclear | No discernible pattern across the 6 samples (Amman, Ankara, protest-note subjects, Brasilia, Paris) — insufficient signal |
| `NUTS` | **Likely not a real TAGS code at all** — samples show the literal English word (babassu nuts, almonds, dried fruit shipments) | Almost certainly a comma-split/parenthetical-fragment artifact (same mechanism as the `EARL`/`JACK` name leaks), not an organization code |
| `LIMA` | Likely informal drafter usage flagging the "Lima Programme"/Non-Aligned conference held in Lima, Peru — not a standard TAGS code | Real ACP-127 geographic TAGS are 2-letter country codes, not 4-letter city names; this looks like an ad hoc addition rather than a defined code |
| `IDEA` | Uncertain — recurring "IDEA CONFERENCE" across many cities (Santiago, Amsterdam, Cairo, Kuala Lumpur, Paris); one cable parenthetically glosses it as "IDEA (IAA)", hinting at a link to an advertising-industry association (IAA) | No sample spells out the full name; the IAA connection is speculative |

## Non-4-letter Organization TAGS (added while building src/tags_normalize.py)

`src/tags_normalize.py`'s classifier initially only checked `ORGANIZATION_TAGS`
for exactly-4-letter codes, so real (non-4-letter) organization codes it
encountered fell into `other` unclassified. Rather than add them from general
knowledge, the same sampling methodology used above (jq pass finding docs
tagged with each candidate code across all 7 years, sampling up to 8 per
code, checking subject/body text for confirming context) was applied to 24
candidates found in the `other` bucket. **23 confirmed, 1 explicitly
rejected**:

| Code | Meaning | Evidence |
|---|---|---|
| `ADB` | Asian Development Bank | 1976THEHA01371: "ASIAN DEVELOPMENT BANK (ADB) ANNUAL MEETING" |
| `BIE` | Bureau International des Expositions | 1976STATE307281: "BUREAU OF INTERNATIONAL EXPOSITIONS (BIE)" |
| `CENTO` | Central Treaty Organization | Consistent "CENTO MINISTERIAL MEETING"/"CENTO COUNCIL" usage across Ankara/Islamabad/London cables |
| `COCOM` | Coordinating Committee for Multilateral Export Controls | Consistent "COCOM DOC(nn)nnnn" / export-control-list-review context across multiple years |
| `ECAFE` | UN Economic Commission for Asia and the Far East | Bangkok-origin cables (ECAFE's actual HQ), "ECAFE: EXECUTIVE SECRETARY VISIT", "GUAM MEMBERSHIP IN ECAFE" |
| `ECE` | UN Economic Commission for Europe | Geneva-origin cables (ECE's actual HQ), "ECE SEMINAR ON..." recurring pattern |
| `ECOSOC` | UN Economic and Social Council | USUNN-origin: "ELECTED BY ECOSOC ON A BROAD AND FAIR GEOGRAPHIC BASIS", "62D ECOSOC" |
| `EEC` | European Economic Community | 1977BRUSSE09041: "MEETINGS OF THE EEC-ACP INSTITUTIONS" |
| `FAO` | Food and Agriculture Organization | Rome-origin cables (FAO's actual HQ), "AQUINO CANDIDACY FOR FAO DIRECTOR GENERAL" |
| `ILO` | International Labour Organization | 1977YAOUND02290: "63RD INTERNATIONAL LABOR CONFERENCE (ILC)" |
| `IMF` | International Monetary Fund | Consistent "IMF/IBRD MEETINGS", "IMF EXECUTIVE DIRECTOR" usage |
| `ITU` | International Telecommunication Union | Geneva-origin, "ITU MONTHLY MAGAZINE TELECOMMUNICATION" |
| `NAC` | North Atlantic Council (NATO) | NATOB/USNATO-origin: "NOON SESSION OF NAC IN BRUSSELS", "DECEMBER NAC MINISTERIAL" |
| `OAS` | Organization of American States | Consistent "OAS SPECIAL COMMITTEE", "SECRETARY GENERALSHIP OF OAS" usage |
| `OAU` | Organization of African Unity | Addis Ababa-origin cables (OAU's actual HQ), "OAU SECRETARY GENERAL" |
| `PANAM` | Pan American World Airways | 1975BRUSSE01878: "PANAM BRUSSELS REP WILLIAM O'GORMAN" |
| `SEATO` | Southeast Asia Treaty Organization | Bangkok-origin cables (SEATO's actual HQ), "SEATO COUNCIL MEETING" |
| `UNCTAD` | UN Conference on Trade and Development | Geneva-origin, "UNCTAD: COMMITTEE ON ECONOMIC CO-OPERATION" |
| `UNESCO` | UN Educational, Scientific and Cultural Organization | Paris-origin cables (UNESCO's actual HQ), "IO/UNESCO" |
| `UNIDO` | UN Industrial Development Organization | Vienna-origin cables (UNIDO's actual HQ), "UNIDO TENTH SESSION INDUSTRIAL DEVELOPMENT BOARD" |
| `UNRWA` | UN Relief and Works Agency for Palestine Refugees | Beirut/Amman-origin, "UNRWA AND PLO", "UNRWA: JORDAN AND US CO-SPONSOR" |
| `WHO` | World Health Organization | Geneva-origin, "WHO PROGRAM BUDGET 1978-1979" |
| `WMO` | World Meteorological Organization | 1978GENEVA09021: "WORLD METEOROLOGICAL ORGANIZATION (WMO)" spelled out |

**Rejected: `XMB`.** All 8 sampled documents either show no direct mention of
`XMB` anywhere in subject/body text, or only indirect co-occurrence with
Export-Import Bank subjects ("REOPENING EX-IM BANK LENDING TO CHILE",
"EXIMBANK FINANCING", "FCIA CLAIM"). Unlike every confirmed code above, no
sample ever names what `XMB` stands for. This is consistent with it being a
State Department distribution/action-office code (like the `EB-11`, `OCT-01`
style codes seen in cable header routing lines) rather than an organization —
exactly the failure mode to guard against, and why it is **not** in
`ORGANIZATION_TAGS`.

### Caveats

- Sample size is small (up to 6 docs per code, spread across the full match
  list but not exhaustive) — a "documented" entry could still occasionally
  co-refer to something else in a small number of documents (e.g. `AIIC`,
  `CEMA`, `ABCC` all have plausible alternate meanings in other domains that
  didn't surface in this sample).
- This is TAGS-code research, not a verified authoritative reference — for
  anything load-bearing, cross-check against the actual NARA TAGS/Terms
  handbooks referenced in `docs/faqs.txt` Q3, which are outside this repo.
- The 111 codes described above (88 + 23) were this session's corpus-research
  additions to `ORGANIZATION_TAGS`. **Superseded/extended below**: a primary
  source (the actual 1974 State Dept TAGS handbook) was later located and is
  now the preferred source wherever it overlaps — see the section below.
  The 12 **guessed/unclear** codes (`BTOP`, `AADP`, `XCSS`, `AORC`, `APAG`,
  `FORD`, `GULF`, `OPDC`, `ODIP`, `NUTS`, `LIMA`, `IDEA`) remain deliberately
  left out — this document is the only place they're recorded.
  `ORGANIZATION_TAGS` is a separate dict from
  `PERMANENT_SUBJECT_TAGS`/`TEMPORARY_SUBJECT_TAGS` so the FAQ-sourced
  Subject TAGS mapping and the Organization TAGS mapping are never conflated.
  `classify_subject_tag()` is unaffected and still classifies these same
  codes as `"unknown"`, since they are not Subject TAGS in `docs/faqs.txt`'s
  sense; use `lookup_organization_tag()` for this mapping instead.

## Primary source found: the actual 1974 State Dept TAGS handbook

The user supplied `docs/rg59_state_dept_tags_74.pdf` / `.txt` — "TRAFFIC
ANALYSIS BY GEOGRAPHY AND SUBJECT and EXECUTIVE ORDER 11652 CODES", Department
of State, TL:TAGS-1, dated **6-28-74**. This is the actual period-accurate
primary source for this corpus (1973-1979), superseding both the corpus-
sampling research above and the modern (2024) FAM reference for anything it
covers. **The embedded/extracted OCR text (both the user's `.txt` and a fresh
`pdftotext` pass) is too corrupted to use directly** (e.g. "GEQGRAPHY A N D
SUBJECT", "T;L4NSh.lITT.4!,"). Instead, `pdftoppm` was used to render the
relevant pages (Sections 11 "Geographic TAGS" and 15 "Organization TAGS") as
images at 200dpi, which were read and transcribed directly (visually, not via
OCR) into `src/tags_mapping.py` as `COUNTRY_TAGS_1974`, `REGION_TAGS_1974`,
and merged into `ORGANIZATION_TAGS` (1974 wording wins where it overlaps with
the corpus-research entries above; entries not covered by the 1974 handbook
are kept as-is).

**Also fetched**: the modern State Dept TAGS reference itself, since it was
the first thing checked before the 1974 handbook was supplied —
[5 FAH-3 H-410](https://fam.state.gov/FAM/05FAH03/05FAH030410.html)
(Geo-Political TAGS, current) and
[5 FAH-3 H-110](https://fam.state.gov/fam/05fah03/05fah030110.html)
(Subject TAGS Categories, current) — both UNCLASSIFIED (U) published
reference material. `fam.state.gov` serves an incomplete TLS certificate
chain (a server-side misconfiguration, not a trust concern for this
unauthenticated public page), so `curl -k` was used to fetch it.

### Coverage impact (measured on full 1973 data, 155,278 docs)

| Metric | Corpus-research + modern FAM only | + 1974 handbook (primary) |
|---|---:|---:|
| Geographic-shaped occurrences resolved | 66.8% (modern FAM table only) | **94.8%** |
| `tags_normalize.py` named rate | 50.12% | **63.60%** |
| `tags_normalize.py` classified rate | 82.06% | **95.45%** |
| `tags_normalize.py` `unknown` bucket | 65,937 (13.79%) | **3,387 (0.71%)** |

### `XMB` resolved

The previous session flagged `XMB` (471-586 occurrences depending on year) as
correlating with Export-Import Bank subjects but rejected it for lack of
direct confirmation — exactly the caution the user asked for. The 1974
handbook's Organization TAGS list (Section 15) settles it definitively:
**`XMB` = "Export-Import Bank of the United States"**. It was a real,
prescribed Organization TAGS code; the earlier corpus-sampling method simply
couldn't prove it without the primary source. Now included in
`ORGANIZATION_TAGS`.

### Geographic TAGS — 1974 vs. current codes differ substantially

The 1974 handbook uses a **different 2-letter coding scheme** than today's
GENC/ISO-3166 standard. Common differences found: `UK` (not modern `GB`) for
United Kingdom, `JA` (not `JP`) for Japan, `SP` (not `ES`) for Spain, `TU`
(not `TR`) for Turkey, `IZ` (not `IQ`) for Iraq, `PO` (not `PT`) for
Portugal, `HO` (not `HN`) for Honduras, `IC` (not `IS`) for Iceland (note:
`IC`≠"Chile" despite the near-miss — `CI` is Chile, `IC` is Iceland), plus
codes for entities with no current equivalent: `UR` (Soviet Union), `YO`
(Yugoslavia), `CS` (Costa Rica in the 1974 scheme — **not** Czechoslovakia,
which is `CZ`), `VS`/`VN` (South/North Vietnam), `CB` (Khmer Republic/
Cambodia), `WB` (West Berlin), `RH` (Rhodesia). `src/tags_mapping.py`'s
`lookup_geographic_tag()` checks the 1974 tables first and only falls back to
the modern ones for codes the 1974 handbook doesn't have (post-1974
independences like Angola, Mozambique).

### Verification pass

Every transcribed entry was re-checked directly against the page images a
second time (all of Section 11's country/region pages, both pages of
Section 15's Organization TAGS list). Every single Organization TAGS entry
(pages TAGS 15 p.1-2) matched exactly on the second pass — zero errors.

Cross-checking Section 11 (the alphabetical-by-country list, pages TAGS 11
p.1-3) against Section 12 (the by-region cross-reference, pages TAGS 12
p.1-6, which repeats every country grouped under its world region) surfaced
two codes present in Section 12 but **missing from Section 11's own
alphabetical list** — an omission in the original 1974 document itself, not
a transcription error on this side:

| Code | Country | Found in |
|---|---|---|
| `TK` | Turks and Caicos Islands | Section 12, "XL Caribbean" region group only |
| `TL` | Tokelau Islands | Section 12, "XP Pacific Ocean Area" region group only |

Both are now included in `COUNTRY_TAGS_1974` (229 entries total, up from
227). No other discrepancies were found across either section on this
verification pass.
