# HSIYC 文章助手 · HSIYC Article Writer

An AI agent that writes HITSZ International Youth Club (哈工大（深圳）国际青年俱乐部)
event articles in the **exact bilingual style of the articles the youth committee has
already approved**, and checks them against the reasons articles get returned before
anyone sends them.

It reads your event notes and photos, drafts the article in Chinese + English, runs a
deterministic pre-submission check, repairs what it can, and writes out a preview, a
Word file, a PDF and a paste-ready Markdown version.

---

## Why it works the way it does

The style is not guessed. It was measured from your 17 approved PDFs:

| What was measured | Result |
|---|---|
| Bilingual protocol | Section by section, **CN paragraph then its EN twin**. 13/13 text-complete articles. **0/130 headings are Chinese-only.** |
| CN:EN length ratio | 1.73 mean / 1.79 median (range 1.18–2.26 CN characters per English word) |
| Body length | median 860 CN characters (range 305–2,261) |
| Headings | 4–24 per article, median 11 |
| Credit block | 6 roles; **only invariant is 卢锦章 as final approver** (16/16); 一审 has 8 different name sets, 二审 has 7 |
| Photo layout | **No multi-photo grid exists in the corpus** — one full-bleed image per block, ~2.8 photos per article |
| Page colour | 88.6 % pure white; colour carried by thin navy rules (`#1B3870`), not fills |
| Body text | `#4C4C4C`, flush left, no first-line indent |

Full evidence: [`_work/analysis/TEXT_PATTERNS.md`](_work/analysis/TEXT_PATTERNS.md) (text)
and [`_work/analysis/VISUAL_PATTERNS.md`](_work/analysis/VISUAL_PATTERNS.md) (visual),
with [`design_tokens.json`](_work/analysis/design_tokens.json).

The rules the generator follows are in [`spec/STYLE_SPEC.md`](spec/STYLE_SPEC.md), and the
checks are in [`spec/REJECTION_CHECKLIST.md`](spec/REJECTION_CHECKLIST.md).

---

## Install

Nothing to install. Pure Python standard library, plus libraries already present in the
bundled runtime:

| Library | Used for | Required? |
|---|---|---|
| `Pillow` | photo handling, and every generated image | yes |
| `numpy` | gradients, noise and compositing for the artwork | yes, for artwork only |
| `python-docx` | the `.docx` deliverable | yes |
| `python-pptx` | the `.pptx` deck | optional |
| `openpyxl` | the `.xlsx` tracker | optional |

The app runs on either interpreter on this machine. The bundled runtime has every library;
the system Python 3.11 has all of them except `python-pptx` and `XlsxWriter`, which it
borrows from the bundled runtime automatically (append-only, so system packages still
win). A missing optional library costs the deck or the tracker and never the article —
the reason is written into `render_warning.txt`.

```powershell
$py = "C:\Users\hp\AppData\Local\Programs\Python\Python311\python.exe"
cd C:\Users\hp\OneDrive\Desktop\ArticlesAgentica
```

### API key

The agent uses your own DeepSeek API key. It is resolved from
`DEEPSEEK_API_KEY`, or from `hsiyc_writer\.deepseek_key` (already set on this machine).

```powershell
$env:DEEPSEEK_API_KEY = "sk-..."     # or write the key into hsiyc_writer\.deepseek_key
& $py -m hsiyc_writer key            # shows the key masked, plus the base URL
```

---

## Use it

### Browser UI

```powershell
& $py -m hsiyc_writer web
# -> http://127.0.0.1:8765
```

The default page is an **English intake form**: 27 questions in 6 groups, 11 of them
required. Answer them, drop in the photos, press **Generate article**. An older free-form
"paste your notes" page is still available at `/legacy`, and **`/gallery`** lists every
article produced so far — poster thumbnail, validator score and download links, newest
first.

| Group | Questions |
|---|---|
| **Event story** | **Describe the event in your own words** — one open box, anything you like |
| **Event basics** | Event name (English / Chinese) · article type · date · last day if multi-day · start and end time · venue (English / Chinese) · organisers · co-organisers · who took part and how many |
| **People** | Judges / speakers / guests · award winners · contact or registration link |
| **Results** | Anything memorable to include · outcome summary |
| **Article structure** | Programme or series · previous article title · next article title |
| **Review credits (三审)** | 文字 · 图片 · 排版 · 一审 · 二审 · 三审 — all six required |

