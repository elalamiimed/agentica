# HSIYC approved-article style spec

Distilled from the 17 approved articles in this repository (`_work/analysis/TEXT_PATTERNS.md`,
which is the full evidence report; this file is the operational summary the generator reads).

Every number below was counted over the corpus. Where articles contradict each other, the
contradiction is recorded rather than smoothed over, because the reviewers clearly tolerate both
forms — and a rule invented out of thin air is worse than no rule.

---

## 1. Document skeleton (literal block order)

```
1. WeChat headline            CN, one line. 国际青年俱乐部 | <类型词>：<主题>
2. Publisher stamp            Original  国际教育中心 哈工大深圳校区国际教育中心 <date> 广东
3. Lead paragraph             CN, then its EN mirror
4. Body sections              repeating: bilingual heading -> CN paragraph(s) -> EN paragraph(s)
5. Closing                    结语 | Closing  (+ optional CN/EN tagline)
6. Sign-off block             哈工大（深圳）国际青年俱乐部 / HITSZ International Youth Club [/ AcademiaSphere]
7. Credit block               文字 | … 图片 | … 排版 | … 一审 | … 二审 | … 三审 | …
8. TOC card                   精彩回顾 · Table of Contents / Previous / Next
```

The credit block is the LAST content block before the TOC card. The sign-off block is not
mandatory (present in some form in 10/17) and the TOC card is not mandatory either (13/17), but
both are safe to include and the credit block is effectively mandatory.

## 2. The bilingual protocol — the single strictest rule

* **Section by section, CN first, then EN.** 13/13 text-complete articles do this. Full-CN-then-
  full-EN appears **0 times**.
* **No heading may be Chinese-only.** 130/130 headings carry English, either stacked (98) or
  inline on one line (29), or English-only (3).
