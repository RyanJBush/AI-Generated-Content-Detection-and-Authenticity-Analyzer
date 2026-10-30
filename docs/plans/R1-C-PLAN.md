# R1-C plan — Text quality observers

**Status: PROPOSED — not approved.** Plan only; no observer code exists. Drafted
2026-10-30 on top of `6b94138`. Governing documents: R1-PLAN-CORRECTIONS-A.md >
R1-PLAN.md > SPEC-v0.3-ADDENDUM-B.md > SPEC-v0.3-ADDENDUM-A.md > SPEC.md. Every
choice below marked **OPEN** is for Ryan to decide (§h).

Python facts cited below were checked on the project interpreter (CPython
3.13.7, stdlib `re`) on 2026-10-30. Anything not checked is labeled.

---

## a) Separation from origin evidence

**Record type.** Observers emit only `QualityObservation` (SPEC §4.3; already in
`src/litmus/schemas.py`):

| Field | Meaning in R1-C |
|---|---|
| `observer_id` | `stock_phrases`, `hedges`, `repeated_word_3grams`, `claim_phrases_to_inspect` |
| `observer_version` | Observer code version, e.g. `"1"` (bumped on any matching-rule change) |
| `status` | `observed` (count ≥ 1) · `none_found` (count 0) · `not_supported` (not a text segment; see below) · `error` (observer raised, or its lexicon failed validation) |
| `count` | Integer per observer definition (§b); `null` on `error` / `not_supported` |
| `rate_per_100_words` | `count / words × 100`; `null` when `words == 0`, and on `error` / `not_supported` |
| `spans` | `[start, end)` code-point ranges in the segment's `text_codepoints` frame |
| `notes` | Fixed-format strings, e.g. `lexicon_sha256=…` (§d), error class on `error` |

No `result`, score, threshold, or calibration (SPEC §4.3).

**Isolation by interface.**
- Each observer is a pure function `observe(text: str, words: WordIndex) -> QualityObservation`.
- It receives the decoded segment text, a precomputed word index (§c) and nothing else. It has no access to the `Segment`, the report or any `OriginEvidence`.
- The report builder computes origin evidence first, then runs observers, then appends to `segment.quality`.
- Observers run only on text segments. Image segments keep `quality: []` (SPEC §4.1: text only in R1), so `not_supported` is reserved for a future call on a non-text frame and is not emitted in R1. **OPEN (minor):** emit `not_supported` records for image segments instead of an empty list.

