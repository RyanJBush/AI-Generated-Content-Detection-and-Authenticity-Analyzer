# R1-C plan — Text quality observers

**Status: PROPOSED — not approved.** Plan only; no observer code exists.

- **Drafted** 2026-10-30 on top of `6b94138`. **Revision 2**, 2026-10-30, on top of `22aa1db`, following Ryan's revision instruction.
- **Governing documents:** R1-PLAN-CORRECTIONS-A.md > R1-PLAN.md > SPEC-v0.3-ADDENDUM-B.md > SPEC-v0.3-ADDENDUM-A.md > SPEC.md.
- **Status labels:**
  - **RECOMMENDED — pending Ryan's approval:** a proposal that is in this plan's design but not yet approved. All are listed in §h.1.
  - **OPEN:** still undecided (§h.2).

Python facts cited below were checked on the project interpreter (CPython 3.13.7, stdlib `re`) on 2026-10-30. Anything not checked is labeled.

---

## a) Separation from origin evidence

**Record type.** Observers emit only `QualityObservation` (SPEC §4.3; already in `src/litmus/schemas.py`):

| Field | Meaning in R1-C |
|---|---|
| `observer_id` | `stock_phrases`, `hedges`, `repeated_word_3grams`, `claim_phrases_to_inspect` |
| `observer_version` | Observer code version, e.g. `"1"` (bumped on any matching-rule change) |
| `status` | `observed` (count ≥ 1) · `none_found` (count 0) · `not_supported` (not emitted in R1; see below) · `error` (observer raised, or its lexicon failed validation) |
| `count` | Integer per observer definition (§b), always exact even when spans are capped; `null` on `error` |
| `rate_per_100_words` | `count / words × 100`; `null` when `words == 0`, and on `error` |
| `spans` | `[start, end)` code-point ranges in the segment's `text_codepoints` frame, capped at 1,000 (§c) |
| `notes` | Fixed-format `key=value` strings (§d) |

No `result`, score, threshold, or calibration (SPEC §4.3).

**Isolation by interface.**
- Each observer is a pure function `observe(text: str, words: WordIndex) -> QualityObservation`.
- It receives the decoded segment text, a precomputed word index (§c) and nothing else. It has no access to the `Segment`, the report or any `OriginEvidence`.
- The report builder computes origin evidence first, then runs observers, then appends to `segment.quality`.

