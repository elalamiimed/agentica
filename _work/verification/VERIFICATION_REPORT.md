# Independent verification — HSIYC article agent

**Verifier:** teammate `verifier` (shared task `task-3`)
**Date of runs:** 2026-10-13, all times CST, workspace `C:\Users\hp\OneDrive\Desktop\ArticlesAgentica`
**Interpreter:** `C:\Users\hp\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`
**Write scope:** `_work\verification\` only. Nothing in `hsiyc_writer\`, `spec\`, `tests\`, `output\` was modified.

Every claim below cites either an artifact under `_work\verification\` or a command whose
output is quoted. Nothing rests on reading source alone.

---

## 1. VERDICT

**The engineering is real; the safety net is not.** I reproduced the whole pipeline end to end:
it generates, validates, renders a bilingual A4 PDF with a working CJK text layer, writes DOCX /
MD / HTML, and all four offline test files pass. My own freshly generated article scored 99/100
and contained no invented names, numbers, dates or venues — it even refused to invent an APEC
link the brief did not contain, and asked the editor instead.

**But the product is not ready to be relied on as a pre-submission safety net, and the Lead's
shipped article should not go to 送审 unchanged.**

Two things break it:

1. The shipped APEC article contains **five specific claims that are in no brief the operator
   supplied** — `三场独立竞赛`, `创新、合作、开放`, `亚太共同体`, `首场赛事`, `首场竞赛` — lifted
   from corpus articles #11/#15, and `-m hsiyc_writer check -b <brief>` reports **86/100, 0 errors,
   "passes the structural/bilingual gate"**. The validator missed exactly the failure mode that
   gets articles returned.
2. Of the four defects the task asked me to plant, the validator caught **three**. It did not
   catch the invented person's name — because it has no name-level fact checking at all.

On top of that, **the PDF that would be sent to the committee has the agent's internal QA report
printed on its last page** (`需人工确认 / Before 送审` plus `送审前自检 / Pre-submission check —
86/100 (0 errors, 2 warnings)` and `[WARNING] SIMILARITY` lines naming internal corpus files).

**Would this pass a youth-committee review unchanged? No.** With edits, in this order:
delete the QA handover block from the PDF; delete `三场独立竞赛`/`创新、合作、开放`/`亚太共同体` and
rewrite the lede from the brief; de-duplicate the four award rows (each winner's name is printed
twice); fix the weekday (the brief says 周六, 2026-11-08 is a **Sunday**); fix or remove the stray
navy accent bars that overlap body text and orphan at page tops; replace the three placeholder photo
filenames with real attachments; decide who supplies the scales the article promises. A human must
fact-check names against the brief every single time — the tool will not do it.

---

## 2. WHAT I RAN

| # | command | result |
|---|---|---|
| R1 | `check output\...\...recap.json -b examples\brief_apec_future_skills.md` | score 86/100, 0 errors, 2 warnings, **exit 0** |
| R2 | `check output\...\...recap.json` (no brief) | score 86/100, 0 errors — identical, so the shipped `output\` report is stale (§4.D7) |
| R3 | `tests\probe_render.py` / `validate_cases.py` / `fontcheck.py` / `fidelity.py` | all four **exit 0** |
| R4 | `generate -b _work\verification\brief_beach_cleanup.md --doc-type 招募 --repair-rounds 1 -o _work\verification\gen` | 99/100, 0 errors, 1 attempt, **11,946 tokens / 17.0 s** |
| R5 | 10 adversarial variants + control through `check -b <brief>` (`make_adversarial.py`, `extras.py`) | see §4 |
| R6 | `extras.py` → render shipped article with the real engine; `measure_and_render.py` → render with the validator report attached, and a 4-photo variant | 3 PDFs under `_work\verification\pdf\` |
| R7 | `pdftoppm` at 100 dpi → `read_image` on every page; `pdftotext -enc UTF-8` | see §5 |

My own brief: `_work\verification\brief_beach_cleanup.md` (814 chars, a 招募 for a Shenzhen Bay
beach clean-up with 45/25/12/8 headcounts, two dates, an email, a partner org and a six-role
credit block whose 二审 deliberately drops 崔雨旸 to test credit leakage).

---

## 3. ANSWERS TO THE FIVE QUESTIONS

### 3.1 Does a generated article contain facts not in the brief? — YES for the shipped one, NO for mine

`measure_and_render.py` compared the shipped article's Chinese body against its own brief:

```
--- corpus-derived phrases present in the shipped body but absent from its brief
    '三场独立竞赛'      in brief=False   in article body=True
    '创新、合作、开放'    in brief=False   in article body=True
    '亚太共同体'        in brief=False   in article body=True
    '首场赛事'          in brief=False   in article body=True
    '首场竞赛'          in brief=False   in article body=True
