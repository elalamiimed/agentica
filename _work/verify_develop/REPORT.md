# Adversarial verification: `event_description` / `develop.unsourced()` / form date warning

Revision verified: the current working tree (validate.py + develop.py after the `canonical_dates`
dedup refactor landed at ~19:24; all seven `hsiyc_writer` modules import cleanly).
Nothing under `hsiyc_writer/`, `tests/`, `tools/`, `spec/`, `README.md` was modified.
Scratch work: `_work/verify_develop/` (probes + `repro.py`).

All commands run from the project root with
`$env:PYTHONIOENCODING="utf-8"` and
`& "C:\Users\hp\AppData\Local\Programs\Python\Python311\python.exe"`.

`_work/verify_develop/repro.py <case-id>` reproduces every numbered case below.
No HTTP call was made; `/api/develop` and `/api/generate-form` were never touched.

---

## DEFECTS

### D1 — MEDIUM — a date range's end day is not blanked, so a faithful Chinese→English range rewrite is reported as inventing both a number and a date

Repro:
```
& $py "_work\verify_develop\repro.py" fp1
```
* notes: `活动于11月8日至9日举行。`
* rewrite: `The event was held from 8 to 9 November.`
* observed: `{'numbers': ['8'], 'dates': ['11-09'], 'names': []}`
* expected: `{'numbers': [], 'dates': [], 'names': []}`

`canonical_dates()` matches `11月8日` and stops; the `9` of `至9日` is outside every match
span, so it is never blanked and survives as a stray figure. The rewrite's `9 November` is
matched, blanked, and compared against the source's date set, which contains only `11-08` —
so the same day is simultaneously an invented number and an invented date.
Why it matters: the operator's own faithful text is shown as "facts you never wrote",
which is the fastest way to teach the club to ignore the check.

### D2 — LOW/MEDIUM — a month name used as an ordinary word fabricates a date, and that phantom date hides the rewrite's real figures

Repro:
```
& $py "_work\verify_develop\repro.py" fp3 fp4 fp4b
```
* fp3/fp4: notes `We march five kilometres to the hall.` → rewrite `We march 5 kilometres to the hall.`
  * observed: `{'numbers': ['5'], ...}`  • expected: all empty
* fp4b control: `They walk five kilometres…` → `They walk 5 kilometres…`
  * observed: all empty (the warning disappears when the month word goes)

`_SPAN_DATE_PATTERNS[4]` matches `march 5` and `may 5`/`May 8` regardless of meaning, blanks
the `5`, and drops `03-05` into the date set. The check then sees the note's figure vanish
while the rewrite's survives. The same phantom date mis-fires the form warning:
```
& $py "_work\verify_develop\repro.py" fp8
```
* description `The students march 5 kilometres.`, `date_start=2026-11-08`
* observed warning: `The description mentions 03-05, which is neither the start nor the end date you gave.`
* expected: no date warning

### D3 — LOW — full-width digits in the operator's notes are invisible to the checker

Repro:
```
& $py "_work\verify_develop\repro.py" fp2
```
* notes: `共有３２名学生报名。` → rewrite: `共有32名学生报名。`
* observed: `{'numbers': ['32'], 'dates': [], 'names': []}`
* expected: all empty

`_FIGURE_RE` is `\d`, ASCII-only, so the note's `３２` is never extracted and the rewrite's
`32` cannot match it. Same for `５０９` vs `509`, `Ａ５０９` vs `A509`.
Why it matters: an operator typing Chinese on a full-width IME gets accused of inventing
the very count they wrote.

### D4 — MEDIUM — `8th of November 2026` parses as **November 20th** in the shared date model

Repro:
```
& $py "_work\verify_develop\repro.py" fp9
```
* observed: `(['11-20'], ['2026-11-08'])` for `_dates("8th of November 2026")` vs `_dates("2026年11月8日")`
* expected: both `['2026-11-08']`

The `\d{1,2}` day pattern matches the `20` of `2026` (`8th of November` then whitespace then `2026`);
`(?:st|nd|rd|th)?\s+` is satisfied by the space, so `d=20` and the year group never fills.
`canonical_dates` now serves both `develop` and `form`, so the Chinese-written date
`8th of November 2026` is read as 11月20日 in the develop report *and* in the form warning
(`The description mentions 11-20 …`). Any phrase `Nth of Month YYYY` lands on a bogus day.
Related, same function: `the 8th of November` (no year) yields **no date at all**, so the day
stays in the figure stream as a stray number.

