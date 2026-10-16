# HSIYC 视觉设计系统 / HSIYC Visual Design System — Reverse-Engineered Report

Task: `task-2` · Author: `image-analyst` · Source of truth: the 188 rendered page images in
`_work/pages/<NN_slug>/page-NN.jpg` (100 dpi JPEG, 850 × 1100 px, 17 articles).

**No value in this document or in `design_tokens.json` was eyeballed.** Every colour is the
modal RGB of a measured pixel set, and every geometry value is a detected run of pixels.
Where I had to interpret (font family, intent) it is explicitly flagged as inference.

---

## 0. Method, scale convention, and the code that produced the numbers

### 0.1 Scale bridge (needed to turn measured px into renderable units)

850 × 1100 px at 100 dpi = **8.5 in × 11 in = 612 pt × 792 pt** (US Letter). Therefore:

| conversion | factor |
|---|---|
| 1 px @100 dpi | 0.72 pt |
| 1 pt | 1.3889 px @100 dpi |
| **1 px @100 dpi** | **0.96 CSS px** (1 CSS px = 0.75 pt) |

So *CSS px ≈ measured px × 0.96*. Cross-check: the body-text glyph band measures 16 px on
`03_page-04.jpg` → 15.4 CSS px, i.e. the WeChat default **15 px** body size; the line pitch
measures 24 px → 23.0 CSS px ≈ **line-height 1.6** on 15 px. The bridge is validated.

### 0.2 Tools (bundled Python 3.12.14, Pillow 12.3.0, numpy 2.3.5)

All scripts live in `_work/analysis/sample_pages/_scripts/` and are reproducible:

| script | what it measures |
|---|---|
| `lines.py` | segments horizontal text lines; per line: y-band, height, x-extent, ink density, **glyph-core colour** (modal of darkest 12 %), local background, inter-line gap |
| `probe.py` | top-12 exact RGB values + % inside an arbitrary rectangle; darkest-10 %/lightest-10 % modal |
| `rowprofile.py` | per-row ink fraction, x-extent and darkest modal colour → exact rule/border thickness + colour |
| `cardinfo.py` | card border colour + thickness per edge, interior fill, corner-radius estimate |
| `bands.py` | horizontal bands (row runs ≥45 % page width, 1–260 px tall) with the colour of the **middle row** (immune to JPEG edge ringing); vertical line detector |
| `bandsum.py` | deduplicated band/vline census per article |
| `gutters.py` | photo-grid detector: paper-white gutter 2–40 px wide, ≥60 px long, flanked by ink on both sides |
| `photogrid.py` | photo-like rectangles by block luminance-variance + saturation |
| `rank.py` / `inventory.py` | per-page photographic-content ranking; blank/placeholder/rule census |

Representative invocation (all numbers below come from calls like this):

```powershell
$py = "C:\Users\hp\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
& $py _work\analysis\sample_pages\_scripts\lines.py "03_page-04.jpg" --x=100,760
& $py _work\analysis\sample_pages\_scripts\rowprofile.py "11_page-02.jpg" 348 360
& $py _work\analysis\sample_pages\_scripts\bands.py text "01_,03_,11_,14_,16_,17_"
```

### 0.3 Corpus-level colour census (all 188 pages, 163,480,960 px)

| rank | hex | px | share |
|---|---|---|---|
| 1 | `#FFFFFF` | 155,782,637 | **88.624 %** |
| 2 | `#FEFEFE` | 619,810 | 0.353 % |
| 3 | `#FFFFFD` | 514,745 | 0.293 % |
| 4 | `#FDFDFD` | 511,008 | 0.291 % |
| 5 | `#FFEE8A` | 457,593 | 0.260 % |
| 6 | `#FFF0AF` | 386,654 | 0.220 % |
| 7 | `#FCFCFC` | 373,907 | 0.213 % |
| 8 | `#FEE566` | 356,453 | 0.203 % |
| 9 | `#FFF9CB` | 322,467 | 0.183 % |
| 10 | `#BEE3FD` | 89,412 | 0.051 % |

> **Headline finding: the approved HSIYC article is 88.6 % white paper.** There is no tinted
> page background, no card background fill (interiors measure `#FFFFFF`), and no colour block
> larger than a poster image. Colour is carried by *thin rules, borders and headings only*.

### 0.4 Data-quality caveats that constrain every conclusion below

Measured with `inventory.py`:

1. **57 of 188 pages (30.3 %) are pure white** (`min(RGB) ≥ 245` for 100 % of pixels) — filler
   pages in the PDF export. Worst: `08_` 26/29 blank, `09_` 14/18, `10_` 8/12.
2. **24 pages still carry a failed-image placeholder frame** (rose `#83395E`, e.g.
   `01_page-2.jpg` … `01_page-6.jpg`).
3. **Articles `14_`, `16_`, `17_` render body text at `#AAAAAA`–`#B2B2B2`** (measured glyph-core
   modes `#B2B2B2`/`#B3B3B3` for `14_`, `#AAAAAA`/`#A9A9A9` for `16_`, `#ABABAB` for `17_`),
   i.e. washed-out low-contrast text — these pages were screenshotted mid fade-in animation.
   **Do not copy `#ABABAB` as a body colour**; it is a capture artefact, not a token.

---

## A. Article banner / header

### A.1 Structure (all 17 articles)

The banner is **not** a rebuildable HTML block. In every article the top of the page carries
the WeChat chrome (title + byline), then the club's own cover artwork as **one full-bleed
raster image**. Nothing in the corpus repeats a title card per page.

| element | measurement | citation |
|---|---|---|
| H1 title band | y = 61–87, **h = 27 px**, x = 120–615 | `13_page-1.jpg` (lines.py) |
| H1 title band | y = 62–83, **h = 22 px**, x = 114–515 | `03_page-01.jpg` |
| H1 core colour | **`#141414`** (modal of darkest 12 %) | `13_page-1.jpg` |
| H1 core colour | **`#131313`** | `03_page-01.jpg` |
| H1 alignment | flush left at x = 114–123 | `03_page-01.jpg`, `13_page-1.jpg`, `17_page-1.jpg` |
| byline band | y = 96–117, **h = 22 px**, x = 123–640, core `#38373F` | `13_page-1.jpg` |
| byline band | y = 96–114, **h = 19 px**, x = 123–630 | `03_page-01.jpg` |

Title text pattern: `APEC青年讲堂 | 讲座回顾: 游戏化思维——从玩家到赢家` (`01_page-1.jpg`),
`国际青年俱乐部 | 国际学子鹏海模联2026斩获三项大奖` (`13_page-1.jpg`),
`哈工大（深圳）首届国际文化嘉年华 International Cultural Carnival | 活动摊位与节目招募启动!`
(`07_page-1.jpg`) — i.e. `[系列名] | [标题]`, CJK-first with an inline EN title for
international events.