```

`三场独立竞赛` is verbatim from `_work\国际青年俱乐部___APEC智慧校园创新系列竞赛.txt` line 8 and
`_work\国际青年俱乐部___活动回顾_APEC智慧校园创新系列.txt` line 4; `创新、合作、开放` is verbatim from
line 5 of the latter. The brief describes **one** event ("未来技能挑战赛（首届积分蜜蜂赛）") and says
only that the series' theme is APEC 核心理念**之一**「创新」.

To be precise and fair: these particular claims are probably *true of the real series* — the corpus
says the series has three competitions. That does not make them safe. The mechanism is what matters:
retrieval handed the model two same-series articles as exemplars, and the model copied a specific
claim about **event scope** out of them. The brief is the only thing the operator vouched for, and
the operator never said "three". Run the same mechanism on a one-off event and it injects a false
number. The product's own rule — *"everything a reviewer can check against the real world … must
come from the brief"* (`spec\REJECTION_CHECKLIST.md`) — is broken here, and the validator says
"passes".

**My fresh article is clean on this axis.** All 14 body numbers trace to my brief (45/25/12/8,
2026-03-28, 08:30-12:00, 2026-03-20, 23:59, 4 hours, 3 groups); no invented date, venue, or person.
It explicitly declined the APEC framing:

> 请确认是否需要在文末补充 APEC / 亚太青年框架表述；简报未提供该活动与 APEC 项目的关联信息，故正文未写入。

and its `needs_editor` flags exactly the right gaps (partner's official English name, transport
arrangements, who issues the volunteer-hours certificate). Residual inventions of detail, none
checked by any rule: `小组长` (group leaders) and `称重` (weighing the waste) — the brief's kit list
is 手套、垃圾夹、垃圾袋, with no scale. Both are plausible; neither is in the brief.

### 3.2 Does the validator catch the four planted defects? — 3 of 4, and stays quiet when it should

`_work\verification\adversarial\`, all run with `-b examples\brief_apec_future_skills.md`:

| case | planted defect | exit | caught? |
|---|---|---|---|
| `case_E_control` | none (control) | 0 | correct — no false positive |
| `case_A_invented_winner` | added `特别奖 / Special Prize — 王梓涵 Wang Zihan` to the award list | **0** | **NO — false negative** |
| `case_B_missing_en` | deleted the `en` twin of a bilingual block | 2 | yes — `BIL-PARAGRAPH` |
| `case_C_no_final_review` | deleted `credits["三审"]` | 2 | yes — `CREDIT-MISSING` |
| `case_D_cn_only_heading` | blanked `heading_en` of section 2 | 2 | yes — `BIL-HEADING` |
| `case_H2_invented_venue_bodyonly` | `A509` → `B201` in the body, meta honest | 2 | yes — `FACT-NUMBER: ... 201` |
| `case_G_invented_number_undeclared` | `32` → `57`, not declared in `facts[]` | 2 | yes — `FACT-NUMBER: ... 57` |
| `case_F_invented_number_self_sourced` | same `57`, **plus one `facts[]` entry** | **0** | **NO — false negative** |
| `case_I_invented_person` | `凌怡老师` → `欧阳明德老师`, `Professor Ling` → `Professor Ouyang` | **0** | **NO — false negative** |

So: shapes are caught, **content is not**. The validator checks *numbers* and *structure*; it never
checks a name against anything. An invented winner, judge or partner — the fastest route to
rejection — sails through with a 86/100 "passes".

**False positives:** none found. The control passed, my fresh article passed at 99/100 / exit 0, and
a legitimate style choice (which credit separators, CN-above-EN headings) was never flagged, exactly
as `spec\REJECTION_CHECKLIST.md` says it should not be.

### 3.3 Does the PDF render Chinese and English with no blank glyphs? — YES

* Pages were rasterised at 100 dpi with `pdftoppm` and **looked at** with `read_image`. I viewed
  `png\fresh-1.png`, `png\fresh-2.png`, `png\apec-1.png` (= `apecall-1.png`), `png\apecall-2.png`,
  `png\apecall-3.png`, `png\apecall-4.png`, `png\rep-4.png`, `png\grid-2.png` and
  `png\crop_fresh_heading01.png` — i.e. **every page of both 3-page PDFs plus the report-attached and
  grid renders**. No tofu boxes, no blank glyphs, in either language.
* `pdftotext -enc UTF-8` recovers 4,776 chars; every probe string found —
  `哈工大（深圳）国际青年俱乐部`, `海岸课堂`, `2026年3月28日`, `报名截止`, `Kavindya`, `卢锦章`, `三审`,
  `Green Campus`, `Sunrise Theater` — and **0** U+FFFD replacement characters.
* `tests\fontcheck.py`: "characters verified against the original font: 67/67".
  `tests\fidelity.py`: "text layer: all 6 source sentence(s) recovered".
* The 三审 credit block renders as six rows with 卢锦章 correct (`png\rep-4.png`), and the bilingual
  sign-off is centred as the corpus requires.
* `pdfinfo`: 3 pages, 595 × 842 pts (A4).

### 3.4 Does the text match the measured corpus style? — Mostly, but it is thin

Measured with `measure_and_render.py` (CN = CJK ideographs only, over lead + body + closing):

| metric | shipped APEC | my fresh 招募 | corpus band (`TEXT_PATTERNS.md`) |
|---|---|---|---|
| sections / headings | 5 | 4 | 4–24, median 11; generator target **8–13** |
| CN chars | 654 | 637 | 305–2,261, median 860; contract **700–1,400** |
| EN words | 433 | 390 | — |
| CN:EN ratio | 1.51 | 1.63 | 1.18–2.26, median 1.79 ✓ |
| CN blocks with no EN twin | 0 of 6 | 0 of 5 | 0/131 in corpus ✓ |
| headings with no English | none | none | 0/130 in corpus ✓ |
| credit roles | all 6, **exact match to brief** | all 6, **exact match to brief** | ✓ |
| facts declared | 17 | 17 | — |

The bilingual protocol and the credit block are genuinely faithful — credit strings match the brief
character for character in both articles, including my deliberately-shortened 二审 `周宣彤、高容驷`
(no 崔雨旸 bled in from the corpus).

The style gap is **structure**: both articles sit at 4–5 sections against a documented generator
target of 8–13, and the app's own counter reports 777 / **686** CN characters — both below the
700-character floor of the contract in `TEXT_PATTERNS.md` §K. The validator's `LEN-SHORT` threshold
is 305, so it stays silent, and my article scored **99/100** while being under the documented length
contract. Approved articles also always carry imagery (48 full-bleed photo blocks across 17
articles); my article has `photos_placed: 0` and still scored 99/100.

### 3.5 What does one generation cost? — measured, not estimated

From `run_log.json` files:

| run | attempts | prompt | completion | total | wall clock |
|---|---|---|---|---|---|
| my 招募, clean first pass | 1 | 8,236 | 3,710 | **11,946** | **17.0 s** |
| Lead's APEC recap (1 repair round) | 2 | 19,582 | 7,483 | **27,065** | **29.6 s** |
| `...integration-bee-recap` (1 repair round) | 2 | 18,815 | 8,045 | **26,860** | **31.8 s** |

So: **~12k tokens / 17 s** when the draft passes first time, **~27k tokens / ~30 s** when a repair
round runs. The task's "~27k per article" is the repair path; a clean generation is less than half
that. Cost is dominated by the prompt, which carries two full exemplar articles.

---

## 4. DEFECTS, RANKED BY LIKELIHOOD OF GETTING AN ARTICLE REJECTED

### D1 — CRITICAL: facts imported from the corpus are invisible to the validator
The shipped article states `三场独立竞赛分别对应亚太共同体的核心理念` and `创新、合作、开放` — no brief
contains them; the corpus does, verbatim. `check -b <brief>` → **86/100, 0 errors, "passes"**.
`FACT-CORPUS-LEAK` exists but fires only when a fact's `source` string literally contains
`corpus:` — i.e. only when the model self-reports leakage. Proof both ways:
`case_J_corpus_source_label.json` (source rewritten to `corpus: …`) → the warning fires;
the real leak, whose source reads `STRUCTURED BRIEF …`, never triggers it.
*Fix direction:* cross-check proper nouns and scope claims in the body against the brief, not just
numbers; and treat a phrase that appears verbatim in a corpus article but not in the brief as at
least a warning.

### D2 — CRITICAL: no name-level fact checking at all
`case_A_invented_winner` (fabricated winner added to the award list) and `case_I_invented_person`
(judge renamed) both exit 0 at 86/100. Invented **numbers** are caught (`57`, `201` both fired);
invented **people** are not, even with the brief supplied and the names sitting in it.
Since the single most likely hard rejection is a wrong name (`spec\REJECTION_CHECKLIST.md` calls the
credit block and reviewer names "the single most likely hard rejection"), this is the biggest hole.
*Fix direction:* for each `credits` role and each name-like token in the body, require a match in the
brief's name set; warn on anything not matched.

### D3 — HIGH: the published PDF contains the internal QA report
`pdfout.py` appends `需人工确认 / Before 送审` (every `needs_editor` item) and
`送审前自检 / Pre-submission check — 86/100 (0 errors, 2 warnings)` plus `[WARNING] SIMILARITY …`
lines that quote internal corpus filenames, to the **article** PDF. Seen and photographed on the
last page of both `png\apecall-4.png` (report=None, so only the handover block) and
`png\rep-4.png` (real pipeline path, with the report attached) — the latter shows
`'国际青年俱乐部___APEC智慧校园创新系列竞赛'` printed into the deliverable. No approved article has
anything like it. This alone would get the file sent back.
*Fix direction:* render `needs_editor` and the report into a separate `check_report.txt`/`.md`
only, never into the article PDF.

### D4 — HIGH: numeric fact-checking is circular
CLI-verified: `case_G` (invented `57`, undeclared) → **error**; `case_F` (same `57`, plus one
`facts[]` entry whose source reads `STRUCTURED BRIEF participants_count / RAW NOTES 参与人数`) →
**0 errors, passes**. The allowed-number set is built from the article's own `facts[]` and `meta`,
so a model that invents a number and then lists it as a fact launders it. Related dead code:
`unexplained = {n for n in body_numbers - brief_numbers if len(n) > 1 or True}` — the guard is
always `True`.
*Fix direction:* derive allowed numbers from the **brief file** only, never from the article's own
`facts`/`meta`.

### D5 — MEDIUM-HIGH: the section accent bar is drawn 36 pt above its own heading
`canvas.rect(MARGIN_X, canvas.y + 22, 3, 22, ACCENT)` places the bar at `y+22…y+44`, while the
heading text baseline is `canvas.y - 14`. Result: the navy bar floats in the tail of the previous
paragraph instead of beside the heading, it **strikes through** the `slide right for more pictures`
hint, and when a section starts a page it is **orphaned at the top margin with no heading beside it**.
Visible in `png\crop_fresh_heading01.png` (bar sits next to "…ideas into concrete action." while the
heading `01 活动概览` has no bar), `png\apecall-2.png` (orphan bar at the top of page 2, bar through
the slide hint), `png\apecall-3.png` (orphan bar at the top of page 3, bar through the slide hint)
and `png\grid-2.png`. `VISUAL_PATTERNS.md` §G5 specifies a 280 px centred header group with navy
rules; a stray bar overlapping body text is not a style variant.
*Fix direction:* draw the bar at the heading's own y range, e.g. `y - 14 … y + 8`, and skip it when
the heading is the first thing on a fresh page.

### D5b — MEDIUM-HIGH: every award row prints the winner's name twice
`pdfout.py` builds a list row as `" ".join(value_cn, value_en)`. When the two are identical — which
is normal for Latin names and for `谢昊轩 Xie Haoxuan` — the deliverable reads:

> `冠军 Champion: Tugsuu Rentsennatsag Tugsuu Rentsennatsag`
> `亚军 First Runner-up: Brandon Mantovanni Yunata Brandon Mantovanni Yunata`
> `季军 Second Runner-up: 谢昊轩 Xie Haoxuan 谢昊轩 Xie Haoxuan`

…for all four rows (`png\apecall-3.png`). A duplicated name is a proofing error a reviewer sees
immediately, and no validator rule covers the rendered row text.
*Fix direction:* de-duplicate `value_cn`/`value_en` when they are equal (or render either the CN or
the EN value per row).

### D6 — MEDIUM: photo layout contradicts the measured corpus
`VISUAL_PATTERNS.md` §C.1 is explicit: "no 2-up / 3-up / 2×2 photo grid can be measured from the
approved corpus, and therefore none should be invented… one full-bleed image per block."
`pdfout.py` picks `cols = 2 if len(tiles) > 1` and renders exactly that forbidden 2×2 grid with
6 pt white gutters — `png\grid-2.png`. Separately, approved photos are 624 px wide at aspect
1.46:1 bleeding past the text measure; the renderer draws 483 × 130 pt boxes (aspect **3.7:1**)
inside the measure. The block's own `cn`/`en` hint is ignored in favour of a hardcoded
`slide right for more pictures`.

### D7 — MEDIUM: the shipped `output\` evidence bundle is stale and not reproducible
`output\...\...recap\` has **no PDF and no `media\`**, and its `check_report.json` says
`"ok": false, "score": 68` with `SIMILARITY` at severity **error**, while the shipped validator run
on that same file today returns **score 86, 0 errors, SIMILARITY as warning, exit 0** — with or
without `-b`. A reviewer trusting the bundle reads "NOT READY"; the tool says "passes". The run
also predates the PDF feature, which is why the task's instruction to inspect "the generated PDF"
could not be followed on the shipped artifacts — I had to re-render them myself. `run_log.json`'s
`usage.model` is `""` in every run, so no run records which model produced it.

### D8 — MEDIUM: a wrong weekday flows through unchecked
`examples\brief_apec_future_skills.md` says `2026年11月8日（周六）`; the article repeats `（周六）` and
`8 November 2026 (Saturday)`. `datetime.date(2026, 11, 8).strftime("%A")` → **Sunday**. Verified by
execution. `FACT-DATE-MISMATCH` only compares CN wording against EN wording, never a date against a
calendar, so the wrong weekday survives into a "passing" article. (My own brief's 2026-03-28 /
2026-03-20 are a genuine Saturday / Friday.)

### D9 — MEDIUM: "no photos at all" is unguarded
My fresh article has `photos_placed: 0` against a brief that mentions a poster and past photos, and
scored **99/100, exit 0**. Uploading one photo to the same article flips it to **81/100, exit 2**
with `PHOTO-NONE` + `PHOTO-UNUSED`. So `PHOTO-NONE` can only fire when photos were uploaded but
left unplaced — the common operator error (forgot the attachments) is exactly the case it misses,
even though every approved article carries imagery.

### D10 — LOW: invented operational detail is unchecked
`小组长` and `称重` in my fresh article, against a kit list of 手套、垃圾夹、垃圾袋 and no scale.
Harmless here, but it is the same class as D1/D2 and shows the `facts[]` mechanism is self-reported:
the model listed 17 facts, all labelled "活动简报 / Event brief", including ones the brief does not
contain in that form.

### D11 — LOW: metadata blank, TOC heading hardcoded
`meta.model`, `meta.generated_at`, `run_log.generated_at` and `usage.model` are all `""` in my run
(`_postprocess` uses `setdefault`, which does not overwrite the model's empty strings). The TOC
eyebrow is hardcoded `精彩回顾 · Table of Contents` even though my brief said
`活动资讯 · Table of Contents` — my PDF printed `精彩回顾`.

---

## 5. WHAT GENUINELY WORKS (verified, not assumed)

* `generate` end to end from an arbitrary brief: brief → structured brief → local exemplar retrieval
  → bilingual article → validate → render. 1 attempt, no repair needed, on a genuinely new event.
* **Bilingual discipline is real**: every CN body block had an EN twin, every heading carried English,
  CN:EN ratio 1.63 (band 1.18–2.26), CN-before-EN order, in both articles.
* **Credit fidelity is real**: extracted from the brief and matched **exactly** (all six roles,
  character-for-character) in both the shipped and the fresh article — including the shortened
  二审 in my brief and the 三审 = 卢锦章 invariant.
* **The four offline tests all pass**: `probe_render.py` (render OK, PDF 65,290 B, 3 pages, text ok),
  `validate_cases.py` ("every rule fires on its defect and stays quiet on approved style"),
  `fontcheck.py` (67/67 glyphs round-trip), `fidelity.py` (6/6 sentences recovered).
* **The PDF engine is sound on the hard part**: real CJK TrueType font embedded, searchable text
  layer, 0 replacement characters, no tofu, correct 三审 block. Ghostscript shrinking works
  (84 KB output) and the `.full.pdf` fallback path exists.
* **The "omit rather than invent" instinct works in the fresh run**: the model refused to fabricate
  an APEC link and listed the gap for the editor. It also found the right genre exemplars
  (two 游园会 posts for a 招募).

---

## 6. LIMITS OF THIS VERIFICATION

* **2 generations run** (1 mine, plus reuse of the Lead's two logged runs). The corpus-leak defect (D1)
  is topic-dependent: it reproduced because the APEC brief retrieves same-series exemplars. My brief
  did not trigger it. I did not measure the base rate.
* I could not inspect the shipped PDF because none exists; `apec_shipped_render.pdf` is my own render
  of the shipped JSON with the shipped renderer — same code path, but not byte-identical to anything
  the Lead produced.
* I did not test the browser UI (`web`), the vision/photo path (no real photos supplied), or DOCX
  fidelity beyond its successful creation.
* Adversarial cases were derived by editing the shipped APEC JSON; a truly hand-written article
  could trip additional schema paths I did not exercise.

## 7. ARTIFACT INDEX (`_work\verification\`)

```
VERIFICATION_REPORT.md          this report
brief_beach_cleanup.md          my independent brief (the fresh-generation input)
make_adversarial.py             builds the 8 adversarial variants + control
extras.py                       venue/person variants + re-render of the shipped article
measure_and_render.py           style metrics vs corpus bands; report-attached + 4-photo renders
inspect_pdf_ops.py              PDF content-stream dump
crop_heading.py                 crops for the accent-bar defect
gen\hsiyc-coast-classroom-.../  full fresh bundle: .json .md .docx .pdf .preview.html .html
                                check_report.txt/.json run_log.json
adversarial\                    case_A..J variants
pdf\                            apec_shipped_render.pdf, apec_with_report.pdf, grid4.pdf
png\                            all page renders + crops (evidence images)
fresh_text.txt                  pdftotext extraction of the fresh PDF
```