**Image segments (RECOMMENDED — pending Ryan's approval).** Image segments keep `quality: []`. No `not_supported` records are emitted in R1 (SPEC §4.1: quality is text only in R1).

**Import isolation.** The quality-observer modules (`litmus.quality.*`) and the lexicon loader must not import `torch`, `transformers` or the scorer stack (`litmus.scorer.*`). Test: a fresh `python -I` subprocess, used in tests only:
1. Imports `litmus.quality`.
2. Constructs all four observers.
3. Runs them on a sample text.
4. Asserts that none of `torch`, `transformers` or any `litmus.scorer` module is in `sys.modules`.

**Origin-separation test (required, R1-PLAN "Done when").** For each fixture:
1. Build the report with observers off, and again with observers on.
2. For every segment, serialize `origin` with `schemas.to_json` and then `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.
3. Assert the UTF-8 bytes are identical.

Origin variants to run:
- the R0 placeholder;
- a deterministic stub `TextOrigin` that returns a fixed `OriginEvidence` with a `raw_score` and details;
- a stub observer that raises, which must give a `status: error` record and leave origin byte-identical;
- an identity check that the segment's origin list is the same object with equal contents before and after observers run.

Fixtures: text with matches in every observer; whitespace-only text; an image fixture, where `quality` must stay `[]`.

## b) Observers (SPEC §8.3)

**Ship all four observers with the small lexicons in §d (RECOMMENDED — pending Ryan's approval).**

| Observer | Definition | `count` |
|---|---|---|
| `stock_phrases` | Matches of entries in lexicon `stock_phrases` | Number of non-overlapping matches |
| `hedges` | Matches of entries in lexicon `hedges` | Number of non-overlapping matches |
| `repeated_word_3grams` | Word 3-grams whose key occurs **≥ 2** times. A word 3-gram is three consecutive words of the word index; its key is the three words, each `str.casefold()`ed, used only as a dictionary key and never to compute offsets | Total occurrences of all repeated 3-grams (a 3-gram seen 3 times adds 3) |
| `claim_phrases_to_inspect` | Matches of entries in lexicon `claim_phrases_to_inspect` | Number of non-overlapping matches |

**Repeated 3-grams: span rules.**
- Every occurrence of a repeated 3-gram is one span: from the start of its first word to the end of its third word. The 1,000-span cap (§c) applies.
- Occurrences may overlap within this observer (e.g. `"x x x x"` has `(x,x,x)` at word positions 0 and 1), because every occurrence is reported. The lexicon overlap policy (§c) does not apply here.
- **Crossing boundaries (RECOMMENDED — pending Ryan's approval):** word 3-grams are sequences of words under the word regex and may cross punctuation and line breaks. There is no sentence segmentation.
- **Stop words (RECOMMENDED — pending Ryan's approval):** no stop-word filtering, so `"one of the"` counts.

**Claim phrases are not evidence.**
- Every `claim_phrases_to_inspect` record carries the notes `label=phrase to inspect` and `note=not evidence that any claim is unsupported`.
- The UI shows the label verbatim (§g).

## c) Text handling (exact rules)

**Input.** The already-decoded segment string, exactly as ingestion produced it. No Unicode normalization, no case conversion and no whitespace changes (SPEC §5.3). All offsets index this string.

**Case-insensitive matching on the original string.**
- Each lexicon compiles to one `re.compile(pattern, re.IGNORECASE)` (Unicode is the default for `str` patterns), and matching runs with `finditer` on the original text.
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
- **Combining marks:** these are not `\w` in stdlib `re` (checked: `\w` does not match U+0301), so the blocks listed above are added explicitly. Combining marks outside them still split words; this is documented.
- **Underscore:** a separator.
- **CJK and other scripts without spaces:** a contiguous run counts as one word. Word counts and rates for such text are not meaningful (documented limitation; see §h.2).
- **Zero-width and format characters (Cf, e.g. U+200B, U+200D, U+00AD):** not word characters (checked for U+200B), so they split words (§e).

**Lexicon entry → pattern.**
- Each entry is a sequence of words (validated in §d) separated by single spaces.
- A space in an entry matches `\s+`. Python `\s` is Unicode whitespace; U+200B is not `\s` (checked).
- An apostrophe in an entry matches `['’]`, and a hyphen matches `[-‐‑]`.
- Other characters are matched literally (`re.escape`).
- **Contractions (RECOMMENDED — pending Ryan's approval):** a contraction matches only if it is listed explicitly as an entry. There is no automatic expansion: `it is important to note` does not match `it's important to note` unless that form is also listed.
- Boundaries, using fixed-width lookarounds only:
  ```
  (?<!WORD_CHAR)(?<!WORD_CHAR JOINER)  <entry>  (?!WORD_CHAR)(?!JOINER WORD_CHAR)
  ```
  A match therefore never starts or ends inside a `WORD`. `perhaps` does not match inside `perhaps-not` or `perhapsx`, but it does match in `perhaps, not` and `"perhaps"`. This is Litmus's word definition, not `\b`, which treats `_` as a word character and splits combining marks.

**Overlap policy (RECOMMENDED — pending Ryan's approval).**
- Leftmost-longest, non-overlapping, scanned left to right, within each lexicon observer.
- Implementation: one alternation with entries ordered by (word count descending, character length descending, entry text ascending), run with `finditer`. Python alternation takes the first alternative that matches at the leftmost position, so the longest entry wins at each start.
- Example: with entries `it is important to note` and `important`, the text `it is important to note` gives 1 match.
- Overlaps across observers are allowed: `it is possible that studies show` may yield both a hedge and a claim-phrase span.

**Rate and empty cases.**
- `words` = number of `WORD` matches in the segment.
- `rate_per_100_words = count / words × 100` as a float, not rounded in the record. It is `null` when `words == 0`.
- Whitespace-only text gives `none_found`, `count = 0`, `rate = null`, `spans = []` for every observer, consistent with Addendum B2.
- Text with words but no matches gives `none_found`, `count = 0`, `rate = 0.0`.
- Text without any word character (e.g. `"... !!!"`) is treated the same as whitespace-only: `none_found`, rate `null`.

**Spans.**
- `[start, end)` code points in the segment's local `text_codepoints` frame (SPEC §5.3).
- For lexicon observers, `text[start:end]` equals the matched surface text exactly (`m.start()`, `m.end()` on the original string). For 3-grams, the slice is the original text from the first word's start to the third word's end.
- Spans are sorted by (start, end) and contain no duplicates.

**Span cap (RECOMMENDED — pending Ryan's approval).**
- At most **1,000** spans per observer per segment: the first 1,000 in (start, end) order.
- `count` stays exact.
- Every record carries `spans_truncated=true|false` and `spans_reported=<n>` in `notes`.
- Example: 100,000 repetitions of `"a "` give `count = 99998`, `spans_reported=1000` and `spans_truncated=true`.

**Offline and file access (SPEC §7, Addendum A1.2).**
- Lexicons are read once, at observer initialization, from local package resources (§d). This is local configuration, the same in kind as reading pinned model files from a local directory.
- During observation there is no file access, no network access and no subprocess. `observe()` operates only on its input string and in-memory compiled patterns.
- **This satisfies SPEC §7 ("Pure Python; no I/O beyond the input") for the observation step.** Observers run under `offline_guards()`.

## d) Versioned lexicons

**Package resources.**
- Lexicons ship inside the package as `src/litmus/quality/lexicons/<name>.txt` and are declared as package data in `pyproject.toml`:
  ```toml
  [tool.setuptools.package-data]
  "litmus.quality" = ["lexicons/*.txt"]
  ```
- They are loaded with `importlib.resources.files("litmus.quality").joinpath("lexicons", f"{name}.txt").read_bytes()`, never through `__file__`, a source-tree path or a relative filesystem path.
- Loading happens once, at observer initialization. The loader validates the bytes and computes their SHA-256.
- Add `src/litmus/quality/lexicons/** -text` to `.gitattributes`, so the raw bytes (and therefore the SHA-256) are stable across checkouts.
- Encoding: UTF-8 without BOM, LF line endings.

**Format.**
```
# name: hedges
# version: 1
# author: drafted by the AI coding assistant for the Litmus project; pending Ryan's review
# license: OPEN — pending Ryan's decision
# date: 2026-10-30
# source: written for Litmus; not derived from any published list
perhaps
it seems
```
- **Header:** the first six lines are `# key: value` with exactly these keys in this order: `name`, `version`, `author`, `license`, `date`, `source`. `name` must equal the file stem. `version` is a positive integer. `date` is ISO 8601.
- **Authorship:** the `author` value states authorship accurately. Nobody is named as an author who did not write the file. The value is updated once Ryan has reviewed the file.
- **License:** the `license` value is `OPEN — pending Ryan's decision` until Ryan decides (§h.2). No license is chosen or invented here.
- **Body:** after the header, blank lines and lines whose first non-space character is `#` are **ignored**. Every other line is one entry, with leading and trailing whitespace stripped. Inline comments are not supported, and entries cannot contain `#`.

**Validation (at initialization).** Any failure gives `status: error` for that observer on every segment, with the note `lexicon_invalid=<reason>`. Origin and the other observers are unaffected. Validation fails when:
- the header is missing, misordered or invalid;
- there are **zero valid entries** after ignoring blank and comment lines (e.g. a blank-only or comment-only body);
- there are **duplicate entries under case-insensitive comparison** (`str.casefold()`, used for validation only, never for matching);
- an entry is not one or more `WORD`s (§c) separated by single ASCII spaces;
- an entry contains a control character, a Cf (zero-width or format) character, or `#`.

**Notes format (RECOMMENDED — pending Ryan's approval).**
- Lexicon SHA-256 and observer version are recorded in `notes` in a fixed order and format, with no schema change to SPEC §4.3:
  ```
  observer_version=1
  lexicon_name=hedges
  lexicon_version=1
  lexicon_sha256=<64 lowercase hex>
  spans_truncated=false
  spans_reported=3
  ```
- `repeated_word_3grams` has no lexicon and omits the three `lexicon_*` notes.
- Claim records add the two notes from §b.
- Error records add `error=<exception class>` or `lexicon_invalid=<reason>`.
- R1-F's freeze record (SPEC §10.9) lists all lexicon hashes.
- Observer code is **not** added to `scoring_config_hash`, because quality observations are not part of origin scoring.

**Proposed lexicon contents v1 (small; drafted by the AI coding assistant for Ryan's review).**
- These are common English expressions written for this plan, not copied, scraped or derived from any published or copyrighted list.
- They describe surface patterns, not quality or origin.

| `stock_phrases` (20) | `hedges` (20) | `claim_phrases_to_inspect` (14) |
|---|---|---|
| a myriad of | appears to | according to experts |
| a testament to | arguably | data shows |
| at the end of the day | could be | evidence suggests |
| delve into | generally | experts agree |
| ever-evolving | in some cases | experts say |
| first and foremost | it appears that | it has been proven |
| game changer | it is possible that | it is well known that |
| in conclusion | it seems | it is widely accepted |
| in the realm of | kind of | research has shown |
| in today's fast-paced world | likely | research shows |
| it goes without saying | might | scientists say |
| it is important to note | perhaps | statistics show |
| last but not least | possibly | studies have shown |
| navigate the complexities | probably | studies show |
| needless to say | relatively | |
| pave the way | seems to | |
| plays a crucial role | somewhat | |
| rich tapestry | sort of | |
| shed light on | tends to | |
| unlock the potential | to some extent | |

- **Omit `may` (RECOMMENDED — pending Ryan's approval):** `may` is not in `hedges`, because the month "May" is case-insensitively identical.
- **Contractions:** per §c, only contraction forms that are listed match. `in today's` is listed as written.

**Planned packaging verification (to run at implementation time, not now).** These commands use the existing venv's pip and setuptools, no build isolation and no new packages. The temporary environment is outside the repository, and every command after the build runs from a working directory outside the repository:

```powershell
# 1. Build the wheel from the repository root with the existing venv (no build isolation)
$work = Join-Path $env:TEMP "litmus-wheel-check"
.\.venv\Scripts\python.exe -m pip wheel . --no-deps --no-build-isolation -w "$work\dist"

# 2. Temporary virtual environment OUTSIDE the repository (stdlib venv; no downloads)
.\.venv\Scripts\python.exe -m venv "$work\venv"

# 3. Install only the wheel, offline, without dependencies
& "$work\venv\Scripts\python.exe" -m pip install --no-deps --no-index (Get-ChildItem "$work\dist\litmus-*.whl").FullName

# 4. From a directory outside the repository, isolated mode (-I: no cwd or PYTHON* path entries),
#    load every lexicon through the installed package and print its location and SHA-256
Push-Location $work
& "$work\venv\Scripts\python.exe" -I -c "import hashlib, importlib.resources as r, litmus; print(litmus.__file__); d = r.files('litmus.quality').joinpath('lexicons'); [print(p.name, hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(d.iterdir(), key=lambda p: p.name) if p.name.endswith('.txt')]"
Pop-Location

# 5. SHA-256 of the source files, for comparison
Get-FileHash -Algorithm SHA256 src\litmus\quality\lexicons\*.txt
```

Acceptance for this check:
- `litmus.__file__` resolves inside `$work\venv`, not the repository.
- Every lexicon is listed.
- Each SHA-256 equals the source file's SHA-256.
- The observers also construct successfully through the installed package, which goes through the real loader rather than direct resource reads.

## e) Limitations (for reports and the README)

When observers run, the report's top-level `limitations` gain fixed sentences. The README gets a matching section:

1. **Language:** lexicons are English-oriented. Results on other languages are not meaningful, and scripts written without spaces count runs as single words.
2. **Genre:** frequencies depend on genre and register (recipes, legal text, academic hedging, marketing). There are no norms or baselines.
3. **Surface patterns only:** counts describe surface patterns, not quality judgments. A high count is not "bad writing", and a zero count is not "good writing".
4. **Origin:** quality observations do not establish AI origin and never affect origin results. No accuracy claim is made for them.
5. **Evasion:** homoglyphs (e.g. Cyrillic `о` for Latin `o`) and zero-width or format characters (e.g. U+200B) can split words or break matches, so phrases written that way are not counted. Unicode equivalences beyond simple case folding (e.g. `ß` ↔ `ss`, ligatures, compatibility forms) are not matched. This is documented behavior: tests assert a correct, non-crashing result with the reduced count.
6. **Claim phrases:** a "phrase to inspect" points at wording worth checking. It is not evidence that a claim is unsupported.
7. **Span cap:** at most 1,000 spans are listed per observer. The count is always exact.

## f) Tests

All tests below are in the default suite, model-free, run under the socket guard, and contain **no wall-clock assertions**.

**Per-observer unit tests: exact counts and exact spans.**
- `stock_phrases`, `hedges` and `claim_phrases_to_inspect`: fixed texts with known entries, giving exact `count`, `spans` and `rate`.
- Checks: case variants (`DELVE INTO`), multi-space and newline inside a phrase, a boundary miss (`perhapsx`, `perhaps-not`), longest-match (`it is important to note` counts once), adjacency of two entries, and a listed versus an unlisted contraction.
- `repeated_word_3grams`: `"a b c d a b c"` gives count 2 with spans for both `a b c`. `"x x x x"` gives count 2 with overlapping spans. A text without repeats gives `none_found`. Case-insensitive key: `"The cat sat. the CAT sat"` gives 2. A 3-gram across a line break and punctuation counts.

**Metamorphic tests.**
- **Insert a phrase:** inserting one lexicon phrase, surrounded by spaces, between two neutral words that start no lexicon entry raises that observer's count by exactly 1 and the word count by the phrase's word count. Other lexicon observers are unchanged, unless the phrase is also in their lexicon (constructed to avoid this).
- **Duplicate a sentence:** let S be a sentence of `w ≥ 3` pairwise-distinct words, with no word repeated in the base text. Then `T = S` has `repeated_word_3grams.count = 0`. `T' = S + " " + S` has count exactly `2(w − 2)`: each internal 3-gram appears twice. The boundary 3-grams are unique because the words are distinct, so they add 0.
- **Number after "studies show":**
  - **Expected:** appending ` 42%` after `studies show` (separated by whitespace) leaves the claim count unchanged (1 → 1), because the match ends at `show` and the next character is a space.
  - **Also asserted:** `studies show42` gives count 0, because digits are word characters and the boundary fails (documented).
  - **Also asserted:** `studies show, 42` gives count 1.

**Span-integrity tests.** For every span, `0 ≤ start < end ≤ len(text)` and `text[start:end]` equals the expected surface string. Inputs:
- **Emoji:** an emoji (supplementary-plane, e.g. U+1F600) before a phrase gives offsets in code points.
- **ZWJ sequence:** an emoji ZWJ sequence before a phrase.
- **CJK:** CJK text around an English phrase.
- **Combining characters:** decomposed `cafe` + U+0301 counts as one word.
- **Sharp s:** `ß`/`ẞ` inside a phrase-adjacent word. Offsets are unchanged, and there is no `ss` match.
- **U+200B:** inside a phrase, the match is missing and there is no crash. Between words, it acts as a separator.
- **Homoglyph:** Cyrillic `о` inside `show` means no match, the word count is still correct, and there is no crash.

**Empty cases.**
- Empty string, whitespace-only, and punctuation-only text give `none_found`, `count 0`, `rate null` and `spans []` for all four observers.
- A text with one word and no matches gives rate `0.0`.

**Lexicon validation.**
- **Fails with reason:** a missing header, wrong key order, name ≠ stem, a **blank-only body**, a **comment-only body**, **duplicate entries** (`Perhaps` / `perhaps`), a Cf character, `#` in an entry, an unmatchable entry (e.g. `--`).
- **Passes:** a **valid file with interleaved blank and comment lines**, whose entries are exactly the non-blank, non-comment lines.
- An invalid lexicon gives that observer `status: error` with `lexicon_invalid=…`. The other observers and origin are unchanged.
- All committed lexicons validate, load through `importlib.resources`, and their SHA-256 values match those recorded in `docs/decisions.md` at approval.

**Large-input behavior (algorithmic, no time limit).**
- On 200,000-code-point inputs, all four observers complete and return exact results:
  - 100,000 × `"a "`: `words = 100000`, 3-gram `count = 99998`, `spans_reported=1000`, `spans_truncated=true`;
  - one 200,000-character word: `words = 1`, all counts 0;
  - 200,000 CJK characters: `words = 1`;
  - word-salad English with a known number of inserted phrases: exact counts.
- No wall-clock bound is asserted.

**Import isolation.** The test from §a.

**Origin separation.** The test from §a.

**Schema round-trip.**
- `from_json(Segment, to_json(segment))` equals the original for segments carrying all four observation kinds, including `rate null`, overlapping spans, capped spans and notes.
- An invalid `status` is rejected.
- A full CLI report with `--quality on` parses and round-trips.

**Performance (not a test).**
- The 5 s / 200,000-code-point target is an **ESTIMATE**. It is measured by a separately invoked script, `scripts/benchmark_r1c_quality.py`, run on Ryan's machine.
- The script uses the four large inputs above plus a natural-length set. It records hardware, OS, Python version, date, every raw timing and min/median/p90/max.
- Results go to `eval/results/r1c_quality_benchmark.json`, and the console log goes to `eval/results/logs/`.
- It is never a timing assertion in the default suite.
- The patterns contain no nested quantifiers, only `\s+` between literals, so catastrophic backtracking is not expected. This is an ESTIMATE, to be confirmed by the benchmark.

## g) Report and UI integration

**CLI report (RECOMMENDED — pending Ryan's approval: opt-in).**
- Quality observers are **off by default**. They are enabled with the flag **`--quality {off,on}`** (default `off`), which mirrors `--text-origin`.
- With the default, reports are unchanged and the R0 golden files stay valid.
- With `--quality on`:
  - observations go in `segments[i].quality[]` in the order `stock_phrases`, `hedges`, `repeated_word_3grams`, `claim_phrases_to_inspect`;
  - the top-level `limitations` gain the §e sentences.

**UI (R1-H).**
- Quality observations appear in a section titled **"Content observations (not origin evidence)"**.
- That section is visually separate from the origin section: its own heading and container, no shared color scale, and never placed inside or beside the origin result badge.
- Claim phrases are shown with the label "phrase to inspect".
- Spans are highlighted in the text view with a style distinct from any origin display.
- The "not a probability" note belongs to origin only.

## h) Decisions

### h.1 RECOMMENDED — pending Ryan's approval

1. Ship all four observers with the proposed small lexicons (§b, §d).
2. Omit `may` from the `hedges` lexicon (§d).
3. Contractions match only when listed explicitly as entries (§c).
4. Overlap policy: leftmost-longest, non-overlapping, within each observer (§c).
5. Lexicon SHA-256 and observer version are recorded in `notes` in a fixed format, with no schema change (§d).
6. No stop-word filtering (§b).
7. Word 3-grams are sequences of words under the word regex and may cross punctuation and line breaks, with no sentence segmentation (§b).
8. Spans are capped at 1,000 per observer. `count` stays exact, and truncation is reported as `spans_truncated=true`, `spans_reported=1000` (§c).
9. Quality observers are opt-in through `--quality {off,on}`, default `off` (§g).
10. Image segments keep `quality: []`, with no `not_supported` records in R1 (§a).

### h.2 OPEN — for Ryan

1. **Final lexicon contents:** the three v1 lists in §d, to be reviewed entry by entry.
2. **Licensing:** the lexicon `license` header value and the repository license. Both are `OPEN — pending Ryan's decision`, and none is chosen here.
3. **Lexicon authorship line:** the final `author` wording once Ryan has reviewed the lexicons. The draft reads "drafted by the AI coding assistant for the Litmus project; pending Ryan's review".
4. **Performance target:** whether 5 s per 200,000 code points (ESTIMATE) is the R1-C acceptance target, and what follows if the measured value exceeds it (accept and document, or optimize before acceptance).
5. **Scripts without word spaces:** keep the documented limitation (a CJK or Thai run counts as one word, so rates are not meaningful), or report `rate_per_100_words = null` when a segment is predominantly in such scripts. Recommendation: keep the limitation in R1.
6. **Default after R1-H:** whether `--quality` becomes `on` by default when the UI ships. That would require one deliberate golden-file regeneration.

## i) Effort (ESTIMATE) and checkpoints

**Effort: ESTIMATE 8–12 focused hours.**

| Part | ESTIMATE |
|---|---|
| Package-resource loader, lexicon format and validator, packaging check | 2–3 h |
| Word index and entry→pattern compiler | 1–1.5 h |
| Four observers (incl. span cap, notes format) | 1.5–2 h |
| Unit, metamorphic, span-integrity, empty-case, validation, large-input tests | 2–3 h |
| Report/CLI integration, origin-separation and import-isolation tests, round-trip | 1–1.5 h |
| Benchmark script, docs (interfaces.md, README limitations, decisions.md) | 0.5–1 h |

**Checkpoints.** Each ends with a commit, the default suite from the repository root and from outside it, Ruff, a clean tree and an independent review. The GPU and slow suites are needed only if model-dependent code changes.

- **R1-C1: lexicons, loader and word index.**
  - `src/litmus/quality/` with the package-resource loader and validator, the lexicons Ryan approves, `pyproject.toml` package data and `.gitattributes`.
  - The word regex and entry compiler, with word-definition, span-integrity and validation tests.
  - The packaging verification in §d, run and recorded.
  - Accepted when:
    - all validation tests pass;
    - the installed-wheel check shows matching hashes from outside the repository;
    - lexicon hashes are recorded in `docs/decisions.md`;
    - import isolation passes;
    - no observer is wired into reports yet.
- **R1-C2: observers and integration.**
  - The four observers with unit, metamorphic and large-input tests.
  - `--quality {off,on}`, and the §e limitations in the report and README.
  - The origin-separation and round-trip tests.
  - The benchmark script, run separately, with results recorded as measured values.
  - Accepted when:
    - origin bytes are identical with and without observers on every fixture;
    - every span slice equals its surface text;
    - whitespace-only text gives `none_found` with rate `null`;
    - the default report is unchanged;
    - benchmark results are recorded with hardware and date;
    - documentation is updated.

**Out of scope for R1-C:** RAID data, calibration, C2PA, UI implementation (R1-H), and any change to origin scoring or `scoring_config_hash`.