Byline variants (measured band heights identical; only the text differs):

* `Original 国际教育中心 哈工大深圳校区国际教育中心 <date> 广东` — `01_page-1.jpg`, `03_page-01.jpg`, `11_page-01.jpg`, `14_page-1.jpg`, `15_page-1.jpg`, `16_page-1.jpg` (**most common, 6+**)
* `哈工大深圳校区国际教育中心 <date> 广东` — `05_page-1.jpg`, `17_page-1.jpg`
* `Study at HITSZ <date> 广东` — `07_page-1.jpg`, `08_page-01.jpg`, `09_page-01.jpg`, `10_page-01.jpg`

### A.2 Brand block inside the cover artwork

| motif | measurement / citation |
|---|---|
| co-brand line, letter-spaced caps | `HSIYC x AcademiaSphere \| APEC Gamification Lecture` — `02_page-2.jpg`, y = 84–95 |
| square-bracket club line | `［ 哈工大（深圳）国际青年俱乐部 ］` — `06_page-1.jpg` (y ≈ 200), `17_page-1.jpg` (y ≈ 172) |
| "HSIYC" logo lockup | vertical letter stack `H S I Y C` at x = 216–222, y = 176–258, ON TOP of the hero photo — `13_page-1.jpg` |
| anchor EN line, letter-spaced | `HITSZ International Youth Club` centred, h = 12 px — `06_page-1.jpg` (y ≈ 480), `14_page-1.jpg` (y ≈ 513), `17_page-1.jpg` (y ≈ 465) |
| platform watermark | `公众号 · 哈工大深圳校区国际教育中心` overlaid bottom-right on **every** embedded image — `01_page-1.jpg`, `03_page-01.jpg`, `11_page-01.jpg`, `13_page-1.jpg`, `15_page-1.jpg` |
| decorative motifs | hand-drawn navy line-art campus + satellite + orbit rings + dot grids (`11_page-01.jpg`, `15_page-1.jpg`); red lanterns with gold strings (`04_page-01.jpg`); paper-cut medallion in a red double-ruled frame (`04_page-02.jpg`); yellow gradient + bunting (`08_page-02.jpg`); orange/blue geometric shards (`05_page-1.jpg`) |

**Renderer implication:** the cover must be supplied as an image asset. What the renderer *can*
own is the H1 (15–20 CSS px bold, `#141414`, left-aligned) and the byline line.

---

## B. Section-header system

There are **four** distinct header grammars in the corpus. They are not variants of one block.

### B1 — Numbered banner header ("01 / Future Skills Challenge / 未来技能挑战赛") ★ the one asked about

Measured on `11_page-02.jpg` (`11_page-02` = sample page
`11_page02_numbered_section_header_double_rule_orange_box.jpg`) and `15_page-2.jpg`:

| element | measurement (`11_page-02.jpg`) | measurement (`15_page-2.jpg`) |
|---|---|---|
| whole header group band | y = 215–257, **h = 43 px**, x = **288–567** (280 px wide) | y = 392–433, **h = 42 px**, x = 296–551 |
| "01" numeral | part of the same band, left of the label; visually 2–3× the label cap height, heavy weight, slightly oblique | same |
| label line 1 | `APEC \| 未来技能挑战赛` — CJK, bold | same |
| label line 2 | `Future Skills Challenge` — EN, bold italic, directly under line 1 | same |
| biling. stack order | **CN above EN** (EN is the italic second line) | CN above EN |
| header ink colour | **`#0E2278`** (modal of darkest 12 %) | **`#162A69`** |
| double rule | **y = 268–273 (h = 6 px, `#213769`) + y = 276–277 (h = 2 px, `#2A395A`)** | y = 440–448 (h = 9 px merged, `#20336B`) + y = 450 (h = 1, `#2E325F`) |
| rule extent | x = **288–565** (278 px) — i.e. exactly the header group width, **not** full-bleed | x = 293–556 |
| sub-label under rule | `Integration Bee Championship` — EN, bold italic, `#20276B`, band h = 16 px, x = 288–503 | `Integration Bee Championship`, band h = 16 px, x = 291–495, `#1D2959` |
| default underline | thin 1 px line under the sub-label, e.g. y = 326, x = 168–395 | — |

**Geometry summary for the renderer:** thick navy rule **4–6 px + thin navy rule 2 px**, total
block width ≈ **280 px @850** (= 202 pt = **194 CSS px**), centred as a group; the numeral and
the two-line label sit above the rule, an italic sub-label below it, all centre-aligned on the
rule's midpoint (x ≈ 427 ≈ page centre 425).

### B2 — Numbered row header with hairline ("02 ... Day 2 · Bangladesh")

Measured on `03_page-04.jpg`, `03_page-06.jpg`, `03_page-01.jpg`:

| element | measurement |
|---|---|
| numeral "02" | band y = 95–119, left edge at x = **146**, colour ≈ `#9F9F9F` (light blue-gray; darkest rows of the digit measure `#9F9F9F`) |
| hairline rule | **y = 126, h = 1 px, x = 138–428 (291 px), `#293241`, row ink = 0.441** |
| right-hand label | `Day 2 · Bangladesh` → right-aligned, x ends 719, same band, navy `#303E4B`, with a trailing glyph/flag |
| bilingual stack below | centred, 3 lines: `第二站·孟加拉国 \| Bangladesh` (band h = 17, x = 312–543) / `传统之彩：孟加拉民俗工艺` (h = 24, x = 329–527) / `Colors of Tradition: Bengali Folk Crafts` (h = 20, x = 280–579) |
| stack colours | `#1D2F47`, `#172F49`, `#1B354E` → one navy ≈ **`#1B3049`** |
| stack is centred | line midpoints 427 / 428 / 429 — page centre is 425. **Centred.** |

Same grammar at the article level: `01` + `Day 1 · China` (`03_page-01.jpg`, y = 1016–1045,
rule y = 1042–1045 h = 4 px x = 128–429).

### B3 — Plain numbered heading (AcademiaSphere / 学域 series)

`16_page-1.jpg`: `1. 活动概述` / `Event Overview` centred, band h = 20 & 16 px.
`16_page-4.jpg`: `2. 活动现场` / `On the Day`, then a sub-heading
`环节一：专业培训讲座` / `SESSION 1: Specialized Training Lectures` (EN sub-label in **ALL CAPS**).
Bilingual stack order: **CN above EN**. Colour: grey/near-black, not navy.

### B4 — Inline bilingual heading (CN · EN on one line)

`特别嘉宾 · Special Guest` — `03_page-05.jpg`, centred, band y ≈ 962–978, navy bold.
`关于我们，学域 (AcademiaSphere)` (`05_page-1.jpg`) followed by the EN twin
`About Us, AcademiaSphere (学域)` — CN above EN, both bold, inside a teal double rule.
`会议详情` (`#A6A6A6`, band h = 20) / `Event Highlights` (`#1F336E`, band h = 16) —
`13_page-1.jpg`, y = 875–927.