* **Every CN paragraph needs its EN twin.** 131 CN paragraphs, pairs throughout.
* **EN may compress but must add no fact.** This is graded: the corpus itself fails it in places
  (one article's CN lists three MUN topics while its EN lists two). Every fact in EN must exist in CN.
* **CN:EN length ratio: 1.73 mean, 1.79 median, range 1.18–2.26 CN characters per English word.**
  A paragraph far outside that band reads as a translation problem to a reviewer.

## 3. Heading grammar

* Bilingual pairs, stacked or inline. Stacked order flips in the corpus (CN-first in most, EN-first
  in two) — **pick one and stay consistent within the article**. Default to CN above EN.
* Recap articles with distinct sub-events use numbered headers `01`/`02`/`03` with a bilingual
  title block underneath (e.g. `01 Future Skills Challenge / 未来技能挑战赛`).
* Heading vocabulary that recurs: `活动详情 / Event Highlights`, `获奖名单 / Award Winners`,
  `精彩瞬间 / Highlights`, `特别感谢 / Special Thanks`, `结语 / Closing`, `活动安排 / Event Schedule`,
  `活动概览 / Event Overview`, `报名方式 / How to Register`, `评审标准 / Judging Criteria`.
* ALL CAPS is used only for small English eyebrows, never for headings.

## 4. Body rhythm

| Metric | Corpus value |
|---|---|
| Body CN characters | median 860; range 305–2,261 |
| Headings per article | median 11; range 4–24 |
| CN paragraphs | 8–15 typical; mean 70 characters, median 62 (p10 28, p90 130) |
| Arabic-digit facts | median 24; 15–45 for a complete article |
| Dates (`N月N日`) | median 2; 0–7 |

Target for a **new** article: **700–1,400 CN body characters**, 4–10 sections, paragraphs of
30–130 characters. Short is the more common failure: a 300-character article looks unfinished.

## 5. Micro-blocks (all optional — do not treat any as mandatory)

| Block | Frequency | Form |
|---|---|---|
| `slide right for more pictures` | 11× in 5/17 articles | hint under a photo block; CN variant 左右滑动查看更多 |
| Ranking list | 3/17 | `冠军：…` / `第一名：…` |
| `特别感谢 / Special Thanks` | 3/17 | short acknowledgement paragraph |
| TOC card | 13/17 | `精彩回顾 · Table of Contents` (9) or `活动资讯 · Table of Contents` (4) |
| Sign-off block | 10/17 | 2- or 3-line, or absent |

## 6. Credit block — the top rejection risk

Six roles, copied from the brief, never from the previous article:

```
文字 | <writer(s)>
图片 | <photographer(s)>
排版 | <layout>
一审 | <1-3 names>
二审 | <1-3 names>
三审 | <1-2 names>
```

* Only invariant across the corpus: **卢锦章 holds the final approval role** (16/16).
* 一审 has 8 distinct name sets and 二审 has 7 — they rotate weekly. **Never guess these.**
* Separators are deliberately inconsistent: ASCII `,` in 8 blocks, `，` in 5, `、` in 5, bare space
  in 4; 7 of 12 club blocks mix two or more separators inside the same block. A validator must
  **not** demand a consistent separator; it must demand the exact role labels and exact name strings.
* Three other schemas exist in the corpus (`文字/编辑/初审/复审/终审`, `文字编辑/图文排版/图文审核`,
  and one `图文` merges writer+photo). Use the club schema unless the brief says otherwise.

## 7. Chinese style rules

1. Full-width punctuation in CN: `，。、：！？；（）“”《》`. No space before or after a full-width mark.
2. `、` is for enumerations only (name lists, item lists); clause separation uses `，`.
3. `“”` is the default quote. `「」` is rare (3 in the whole corpus) and reserved for slogans.
   `《》` for titles of works. Avoid ASCII `"` inside CN prose.
4. Arabic numerals everywhere for dates, times, counts, scores. `一、二、三` only as list markers.
5. Dates: `2026年7月19日至21日`, `8月19日至21日`, `6月20日（周六）10:00`. Pick one form and stay
   consistent. Preserve the brief's exact range style — never convert `3-5` into `3至5`.
6. Official names: `哈工大（深圳）` in body copy, `哈尔滨工业大学（深圳）` for formal/first mention,
   `HITSZ`, `HSIYC`, `HITSZ International Youth Club`, `国际教育中心`, `AcademiaSphere` / `学域`.
7. Spacing around Latin/numerals in CN text is loose in the corpus. Do not add spaces the brief
   did not use; do not let a validator treat this as an error.
8. International names stay in Western order and are NOT transliterated (`Zhumabay Aruzhan`).
   Chinese names appear in CN characters, optionally with surname-first romanisation
   (`谢昊轩 Xie Haoxuan` — surname first, not `Haoxuan Xie`).
9. Tense by article type: recaps use perfective/result verbs (`圆满落幕`, `成功举办`, `斩获`);
   previews and recruitment use future/imperative (`即将启幕`, `请扫描`, `快来加入`). Never mix them.
10. Institutional voice: `我们` for the club, `你/大家/同学们` for readers, third person for HSIYC in
    the lede. First-person singular does not occur.

## 8. Headline formulas

* CN title on the WeChat line, with the club name and a separator:
  `国际青年俱乐部 | <类型>：<主题>` (ASCII `|` is the common form; `｜` and `：`/`：` also appear).
* Type vocabulary: 预告, 招募, 回顾, 收官, 圆满落幕, 斩获, 讲堂, 竞赛.
* A separate English headline exists in only 9/17 and is never the WeChat title.
* English sub-headline belongs in the hero/kicker area, not the title line.

## 9. Photo grammar (see `_work/analysis/VISUAL_PATTERNS.md`)

**There is no multi-photo grid in the approved corpus.** The gutter detector found zero grid
gutters across 188 pages. Approved photo layout is **one full-bleed image per block** (about
624 px wide, ~1.46:1), or a rounded carousel frame with the hint `slide right for more pictures`
centred on its bottom border. Average 2.82 photos per article, range 0–8.

Do not invent 2×2 or 3-up grids — an off-brand grid is a visible style breach.

## 10. Palette and typography (measured, `_work/analysis/design_tokens.json`)

* Page background `#FFFFFF` — 88.6 % of all pixels. **No tinted background, no card fill.**
  Colour is carried by thin rules, 1 px borders and headings.
* Body text `#4C4C4C`; H1 `#141414`; byline `#7F7F7F`.
* Brand navy for text and rules `#1B3870` (range `#083169`–`#2A395A`).
* Card border navy `#20314B` — a **different** navy from the brand one.
* Body typography recipe: 15 px / line-height 1.6 / paragraph gap equal to one blank line /
  flush-left block paragraphs / **no first-line indent**.
* Footer furniture: three centred sign-off lines inside navy rules, then the credit block flush left.

## 11. Fact discipline

Never invent: dates, times, venues, people and their roles, counts, winners and award titles,
partner/sponsor names, links. The corpus proves reviewers will pass an article whose numbers
conflict with an earlier post — which is exactly why the numbers must come from the brief.

Where a fact is missing, omit it and record it under `needs_editor`. A single fabricated name or
score is a guaranteed return.