**The article itself is still bilingual** — Chinese and English, exactly like the approved
PDFs. Only the *questions* are in English.

#### The description box

The first question is deliberately open: *"Describe the event in your own words."* Write it
the way you would explain it to a friend — rough notes, half-sentences, Chinese, English or
both. Agentica does the rest:

* **It develops the notes into the article.** The description becomes the spine: the agent
  orders the story, turns fragments into full bilingual prose and expands passing details
  into proper sentences — while keeping every fact you wrote and adding none. The article
  prompt is explicit that it may not reuse your wording verbatim, and may not introduce a
  name, number, quote or sponsor the description does not contain.
* **Anything you write in it becomes allowed material.** The box goes into the brief, so a
  figure or a name that appears only there is *sourced* — exactly like the labelled fields.
  The check will not flag what you wrote; it will still flag what you did not.
* **“Develop this description” improves it before you generate.** One short API call
  rewrites your notes into a cleaner description, hands it back **into the box** for you to
  edit, and offers **Undo** to put your own text back. Two things come back with it:
  * **questions** — up to five gaps a reviewer would notice (an exact count, a judge's full
    name, the prize titles). Answer them in the fields below, or leave them; anything you
    leave out is handed to the editor as a gap instead of being invented.
  * **a check on the rewrite itself** — every figure, date and Latin name in the improved
    text must already exist in what you typed. Anything that does not is listed in the panel
    as *"not in your notes"*. Writing a fact differently is not inventing it, so the check
    normalises representations before comparing: `five integrals` → `5`, `8 november` and
    `11月8日` are the same day, `8 to 9 November` and `11月8日至9日` are the same two days,
    `in A509.` still contains the room number, `３２` equals `32`, `March 5` is a date but
    `we march 5 kilometres` is not, and `Judge Alan Turing` is reported as `Alan Turing`. A
    *moved* date (`11月9日` when the notes say 8 November) is still reported. This is the
    same rule the article check applies, applied one step earlier — and its blind spots are
    listed under [Known limits](#known-limits).
* **A date in the box that contradicts the date fields warns before anything is spent** — a
  recap published on the wrong day is a guaranteed correction.

The box is optional; every other field still works on its own, and a bundle generated
without it is identical to before.

Three things the form does for you:

1. **It asks for the facts the articles always contain**, so nothing has to be invented.
   Dates come back formatted the way the corpus writes them (`2026年11月8日（周日）`,
   `7月19日至21日`).
2. **It blocks a hopeless run before spending tokens.** Required answers are checked in the
   browser and again on the server; impossible dates and times are rejected, and soft
   omissions (no winners for a recap, no registration link for a 招募) warn instead.
3. **It removes the normalising LLM call.** Because every fact arrives labelled, the brief
   is assembled directly — one fewer API call and no chance of a date or name being
   reinterpreted on the way in. The brief shown to the model is exactly the whitelist the
   fact checks run against, and the result panel lets you read it.

### Command line

```powershell
# see the questions, plus a JSON skeleton to fill in
& $py -m hsiyc_writer form

# generate from a filled-in answers file
& $py -m hsiyc_writer form --answers answers.json -p photos\

# develop the rough 'event_description' before writing (writes back into the file)
& $py -m hsiyc_writer develop --answers answers.json --write
& $py -m hsiyc_writer develop --text "32 students, 1v1 blitz, Tugsuu won"
& $py -m hsiyc_writer develop -f notes.txt --doc-type 回顾

# the free-form route, for long notes
& $py -m hsiyc_writer generate -b my_brief.md --doc-type 招募

# check an article you wrote yourself (works on any article JSON)
& $py -m hsiyc_writer check output\<slug>\<slug>.json -b my_brief.md --json

# list the approved articles used as style exemplars
& $py -m hsiyc_writer corpus

# artwork: auto tries the online image model, then falls back to drawing it locally
& $py -m hsiyc_writer generate -b brief.md --art auto          # default
& $py -m hsiyc_writer generate -b brief.md --art local         # never touches the network
& $py -m hsiyc_writer generate -b brief.md --art none --no-deck

# redo the artwork for an existing bundle, without regenerating the article
& $py -m hsiyc_writer art output\<slug> --backend auto
& $py -m hsiyc_writer art output\<slug> --kind poster --light --seed 7

# Excel tracker: one row per article, the 三审 roster, every open finding
& $py -m hsiyc_writer tracker

# run the offline test suite (no API key, no network)
& $py -m hsiyc_writer selftest
```

Add `--strict` to get a non-zero exit code when the check fails — useful in a batch script
or a pre-publication gate.

### From Python / HTTP

```python
from hsiyc_writer.apiclient import generate_via_api
state = generate_via_api("http://127.0.0.1:8765", brief_text, photos=["a.jpg"], doc_type="回顾")
print(state["result"]["check"]["score"])
```

---

## What you get per article

Written to `output/<slug>/`:

| File | Use |
|---|---|
| `<slug>.preview.html` | Visual preview matching the approved look, with the event artwork shown underneath |
| `<slug>.docx` | Word file for the layout editor |
| `<slug>.pdf` | Submit-ready PDF (selectable Chinese text, ~45–135 KB) — **the article only**; the check report is never printed on it |
| `<slug>.pptx` | Presentation deck for the club to show, or slice into social posts |
| `<slug>.md` | Paste-ready copy for the WeChat editor |
| `<slug>.xiumi.html` | **The 秀米 / WeChat paste export** — open it, select all, copy, paste into 秀米 |
| `<slug>.xiumi.md` | The handover for whoever does the layout: paste steps and the photo list |
| `<slug>.json` | The structured article, for re-rendering or diffing |
| `art/` | Event artwork: `banner.png`, `cover.png` (WeChat's 2.35:1 crop), `poster.png`, `social.png`, one `divider-NN.png` per section, and `manifest.json` explaining what was made and how |
| `check_report.txt` / `.json` | The pre-submission check (internal) |
| `run_log.json` | Which approved articles were used as exemplars, token cost, timings, which art backend ran, and the brief the article was built from |
| `media/` | The photos, so the bundle is self-contained |

The artwork is a **separate deliverable**: posters, banners and social cards to
promote the event. It is never placed in the article PDF or DOCX, because those
are what goes to the youth committee and the approved format is text plus real
photographs. Every generated image is labelled as an illustration, never as a
photo of something that happened. See [spec/ART_SPEC.md](spec/ART_SPEC.md).

### Laying it out in 秀米 / 微信

Every bundle carries `<slug>.xiumi.html`: the same article written as markup that survives
the paste. On the result page there is a **Copy for 秀米** button that puts it on the
clipboard as rich text, or open the file and press Ctrl+A, Ctrl+C, then Ctrl+V into the
秀米 图文编辑 body.

The button tries three routes, because the modern Clipboard API is not always permitted —
it is refused outright inside iframes and webviews, and a write that arrives after an
`await` loses the user gesture ([WebKit bug 222262](https://wiki.webkit.org/show_bug.cgi?id=222262)):

1. **`execCommand('copy')` on a hidden selection** — synchronous, so the click's gesture is
   still live, and not gated by the clipboard-write permission. The paste markup already
   travels in the result payload, so nothing is fetched inside the handler.
2. **`navigator.clipboard.write()`** — called with no `await` before it, as the fallback.
3. **The article shown on the page, already selected** — needs no permission and no new
   tab; if both clipboard routes are refused, press Ctrl+C and paste.

Both 秀米 and the WeChat article editor keep **only inline styles**, so the export is built
to one rule: every tag carries its own style and nothing refers to anything outside itself.
No stylesheet, no classes, no ids, no `<div>`, no flex or grid, no external file — because
each of those is silently dropped on paste, and the failure looks fine in the bundle and
arrives in 秀米 as unstyled grey paragraphs. The tests assert exactly those properties, so
a renderer change cannot quietly break the paste.

It is a **finished layout**, not styled text — masthead, bilingual title, a rule under it,
decorative separators, numbered section headers with a rule, navy award cards with rank
chips, captions marked with a small ▪ against their photo, a boxed editorial (三审) card and
the 精彩回顾 card. That matters because 秀米 is where the article is finished when the club
cannot use the WeChat API yet: nothing here needs 公众号 access, and publishing can wait.

Two honest limits:

- **Photographs cannot cross a clipboard.** A path on your disk means nothing to a web
  editor, a `data:` URI is stripped, and WeChat re-hosts every image on its own CDN anyway.
  So each photo position pastes as a numbered dashed box — **[待插入照片 01]** + the file
  name + its caption — and the bundle carries `xiumi-photos/01-…`, `02-…` in article order,
  so the file picker's default sort is already the order the article needs. Upload the photo
  where its box sits, delete the box. The list is also in `<slug>.xiumi.md`.
- **There is no 秀米 link this tool can give you.** 秀米 has no public API for creating or
  importing a document from outside, and a 秀米 document lives inside your logged-in
  account. The one-click 同步到公众号 additionally needs the **公众号 administrator** to
  scan an authorisation QR code — 秀米's own
  [authorisation guide](https://xiumi.us/wxauth/guide) says an 运营者 cannot do it. That is
  a human step with the club's credentials, not something an agent can hold. Producing the
  paste-ready article is the part that can be automated, and it is.

Your own 秀米 template still applies on top: the export carries only the club's typography
and colours inline, so a 秀米 template can restyle it freely without fighting a stylesheet.

### Skipping 秀米 entirely: straight into the 公众号 draft box

秀米 has no import, and its 一键同步 needs a human to scan an authorisation QR code. But the
thing that button does behind the scenes is the **official WeChat server API**, and the club
can call it directly — that is the fast route, and it removes the layout step for everything
except your own 秀米 template:

```
photos  -> POST /cgi-bin/media/uploadimg      -> mmbiz.qpic.cn URLs
cover   -> POST /cgi-bin/material/add_material -> permanent media_id
article -> POST /cgi-bin/draft/add            -> a draft in 草稿箱
```

The markup we already produce is exactly what that API accepts (inline styles, `<section>`,
no stylesheet) — one renderer feeds both the 秀米 paste export and the draft body, so the two
can never drift apart.

```powershell
# 1. does the setup work? one real API call: token -> proves AppID, AppSecret and the IP whitelist
& $py -m hsiyc_writer wechat --check

# 2. what would be sent: no network, nothing created
& $py -m hsiyc_writer wechat output\<slug>

# 3. upload the photos and create the draft
& $py -m hsiyc_writer wechat output\<slug> --send
```

Dry run is the default everywhere, including the web UI: creating a draft is external state
in the club's account, so a stray click must not leave one behind. Either way the exact
payload lands in `output/<slug>/wechat-draft.json` for inspection. The web UI shows the same
card with a **Test the connection** button, so the setup can be checked from the page.

**Setup, in order** (公众号后台 → 设置与开发 → 基本配置):

1. **AppID + AppSecret** → `HSIYC_WECHAT_APPID` / `HSIYC_WECHAT_SECRET`, or the files
   `hsiyc_writer/.wechat_appid` and `hsiyc_writer/.wechat_secret`. Nothing is printed in full:
   `wechat --check` shows the AppID and only confirms the secret is set.
2. **This machine's public IP in the IP 白名单** — same page. `wechat --check` prints the
   address as WeChat will see it (`errcode 40164` until it is listed). If you generate from a
   different network, that network's address needs listing too.
3. **An account with the draft/material interface permission** — the draft interface is
   available to 公众号 and 服务号; a 未认证 account generally cannot call it (`errcode 48001`).

Only `/cgi-bin/token` is called by `--check`; it costs no quota worth worrying about, and it
is the same call every other step depends on.

WeChat also enforces its own limits, all of which the tool applies before sending: title ≤ 32
characters, author ≤ 16, digest ≤ 120, body under 1 MB, and every image jpg/png under 1 MB —
phone photos are resized and re-encoded automatically, transparency is composited onto white
rather than turned black, and a file that is not really an image is reported by name instead
of failing halfway through a send. External image URLs are filtered by WeChat, so a photo
that is placed in the article but missing from the bundle stops the send instead of producing
a broken draft.

Artwork now uses separate portrait, square and landscape composition prompts.
Posters and social cards keep long bilingual headlines within fixed text budgets;
exceptionally long text is shortened with an ellipsis to preserve the date and venue.
Each asset has an independent seed, so regenerating only a poster reproduces the
same poster as a full kit with that seed. The results gallery includes PNG downloads,
dimensions and per-image provider labels; the output list also includes section bands.

Custom image providers can set `HSIYC_ART_SIZE` (for example, `1024x1024`) when they
require a specific generation size; final deliverables retain their standard dimensions.
The custom API request omits the nonstandard `seed` parameter. Seeds distinguish cached
variants there, but a custom provider is not guaranteed to reproduce an uncached image.

Build the Excel tracker across every bundle — one row per article, the 三审
credit roster, and every open validator finding:

```powershell
& $py -m hsiyc_writer tracker
```

Re-render an existing bundle after changing the renderer:

```powershell
& $py tools\refresh_outputs.py            # all bundles
& $py tools\refresh_outputs.py <slug>     # one bundle
```

It re-reads the stored brief from `run_log.json`, so the bundle is re-checked against the
same material it was written from.

---

## How it works

```
intake form answers      ->  event description + labelled facts   the operator's own words
event photos             ->  what the photos show                  DeepSeek vision
brief (free-form notes)  ->  structured brief                      DeepSeek, JSON mode
12 approved articles     ->  nearest one as exemplar               local retrieval, no API call
        |
        v
   bilingual article JSON  ->  deterministic validation  ->  targeted repair (bounded)
        |
        v
   HTML preview / DOCX / PDF / Markdown / check report
```

The description box can be developed on its own first — one short call, checked for invented
figures and names before it is handed back to the operator:

```
rough notes  ->  "Develop this description"  ->  improved description + questions
                                              ->  figures/names not in the notes
                                              ->  back into the editable box
```

Three design decisions worth knowing:

1. **The style is data, not code.** It lives in `spec/`, so when the committee's
   expectations drift you edit a Markdown file, not Python.
2. **One already-approved article is always fetched and shown to the model.** Retrieval is
   local (character bigrams for Chinese plus word tokens for English), so it costs nothing
   and the model sees a real approved article rather than a description of one.
3. **The validator is deterministic and offline.** It costs no tokens, and you can run it
   on a human-written draft too.

---

## The pre-submission check

`hsiyc_writer/validate.py` implements 25 rules derived from the corpus. The blocking ones:

- the 三审 credit block is incomplete, or contains placeholder text
- a Chinese paragraph has no English twin, or a heading is Chinese-only
- **a number in the body that appears in no supplied material** — and the article's own
  `facts` list deliberately cannot whitelist a number, so it cannot launder its own claim
- **a person named in the body who appears in neither the brief nor the credits** — a
  fabricated winner or judge was the one defect that used to pass (add winners, judges and
  speakers to the brief and they are accepted)
- a "fact" with no source, or one sourced from a previous article
- the article places a photo that was never uploaded
- fewer than 3 sections, an empty section, or an unknown block type
- a missing title / lead / closing / sign-off / credits block

It also **deliberately does not check** things the reviewers tolerate: credit separators
(`、`/`，`/`,` all appear, and 7 of 12 approved blocks mix them), bilingual heading order,
ranking vocabulary, TOC wording, and spacing around Latin or numerals. Hard-width punctuation
is only flagged inside running Chinese text, so approved forms like `14:00-17:00` and `1v1`
pass. A validator that rejects approved-style copy is worse than none, so each of those cases
has a regression test asserting it stays quiet.

Two hard-won calibrations, each found by testing rather than reasoning:

- **Similarity to the corpus** only escalates to an error when a sentence recurs across
  *several different* approved articles (generic filler). Overlap with one article is normal —
  the club reuses its own phrasing deliberately when covering the same event or series.
- **Names** are only checked where a person can actually appear (an honorific, or a ranking
  list entry), against a curated surname list. An earlier version matching every surname-like
  token flagged ordinary words like 付出 and 国家的.

The same discipline applies one step earlier, to the description box: the "Develop this
description" rewrite is checked for figures and Latin names that were not in the operator's
notes, so the agent cannot quietly enrich the source material before the article is written.
Whatever the operator leaves in that box is authoritative — which is also the honest limit of
the whole design: **the check proves the article contains nothing you did not supply; it
cannot prove that what you supplied is true.**

Run the rules on their own:

```powershell
& $py -m hsiyc_writer check output\<slug>\<slug>.json -b my_brief.md
```

> Pass `-b/--brief` when checking by hand: without the source material the check cannot trace
> numbers or names, and it says so (`FACT-NO-BRIEF`) rather than pretending to pass.

---

## Accuracy: what is verified, and how

```powershell
& $py -m hsiyc_writer selftest
```

| Test | What it proves |
|---|---|
| `tests/validate_cases.py` | 35 cases: every rule fires on its defect **and stays quiet on approved style** |
| `tests/form_cases.py` | 11 checks on the intake form: required answers block, impossible dates/times reject, dates format like the corpus, and **every answer survives into the brief** so the check cannot flag a fact the operator actually supplied |
| `tests/develop_cases.py` | The description box: a stub is refused before a token is spent, a faithful rewrite passes, an invented figure (`512`), an added date (`12-03`) or an invented name (`Alan Turing`) is caught, and a model-authored brief cannot inject a description. Also pins every false positive an independent verifier found: date ranges, `8th of November 2026`, full-width `３２`, `we march 5 kilometres`, impossible days |
| `tests/xiumi_cases.py` | The 秀米 / WeChat paste export: no stylesheet, class, id, `<div>`, flex or external reference may survive pasting; every element carries its own inline style; no text is lost; each photo position is a labelled slot; article text cannot inject markup; all eight existing bundles re-export balanced and clean |
| `tests/wechat_cases.py` | The 公众号 draft route, offline against a fake transport: a dry run sends nothing, the token is cached, every placed photo is uploaded in order, WeChat's length limits are applied rather than hoped for, a 4 MB phone photo is resized under the 1 MB limit, a file that is not an image is named instead of crashing a send, and each WeChat error code (`40164` IP whitelist, `48001` permission) produces the instruction that fixes it |
| `tests/fidelity.py` | The finished PDF's text layer matches the source, and no drawn CID falls outside the font |
| `tests/fontcheck.py` | Every character maps to a byte-identical glyph outline and back to its code point |
| `tests/probe_render.py` | The PDF opens in a real rasterizer, has pages, and keeps its text |
| `tests/robustness.py` | A failed vision call, a missing photo, malformed article JSON and empty inputs are all handled without crashing |

Two tools drive the live app rather than the library:

```powershell
& $py tools\try_form.py           # fills the form, submits it over HTTP with photos, prints the result
& $py tools\refresh_outputs.py    # re-renders existing bundles after a renderer change
```

The PDF engine embeds a full CJK font and lets Ghostscript subset it. An earlier
hand-written font subsetter produced PDFs whose *text layer was perfect but where some
glyphs rendered blank* — invisible to byte-level checks, which is why the tests above
verify rendering and extraction rather than file structure.

An independent verifier (a separate agent, no access to this session's reasoning) reviewed
the tool and found five real defects, all since fixed: the submission PDF carried the
internal QA report and corpus slugs, award rows printed each winner's name twice, the
section accent bar floated 36pt above its heading, fabricated people passed the check, and
a number could whitelist itself by appearing in the article's own `facts` list. Its report
is at [`_work/verification/VERIFICATION_REPORT.md`](_work/verification/VERIFICATION_REPORT.md).

A second verifier pass audited the event-description feature. It found five ways a
*faithful* rewrite could be accused of inventing something — date ranges (`11月8日至9日` vs
`8 to 9 November`), `8th of November 2026` parsing as 20 November, full-width `３２` being
invisible, the verb in `we march 5 kilometres` read as the month of March, and impossible
days like 30 February being accepted — plus one way a *model* could widen the whitelist: on
the free-form path the normaliser could write its own `event_description` and have it
treated as the operator's material. All six are fixed and pinned in
`tests/develop_cases.py`; its report and one-shot reproductions are at
[`_work/verify_develop/REPORT.md`](_work/verify_develop/REPORT.md). It also confirmed the
blind spots now listed under [Known limits](#known-limits).

---

## Costs

One article is roughly **12k–27k tokens** and **20–35 seconds**. The repair pass only runs
when the check fails, so a first-draft-clean article costs about half.

Measured on real runs against this corpus:

| | sections | CN chars | result |
|---|---|---|---|
| Clean first draft | 6–7 | 900–1,200 | 95–99/100, 0 errors |
| With one repair round | 6–7 | 950–1,050 | 91–98/100, 0 errors |

Both fall inside the measured corpus band (8–13 sections, 700–1,400 CN characters). An
earlier prompt under-wrote at 4–5 sections and 640–690 characters; the prompt now states
the targets explicitly and the check blocks anything under 700.

---

## Layout

```
hsiyc_writer/            the agent
  config.py              API key + model settings
  form.py                the English intake questions and how answers become a brief
  develop.py             "Develop this description" + the check that it invented nothing
  deepseek.py            chat/JSON/vision client (no SDK)
  retrieval.py           finds the nearest approved article
  prompts.py             the prompts (this is the product)
  pipeline.py            form or brief -> photos -> exemplars -> draft -> repair
  validate.py            the pre-submission check
  render.py              HTML / DOCX / Markdown / the 秀米 paste export / the bundle writer
  wechat.py              the official 公众号 draft API (token, image upload, cover, draft)
  pdfout.py              dependency-free CJK PDF engine + Ghostscript shrink
  office_export.py       the .pptx deck and the .xlsx submission tracker
  art/                   generative artwork
    vibe.py              event keywords -> palette, motif, mood, image prompt
    motifs.py            the twelve drawing routines (aperture, lantern, trophy...)
    local.py             the picture engine + poster / banner / cover / social / divider
    remote.py            optional online text-to-image (Pollinations, or your own)
    canvas.py            gradients, noise, supersampled drawing primitives
    text.py              CJK font choice and line breaking
  web.py                 HTTP server + form / legacy / gallery endpoints
  web/form.html          the English intake form
  web/gallery.html       everything produced so far, with posters
  web/index.html         the older free-form brief page
  cli.py                 command line
spec/                    style spec, rejection checklist, article schema, artwork spec
tests/                   offline test suite (nine files)
tools/                   try_form.py, refresh_outputs.py, backfill_brief.py
_work/analysis/          the corpus evidence reports
_work/pages/             rendered page images of all 17 approved PDFs
output/                  generated articles
examples/                sample briefs
```

## Known limits

- **The credit block must come from your brief.** The reviewers rotate weekly; the agent
  will not invent a name, and the check fails if the block is incomplete. Fill it in.
- **Photos are placed by filename.** If you generate without uploading photos, the article
  contains placeholder filenames and the check warns about it.
- **The PDF is a faithful summary of the layout, not a pixel-replica of WeChat.** The
  DOCX is what your layout editor should start from.
- Articles longer than about 6,000 Chinese characters exceed anything in the approved
  corpus; the check flags it.
- **The online image model is rationed.** The keyless public endpoint used for AI
  illustrations serves roughly one novel prompt in six, and answers `HTTP 402` once its
  budget is gone. `--art auto` falls back to the offline renderer immediately when that
  happens, so a run is never delayed, but do not expect an AI image every time. Point
  `HSIYC_ART_ENDPOINT` + `HSIYC_ART_API_KEY` at a provider you pay for to make it
  reliable.
- **Generated artwork is decoration, not evidence.** It carries a visible
  "AI-generated artwork (not an event photo)" line and is never placed in the article
  itself.
- **The description box is authoritative, and that cuts both ways.** Anything you type there
  is material the article is allowed to use — so a figure you get wrong is a figure the
  check will not catch. The check proves the article contains nothing *you* did not supply;
  it cannot prove that what you supplied is true.
- **The "Develop this description" check only sees figures, dates and Latin names.** An
  independent verifier probed it with 20 dishonest rewrites. It catches a changed score, an
  invented date, a moved year, a two-word invented name (`Grand Ballroom`). It does **not**
  catch: a unit change that keeps the digit (`32 students` → `Thirty-two pairs`),
  a substituted single-word name (`Tugsuu` → `Michael`), pinyin turned into characters
  (`ling yi laoshi` → `凌一老师` — the prompt now forbids this and asks for the characters
  instead), an invented claim or quote with no number in it, or an invented rank. Read the
  rewrite; the check is a net, not a proof.
- **Word-spelled numerals in the brief are read generously.** `number_words()` accepts
  `five` for 5 and `三十二` for 32, and that also means a brief containing an ordinary word
  like 五官 or 一起 (`五官` → 5, `一起` → 1) whitelists that digit. That is a deliberate
  trade: the opposite error — flagging an article for a number you wrote as a word — was a
  real false positive that reached a live run and cost a good article 14 points.