**Origin-separation test (required, R1-PLAN "Done when").** For each fixture:
1. Build the report with observers disabled, and again with observers enabled.
2. For every segment, serialize `origin` with `schemas.to_json` and then `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.
3. Assert the UTF-8 bytes are identical.

Origin variants to run:
- the R0 placeholder;
- a deterministic stub `TextOrigin` that returns a fixed `OriginEvidence` with a `raw_score` and details;
- a stub observer that raises, which must give a `status: error` record and leave origin byte-identical;
- a stub observer that tries to mutate its input. Python `str` is immutable, so the test instead asserts that the `Segment` object's origin list is the same object with equal contents before and after.

Fixtures: text with matches in every observer; whitespace-only text; an image fixture, where `quality` must stay `[]`.

## b) Proposed observers (SPEC §8.3)

All lexicon observers share one matcher (§c). Definitions:

| Observer | Definition | `count` |
|---|---|---|
| `stock_phrases` | Matches of entries in `data/lexicons/stock_phrases.txt` | Number of non-overlapping matches |
| `hedges` | Matches of entries in `data/lexicons/hedges.txt` | Number of non-overlapping matches |
| `repeated_word_3grams` | Word 3-grams (three consecutive words of the word index; key = the three words, each `str.casefold()`ed, used only as a dictionary key, never to compute offsets) whose key occurs **≥ 2** times | Total occurrences of all repeated 3-grams (a 3-gram seen 3 times adds 3) |
| `claim_phrases_to_inspect` | Matches of entries in `data/lexicons/claim_phrases_to_inspect.txt` | Number of non-overlapping matches |

**Repeated 3-grams: span rules.**
- Every occurrence of a repeated 3-gram is one span: from the start of its first word to the end of its third word.
- Spans may overlap within this observer (e.g. `"x x x x"` has 3-gram `(x,x,x)` at word positions 0 and 1). The lexicon overlap policy (§c) does not apply here, because the requirement is to report every occurrence.
- Proposed: 3-grams cross punctuation and line breaks, since words are word-index tokens and everything between them is ignored. **OPEN:** whether 3-grams should stop at sentence or line boundaries.
- No stop-word filtering, so `"one of the"` counts. **OPEN:** stop-word filtering (proposed: none in R1).

**Claim phrases are not evidence.**
- Every `claim_phrases_to_inspect` record carries the note `label=phrase to inspect` and `note=not evidence that any claim is unsupported`.
- The UI shows the label verbatim (§g).

## c) Text handling (exact rules)

**Input.** The already-decoded segment string, exactly as ingestion produced it. No Unicode normalization, no case conversion and no whitespace changes (SPEC §5.3). All offsets index this string.

**Case-insensitive matching on the original string.**
- Lexicon entries compile to one `re.compile(pattern, re.IGNORECASE)` per lexicon (Unicode is the default for `str` patterns), and matching runs with `finditer` on the original text.
- No `lower()`/`casefold()` copy is ever matched and mapped back. Checked behavior:
  - `'ß'.casefold()` is `'ss'` (length 2) and `'İ'.lower()` has length 2, so a lowered copy would shift offsets.
  - `re` with IGNORECASE uses simple case folding, so lengths are preserved: `(?i)ß` matches `ẞ` but not `SS`, and `(?i)k` matches `K` (Kelvin sign U+212A).
- **Consequence (documented):** full-case-folding equivalents such as `ß` ↔ `ss` and ligatures like `ﬁ` ↔ `fi` are not matched.

**Word definition (one regex, used for word counts, 3-grams and lexicon boundaries).**
```
WORD_CHAR = [^\W_]  plus combining marks  [̀-ͯ᪰-᫿᷀-᷿⃐-⃿︠-︯]
JOINER    = ['’\-‐‑]
WORD      = WORD_CHAR+ (?: JOINER WORD_CHAR+ )*
```
- **Letters and digits:** any script counts (`[^\W_]` is Unicode `\w` minus the underscore). Cyrillic and CJK letters are word characters (checked). Digits are word characters, so `2024` is a word.
- **Apostrophes:** ASCII `'` and U+2019 join two word runs, so `don't` and `don’t` are one word. A leading or trailing apostrophe is not part of the word.
- **Hyphens:** `-`, U+2010 and U+2011 join two word runs, so `ever-evolving` is one word. A dash (U+2013, U+2014) separates words.
- **Combining marks:** these are not `\w` in stdlib `re` (checked: `\w` does not match U+0301). Without the explicit ranges above, decomposed `e` + U+0301 would split a word. Combining marks outside the listed blocks still split words; this is documented.
- **Underscore:** a separator.
- **CJK and other scripts without spaces:** a contiguous run counts as one word. Word counts and rates for such text are not meaningful (documented limitation).
- **Zero-width and format characters (Cf, e.g. U+200B, U+200D, U+00AD):** not word characters (checked for U+200B), so they split words (§e).

**Lexicon entry → pattern.**
- Each entry is a sequence of words (validated in §d) separated by single spaces.
- A space in an entry matches `\s+`. Python `\s` is Unicode whitespace; U+200B is not `\s` (checked).
- An apostrophe in an entry matches `['’]`, and a hyphen matches `[-‐‑]`.
- Other characters are matched literally (`re.escape`).
- Boundaries, using fixed-width lookarounds only:
  ```
  (?<!WORD_CHAR)(?<!WORD_CHAR JOINER)  <entry>  (?!WORD_CHAR)(?!JOINER WORD_CHAR)
  ```
  A match therefore never starts or ends inside a `WORD` as defined above. `perhaps` does not match inside `perhaps-not` or `perhapsx`, but it does match in `perhaps, not` and `"perhaps"`. This is Litmus's word definition, not `\b`, which treats `_` as a word character and splits combining marks.

**Overlap policy within one lexicon observer (proposed; OPEN).**
- Leftmost-longest, non-overlapping, scanned left to right.
- Implementation: one alternation with entries ordered by (word count descending, character length descending, entry text ascending), run with `finditer`. Python alternation takes the first alternative that matches at the leftmost position, so the longest entry wins at each start.
- Example: with entries `it is important to note` and `important`, the text `it is important to note` gives 1 match, not 2.
- Overlaps across observers are allowed: `it is possible that studies show` may yield both a hedge and a claim-phrase span.

**Rate and empty cases.**
- `words` = number of `WORD` matches in the segment.
- `rate_per_100_words = count / words × 100` as a float, not rounded in the record. It is `null` when `words == 0`.
- Whitespace-only text gives `none_found`, `count = 0`, `rate = null`, `spans = []` for every observer, consistent with Addendum B2.
- Text with words but no matches gives `none_found`, `count = 0`, `rate = 0.0`.
- Text without any word character (e.g. `"... !!!"`) is treated the same as whitespace-only: `none_found`, rate `null`.

**Spans.**
- `[start, end)` code points in the segment's local `text_codepoints` frame (SPEC §5.3).
- For lexicon observers, `text[start:end]` equals the matched surface text exactly (`m.start()`, `m.end()` of the match on the original string). For 3-grams, the slice is the original text from the first word's start to the third word's end.
- Spans are sorted by (start, end) and contain no duplicates.

**Offline (SPEC §7, Addendum A1.2).** Observers are pure Python, with no network-capable code and no subprocesses, and they run under `offline_guards()`.

**Note for Ryan:** SPEC §7 says "no I/O beyond the input". Lexicons are files (SPEC §8.3), so this plan reads and validates them once when the observers are constructed, before analysis. The `observe()` call itself does no I/O. Confirm this reading.

## d) Versioned lexicons

**Location and encoding.**
- `data/lexicons/<name>.txt`, UTF-8 without BOM, LF line endings.
- Add `data/lexicons/** -text` to `.gitattributes` so the SHA-256 of the raw bytes is stable across checkouts.
- The SHA-256 is computed over the raw file bytes.

**Format.**
```
# name: hedges
# version: 1
# author: <OPEN: author attribution, e.g. "Litmus project (author-written)">
# license: <OPEN: repository license is not yet chosen (README)>
# date: 2026-10-30
# source: author-written for Litmus; not derived from any published list
perhaps
it seems
```
- **Header:** the first six lines are `# key: value` with exactly these keys in this order: `name`, `version`, `author`, `license`, `date`, `source`. `name` must equal the file stem. `version` is a positive integer. `date` is ISO 8601.
- **Comments:** after the header, a line whose first non-space character is `#` is a comment. Blank lines are ignored. Entries cannot contain `#`, and inline comments are not supported.
- **Entries:** one per line, with leading and trailing whitespace stripped.

**Validation (at load; any failure gives `status: error` for that observer, with the note `lexicon_invalid=<reason>`; origin and other observers are unaffected):**
- The header is present and valid.
- At least one entry, and no empty entries.
- No duplicates under case-insensitive comparison, using `str.casefold()` on entries. This comparison is for validation only, never for matching.
- Each entry is one or more `WORD`s (§c) separated by single ASCII spaces, so every entry is matchable under the word definition.
- No entry may contain a control character, a Cf character (zero-width or format), or characters outside the `WORD` alphabet plus apostrophe and hyphen.

**Where the hash and version go (proposed; OPEN).**
- Fixed-format entries in `notes`: `lexicon_name=hedges`, `lexicon_version=1`, `lexicon_sha256=<64 hex>`.
- `observer_version` stays the code version.
- This needs no schema change to SPEC §4.3. The alternative is new optional fields on `QualityObservation`, which would amend SPEC §4.3.
- In either case, R1-F's freeze record (SPEC §10.9) lists all lexicon hashes.
- Observer code is **not** added to `scoring_config_hash`, because quality observations are not part of origin scoring.

**Proposed lexicon contents v1 (author-written, small, for Ryan's review).**
- These are common English expressions written for this plan, not copied from any list.
- They describe surface patterns, not quality or origin.

| `stock_phrases` (20) | `hedges` (20) | `claim_phrases_to_inspect` (14) |
|---|---|---|
| a myriad of | arguably | according to experts |
| a testament to | could be | data shows |
| at the end of the day | generally | evidence suggests |
| delve into | in some cases | experts agree |
| ever-evolving | it appears that | experts say |
| first and foremost | it is possible that | it has been proven |
| game changer | it seems | it is well known that |
| in conclusion | kind of | it is widely accepted |
| in the realm of | likely | research has shown |
| in today's fast-paced world | might | research shows |
| it goes without saying | perhaps | scientists say |
| it is important to note | possibly | statistics show |
| last but not least | probably | studies have shown |
| navigate the complexities | relatively | studies show |
| needless to say | seems to | |
| pave the way | somewhat | |
| plays a crucial role | sort of | |
| rich tapestry | tends to | |
| shed light on | to some extent | |
| unlock the potential | appears to | |

Notes on the contents:
- `may` is deliberately excluded from hedges because the month "May" is case-insensitively identical. Ryan to confirm.
- `it's important to note` is not listed separately. **OPEN:** whether entries should also match the contracted form. Proposed: no automatic expansion; add contractions as explicit entries.
- `appears to` and `it appears that` coexist; longest-match handles `it appears that`.

## e) Limitations (for reports and the README)

When observers run, the report's top-level `limitations` gain fixed sentences. The README gets a matching section:

1. **Language:** lexicons are English-oriented. Results on other languages are not meaningful, and scripts written without spaces count runs as single words.
2. **Genre:** frequencies depend on genre and register (recipes, legal text, academic hedging, marketing). There are no norms or baselines.
3. **Surface patterns only:** counts describe surface patterns, not quality judgments. A high count is not "bad writing", and a zero count is not "good writing".
4. **No accuracy claim:** quality observations have no relationship to AI origin and never affect origin results.
5. **Evasion:** homoglyphs (e.g. Cyrillic `о` for Latin `o`) and zero-width or format characters (e.g. U+200B) can split words or break matches, so phrases written that way are not counted. Unicode equivalences beyond simple case folding (e.g. `ß` ↔ `ss`, ligatures, compatibility forms) are not matched. This is documented behavior: tests assert a correct, non-crashing result with the reduced count.
6. **Claim phrases:** a "phrase to inspect" points at wording worth checking. It is not evidence that a claim is unsupported.

## f) Tests

All tests are in the default suite, model-free, and run under the socket guard.

**Per-observer unit tests: exact counts and exact spans.**
- `stock_phrases`, `hedges` and `claim_phrases_to_inspect`: fixed texts with known entries, giving exact `count`, `spans` and `rate`.
- Checks: case variants (`DELVE INTO`), multi-space and newline inside a phrase, a boundary miss (`perhapsx`), longest-match (`it is important to note` counts once), and adjacency of two entries.
- `repeated_word_3grams`: `"a b c d a b c"` gives count 2 with spans for both `a b c`. `"x x x x"` gives count 2 with overlapping spans. A text without repeats gives `none_found`. Case-insensitive key: `"The cat sat. the CAT sat"` gives 2.

**Metamorphic tests.**
- **Insert a phrase:** inserting one lexicon phrase, surrounded by spaces, between two neutral words that start no lexicon entry raises that observer's count by exactly 1 and the word count by the phrase's word count. Other lexicon observers are unchanged, unless the phrase is also in their lexicon (constructed to avoid this).
- **Duplicate a sentence:** let S be a sentence of `w ≥ 3` pairwise-distinct words, with no word repeated in the base text. Then `T = S` has `repeated_word_3grams.count = 0`. `T' = S + " " + S` has count exactly `2(w − 2)`: each internal 3-gram appears twice. The two boundary 3-grams (last two words of the first S + first word of the second, and so on) are unique because the words are distinct, so they add 0.
- **Number after "studies show":**
  - **Expected:** appending ` 42%` after `studies show` (separated by whitespace) leaves the claim count unchanged (1 → 1): the match ends at `show`, and the next character is a space, not a word character.
  - **Also asserted:** `studies show42` gives count 0, because digits are word characters and the boundary fails. This follows from the word definition and is documented.
  - **Also asserted:** `studies show, 42` gives count 1.

**Span-integrity tests.** For every span, `0 ≤ start < end ≤ len(text)` and `text[start:end]` equals the expected surface string. Inputs:
- **Emoji:** an emoji (supplementary-plane, e.g. U+1F600) before a phrase gives offsets in code points, not UTF-16 units.
- **ZWJ sequence:** an emoji ZWJ sequence before a phrase.
- **CJK:** CJK text around an English phrase.
- **Combining characters:** decomposed `cafe` + U+0301 counts as one word.
- **Sharp s:** `ß`/`ẞ` inside an entry-adjacent word. Offsets are unchanged, and there is no `ss` match.
- **U+200B:** inside a phrase, the match is missing and there is no crash. Between words, it acts as a separator.
- **Homoglyph:** Cyrillic `о` inside `show` means no match, the word count is still correct, and there is no crash.

**Empty cases.**
- Empty string, whitespace-only, and punctuation-only text give `none_found`, `count 0`, `rate null` and `spans []` for all four observers.
- A text with one word and no matches gives rate `0.0`.

**Lexicon validation.**
- Each rule in §d fails with its reason: missing header, wrong key order, name ≠ stem, an empty entry, a case-insensitive duplicate (`Perhaps` / `perhaps`), a Cf character, `#` in an entry, an unmatchable entry (e.g. `--`).
- All committed lexicons validate.
- Their SHA-256 values match the values recorded in `docs/decisions.md` at approval.
- The hash note appears in each record.

**Performance.**
- A 200,000-code-point input (ingestion's `MAX_DECODED_CHARS`) completes all four observers within **5 s** wall time on the R1-B2 machine. **This bound is an ESTIMATE, not measured.**
- Inputs:
  - word-salad English with phrase hits;
  - 100,000 repetitions of `"a "`, the worst case for 3-gram span volume;
  - one 200,000-character word with no spaces;
  - 200,000 CJK characters.
- The entry patterns contain no nested quantifiers, only `\s+` between literals, so catastrophic backtracking is not expected (ESTIMATE, to be confirmed by this test).
- The measured time is recorded in the R1-C report.

**Origin separation.** The test from §a.

**Schema round-trip.**
- `from_json(Segment, to_json(segment))` equals the original for segments carrying all four observation kinds, including `rate null`, overlapping spans and notes.
- An invalid `status` is rejected (existing behavior, re-asserted for observer output).
- A full CLI report with observers enabled parses and round-trips.

## g) Report and UI integration

**CLI report.**
- Observations go in `segments[i].quality[]`, a field that already exists and is currently always `[]`.
- Order: `stock_phrases`, `hedges`, `repeated_word_3grams`, `claim_phrases_to_inspect`.
- When observers ran, the top-level `limitations` gain the §e sentences.
- **OPEN:** whether observers are on by default.
  - If on by default, the R0 golden files are regenerated deliberately in one commit with the reason recorded.
  - If opt-in, a `--quality {off,on}` flag mirrors `--text-origin`. Proposed: opt-in for R1-C, with the default switched at R1-H.

**UI (R1-H).**
- Quality observations appear in a section titled **"Content observations (not origin evidence)"**.
- That section is visually separate from the origin section: its own heading and container, no shared color scale, and never placed inside or beside the origin result badge.
- Claim phrases are shown with the label "phrase to inspect".
- Spans are highlighted in the text view with a style distinct from any origin display.
- The "not a probability" note belongs to origin only and is not repeated as if it applied to counts.

## h) Open decisions for Ryan (not decided here)

1. **Lexicon contents:** the three v1 lists in §d, including dropping `may`, contraction handling, and the author and license header values (repository license is still OPEN).
2. **Overlap policy:** leftmost-longest non-overlapping within a lexicon observer (proposed), versus reporting all overlapping matches.
3. **Lexicon hash location:** `notes` key=value entries (proposed, no schema change) versus new optional `QualityObservation` fields (SPEC §4.3 amendment).
4. **Performance bound:** 5 s for 200,000 code points (ESTIMATE until measured).
5. **Whether `claim_phrases_to_inspect` ships in R1**, or is deferred.
6. **Additional decisions raised by this plan:**
   - 3-grams crossing sentence and line boundaries (proposed: they cross).
   - Stop-word filtering (proposed: none).
   - Span cap: every occurrence is reported, so a 200,000-character repetitive input can produce tens of thousands of spans (megabytes of JSON). Options are no cap (proposed for R1, with size measured in the performance test) or a cap that keeps the exact `count` and adds the note `spans_truncated`.
   - Observers on by default versus `--quality on` (proposed: opt-in until R1-H).
   - `not_supported` records for image segments versus an empty `quality` list (proposed: empty list).
   - Confirming that reading lexicon files at construction satisfies SPEC §7 "no I/O beyond the input".

## i) Effort (ESTIMATE) and checkpoints

**Effort: ESTIMATE 7–11 focused hours.**

| Part | ESTIMATE |
|---|---|
| Word index, lexicon format, validator, entry→pattern compiler | 1.5–2.5 h |
| Four observers | 1.5–2 h |
| Unit, metamorphic, span-integrity, empty-case and validation tests | 2–3 h |
| Report/CLI integration, origin-separation test, round-trip, performance test | 1–2 h |
| Docs (interfaces.md, README limitations, decisions.md) | 1–1.5 h |

**Checkpoints.** Each ends with a commit, the full default and slow suites, Ruff, a clean tree and an independent review.

- **R1-C1: word index, lexicons and validator.**
  - Lexicon files with the contents Ryan approves, plus `.gitattributes`.
  - Word regex and entry compiler, plus tests (word definition, span integrity, validation).
  - Accepted when all §d validation tests pass, the lexicon hashes are recorded in `docs/decisions.md`, and no observer is wired into reports yet.
- **R1-C2: observers and integration.**
  - The four observers and their unit and metamorphic tests.
  - Report integration (per decision 6) and the §e limitations in the report and README.
  - The origin-separation, round-trip and performance tests.
  - Accepted when:
    - origin bytes are identical with and without observers on every fixture;
    - every span slice equals its surface text;
    - whitespace-only text gives `none_found` with rate `null`;
    - the performance test meets the approved bound, with its measured time recorded;
    - documentation is updated.

**Out of scope for R1-C:** RAID data, calibration, C2PA, UI implementation (R1-H), and any change to origin scoring or `scoring_config_hash`.