### B5 — Bilingual display heading, **EN above CN** (article 15 family)

`15_page-2.jpg`: `Preliminary Rounds` (band y = 736–761, **h = 26 px**, x = 160–383,
core **`#193576`**) then `预赛` (band y = 764–791, h = 28, x = 160–367, core **`#083169`**).
`15_page-8.jpg`: `Closing` / `结语` — `Closing` band y = 95–135, h = 41 (includes descender),
x = 159–247, core **`#192C6E`**; `结语` band h = 16, core `#1D2A4A`.
**Left-aligned**, not centred; EN is the larger line.

### B.6 Bilingual stacking order — measured distribution

| order | articles | count |
|---|---|---|
| **CN above EN** | `01_`, `02_`, `03_`, `04_`, `05_`, `11_`, `13_`(headings), `16_` | **8** ← most common |
| **EN above CN** | `15_` | 1 |
| EN only / CN only | `07_`, `08_`, `09_`, `10_`, `12_`, `14_`, `17_` | 7 |

Uppercase treatment: **ALL CAPS is used only for small eyebrow/label text**, never for the main
heading. Measured: `CULTURAL JOURNEY` (`03_page-01.jpg`, band y = 665–675, h = 11 px, core
`#A8A8A8`, letter-spaced), `INNOVATION` (`11_page-02.jpg`, band y = 373–399, h = 27 px, core
`#A65516`), `SESSION 1: Specialized Training Lectures` (16_page-4), `CULTURAL JOURNEY` /
`HSIYC · 2026` card footer (`03_page-01.jpg`, y = 1042–1045).

---

## C. Photo-grid grammar ★ (the load-bearing negative result)

### C.1 There is no multi-photo row with white gutters anywhere in this corpus

`gutters.py` searched all 188 pages for the signature of a photo strip — a paper-white gutter
**2–40 px** wide, **≥60 px** long, flanked by ≥50 % ink on *both* sides.

* **Total hits: 9 vertical + 19 horizontal across 188 pages.**
* Every hit is **60–94 px long** and sits inside poster artwork, not in a content gallery:
  `01_page-1.jpg` (x = 425–426 y = 285–352 inside the GAMIFICATION poster),
  `02_page-2.jpg` (x = 362–363 y = 152–242), `11_page-01.jpg` (x = 528–529 y = 319–394),
  `08_page-02.jpg`/`09_page-02.jpg` (y = 168–174, x = 304–367), `12_page-2.jpg` (y = 592–600).
* Consequence: **no 2-up / 3-up / 2×2 photo grid can be measured from the approved corpus**, and
  therefore none should be invented. The renderer must treat photo layout as *one full-bleed
  image per block*, which is what the surviving evidence actually shows.

### C.2 What the photos actually are

Measured with `photogrid.py` + `inventory.py` (a "full-bleed photographic block" = one
connected photographic region ≥ 420 × 150 px, non-overlapping within a page):

| art | full-bleed photographic blocks | pages carrying a placeholder frame |
|---|---|---|
| 01_ | 0 | 3 |
| 02_ | 2 | 2 |
| 03_ | 2 | 0 |
| 04_ | 6 | 2 |
| 05_ | 6 | 0 |
| 06_ | 2 | 2 |
| 07_ | 3 | 4 |
| 08_ | 0 | 1 |
| 09_ | 0 | 1 |
| 10_ | 0 | 1 |
| 11_ | 8 | 1 |
| 12_ | 6 | 5 |
| 13_ | 3 | 1 |
| 14_ | 0 | 0 |
| 15_ | 6 | 0 |
| 16_ | 3 | 0 |
| 17_ | 1 | 1 |
| **total** | **48** | **24** |

**Average photographs per article = 48 / 17 = 2.82** (range 0–8). Most of those 48 are
*poster artwork*, not reportage photos; only `13_page-1.jpg` shows a clean reportage photo.

### C.3 The single clean photo block (the model to copy)

`13_page-1.jpg`:
* photo band **y = 253–679 (h = 427 px), x = 112–735 (w = 624 px)** — row ink = 0.904
* 624 × 427 px = 449 × 307 pt = **599 × 410 CSS px**, aspect **1.46 : 1**
* spans the **full 624 px content width** (x 112–735), i.e. **22 px wider on each side than the
  text column** (x 134–717) — images bleed past the paragraph measure
* no border, no radius, no caption measured on this block
* second photo starts at y = 976 (x = 147–703, w = 557) and continues onto the next page

### C.4 The carousel / "slide right for more pictures" block

`15_page-8.jpg` (sample page `15_page08_photo_carousel_slide_hint_double_rule_signoff.jpg`) —
the only carousel in the corpus:

| property | measured value |
|---|---|
| frame outer box | **x = 140–704 (w = 565 px), y = 372–736 (h = 365 px)** |
| frame aspect | 565 × 365 = 1.55 : 1 |
| border | 1 px, light blue-gray; modal at the rounded corner `#7883A5` / `#B5BEDB`; top border row y = 373–374, ink = 0.848, `#7883A3` |
| corner radius | top border starts at x = 145 (offset **5 px** from box left, so r ≈ 5–8 px); left border starts at y = 383 (offset **11 px**) → **radius ≈ 8–11 px @850 ≈ 8–10 CSS px** |
| interior | **100 % `#FFFFFF`** — the slide is empty; the photos never rendered |
| hint text | `slide right for more pictures`, band **y = 736–744 (h = 9 px)**, x = 142–708, core **`#3F426B`** |
| hint placement | centred **on the frame's bottom edge**; the bottom border is interrupted across the hint (bottom border ink = 0.249 on that row vs 0.848 for the top) |
| hint size | band h = 9 px → ≈ 8.6 CSS px cap height, i.e. a 10–12 CSS px caption |

### C.5 Photos-per-section distribution

Because sections are `01/02/03` numbered blocks (B1/B2) and the pages between them carry at most
one image, the measured distribution is: **0 or 1 image per section**, with the numbered header
+ text + (optional) one full-bleed image being the whole section. Sections that have a carousel
(`15_`) have a frame but a measured **0 rendered tiles**.

---

## D. Footer / credit block design

### D.1 Club sign-off block

`15_page-8.jpg` (rulerow measurements):

| element | measurement |
|---|---|
| double rule above | **y = 808–814 (h = 7 px, `#1B3870`) + y = 816–818 (h = 3 px, `#313B56`)**, x = **112–735 (624 px)** |
| line 1 CN | `哈工大（深圳）国际青年俱乐部` — band y = 832–847, **h = 16 px**, x = 328–522, core **`#1F3276`** |
| line 2 EN | `HITSZ International Youth Club` — band y = 856–871, h = 16 px, x = 320–535, core **`#1D2A4A`** |
| line 3 brand | `AcademiaSphere` — band y = 880–895, h = 16 px, x = 368–481, core **`#1D2856`** |
| double rule below | y = 916–921 (h = 6 px, `#1B396D`) + y = 924–925 (h = 2 px, `#29395A`), x = 116–735 |
| line pitch | 24 px (832 → 856 → 880) |
| alignment | centred on x ≈ 428 |