### D5 — LOW — `canonical_dates` accepts impossible calendar dates

`2026-02-30` → `2026-02-30`; `31 February` → `02-31`; only `1<=month<=12 and 1<=day<=31`
is enforced, never day-per-month. The form then warns `The description mentions 2026-02-30,
which is neither the start nor the end date you gave` — a message about a date that cannot
exist, where "fix your typo" would be the useful text. (`2026-13-45` and `13月45日` are
correctly rejected.)

### D6 — LOW — a description date that omits the year is compared on month+day only, so a wrong-year event passes the warning

`form.py:514`: a date found in the description with no year is compared via `found[-5:]`
against `declared_days`, so `date_start=2026-11-08` plus a description saying
`活动于 11月8日 举行。` does not warn — correct, and intended. The asymmetry worth recording:
the same description written **with** the year (`The event was held on 8 November 2025.`)
does warn, because the exact-match branch compares `2025-11-08` against `2026-11-08`.
So the warning's strictness depends on whether the operator happened to type a year, which
is defensible but not what a reader of the message would guess. Not raised as a defect.

### D7 — MEDIUM (design consequence, not a bug) — the description box is an authoritative whitelist, so an operator can authorise a fabricated figure; and the whitelist is wider than "what the operator typed"

Evidence (`_work\verify_develop\probe_d2_rigorous.py`, `probe_exact_masking.py`,
`probe_word_masking.py`):
* A body figure that appears **only** in `event_description` passes `validate`: with
  `event_description = "… 137 volunteers helped on the day."` the report's FACT-NUMBER no
  longer names `137`; with the same article and `event_description` cleared it does. The same
  for `211`. This is intended per the design ("what the operator typed is exactly what the
  article is verified against") — recorded so it can be documented honestly.
* **The model can widen the whitelist too, and not only through invented prose.** In
  `run_notes`/`normalise_brief` the structured brief is model-authored, and
  `brief["event_description"]` is scanned by `validate._iter_scalars`, so a normaliser that
  writes a count the operator never gave whitelists that count for the article check. The
  same field is the one `build_article_messages` then hands to the writer as "the spine".
* `number_words()` reads ordinary words as figures: `五官` → `5`, `十分` → `10`, `三天` → `3`,
  `一起` → `1`, `两国` → `2`, `one of the members` → `1`, `Two of us` → `2`. Because
  `validate` puts `number_words(brief)` into `brief_numbers`, those phantoms whitelist the
  matching **digit** in the body: a brief whose description contains `五官` makes an invented
  `5 名选手` in the body pass FACT-NUMBER, where the same brief without `五官` blocks it
  (verified, both directions). `五官`/`十分` are ordinary club-article vocabulary.

---

## FALSE NEGATIVES CONFIRMED (the check provably cannot see these)

From `_work\verify_develop\probe_b_falseneg.py` (20 dishonest rewrites):

| invented fact | result |
|---|---|
| `32 students` → `Thirty-two pairs` (value kept, unit changed) | **not reported** |
| `Tugsuu beat Brandon` → `Michael beat Brandon` | **not reported** |
| `Aruzhan won the final` (single-word name invented outright) | **not reported** |
| `AcademiaSphere` invented as a sponsor (single word) | **not reported** |
| `ling yi laoshi` → `凌一老师` (pinyin → characters) | **not reported** |
| `Tugsuu took the final` → `… and was named champion of the region` | **not reported** |
| `The judge gave feedback` → `The judge said the level was impressive` (claim/quote) | **not reported** |
| `a five-minute integral` → `five rounds` (vocabulary substitution) | **not reported** |

Root causes: `LATIN_NAME_RE` requires two capitalised words of ≥3 letters each, so any
one-word name (most Mongolian / Indonesian / mononym names in this club) is invisible;
Chinese characters are not compared at all, so pinyin→characters is invisible; and the
check only sees figures, dates and Latin names, so a changed unit, a changed verb, an
invented claim with no digit and an invented rank all pass.

Reported (these are *not* gaps): `9-11` scores and invented times are caught as their
digits; an invented date is caught; `Grand Ballroom` is caught by the two-word rule;
`2026`→`2025` is caught; a reordered `11月8日`→`8月11日` is caught.

---

## CLEAN

* **Date-blanking mechanics (part C):** no crash on `""`, `None`, `13月45日`, `2026-13-45`,
  `2026年11月8日`, `2026年11月8` (no 日), `9999年99月99日`, dates at position 0 or at the end,
  adjacent dates (`1月1日1月2日`, `11月8日11月9日`), adjacent full dates, `２０２６年１１月８日`.
  `_blank` preserves string length in every case and blanks exactly the month/day digits it
  reports; the year is left in the stream by design. Overlap resolution ("longest match at a
  position wins") behaves as documented.
* **Date notation equivalence:** `8 November` ≡ `Nov 8` ≡ `8th November 2026` ≡ `11月8日` ≡
  `11月8号` ≡ `2026年11月8日` ≡ `2026-11-08` ≡ `2026/11/8` ≡ `2026.11.8`; two dates in swapped
  order; a year written in only one text (correctly reported as a new figure).
* **Labels, rooms and codes:** `A509`, `Room 3`, `3号场`, `1v1`, `90 seconds`, `15:00-18:00`,
  `15:00至18:00`, `双打12对`, `80%`, `1:4`, `HS-2026-11-08`, `5.5`, `11-9` scores — all clean
  both directions.
* **Spelt vs digits:** `five`↔`5`, `thirty-two`↔`32`, `三十二`↔`32`, `九十`↔`90`, `十`↔`10`,
  `twelfth` inside a date, `two to three people`↔`2-3`.
* **Full-width punctuation:** `，。、（）：` tidy-ups are clean (only full-width *digits* are
  the problem, D3).
* **`May` at the start of a sentence** (`May I say 8 students came?`) is *not* misread — only
  a month word followed by a digit is (D2).
* **Guards:** empty / `<12` chars / `>8000` chars notes are refused before any token is spent;
  an empty model rewrite raises `DescriptionError`; `usage`, `questions`, `dropped` and
  `original` are carried through correctly.
* **Prompt wiring:** `DESCRIPTION_DEVELOPER_PROMPT` reaches the system message verbatim with
  the doc type and notes in the user message; rules 8 and 9 (keep romanised names, keep the
  operator's vocabulary) are present. `build_article_messages` emits the
  `THE CLUB'S OWN DESCRIPTION OF THE EVENT` block with the full description.
* **Part D forwarding:** the description reaches all three consumers with no line dropped —
  `answers_to_brief` (`EVENT DESCRIPTION …` block), `answers_to_structured_brief`
  (`event_description`, exact string), and the article prompt (description block + raw-notes
  block).
* **Part E warning, core behaviour:** a description date differing from `date_start` warns
  (`2026-11-09` vs `2026-11-08`); a date matching either end of a multi-day event does not
  (`2026-11-08`–`2026-11-09` with `11月9日`); a description with no full date does not; month-only
  text does not; a matching date written in another notation does not (`2026/11/8`, `11月8日`,
  `11月8号`, ISO); an unrelated registration deadline correctly warns (by design).

---

## HONEST LIMITS

1. The check sees only figures, dates and two-word Latin names. A changed unit
   (`students`→`pairs`), a changed verb, an invented claim, an invented rank, or an invented
   single-word name/sponsor is invisible.
2. Chinese characters are never compared, so `ling yi laoshi` → `凌一老师` (and any
   pinyin→characters or characters→characters substitution) is invisible.
3. A single-word Latin name is invisible in both directions (`Tugsuu` → `Michael`).
4. Full-width digits and full-width Latin letters are invisible to the figure comparison.
5. `number_words` reads ordinary words as figures (`五官`, `十分`, `one of the members`), which
   both causes false positives in `develop.unsourced` and silently widens the `validate`
   whitelist for single/double-digit figures.
6. The whitelist is only as narrow as what lands in the brief: the operator's description box
   is authoritative material (intended), and a model-authored structured brief can widen the
   whitelist the same way.

---

## INTERRUPT REPORTED DURING THE RUN (now resolved by the parent)

At ~19:24 `develop.py:25` imported `canonical_dates` from `validate.py` before it existed —
`import hsiyc_writer.develop` raised `NameError: name 'canonical_dates' is not defined`,
which would have taken out `/api/develop`, the `develop` CLI subcommand and the button.
Sent to the parent immediately; the refactor has since landed and all seven modules import
cleanly, so this is recorded as an observation, not an outstanding defect.