Variants:

* **Single 1 px rules instead of a double rule** — `01_page-7.jpg`: rule above at **y = 859,
  h = 1 px, x = 116–734, `#2E3458`**; rule below at **y = 941–942, h = 2 px, x = 112–730,
  `#313B56`**. Line 1 band h = 16 px (`哈工大（深圳）国际青年俱乐部`), line 2 h = 16 px.
* **Three lines incl. `AcademiaSphere x Nexus Hive`** — `01_page-7.jpg`, `11_page-18.jpg`
  (rules y = 515 h = 1 `#000032`-family, y = 519 h = 1; sign-off lines at y = 470–520 region).
* **Near-black instead of navy** — `03_page-17.jpg`: line 1 band y = 552–569, h = 16,
  x = 318–535, core **`#3E3E3E`**; line 2 band y = 585–598, h = 14, core **`#3D3D3D`**.
  No rule above the block on this page (the navy card's bottom border serves as the separator).
* **No sign-off at all** — `08_page-29.jpg`, `09_page-18.jpg` carry only the credit block.

### D.2 Credits block (`文字 | 图片 | 排版 | 一审 | 二审 | 三审`)

`03_page-17.jpg` (lines.py, 6 rows):

| row | band | x-extent | core |
|---|---|---|---|
| `文字 \| Zhumabay Aruzhan` | y = 747–758, h = 12 | 136–280 | `#4A4A4A` |
| `图片 \| Tanvir, Fatima, …` (10 names, wraps) | y = 768–783, h = 16 | 136–679 | `#4F4F4F` |
| `排版 \| Zhumabay Aruzhan` | y = 797–808, h = 12 | 137–281 | `#4C4C4C` |
| `一审 \| 柯炽炜、Samin、Ahmed（韩沐）` | y = 822–835, h = 14 | 137–353 | `#4E4E4E` |
| `二审 \| 周宣彤、崔雨旸、高容弼` | y = 848–860, h = 13 | 136–311 | `#585858` |
| `三审 \| 卢锦章` | y = 873–883, h = 11 | 137–215 | `#505050` |

* **Alignment: flush left at x = 136–137** (same as the body measure). Not centred, not boxed.
* **Row pitch 25 px**; row band 11–16 px → ≈ 12–15 CSS px, i.e. the same body size, no bold.
* Separator between label and names: **` | ` (U+007C with spaces)** in articles 01/03/11/13/15/17;
  `：` (full-width colon) in 07 (all rows) and 08/09/10 (`文字：周玥萱`).
* Label colour and name colour measure the same (neutral grey `#4A4A4A`–`#585858`); no bold
  label was detected.

**Credit-label vocabulary across the corpus (this is a real brand inconsistency):**

| variant | articles | citation |
|---|---|---|
| `文字 / 图片 / 排版 / 一审 / 二审 / 三审` (**most common, 6 rows**) | `01_`, `03_`, `13_`, `15_`, `17_` | `03_page-17.jpg`, `13_page-7.jpg` |
| `图文 / 排版 / 一审 / 二审 / 三审` (5 rows) | `02_`, `06_`, `11_` | `02_page-6.jpg`, `11_page-18.jpg`, `06_page-5.jpg` |
| `文字 / 编辑 / 初审 / 复审 / 终审` (5 rows) | `08_`, `09_`, `10_` | `08_page-29.jpg`, `09_page-18.jpg` |
| `文字编辑 / 图文排版 / 图文审核` (3 rows) | `07_` | `07_page-4.jpg` |
| adds `视频 \|` row | `17_` | `17_page-8.jpg` |

### D.3 "精彩回顾 · Table of Contents / Previous / Next" card

`03_page-18.jpg` — the whole card is **unboxed** (no border, no background; a `#EEEEEE`
hairline was detected only in `13_page-4.jpg`):

| element | measurement (`03_page-18.jpg`) |
|---|---|
| eyebrow `精彩回顾 · Table of Contents` | band **y = 61–72, h = 12 px**, x = 137–306, core **`#818181`** — grey, left-aligned at the body measure |
| column heads `Previous` / `Next` | band **y = 98–106, h = 9 px**, x = **147–703** (two columns in one band), core **`#1E1E1E`**, bold |
| link titles | band y = 118–135, h = 18; second line y = 138–150, h = 13; core **`#373737`** |
| left column | x = 136 → ~340, **left-aligned** |
| right column | x ≈ 430 → **719**, **right-aligned** (`Next` head sits at x ≈ 690–703, i.e. flush right) |
| eyebrow wording variants | `精彩回顾 · Table of Contents` (`01_page-8.jpg`, `03_page-18.jpg`, `13_page-7.jpg`, `15_page-9.jpg`, `17_page-9.jpg`) vs `活动资讯 · Table of Contents` (`02_page-6.jpg`, `04_page-10.jpg`, `11_page-18.jpg`) — **split ~50/50** |
| `Previous` / `Next` English heads | constant in **all 17** articles |

`01_page-8.jpg` adds a trailing `修改于2026年5月27日` timestamp line (`17_page-9.jpg`: `修改于
2026年5月27日`; `15_page-9.jpg`: `修改于2026年7月21日`), grey `#A8A8A8`-class, same left measure.
`05_page-9.jpg` shows the degraded single-column case: `Next · 感知中国实践活动 | 2026年"湾区艺旅"
"寒假冬令营圆满收官"` centred, with **no** `Previous` column.

### D.4 The navy bordered card (used for lead + closing paragraphs)

| property | `03_page-01.jpg` (CULTURAL JOURNEY card) | `03_page-17.jpg` (closing card) |
|---|---|---|
| outer box | x = 133–717 (585 px), y = 640–949+ | x = 133–716 (584 px), y = 86–525 (440 px) |
| border rows | y = 640–645 (h = 6, modal `#D9EDFF`, darkest10 % **`#223158`**), y = 648–649 (h = 2) | y = 86–92 top (darkest10 % **`#20314B`**, 59.9 % share) ; y = 519–525 bottom (**`#233355`**, 47 %) |
| vertical border | x = 133 / x = 716 (1 px) | x = 134–140 (**`#1B334B`**, 7 px detected incl. antialias) |
| interior | `#FFFFFF` at 66–74 % of interior pixels — **no fill** | `#FFFFFF` 74 % |
| corner radius | top border starts at x = 134 (offset 1) → **square corners** | **square** |
| eyebrow inside | `CULTURAL JOURNEY`, band y = 665–675 h = 11, `#A8A8A8`, letter-spaced | — |
| card rule | y = 1042–1045 (h = 4) `#1B344D`, plus footer `HSIYC · 2026` | — |
| CN body inside | `#1B334B` (bands y = 726–742, 744–767) | `#1B334B` (bands y = 352–415) |
| EN body inside | `#4D4D4D`–`#505050` (bands y = 800–839) | `#4E4E4E`–`#535353` |

**Rule that survives everywhere: inside a bordered card the CN text is navy and the EN text is
neutral grey; outside a card both are grey.**

---

## E. Typography

### E.1 Measured hierarchy (band height = glyph band at 100 dpi; × 0.96 = CSS px)

| role | band h (px) | CSS px | weight (stroke density) | colour | citation |
|---|---|---|---|---|---|
| H1 article title | 22–27 | 21–26 | bold | **`#141414`** | `13_page-1.jpg` (27), `03_page-01.jpg` (22) |
| byline / meta | 12–19 | 12–18 | regular | `#7F7F7F`–`#38373F` | `03_page-01.jpg`, `13_page-1.jpg` |
| numbered-header label | 43 (2 lines) | — | bold | **`#0E2278`** | `11_page-02.jpg` |
| numbered-header sub-label | 16 | 15 | bold italic | `#20276B` | `11_page-02.jpg` |
| section heading EN (display) | 26–28 | 25–27 | bold | `#193576` | `15_page-2.jpg` |
| section heading CN | 28 | 27 | bold | `#083169` | `15_page-2.jpg` |
| bilingual stack line (centred) | 17 / 24 / 20 | 16–23 | bold | `#1B3049` | `03_page-04.jpg` |
| body CN | **16** | **15** | regular | **`#4C4C4C`** | `03_page-04.jpg`, `11_page-02.jpg`, `15_page-2.jpg` |
| body EN | 16 | 15 | regular | `#4E4E4E` | `03_page-04.jpg`, `11_page-02.jpg` |
| card body CN | 16–17 | 15–16 | regular | `#1B334B` | `03_page-17.jpg` |
| eyebrow / ALL-CAPS label | 11–13 | 11–12 | bold, letter-spaced | `#A8A8A8` / `#A65516` | `03_page-01.jpg`, `11_page-02.jpg` |
| TOC eyebrow | 12 | 11.5 | regular | `#818181` | `03_page-18.jpg` |
| TOC link title | 18 (2 lines) | 17 | regular | `#373737` | `03_page-18.jpg` |
| carousel hint | 9 | 8.6 | regular | `#3F426B` | `15_page-8.jpg` |
| credits row | 11–16 | 11–15 | regular | `#4A4A4A`–`#585858` | `03_page-17.jpg` |

### E.2 Line spacing, paragraph spacing, indentation, alignment

Measured on `03_page-04.jpg` (lines.py, x-window 100–760):

```
y=568-639  h=72   x=128-727   ink=0.289   gap=332   <- merged CN paragraph block (first line +)
y=641-663  h=23   x=128-648   ink=0.299   gap=  1
y=696-711  h=16   x=128-655   ink=0.279   gap= 32   <- EN paragraph line 1 (new paragraph)
y=720-735  h=16   x=129-703   ink=0.320   gap=  8
y=744-759  h=16   x=129-711   ink=0.319   gap=  8
y=768-783  h=16   x=128-703   ink=0.317   gap=  8
y=792-807  h=16   x=128-679   ink=0.289   gap=  8
y=817-830  h=14   x=128-286   ink=0.099   gap=  9
```

* **Line pitch = 24 px** (720 → 744 → 768 → 792) → **line-height ≈ 23 CSS px ≈ 1.6 × 15 px**.
* **Inter-line gap inside a paragraph = 8 px**; **gap between paragraphs = 32 px** → paragraph
  margin ≈ 24 px = exactly **one blank line**, i.e. WeChat's default paragraph spacing with no
  extra `margin` beyond an empty line.
* **No first-line indent.** Every body line starts at x = 128 (`03_page-04.jpg`), x = 134
  (`03_page-01.jpg`, `03_page-11.jpg`), x = 168 (`15_page-2.jpg`), x = 162 (`15_page-2.jpg` box
  interior), x = 136 (`03_page-17.jpg` credits). Variation between pages is the *container*
  inset, never an indent. **Block paragraphs.**
* **Alignment: left / justified-looking by CJK natural fill, never indented, never centred** —
  line left edges are constant and right edges vary (703 / 711 / 679 / 648). CN headings
  (`03_page-04.jpg` bilingual stack) and the sign-off are **centred** (line midpoints 427/428/429
  vs page centre 425).
* **Text column = x 134–717 (583 px = 420 pt = 560 CSS px)**; the header title starts at x = 114
  and rules/photos span x = 112–735 (624 px = 449 pt = 599 CSS px). So **images and rules bleed
  22 px wider on each side than the paragraph measure.**

### E.3 Font families

Raster-only evidence; the following is **inference**, flagged as such:

* Body CN and CN headings: **sans-serif with uniform stroke width and no serifs on 一/十/入**
  (`03_page-04.jpg`, `11_page-02.jpg`, `15_page-2.jpg`) → PingFang SC / 思源黑体 (Source Han
  Sans SC) class. Consistent with WeChat's default `-apple-system, "PingFang SC"` stack.
* Body EN: humanist sans, identical metrics to the CN sans → same stack.
* **Poster/display faces are serif or heavy display and are inside images**, not text:
  `无界校园·青春共行` (`06_page-1.jpg`), `圆满收官` outline (`17_page-1.jpg`), `模联科普讲堂`
  (heavy, `16_page-1.jpg`), `智慧校园` (navy serif, `11_page-01.jpg`), `A Joyful Closing.`
  (italic serif, `17_page-1.jpg`), `One Campus, Every Corner of the World.` (italic serif,
  `06_page-1.jpg`). The renderer cannot reproduce these with a text font; they need assets.
* EN display accent: **bold italic** is the house style for English sub-headings
  (`Future Skills Challenge` `11_page-02.jpg`, `Integration Bee Championship`,
  `The Art of Folding and Cutting` `03_page-04.jpg`, `A Joyful Closing.` `17_page-1.jpg`).

---

## F. Colour palette — measured, with role and frequency

Frequency = count of pixels whose exact RGB equals the value, aggregated over all 188 pages
(`bands.py text` for glyph colours; `rowprofile.py`/`cardinfo.py` for rules and borders;
`hs_measure.json` for the census).

| role | measured values | canonical | how measured (citation) |
|---|---|---|---|
| page background | `#FFFFFF` 155,782,637 px (88.624 %) | **`#FFFFFF`** | corpus census |
| body text (CN + EN) | `#4B4B4B` 344 / `#4C4C4C` 556 / `#4A4A4A` 301 (`01_`), `#4C4C4C` 556 / `#494949` 547 / `#4A4A4A` 496 (`03_`), `#4B4B4B` 936 / `#494949` 926 (`11_`) | **`#4C4C4C`** (range `#444444`–`#585858`) | glyph-core mode, `bands.py text` |
| H1 title ink | `#141414` (`13_page-1.jpg`), `#131313` (`03_page-01.jpg`) | **`#141414`** | darkest-12 % modal |
| brand navy — headings, numbered header, sign-off | `#0E2278`, `#162A69`, `#1F3276`, `#213769`, `#1B3870`, `#1D2A4A`, `#1D2856`, `#20276B`, `#192C6E`, `#083169`, `#193576` | **`#1B3870`** (range `#083169`–`#2A395A`) | middle-row modal / darkest-12 % modal |
| navy rule / divider | `#2E3458`, `#313B56`, `#29395A`, `#2A395A`, `#213769`, `#1B396D`, `#293474` | **`#2E3458`** | per-row darkest modal, 97 % share of 611 dark px (`01_page-7.jpg` y=859) |
| slate navy — card border | `#20314B` (59.9 % of darkest px), `#233355` (47 %), `#1B334B`, `#223158`, `#203246` | **`#20314B`** | `cardinfo.py` + `rowprofile.py` (`03_page-17.jpg` y=86–92 / y=519–525) |
| card body text (CN) | `#1B334B` repeated over 4 consecutive bands, 50 % share each | **`#1B334B`** | `rowprofile.py` (`03_page-17.jpg`, `03_page-01.jpg`) |
| light blue divider (list separators) | `#EEEEEE` (3 px), `#E6E6E6` (3 px), `#EDEDED`, `#F3F3F3` | **`#EEEEEE`** | band census, `13_page-4.jpg` y = 332–334 |
| metal/grey caption | `#818181`, `#A6A6A6`, `#A8A8A8`, `#ABABAB`, `#B2B2B2` | **`#818181`** (TOC eyebrow) / **`#A8A8A8`** (eyebrows) | darkest-12 % modal |
| rose / magenta accent | `#83395E`, `#84365E`, `#852451`, `#B4789A` | **`#84365E`** (range `#83395E`–`#B4789A`) | 94 % of 166 dark px, `06_page-1.jpg` y = 821 (`时间 Time` pill outline); `01_page-2.jpg` placeholder frame at x = 146–154 |
| teal accent (AcademiaSphere/学域 family) | `#006BA1` (6 px rule), `#0065A3` (6 px rule), `#05699D`, `#0C6796`, `#216083`, `#2D5A71`, `#325771` | **`#006BA1`** | band census, `05_page-1.jpg` y = 589–594 and y = 867–872, x = 130–717 |
| orange accent (article 04 bands) | `#E98A52` (13 px), `#E38853` (13 px), `#F48655` (13 px), `#ED8454` (13 px) | **`#E98A52`** | band census, `04_page-02.jpg` y = 39–51, x = 150–731 |
| orange — box border + CAPS text | border `#CD9064` (3 px, 96 % share), `#C3936D`, `#C2926C`; text `#A65516` | **`#CD9064`** border / **`#A65516`** text | `rowprofile.py` `11_page-02.jpg` y = 351–353 (x = 175–675) and y = 373–399 |
| campaign yellow (08/09/10, 05) | `#FFEE8A` 457,593 px, `#FFF0AF` 386,654, `#FEE566` 356,453, `#FFF9CB` 322,467, `#FFF4B4` 135,418, `#FCCD03` (68 px band) | **`#FFEE8A`** poster fill / **`#FCCD03`** solid band | corpus census + band census `05_page-1.jpg` y = 407–474 |
| campaign orange (08/09/10 headings) | `#F9A221` 18,663 px (`09_`), 16,245 px (`10_`) | **`#F9A221`** | ink census per article |
| red accent (article 07) | `#F44E42` (94 % of 574 dark px), `#D4594A` | **`#F44E42`** | `rowprofile.py` `07_page-1.jpg` y = 1043, x = 134–719, 6 px thick |
| blue accent (article 07 card border) | `#139DE5` (97 % of 561 dark px), `#0E9EE5`, `#00A1EF` | **`#139DE5`** | `rowprofile.py` `07_page-1.jpg` y = 572, x = 137–719, 5 px thick |
| pale blue decorative | `#BEE3FD` 91,412 px (`12_`), `#FEAEB1` 35,624 px (`12_`) | **`#BEE3FD`** | corpus census |
| AcademicSphere lavender/blue ink (`16_`) | `#486489` 527, `#496897` 526, `#899CC6` 464 | **`#496897`** | glyph-core mode (`bands.py text` `16_`) |
| card border (light blue-gray, `16_`) | top `#DFE4EA`, left `#ECF4FF` | **`#DFE4EA`** | `cardinfo.py` `16_page-4.jpg` x = 148–704 y = 690–780 |

**Glossary of the two navies (do not merge them):** the *royal* navy `#1B3870`-family
(`#083169`–`#2A395A`) is used for **text and rules**; the *slate* navy `#20314B`-family
(`#1B334B`–`#233355`) is used for **1 px card borders**. A renderer that uses one navy for both
will look wrong: the measured separation is ~30 units of blue channel at equal darkness.

---

## G. Reusable layout blocks (component specs)

Order = order of appearance. "w" values are at the 850 px page width; multiply by 0.96 for CSS px.

### G1 `wechat_header` — H1 + byline

```
[ H1 ]  x0 = 114–123, band h = 22–27, bold, #141414, flush left
[ byline ] x0 = 123, band h = 12–19, regular, #7F7F7F; text = "Original 国际教育中心
           哈工大深圳校区国际教育中心 <Mon D, YYYY, H:MM AM/PM> 广东"
```
Colours: `#141414`, `#7F7F7F`. Sample: `01_page01_cover_h1_banner_poster.jpg`.

### G2 `cover_art` — full-bleed raster banner

Image only. Full content width (624 px), height varies (300–1000 px measured). Carries the
`公众号 · 哈工大深圳校区国际教育中心` watermark bottom-right. Samples:
`01_page01_cover_h1_banner_poster.jpg`, `03_page-01.jpg`, `11_page-01.jpg`, `15_page-1.jpg`.

### G3 `lead_paragraph` — CN block then EN block

```
CN paragraph:  font-size 15, line-height 1.6, colour #4C4C4C, flush left, no indent,
               paragraph gap 32 px (one blank line)
EN paragraph:  same, colour #4E4E4E
```
Sample: `03_page-04.jpg` (body x = 128–727).

### G4 `card` — navy bordered text card (lead / closing)

```
outer box      w = 584–585, border 1 px  #20314B (top #20314B, bottom #233355)
corner radius  0 (square; top border starts at offset 1 px)
fill           none (#FFFFFF)
padding        ~8 px vertical, ~0 horizontal (interior text x = 134 ≈ border x = 133 + 1)
content        optional CAPS eyebrow (h = 11, #A8A8A8, letter-spaced)
               CN body  #1B334B
               EN body  #4E4E4E
optional rule  h = 4 px navy #1B344D near the bottom + footer "HSIYC · 2026"
```
Samples: `03_page17_navy_card_closing_signoff_credits.jpg`,
`03_page04_numbered_station_header_bilingual_stack.jpg`.

### G5 `numbered_section_header` ★

```
group width    280 px, centred on x = 427 (page centre 425)
line 1         "01"  heavy, left of the label, 2–3× label cap height
line 2         "<SERIES> | <中文题目>"     bold, #0E2278
line 3         "<English Title>"          bold-italic, #162A69
rule A         4–6 px navy #213769, full group width
rule B         2 px navy #2A395A, full group width, 2 px below rule A
line 4         "<Sub-label>"              bold-italic, 16 px band, #20276B
```
Samples: `sample_pages/11_page02_numbered_section_header_double_rule_orange_box.jpg`
(= `11_国际青年俱乐部___APEC智慧校园创新系列竞赛/page-02.jpg`),
`sample_pages/15_page02_section_header_bilingual_ENoverCN.jpg`
(= `15_国际青年俱乐部___活动回顾_APEC智慧校园创新系列/page-2.jpg`).

### G6 `numbered_row_header` (station variant)

```
"NN"            light #9F9F9F, x0 = 146
hairline rule   h = 1 px, #293241, x = 138–428 (291 px)  [not full width]
right label     "Day N · <Country>"  navy #303E4B, right-aligned, ends x = 719
```
Sample: `03_page04_numbered_station_header_bilingual_stack.jpg`.

### G7 `bilingual_section_heading`

Two legal orders — **pick per article family, do not mix**:
* CN-above-EN (8/17 articles): line 1–2 CN bold navy `#1B3049`, line 3 EN bold italic, centred.
* EN-above-CN (article 15): line 1 EN bold navy `#193576` h = 26, line 2 CN `#083169` h = 28,
  **left-aligned** at x = 160.

Samples: `15_page02_section_header_bilingual_ENoverCN.jpg`, `03_page04_...jpg`.

### G8 `full_bleed_photo`

```
width   624 px (= 599 CSS px), x = 112–735
aspect  measured 1.46:1 (624 × 427)
border  none, radius 0, caption none measured
```
Sample: `13_page01_fullwidth_photo_numbered_list.jpg`.

### G9 `photo_carousel_strip` (with slide hint)

```
frame      x = 140–704 (565 px), h = 365 px, aspect 1.55:1
border     1 px, light blue-gray #7883A5 (rendered from a navy hairline), radius 8–11 px
fill       #FFFFFF
hint       "slide right for more pictures", 9 px band, #3F426B, centred ON the bottom border,
           border interrupted behind it
tiles      0 measured (images failed to render in the export)
```
Sample: `15_page08_photo_carousel_slide_hint_double_rule_signoff.jpg`.

### G10 `numbered_list` (link/index rows)

```
row band     h = 15–16 px, row pitch 56 px, x = 136–665
prefix       "01 " / "02 " / "03 " bold, then "<中文> | <English>"
trailing     small "‹" chevron flush right at x ≈ 660
separator    light grey hairline ≈ #EEEEEE (3 px measured), between rows
```
Sample: `13_page01_fullwidth_photo_numbered_list.jpg`.

### G11 `rounded_card_stack` (AcademiaSphere/学域 series)

```
outer box      x = 148–704 (557 px), h = 84–91 px per card
border         1 px, #DFE4EA (light blue-gray)
corner radius  ≈ 7–8 px (top border starts at offset 7 px)
gap            21 px between cards (cards at y = 690–780, 796–879, 904–987)
content        "第N讲 | Lecture N"  (h = 16)
               CN line  (h = 16)
               EN line  (h = 16)
```
Sample: `16_page04_rounded_card_stack_placeholder.jpg`.

### G12 `double_border_card` (article 07 family — different sub-brand)

```
red rule     6 px  #F44E42, x = 134–719
blue rule    5 px  #139DE5, x = 137–719
card body    x = 136–719, interior #FFFFFF
header tab   navy tab overlapping the card's top edge with a red underline (07_page-1.jpg y = 570)
```
Sample: `07_page-2.jpg`.

### G13 `pill_badge` (article 06/17 family)

```
outline   2–4 px rose #84365E (94 % of 166 dark px at y = 821)
shape     fully rounded (radius = h/2)
content   "时间 Time" / "地点 Location" / "活动 ACTIVITIES" — CN then EN, inline, one line
```
Sample: `06_page-1.jpg`.

### G14 `signoff_block`

```
rule above   double: 7 px #1B3870 + 3 px #313B56   (or single 1 px #2E3458 in 01_)
width        624 px, x = 112–735
line 1       "哈工大（深圳）国际青年俱乐部"  h = 16, centred, #1F3276  (03_: #3E3E3E)
line 2       "HITSZ International Youth Club"  h = 16, centred, #1D2A4A
line 3       "AcademiaSphere" | "AcademiaSphere x Nexus Hive"  h = 16, centred, #1D2856
pitch        24 px
rule below   double: 6 px #1B396D + 2 px #29395A
```
Sample: `01_page07_signoff_rules_credit_block.jpg`,
`15_page08_photo_carousel_slide_hint_double_rule_signoff.jpg`.

### G15 `credits_block`

```
6 rows, flush left x = 136, pitch 25 px, band 11–16 px, colour #4A4A4A–#585858
"文字 | …", "图片 | …", "排版 | …", "一审 | …", "二审 | …", "三审 | …"
```
Sample: `01_page07_signoff_rules_credit_block.jpg`, `03_page17_...jpg`.

### G16 `toc_card`

```
eyebrow   "精彩回顾 · Table of Contents" | "活动资讯 · Table of Contents"
          band h = 12, #818181, x = 137
heads     "Previous" (left, x = 147)  "Next" (right, x ≈ 703)   band h = 9, #1E1E1E, bold
titles    band h = 18, #373737, max 2 lines; left col left-aligned, right col right-aligned
box       NONE (no border, no fill)
trailer   "修改于<YYYY年M月D日>" grey, optional
```
Sample: `01_page08_toc_card_previous_next.jpg`.

---

## H. Grading rubric — what makes an article read as "on-brand HSIYC"

Weight = share of the brand signal I could attribute from the measurements; scores are
1–10 per marker, and the weighted total is the predicted committee-approval score.

| # | marker | weight | what full marks requires (measured) |
|---|---|---|---|
| 1 | **Correct footer furniture** — bilingual sign-off + rules + 6-row credit block | **20 %** | `哈工大（深圳）国际青年俱乐部` / `HITSZ International Youth Club` centred in navy `#1F3276`/`#1D2A4A`, 16 px band, 24 px pitch, with navy rules (ideally double, `#1B3870`+`#313B56`) above and below spanning 624 px; credit rows `文字\|图片\|排版\|一审\|二审\|三审` flush left at x = 136, pitch 25 px. Missing sign-off = 0. |
| 2 | **`精彩回顾/活动资讯 · Table of Contents` with `Previous` / `Next`** | **15 %** | eyebrow `#818181` 12 px band; `Previous` left / `Next` right, `#1E1E1E` bold; unboxed; link titles ≤2 lines, `#373737`. |
| 3 | **Whiteness discipline** | **14 %** | page must be ≈88 % `#FFFFFF`; no page background tint, no card fill; colour only via thin rules/borders/headings. |
| 4 | **Body typography** — 15 px / 1.6, `#4C4C4C`, block paragraphs, no indent | **13 %** | line pitch 24 px, in-paragraph gap 8 px, paragraph gap 32 px, every line flush left at a single measure (583 px wide). |
| 5 | **Bilingual pairing rule** — every CN block has an EN twin (and vice-versa) | **12 %** | CN and EN paragraphs alternate as separate blocks; inside a card CN = navy `#1B334B`, EN = grey `#4E4E4E`. |
| 6 | **Numbered/section header grammar** | **10 %** | either the B1 banner header (280 px group, `01` + CN label + italic EN label + 4–6 px/2 px navy double rule + italic sub-label) or the B2 row header (light `#9F9F9F` numeral + 1 px `#293241` hairline 291 px + right-aligned `Day N · Country`), followed by a centred bilingual stack. |
| 7 | **Header title + meta line format** | **8 %** | H1 `[系列] | [标题]` bold `#141414`, band 22–27 px; byline `Original 国际教育中心 … 广东` grey. |
| 8 | **Photo policy** — at most one full-bleed image per section, images bleed 22 px past the text measure | **8 %** | image width exactly 624 px (x = 112–735), no border/radius/caption; if a carousel is used, frame 565 × 365 with radius 8–11 px and the hint `slide right for more pictures` (`#3F426B`, 9 px band) centred on the bottom border. |

**Scoring:** total = Σ(weight × score/10). A page scoring ≥ 8.5 reproduces every measured
regularity; ≤ 6 means at least one of markers 1–4 is wrong, which in this corpus is what
distinguishes the 2025-era articles (`08_`–`10_`, `07_`, `06_`) from the current house style
(`01_`, `03_`, `11_`, `13_`, `15_`, `17_`).

**Marker-by-marker measured citations (all five markers 1–5 verified against real pages):**

| marker | page images the score is checked against |
|---|---|
| 1 footer furniture | `03_page-17.jpg` (6-row credits, near-black sign-off), `15_page-8.jpg` (double rules + navy sign-off), `01_page-7.jpg` (single 1 px rules + `AcademiaSphere x Nexus Hive`), `08_page-29.jpg` (credits with no sign-off → marker 1 = 0) |
| 2 TOC card | `03_page-18.jpg`, `01_page-8.jpg`, `13_page-7.jpg` (`精彩回顾`), `02_page-6.jpg`, `04_page-10.jpg`, `11_page-18.jpg` (`活动资讯`), `05_page-9.jpg` (`Next`-only degraded case) |
| 3 whiteness discipline | corpus census (88.624 % `#FFFFFF`), `03_page-01.jpg` (card interior 66 % white), `15_page-8.jpg` (carousel interior 100 % white) |
| 4 body typography | `03_page-04.jpg` (pitch 24, gap 8/32, x0 = 128), `11_page-02.jpg` (x0 = 168, pitch 24), `15_page-2.jpg` (box interior x0 = 162) |
| 5 bilingual pairing | `03_page-04.jpg` (CN then EN paragraphs), `03_page-17.jpg` (card: CN `#1B334B` + EN `#4E4E4E`), `15_page-2.jpg` (EN display heading `#193576` + CN `#083169`) |
| 6 section-header grammar | `11_page-02.jpg`, `15_page-2.jpg` (B1 banner header), `03_page-04.jpg`, `03_page-06.jpg` (B2 row header) |
| 7 H1 + byline | `13_page-1.jpg` (h = 27, `#141414`), `03_page-01.jpg` (h = 22), `07_page-1.jpg` (`Study at HITSZ` byline variant) |
| 8 photo policy | `13_page-1.jpg` (624 px full-bleed photo), `15_page-8.jpg` (carousel + hint), `16_page-4.jpg` (broken placeholder → marker 8 penalised) |

---

## I. Inconsistencies in the brand system (findings the committee should be told about)

1. **Two different navies are in active use.** Royal navy `#0E2278`–`#2A395A` for text/rules,
   slate navy `#1B334B`–`#233355` for the 1 px card border (`03_page-17.jpg` y = 86–92 vs
   `11_page-02.jpg` y = 215–257). They are ~30 blue-units apart at equal darkness.
2. **Bilingual stacking order flips.** CN-above-EN in 8/17 articles (`01_`, `02_`, `03_`, `04_`,
   `05_`, `11_`, `13_`, `16_`) but **EN-above-CN** in `15_` (`Preliminary Rounds` / `预赛`,
   `Closing` / `结语`) and in the poster text of `06_`/`17_`. There is no rule.
3. **Credit-block vocabulary has four different versions** (see D.2): `文字/图片/排版/一审/二审/
   三审` (most common), `图文/排版/一审/二审/三审`, `文字/编辑/初审/复审/终审`,
   `文字编辑/图文排版/图文审核`. The separator is sometimes `|` and sometimes `：`.
4. **The TOC eyebrow has two names**: `精彩回顾 · Table of Contents` vs
   `活动资讯 · Table of Contents` (roughly 50/50).
5. **The sign-off third line varies**: `AcademiaSphere x Nexus Hive` (`01_page-7.jpg`,
   `11_page-18.jpg`) vs `AcademiaSphere` (`15_page-8.jpg`) vs absent (`03_page-17.jpg`).
6. **Sub-brand palettes do not share a colour**: teal `#006BA1` (article 05 / 学域),
   orange `#E98A52` (article 04), red `#F44E42` + blue `#139DE5` (article 07),
   yellow `#FFEE8A`/`#F9A221` (08/09/10), rose `#84365E` (06/17), lavender `#496897` (16).
   Only articles 01/03/11/13/15 share the navy system.
7. **Article 08's carousel/photo sections are 26/29 blank pages** and `09_` 14/18, `10_` 8/12 —
   these three articles cannot be used as visual references at all.
8. **`14_`, `16_`, `17_` body text measures `#AAAAAA`–`#B2B2B2`** (mid-animation capture). If a
   future renderer "matches" that grey it will fail accessibility and look nothing like the
   approved originals.
9. **`16_page-4.jpg` and `01_page-2.jpg`…`01_page-6.jpg` carry visibly empty image
   placeholders** — proof that the approved articles ship with broken/omitted images, and that
   the committee tolerates it.
