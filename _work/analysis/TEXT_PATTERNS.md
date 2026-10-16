# HSIYC approved-article TEXT PATTERN report

Mined from the 17 approved PDFs' plain-text extractions in `_work\*.txt` (`pdftotext -enc UTF-8 -layout`).
Companion machine file: `_work\analysis\article_index.json` (17 objects, validated with the bundled Python).

**Read this first — what the numbers are measured over.**

| Quantity | Definition used everywhere below |
|---|---|
| **denominator "17"** | all 17 extracted `.txt` files |
| **denominator "13"** | the 13 files with a usable body: body ≥ 300 CJK chars. Excluded: #7, #8, #10 (body never extracted — pages are imagery) and #12 (only 9 text lines) |
| **body slice** | text between the WeChat stamp line (`… 广东` / `Study at HITSZ …`) and the first credit-role line (`文字 \|` / `文字：` / `文字编辑：`). WeChat header, credits, TOC and footer are therefore excluded |
| **CN char** | CJK ideograph only: `U+3400–4DBF, U+4E00–9FFF, U+F900–FAFF`. Punctuation, digits and Latin letters are **not** counted |
| **EN word** | token matching `[A-Za-z][A-Za-z'’-]*` after de-spacing letter-spaced runs (`T h e` → `The`). The raw token count is also recorded in the JSON (`source_en_word_count`) |
| **section / heading** | a heading pair of the article body (hand-curated per file, listed in §D and in the JSON `sections`) |

Corpus totals actually computed: **14,177 CJK chars** and **7,633 de-spaced EN word tokens** in the 17 files as a whole; **12,599 CJK chars** inside the 17 body slices.

### Canonical file IDs used in this report

| # | file (in `_work\`) | type | series |
|---|---|---|---|
| 1 | `APEC青年讲堂___讲座回顾_游戏化思维_从玩家到赢家.txt` | 回顾 | APEC青年讲堂 |
| 2 | `APEC青年讲堂___讲座预告_游戏化思维_从玩家到赢家.txt` | 预告 | APEC青年讲堂 |
| 3 | `APEC青年说___世界传统手艺体验周完美收官.txt` | 收官 | APEC青年说 |
| 4 | `APEC青年说___文化绘卷_7天游6国_世界传统手艺体验周.txt` | 预告 | APEC青年说 |
| 5 | `_码_上进步_智汇寒冬_Code_Your_Way_Forward.txt` | 招募 | 学域 AcademiaSphere |
| 6 | `哈工大_深圳_国际青年俱乐部_HSIYC_诚邀您共赴2026_无界校园_青春共行_深圳大学城社团游园会.txt` | 预告 | 游园会 |
| 7 | `哈工大_深圳_首届国际文化嘉年华11月8日即将启幕_上_.txt` | 预告 | 国际文化嘉年华 |
| 8 | `哈工大_深圳_首届国际文化嘉年华11月8日即将启幕_下_.txt` | 预告 | 国际文化嘉年华 |
| 9 | `哈工大_深圳_首届国际文化嘉年华_International_Cultural_Carnival___活动摊位与节目招募启动_.txt` | 招募 | 国际文化嘉年华 |
| 10 | `哈工大_深圳_首届国际文化嘉年华节目预告.txt` | 预告 | 国际文化嘉年华 |
| 11 | `国际青年俱乐部___APEC智慧校园创新系列竞赛.txt` | 竞赛 | APEC智慧校园创新系列 |
| 12 | `国际青年俱乐部___以乐会友_以言知音_三校中英文音乐交流之夜圆满举行.txt` | 回顾 | 国际青年俱乐部 |
| 13 | `国际青年俱乐部___国际学子鹏海模联2026斩获三项大奖.txt` | 回顾 | 鹏海模联 |
| 14 | `国际青年俱乐部___学业支持_学生心声_同伴之间.txt` | 其他 | 学域 AcademiaSphere |
| 15 | `国际青年俱乐部___活动回顾_APEC智慧校园创新系列.txt` | 回顾 | APEC智慧校园创新系列 |
| 16 | `国际青年俱乐部_国际交流协会_哈尔滨工业大学_深圳_第一届模拟联合国科普讲堂圆满落幕.txt` | 回顾 | 模联 (× 国际交流协会) |
| 17 | `国际青年俱乐部_无界青春_社团游园会圆满收官.txt` | 收官 | 游园会 |

Type census: 预告 6 (#2,4,6,7,8,10), 回顾 5 (#1,12,13,15,16), 收官 2 (#3,17), 招募 2 (#5,9), 竞赛 1 (#11), 其他 1 (#14).
Classification rule used: phase marker in the title/hero wins (`预告/即将启幕/诚邀` → 预告; `招募/征集` → 招募; `回顾/举行/落幕/斩获` → 回顾; `收官/圆满收官` → 收官); a rules-and-registration post for a competition → 竞赛; a non-event feature → 其他. The enum's `讲堂` label is not needed under this rule because both 讲堂 posts are phase-marked — the series is recorded separately in the JSON `series` field.

**Extraction caveat that applies to every aggregate.** 4 of 17 files (#7, #8, #10, #12) have no extractable body although their PDFs have 29, 18, 12 and 7 page images respectively. Their body-derived numbers are 0 **by construction**. Consequence for the generator's spec: any "typical article" statistic must be quoted over the 13 usable files, and #12 is the one article whose credit block cannot be verified at all.

---

## A. Document skeleton — the literal block order

Counted occurrences of each block across the 17 files:

| # | block | present in | notes |
|---|---|---|---|
| 1 | WeChat repost stamp (screenshot header): title line + `Original   国际教育中心 哈工大深圳校区国际教育中心 <Mon D, YYYY, h:MM AM/PM> 广东` | 17/17 (3 stamp variants) | `Original` prefix in 10/17; 3 files (#5, #6, #17) have the account name without `Original`; 4 files (#7, #8, #9, #10) are the **Study at HITSZ** account |
| 2 | hero / cover block (club banner, EN kicker, big CN title, EN subtitle, monogram) | 13/13 with body | #7, #8 unknown; #10 hero is EN-only |
| 3 | kicker + explicit dateline line (`活动回顾 · Event Recap` / `June 15, 2026 · HITSZ`) | **1/13** (#1 only) | everywhere else the date is inside the first sentence, not on its own line |
| 4 | CN lede (1–2 paragraphs) | 13/13 | always first |
| 5 | EN lede (1–2 paragraphs) mirroring the CN lede | 13/13 | always second |
| 6 | body sections (bilingual headings + CN paragraph(s) + EN paragraph(s), image groups flagged by `slide right for more pictures` / `左右滑动查看更多`) | 13/13 | 130 headings total, §D |
| 7 | closing / CTA section described in §B | 13/13 (wording differs) | |
| 8 | acknowledgement micro-block (`Special Thanks / 特别感谢`, `鸣谢 / Acknowledgments`) | 3/17 (#5, #11, #15) | |
| 9 | closing club-name block (2 or 3 lines) | 10/17 in some form, only 8/17 in the canonical form | §E.4 — this is **not** mandatory |
| 10 | credit block | 16/17 extractable | §F; #12 missing |
| 11 | `精彩回顾 · Table of Contents` / `活动资讯 · Table of Contents` navigation block with `Previous`/`Next` neighbour titles | 13/17 | 9× `精彩回顾`, 4× `活动资讯`; absent in #7, #8, #9, #10; #5 has `Next` only |
| 12 | WeChat footer `修改于YYYY年M月D日` | 2/17 (#15, #17) | #17's stamp also carries `标题已修改` |

Literal order for a canonical club article (#15, verified line by line): title → stamp → APEC framing lede (CN) → EN mirror → per-competition numbered hero → bilingual H2 sections with ranking lists and `slide right` hints → `Closing / 结语` → `slide right` → 3-line club block → credits → TOC → `修改于2026年7月21日`.

---

## B. Headline conventions

### B.1 Title formulas (17/17 are CN-only WeChat titles, except #5)

| formula | files | literal examples |
|---|---|---|
| `<栏目> \| <类型>：<主题>` (ASCII pipe, full-width colon) | #1, #2, #11, #12, #13, #14 | `APEC青年讲堂 \| 讲座回顾：游戏化思维——从玩家到赢家` (#1); `国际青年俱乐部 \| 活动回顾：APEC智慧校园创新系列` (#15) |
| `<栏目> \| <主题><结局词>` | #3, #17 | `APEC青年说 \| 世界传统手艺体验周完美收官` (#3); `国际青年俱乐部 ｜无界青春：社团游园会圆满收官` (#17 — note the **full-width ｜**, unique in the corpus) |
| `<主体>诚邀您共赴<时间><主题>` (invitation) | #6 | `哈工大（深圳）国际青年俱乐部（HSIYC）诚邀您共赴2026“无界校园·青春共行”深圳大学城社团游园会` |
| `<活动>……即将启幕（上/下）` | #7, #8 | `哈工大（深圳）首届国际文化嘉年华11月8日即将启幕（上）` |
| `<活动><类型词>` | #9, #10 | `哈工大（深圳）首届国际文化嘉年华 International Cultural Carnival \| 活动摊位与节目招募启动！`; `…节目预告` |
| `<活动> × <合作方>｜<结果>` (full-width ×, full-width ｜) | #16 | `国际青年俱乐部 × 国际交流协会｜哈尔滨工业大学（深圳）第一届模拟联合国科普讲堂圆满落幕` |
| `<CN slogan> <EN slogan>` on one title line | #5 | `“码”上进步·智汇寒冬 Code Your Way Forward` |

Event-type vocabulary actually used: 预告 (2 titles), 即将启幕 (2), 诚邀…共赴 (1), 招募启动 (1), 回顾 (2), 圆满收官 (2), 完美收官 (1), 圆满举行 (1), 圆满落幕 (1), 斩获三项大奖 (1), 竞赛 (1), 文化绘卷 (1), 无界青春 (1). **13 of 17 titles carry an explicit phase word** (#1,#2,#3,#6,#7,#8,#9,#10,#12,#13,#15,#16,#17); the four that don't are #4, #5, #11, #14.

### B.2 English headline: exists in only 9/17 — and never as the WeChat title

`headline_en` is non-empty in 9 files, but in every case it is the **hero/cover English line inside the page**, not the WeChat title: `Seven Days · Six Countries · One Journey` (#3), `PENGHAI MUN 2026 / 鹏海模联2026` (#13), `MUN BOOT CAMP` (#16), `A Joyful Closing.` (#17), `Student Voices` (#14), `Code Your Way Forward` (#5), `One Campus, Every Corner of the World.` (#6), `Harmony in Diversity, A World in Symphony / HITSZ First International Cultural Carnival / Program List Preview` (#10, EN-only hero), `Harmony in Diversity, A World in Symphony.` (#9). So the WeChat title itself is CN-only in **16/17** files (#5 is the sole CN+EN title line).

### B.3 Preview vs recap

| | 预告 / 招募 / 竞赛 (9 files: #2,4,5,6,7,8,9,10,11) | 回顾 / 收官 (7 files: #1,3,12,13,15,16,17) |
|---|---|---|
| first CN sentence | future + reason: `近日，哈工大（深圳）国际青年俱乐部（HSIYC）正式推出“APEC智慧校园创新系列”…灵感来自2026年11月深圳承办APEC峰会。` (#11); `为什么游戏让人上瘾，而学习却让人疲惫？` (#2) | past + result: `2026年4月26日，“无界校园·青春共行”深圳大学城社团游园会在欢声笑语中圆满落幕。` (#17); `2026年7月19日至21日，第二届鹏海模拟联合国大会在深圳北理莫斯科大学（SMBU）成功举办。` (#13) |
| tense/grammar | imperative + future (`请扫描下方二维码`, `Register early`, `快来加入我们`) | perfective + past (`圆满落幕`, `成功举办`, `收获了`, `claimed their prizes`) |
| required closing | logistics or CTA: deadline + QR/group + `席位有限，先到先得` / `名额限制：仅限80人` | thanks + forward promise: `感谢每一位…` + `期待与大家在下一次相遇中` |
| hard numbers | times, venue, capacity, eligibility, prize list, submission rules, email, URL | counts of participants/winners, ranks, names, judge/professor names |
| **counter-example** | — | **#15 opens like a preview**: `2026 年 11 月，深圳将迎来 APEC 峰会…以此为灵感，推出“APEC 智慧校园创新系列”`, and only in paragraph 2 says `如今三场赛事圆满落幕，让我们一同回顾这段旅程。` A recap may therefore open with the why/APEC framing as long as it lands the "it happened" move in the lede. |

---

## C. The bilingual protocol

**C.1 It is section-by-section, and always CN-then-EN inside a section.** In all 13 text-complete files the pattern is: CN heading → EN heading (or one heading line carrying both) → CN paragraph(s) → EN paragraph(s). **0/13** articles place a full CN body before a full EN body, and **0/13** place the EN paragraph before its CN counterpart. The EN paragraph is a *parallel* rendering of the same section, not a continuation: it can shorten or re-word, but it occupies the same slot.

Verified examples of the invariant slot order (CN then EN):
- #15: `预赛 / Preliminary Rounds` → CN `预赛采用快节奏的 1v1 赛制…` → EN `The preliminary rounds followed a blitz 1v1 format…`
- #17: `2026年4月26日，“无界校园·青春共行”深圳大学城社团游园会在欢声笑语中圆满落幕。…` → `On April 26, 2026, the "Boundless Campus, Youth Together" Shenzhen University Town Club Carnival came to a joyful close.…`

**C.2 Every one of the 130 headings carries English; 127/130 carry Chinese.** Breakdown of the 130 curated heading pairs:

| heading form | count | examples (source) |
|---|---|---|
| stacked pair, CN line + EN line (or EN line + CN line) — recorded as `heading_cn` + `heading_en` | **98/130** | `游戏，究竟是什么？` / `WHAT IS A GAME?` (#1); `讲座简介` / `Why This Lecture?` (#2); `课堂之内` / `Inside the Room` (#14); `01 亮相鹏海` / `Represent` (#13) |
| single heading line containing both languages, no separator or with `\|`/`｜`/`·` | **29/130** | `时间 Time`, `地点 Location`, `活动 ACTIVITIES`, `✦ 万语留声 Voices of the World ✦` (#6); `PRIZES \| 奖项` (#11, ×3); `参赛要求 \| Submission` (#11); `第一讲 ｜ Lecture 1` (#16, ×3); `Day 1: 中国 \| China` (#4, ×6); `特别嘉宾 · Special Guest` (#3); `关键节点 · Key Dates` (#16); `Fuel Your Studies 为学习充能` (#5) |
| EN-only heading | **3/130** | `Room A: The Focus Zone`, `Room B: The Collaboration Hub`, `The Strongest Node Program` (all #5) |
| CN-only heading with no English at all | **0/130** | — |

**Rule for the generator: no heading may be Chinese-only.** The 3 EN-only headings are all in one article (#5) and are all "programme-structure" labels; every other heading has an English component.

**C.3 Where English appears alone.** (a) #5's three EN-only headings; (b) #10's whole hero (`Harmony in Diversity, A World in Symphony / HITSZ First International Cultural Carnival / Program List Preview` — no CN counterpart, body not extracted); (c) the `slide right for more pictures` hint line; (d) the `Table of Contents`, `Previous`, `Next` navigation block; (e) WeChat stamp/footer; (f) labels inside artwork (`HITSZ Youth Club` #1, `CULTURAL JOURNEY` #3, `PENGHAI MUN 2026` #13, `MUN BOOT CAMP` #16, `END` #16). **No body paragraph is ever English-only** — every EN paragraph has a CN sibling in the same section (13/13).

**C.4 CN:EN length ratio** (body slices; CN characters ÷ EN words, so the unit is "CN chars per EN word"):

| set | n | mean | median | min | max |
|---|---|---|---|---|---|
| 13 text-complete articles | 13 | **1.727** | **1.788** | **1.184** (#9) | **2.263** (#4) |
| all 17 (0-body files included) | 17 | 3.323 | 1.976 | 0.0 | 10.6 |

Practical band for a generated article: **1.2–2.3 CN chars per EN word** (median ≈ 1.8). Expressed the other way: EN text runs roughly **45–85 %** of the CN text's information volume word-for-word. Per-article values are in `article_index.json` (`cn_en_ratio`). Caveat: #4's EN is letter-spaced in the PDF text layer, so its ratio is an estimate (raw token count 1547 vs 543 de-spaced); #9 is the most CN-heavy (1.184) because its info card is CN with short EN labels.

---

## D. Section rhythm

| metric | value | denominator |
|---|---|---|
| headings per article | min **4** (#14, #17), max **24** (#11), median **11**, mean **10.0** | 13 text-complete files |
| CN body paragraph blocks (blank-line-separated block ≥20 CJK chars and ≥50 % CJK) | **131** blocks total; **10.1** per text-bearing file; per file: #11 27, #5 23, #14 20, #4 13, #15 10, #2 9, #1 8, #3 8, #16 7, #13 4, #9 1, #12 1 | 17 files / 13 |
| CN chars per block | mean **70.4**, median **62**, p10 **28**, p90 **130**, max **250** | 131 blocks |
| bilingual sub-headings per section | every section, no exception (see C) | 130 headings |
| `slide right for more pictures` / `左右滑动查看更多` hints | **11** in **5/17** files | 17 |

Rough generator targets: **8–13 sections**, **8–15 CN paragraphs**, **50–130 CN chars per paragraph** (short 30-char paragraphs are normal in lead-in/payoff positions), and at least **one image hint** after every 2–4 paragraphs in illustrated sections.

**D.1 Numbered headers.** Five different numbering systems are in use, and they are not interchangeable:
- `01 / 02 / 03` + `|` — the APEC series competition blocks: `01 APEC | 未来技能挑战赛` (#15, #11) and the mini-TOC `01 亮相鹏海 | Represent` (#13); six day-badges `01`–`06` (#3).
- `1. 2. 3.` — procedural lists: `1.招募要求` / `2.报名方式` / `2.节目类型` / `3.报名方式` (#9), `1. 活动概览` / `2. 活动现场` (#16), `1.文化礼仪守则` / `2.诚信出席守则` (#4).
- `环节一 / 环节二 / 环节三` + `SESSION 1/2/3` and nested `第一讲 / 第二讲 / 第三讲` (#16).
- `一、二、三` CN numbering with `1. 2. 3.` EN numbering inside the same compliance block (#11 `内容规范` / `Content Guidelines`, repeated twice).
- `①②③④` for lecture-content bullets, CN and EN both (#2 `讲座内容` / `Lecture Contents`).

**D.2 The literal bilingual heading pair inventory** (all 130 are in `article_index.json`; the recurring/idiomatic ones an LLM should reuse verbatim): `讲座简介 / Why This Lecture?`, `嘉宾简介 / Why Her?`, `讲座信息 / Lecture Details`, `讲座内容 / Lecture Contents`, `活动安排 / Event Schedule`, `赛制与规则 / Format & Rules`, `参赛资格 / Eligibility`, `参赛要求 / Submission`, `评审标准 / JUDING CRITERIA` (sic — the approved spelling), `内容规范 / Content Guidelines`, `PRIZES | 奖项`, `鸣谢 / Acknowledgments`, `会议详情 / Event Highlights`, `获奖代表 / Award Winners`, `组织代表 / Organising Delegates`, `结语 / Closing`, `特别感谢 / Special Thanks`, `预赛 / Preliminary Rounds`, `决赛 / Final Rounds`, `课堂之内 / Inside the Room`, `展望未来 / Moving Forward`, `更多精彩，敬请期待 / Looking Ahead: More to Come`, `1. 活动概览 / Event Overview`, `环节二：模联实战模拟训练 / SESSION 2 : Hands-On MUN Simulation Training`, `展位互动 / AT OUR BOOTH`, `幸运抽奖 / LUCKY DRAW`, `文化交流 / CULTURAL EXCHANGE`.

---

## E. Mandatory recurring micro-blocks

**E.1 Counted presence (denominator 17):**

| micro-block | files | count |
|---|---|---|
| `slide right for more pictures` (8 occurrences) | #13, #15 (×5), #16 (×2) | 3 files |
| `左右滑动查看更多` (3 occurrences) | #14, #17 (×2) | 2 files |
| winner/ranking list | #5, #13, #15 | 3 files |
| acknowledgement section (`Special Thanks`/`特别感谢`/`鸣谢`/`Acknowledgments`) | #5, #11, #15 | 3 files |
| `Table of Contents` navigation block | #1,2,3,4,5,6,11,12,13,14,15,16,17 | 13 files |
| closing club-name block in any form | #1,2,3,4,6,11,13,14,15,17 | 10 files |
| legal line `本文最终解释权归…` (CN + EN) | #11 (contiguous), #5 (letter-spaced in the text layer) | 2 files |

Conclusion for the spec: **the only near-mandatory structural blocks are the CN+EN lede pair, the bilingual section body, the credit block and (in 13/17) the TOC navigation block.** The `slide right` hint, the ranking list, the acknowledgement section and even the closing club-name block are optional and event-dependent — a validator that hard-requires them will reject valid articles.

**E.2 Winner / ranking lists — three distinct shapes, all approved.**
- Ranking-by-title (competition 1 of #15): `冠军：Tugsuu Rentsennatsag` / `亚军：Brandon Mantovanni Yunata` / `季军：谢昊轩 Xie Haoxuan` / `第四名：Emil Aliyev` — one per line, space after `：`, no blank lines.
- Ranking-by-number (competitions 2 and 3 of the same article #15): `第一名：Muntaha Fayez`, `第二名：Abrar Shahriar Mahtab`, `第三名：Ganerdene Tuguldur` (blank lines between in one block, contiguous in the other), and `第一名：Nadine Leanora Eddy` / `第二名：Sahir Malak` / `第三名：Sinthia Zahedi Reedi`.
- Award-card (MUN, #13): CN tier + EN tier above a `Country representative / Delegate of X - Name` line: `最佳代表 / Best Delegate` → `孟加拉国代表 / Delegate of Bangladesh - Abrar Mahtab`; `杰出代表 / Outstanding Delegate` → `巴基斯坦代表 / Delegate of Pakistan - Nazir Nayab`; `最具潜力奖 / Best Potential` → `西班牙代表 / Delegate of Spain - Mohammed Mazen`.
- Prize-tier list (#5, MINISO rewards): `第一名： MINISO 智能主动降噪耳机 + MINISO 精选助学礼包 + 荣誉证书` (note the space after `：` here, unlike #15).

**E.3 Acknowledgement section — two literal forms.** `Special Thanks` / `特别感谢` as a stacked heading pair, followed by a CN sentence then an EN sentence (#15: `衷心感谢凌怡老师在决赛中担任裁判，并在筹备期间给予我们宝贵的指导和建议。` / `We would like to express our sincere gratitude to Professor Ling for judging the finals…`); or `鸣谢` / `Acknowledgments` with the partner institution named underneath (#11: `鸣谢 / 国际教育中心 / Acknowledgments / International Education Center`; #5: `特别感谢国际教育中心的悉心指导与信息学部的大力支持，使本项目得以顺利开展。`).

**E.4 Closing club-name block — five variants, not one.**
- 3-line with a collaboration line: `哈工大（深圳）国际青年俱乐部` / `HITSZ International Youth Club` / `AcademiaSphere x Nexus Hive` (#1, #11); `… / AcademiaSphere` (#15).
- 2-line (most common): #2, #3, #6, #13, #17.
- Stacked logo text `HITSZ / INTERNATIONAL / YOUTH / CLUB / (HSIYC)` (#4).
- Letter-spaced one-liner `H I T S Z I n t e r n a t i o n a l Yo u t h C l u b` (#14).
- Absent: #5 (signs off `学域 · AcademiaSphere`), #16 (signs off with a mission statement `国际青年俱乐部与国际交流协会，将始终与每一位热爱模联、心怀世界的同学同行。` + `END` badge), #9, #7, #8, #10, #12.
So the canonical 3-line string block appears in only **3/17** files.

**E.5 The `Table of Contents` navigation block — 13/17, two heading variants and a broken one.**
- Heading `精彩回顾 · Table of Contents` (9 files: #1,3,5,12,13,14,15,16,17) vs `活动资讯 · Table of Contents` (4 files: #2,4,6,11).
- Body: a `Previous` and a `Next` column, each holding another article's title, e.g. #15: `Previous  Global Lens | 从零基础到X9联赛：校区首支在深国际学生赛艇队的成长故事` / `Next  Global Lens | 特辑：国际学生优秀作品展播①`.
- **#5 deviates**: its block has only `Next · 感知中国实践活动 | 2026年“湾区艺旅”寒假冬令营圆满收官` (no `Previous`).

**E.6 Other recurring micro-blocks** (all optional, event-type driven): registration/logistics card (`时间：6月15日 12:30 - 13:30` / `地点：A509` #2, #11), `报名截止时间` + capacity, QR-code line (`Registration QR Code:` #11, `扫码加入 Cache Hub 学习社区` #5), `温馨提醒：礼品数量有限，欢迎提早到场！/ Heads up: Prizes are limited Arrive Early!` (#6), email contact (`iyc.hitsz@outlook.com` #11, #5; `isc@hit.edu.cn` #9), external links (`https://mp.weixin.qq.com/s/...`, `https://www.alipan.com/s/k7sjwpmtMnm`, `https://docs.qq.com/form/page/...`), the date-table `关键节点 · Key Dates` (#16), the compliance block (#11), the `END` badge (#16), and the WeChat footer `修改于2026年7月21日` / `修改于2026年5月27日` (#15, #17).

---

## F. The credit-block schema — exhaustive quotation of all 16 extractable blocks

**16 of 17 files have a credit block; #12 has none in the extraction** (7 page images, 9 text lines — nothing can be asserted about its reviewers).

### F.1 Every literal instance

**#1 `APEC青年讲堂___讲座回顾…`** (club schema, 6 roles)
```
文字 | Zhumabay Aruzhan, Yalalt
图片 | Yalalt, Najmia, Kavindya, Imasha
排版 | Zhumabay Aruzhan
一审 | 柯炽炜，Samin，Yalalt
二审 | 周宣彤，崔雨旸，高容驷
三审 | 卢锦章
```
**#2 `APEC青年讲堂___讲座预告…`**
```
图文 | Yalalt
排版 | Yalalt
一审 | Samin, 柯炽炜
二审 | 周宣彤，崔雨旸，高容驷
三审 | 卢锦章
```
**#3 `APEC青年说___世界传统手艺体验周完美收官`**
```
文字 | Zhumabay Aruzhan
图片 | Tanvir, Fatima, Samira, Nadine, Samin, Rane, Douae, Kelvin, Hafsa, Baiel, Al-Azhari, Saputra
排版 | Zhumabay Aruzhan
一审 | 柯炽炜、Samin、Ahmed（韩沐）
二审 | 周宣彤、崔雨旸、高容驷
三审 | 卢锦章
```
**#4 `APEC青年说___文化绘卷…`** — `图片` is letter-spaced in the text layer (`图 片 | S a y k a t , S a n j i d a , …`); read as:
```
文字 | Samin
图片 | Saykat, Sanjida, Azaliia, Karen, Younes, NurDoolot
排版 | Samin
一审 | 柯炽炜
二审 | 周宣彤、高容驷、崔雨旸
三审 | 卢锦章
```
**#5 `_码_上进步_智汇寒冬_Code_Your_Way_Forward`**
```
图文 | Yalalt
排版 | Yalalt
一审 | 柯炽炜
二审 | 高容驷
三审 | 卢锦章
```
**#6 `…诚邀您共赴2026“无界校园·青春共行”…`** (space-separated lists, and a swapped 三审)
```
图文 | Samin, Yalalt
排版 | Yalalt
一审 | Samin
二审 | 柯炽炜 崔雨旸
三审 | 周宣彤 卢锦章
```
**#7 `…即将启幕_上_.txt` and #8 `…即将启幕_下_.txt`** (Study at HITSZ schema, 5 roles, `：`)
```
文字：周珺童
编辑：许诺言
初审：周宣彤 崔雨旸
复审：吴潇 高容驷
终审：卢锦章
```
**#9 `…活动摊位与节目招募启动_.txt`** (third schema, 3 merged roles, `：`)
```
文字编辑：周宣彤
图文排版：周宣彤
图文审核：高容驷、卢锦章
```
**#10 `…节目预告.txt`** (Study at HITSZ schema, different 初审)
```
文字：王羲茜
编辑：许诺言
初审：周宣彤 冯洋
复审：吴潇 高容驷
终审：卢锦章
```
**#11 `国际青年俱乐部___APEC智慧校园创新系列竞赛`**
```
图文 | Yalalt
排版 | Yalalt
一审 | Samin, 柯炽炜
二审 | 周宣彤，崔雨旸，高容驷
三审 | 卢锦章
```
**#13 `…鹏海模联2026斩获三项大奖`**
```
文字 | Zhumabay Aruzhan
图片 | Yalalt
排版 | Zhumabay Aruzhan
一审 | Samin、柯炽炜
二审 | 周宣彤、崔雨旸、高容驷
三审 | 卢锦章
```
**#14 `…学业支持_学生心声_同伴之间`** (label typo `文子`)
```
文子 | Yalalt
排版 | Yalalt
一审 | Samin, 柯炽炜
二审 | 周宣彤，崔雨旸，高容驷
三审 | 卢锦章
```
**#15 `国际青年俱乐部___活动回顾_APEC智慧校园创新系列`**
```
文字 | Zhumabay Aruzhan, Yalalt
图片 | Najmia Popal, Ferraa Ahmed
排版 | Zhumabay Aruzhan, Yalalt
一审 | Samin、柯炽炜
二审 | 周宣彤、崔雨旸、高容驷
三审 | 卢锦章
```
**#16 `…第一届模拟联合国科普讲堂圆满落幕`**
```
文字 | Zhumabay Aruzhan
图片 | Aziz Fatima、Gohar Ahmed Nader、Galal Mohammed、凌平 等
排版 | Zhumabay Aruzhan
一审 | Samin、柯炽炜
二审 | 周宣彤、崔雨旸、高容驷
三审 | 卢锦章
```
**#17 `…无界青春_社团游园会圆满收官`** (only block with a `视频` role)
```
文字 | Samin, Yalalt
图片 | Adnan, Ferraa, Munkh-Orshikh, Kanan
视频 | Alen, Adnan, Elvira, Zakaria
排版 | Yalalt
一审 | Samin, 柯炽炜
二审 | 周宣彤，崔雨旸
三审 | 卢锦章
```

### F.2 How many names per role (CJK-aware split: split on `、，,` and on spaces only when every fragment is pure CJK)

| role | files with the role | min | median | max | distribution |
|---|---|---|---|---|---|
| 一审 (incl. 初审) | 15 | 1 | 2 | 3 | 3 names ×2 (#1, #3); 2 names ×10; 1 name ×3 (#4, #5, #6) |
| 二审 (incl. 复审) | 15 | 1 | 3 | 3 | 3 ×9; 2 ×5; 1 ×1 (#5) |
| 三审 (incl. 终审) | 15 | 1 | 1 | 2 | 1 name ×14; 2 names ×1 (#6 `周宣彤 卢锦章`) |
| 文字 / 图文 / 文字编辑 | 16 (all except #12) | 1 | 1 | 2 | `Zhumabay Aruzhan` ×5, `Yalalt` (文字 or 图文) ×5, `Samin` ×3, `周珺童` ×2, `王羲茜` ×1, `周宣彤` (文字编辑) ×1, #6 `Samin, Yalalt` ×1, #1/#15 `Zhumabay Aruzhan, Yalalt` ×2 |
| 图片 / 视频 | 7 | 1 | 4 | 12 | #3 lists 12 photographers; #16 lists 4 + `等`; #17 adds a 4-name 视频 line |
| 排版 | 13 | 1 | 1 | 2 | `Yalalt` ×7, `Zhumabay Aruzhan` ×5, `Samin` ×1 (#4), `周宣彤` (图文排版) ×1 (#9), #15 lists 2 |

**Role membership counts (how many files contain the person):**
- 一审: 柯炽炜 11, Samin 10, 周宣彤 3, 崔雨旸 2, Yalalt 1, Ahmed（韩沐） 1, 冯洋 1.
- 二审: 高容驷 13, 崔雨旸 11, 周宣彤 10, 吴潇 3, 柯炽炜 1.
- 三审: **卢锦章 16/16 extractable files** (14× under 三审, 1× as `三审 | 周宣彤 卢锦章` in #6, 1× inside #9's merged `图文审核：高容驷、卢锦章`), 周宣彤 1 (only #6).
- 排版 is not a distinct person: it is always one of the article's own writers/photographers (Yalalt, Zhumabay Aruzhan, Samin, or 周宣彤).
- Self-review is normal: #1's 一审 includes Yalalt who is also 文字/图片; #6's 一审 is Samin who is also 图文; #9's 文字编辑 and 图文排版 are both 周宣彤.

### F.3 Separators — there is no single house style

Separator characters observed **inside the same 6-line block**: ASCII `, ` (8 blocks: #1,2,3,6,11,14,15,17), full-width `，` (5: #1,2,11,14,17), `、` (5: #3,4,13,15,16), and plain space used as the list separator (4: #6 `柯炽炜 崔雨旸`, plus the Study-at-HITSZ blocks #7, #8, #10). Counting only `,`/`，`/`、`, **7 of the 12 club-schema blocks mix two or more separator characters**. Compare #11 `一审 | Samin, 柯炽炜` + `二审 | 周宣彤，崔雨旸，高容驷` (ASCII comma on one line, full-width comma on the next) with #4's pure `二审 | 周宣彤、高容驷、崔雨旸` and #6's space-only `二审 | 柯炽炜 崔雨旸`. **A validator must not require a consistent separator; it must require the exact role labels and the exact name strings.**

### F.4 Normalisation key for `article_index.json`

| JSON field | literal labels folded into it |
|---|---|
| `credits.文字` | `文字 \|`, `文子 \|` (typo, #14), `文字：` (#7, #8, #10) |
| `credits.图片` | `图片 \|`, `图 片 \|` (#4) |
| `credits.排版` | `排版 \|`, `图文排版：` (#9) |
| `credits.一审` | `一审 \|`, `初审：` (#7, #8, #10) |
| `credits.二审` | `二审 \|`, `复审：` (#7, #8, #10) |
| `credits.三审` | `三审 \|`, `终审：` (#7, #8, #10) |
| `credits_extra_roles` | `图文` (merged writer+photo role, #2, #5, #6, #11 — left out of 文字/图片 so no information is invented), `视频` (#17), `编辑` (#7, #8, #10), `文字编辑`/`图文排版`/`图文审核` (#9) |

`credits_schema` values: `club_pipe` 12 files, `study_at_hitsz_colon` 3 (#7, #8, #10), `carnival_colon` 1 (#9), `not_extracted` 1 (#12).

---

## G. Chinese style rules an LLM must obey

Built from counted usage over the 17 body slices (counts are literal character counts, not per-file):

1. **Full-width punctuation for Chinese.** `，` 402, `。` 234, `、` 141, `：` 122, `！` 38, `？` 15, `；` 15, `（` 87 / `）` 86, `《` 5 / `》` 5, `“` 43 / `”` 41. No space is placed before or after a full-width mark.
2. **`、` is only for enumerations** (name lists, item lists: `柯炽炜、Samin、Ahmed（韩沐）`, `积分、徽章、排行榜`); clause-level separation uses `，`. Both appear in the same paragraph routinely.
3. **Corner brackets `「」` are almost unused — 3 occurrences in the whole corpus**, and each quotes a slogan or concept: `「无界校园 · 青春共行」` (#6 hero), `「学生心声 · 同伴之间」` (#14 body), `「合作」` (#15 body). Default to `“”` (43 pairs) inside CN prose; `《》` is for titles of works/programmes (`《国际人机交互期刊》` #2, `《麦地那寻宝》` #3/#4, `《科科什尼克传奇：俄罗斯手工艺》` #4).
4. **ASCII `"` inside a CN sentence is tolerated** but not the norm: `随机"内存"补给` (#5), `本次模拟议题为"人工智能与教育：机遇还是挑战？——学生在使用ChatGPT等AI工具时，学校该如何担起责任"` (#16). Prefer `“”`.
5. **Numerals are Arabic everywhere** for dates, times, counts, scores, years. Chinese numerals `一、二、三` appear only as list markers in the compliance block (#11 `内容规范`: `一、所有作品须严格遵守国家法律法规…`). No percent signs are used anywhere.
6. **Date / time formats actually approved** (all inconsistent with each other, so pick the first form and stay consistent): `2026年11月`; `2026年7月19日至21日` (#13); `8月19日至21日` and `8月19–21日` (en dash, #16); `6月20日（周六）10:00` (#11); `2026年4月26日（周日）18:00-21:30` (#6); `5月19日 下午 6:00 前` (#4); `23:59，6月21日` (#11); `16:00 - 19:00` (#9) vs `18:00-21:30` (#6) — spaces around the hyphen are inconsistent; EN side: `June 26, 23:59` (#1), `From July 19–21, 2026` (#13), `May 5th 2025` (#14, no comma) vs `November 11th, 2025` (#14, comma).
7. **Spacing around Latin/numerals in CN text is loose, not rule-governed.** Norm is no space (`A509教室`, `6月15日 12:30 - 13:30` inside a box, `HSIYC）`), but approved text contains `迎来了 哈工大（深圳）` (#1), `APEC 智慧校园创新系列` (#15), `2026 年 11 月` (#15, spaces around 年/月). Do **not** let a validator flag these; do let the generator avoid them.
8. **Official-name usage:** `哈工大（深圳）` 24 occurrences is the body default; `哈尔滨工业大学（深圳）` 12 occurrences for formal/first/legal mention; `HITSZ` 54; `HSIYC` 40; `HITSZ International Youth Club` 18; `国际教育中心` 28; `AcademiaSphere` 18 / `学域` 10; `HSICA` 4 / `国际交流协会`; `Nexus Hive` 2. The full legal string `哈尔滨工业大学（深圳）国际青年俱乐部（HSIYC）` appears in #11's legal line, #14 and #16; the short form `哈工大（深圳）国际青年俱乐部（HSIYC）` is used in #5 and #15. One approved typo: `HSYIC · 2026` (#3, line 33).
9. **People's names.** International names stay in Western order and are not transliterated: `Zhumabay Aruzhan`, `Najmia Popal`, `Ferraa Ahmed`, `Samin`, `Yalalt`, `Abrar Shahriar Mahtab`, `Tugsuu Rentsennatsag`, `Brandon Mantovanni Yunata`, `Muntaha Fayez`, `Nadine Leanora Eddy`, `Sahir Malak`, `Sinthia Zahedi Reedi`, `Nazir Nayab`, `Mohammed Mazen`, `Abu Obayda Pathan Rezen`, `Enkhtur Yalalt`, `Emil Aliyev`, `Ganerdene Tuguldur`, `Purevdorj`, `Assiya`, `Kenneth`, `Samira`, `Brijesh`, `Jinny`, `Alysh`, `Alfred`, `Tanvir`, `Kelvin`.
   Chinese names appear in CN characters; the EN romanisation is surname-first and appears only where the CN name is also given: `季军：谢昊轩 Xie Haoxuan` (#15) is the corpus's only CN-name+Latin pair. A name that is given in both scripts may also be glossed in parentheses: `Ahmed（韩沐）` (#3).
   Student attributions use nationality + year + name with no space before the name: `—— 蒙古籍大二学生Purevdorj` / `— Purevdorj, Sophomore from Mongolia` (#14).
   Academic titles are loose: the same person is `副教授陈阳老师`, `陈教授` (#1) and `陈阳博士` (#2), EN `Dr. Yang Chen`; `凌怡老师` (#15) becomes `Professor Ling` with a male pronoun `his invaluable guidance`; `黄红宇老师` is `她` in CN and `Professor Huang Hongyu` in EN (#3).
10. **Tense.** CN recaps use perfective/result verbs (`圆满落幕`, `成功举办`, `斩获`, `获得了`, `收获了`) plus present-tense commentary in the closing; previews use future/imperative (`即将启幕`, `将获得`, `请扫描`, `快来加入`, `Register early`). EN mirrors this (past simple for recaps, present/imperative for previews). Never mix a recap's past tense with a preview's imperative in the same article.
11. **Person and address.** Institutional voice: first person plural `我们` for the club, second person `你/大家/同学们` when addressing readers, and `HSIYC`/`国际青年俱乐部` in the third person in the lede. First-person singular does not occur in the corpus.

---

## H. Fact-density profile (what a generated article MUST contain rather than invent)

Counted per article over the body slice:

| # | type | Arabic-digit tokens | `N月N日` dates | year mentions | clock times | org/product-name hits |
|---|---|---|---|---|---|---|
| 1 | 回顾 | 24 | 2 | 1 | 2 | 23 |
| 2 | 预告 | 20 | 2 | 2 | 4 | 5 |
| 3 | 收官 | 36 | 6 | 5 | 0 | 13 |
| 4 | 预告 | 85 | 7 | 0 | 26 | 5 |
| 5 | 招募 | 24 | 3 | 0 | 0 | 36 |
| 6 | 预告 | 15 | 1 | 2 | 4 | 12 |
| 7 | 预告 | 0 | 0 | 0 | 0 | 0 |
| 8 | 预告 | 0 | 0 | 0 | 0 | 0 |
| 9 | 招募 | 30 | 2 | 2 | 4 | 5 |
| 10 | 预告 | 0 | 0 | 0 | 0 | 1 |
| 11 | 竞赛 | 101 | 5 | 2 | 12 | 54 |
| 12 | 回顾 | 1 | 0 | 0 | 0 | 1 |
| 13 | 回顾 | 22 | 1 | 5 | 0 | 11 |
| 14 | 其他 | 27 | 5 | 10 | 0 | 14 |
| 15 | 回顾 | 21 | 0 | 2 | 0 | 27 |
| 16 | 回顾 | 42 | 5 | 7 | 0 | 63 |
| 17 | 收官 | 7 | 1 | 2 | 1 | 24 |

Corpus totals: **455 Arabic-digit tokens** and **40 `N月N日` date expressions** in the 17 body slices. Over the 13 text-complete files the medians are 24 digit tokens and 2 dates; the shortest complete article (#6, 305 CN chars) still carries 15 digit tokens, 1 date, a time range and a booth number.

**Fact categories that recur and must be sourced from the brief, never invented:**
- dates and times (40 date expressions; 12/13 complete articles contain at least one `N月N日`; **#15 has none** — it only says `2026 年 11 月`, so a date is not literally mandatory);
- venue (`A509` #1/#2/#11; `哈工大（深圳）主楼H栋前广场` #9; `深圳大学城国际会议中心东侧` #6; `深圳北理莫斯科大学（SMBU）` #13/#16; `香港中文大学（深圳）` #16);
- people with roles (judge `凌怡老师` #15; speaker `哈尔滨工业大学（深圳）未来设计学院副教授陈阳老师` #1/#2; guest `人文艺术学系教授黄红宇老师` #3; 15 student delegates #13; 40+ attendees #16);
- counts (`32 名参赛者`, `4 位精英选手`, `5 道高难度积分题`, `每题限时 5 分钟`, `12位选手`, `12套方案`, `21个经济体`, `80人` capacity, `3-5 张图像`, `≤5分钟` video, `≤2页` document);
- winners and awards with exact spellings (see E.2);
- partners and sponsors (`国际教育中心`, `共青团哈尔滨工业大学（深圳）委员会`, `研究生会`, `信息学部`, `团委`, `国际事务处`, `国际交流协会（HSICA）`, `鹏海模联组委会`, `CUHK MUN Club`, `AcademiaSphere`, `Nexus Hive`, `MINISO`, `UNESCO`, `MIT`);
- contacts and links (`iyc.hitsz@outlook.com`, `isc@hit.edu.cn`, `https://mp.weixin.qq.com/s/…`, `https://www.alipan.com/s/k7sjwpmtMnm`, `https://docs.qq.com/form/page/…`).

Reality check on the "invent nothing" rule: the corpus itself contradicts itself on two hard numbers — the gamification-competition deadline is `23:59，6月21日` (#11) but `6月26日 23:59` (#1); and the same delegate is `Abrar Mahtab` (#13) and `Abrar Shahriar Mahtab` (#15). Numbers, names and deadlines must therefore come from the brief, and the brief must be checked against any earlier post about the same event.

---

## I. Known-brittle areas (everything a generator can plausibly get wrong)

**I.1 Names and spellings** — the corpus's own slips: `HSYIC · 2026` (#3, should be HSIYC); `文子 | Yalalt` (#14, should be 文字); `Abrar Mahtab` (#13) vs `Abrar Shahriar Mahtab` (#15); `副秘书⻓` (#13, CJK radical glyph instead of 长); `科科什尼克传说` (#3) vs `可可什尼克传说` (#4); `WOLRD ON STAGE` (#17). Chinese-name romanisation is surname-first (`Xie Haoxuan`) — easy to invert.

**I.2 CN/EN fact drift** — the highest-value brittle area, because the corpus proves reviewers accept it but a validator can still catch it: #3 CN `人文艺术学系教授黄红宇老师` vs EN `Professor Huang Hongyu from the School of Future Studies`; #13 CN lists three topics (`1923鲁尔危机、明金辽东之战及COP30气候大会`) while EN lists two (`ranging from the 1923 Ruhr Crisis to COP30`); #1 CN `联合主办的 APEC青年讲座系列` loses `联合` in EN; #14's CN captions omit the course names that the EN captions add (`2025年5月5日由Yalalt主讲的辅导课` vs `May 5th 2025 Electric Circuits II by Yalalt - First Tutor Class Under AcademiaSphere`); #15 EN `the four finalists have claimed their prizes` where CN lists four ranks. **Rule: EN may compress, but every fact in EN must exist in CN.**

**I.3 Title/naming drift inside one series** — `APEC Canvas of Culture` (#3 hero) vs `APEC Canvas of Cultures` (#4 and #3's own closing paragraph); `The Medina Quest: A Moroccan Journey` (#3) vs `The Medina Quest: A Moroccan Cultural Journey` (#4); prize vocabulary `冠军/亚军/季军` (#11 rules post) vs `第一名/第二名/第三名` (#15 recap of the same competitions).

**I.4 Tense and event phase** — a recap that slips into `即将`/`请报名`, or a preview that says `圆满落幕`. The corpus's own trap: #15 (a recap) opens with a future framing.

**I.5 Wrong reviewer names / wrong credit schema** — the single most likely hard rejection. Only `卢锦章` is stable (16/16 as the final approver); 一审/二审 vary from 1 to 3 names and #6 swaps 周宣彤 into 三审. A generator must copy the credit block from the brief, not from the last article. Getting the label wrong (`文字` vs `图文`, `一审` vs `初审`) is also visible: 4 different label sets exist.

**I.6 Missing EN for a whole section or heading** — 0/130 headings are CN-only, so any Chinese-only heading is a deviation; likewise a section whose EN paragraph is dropped breaks the CN→EN pairing that holds 13/13.

**I.7 Numbers that must not be rounded or reused** — `32` competitors, `4` finalists, `5` integrals, `5` minutes, `12` systems, `40+` attendees, `80` seats, `15` delegates, `21` economies, `3-5` images, `≤5`/`≤2` limits. Converting `3-5` to `3至5`, or `40+` to `四十余`, changes house style.

**I.8 Glyph-level traps** — ASCII `|` vs full-width `｜` (title formulas use ASCII `|`, while #17's and #16's titles use full-width `｜`); `x` vs `×` in collaboration lines (`AcademiaSphere x Nexus Hive` #1/#11 vs `国际青年俱乐部 × 国际交流协会` #16); `·` vs `・` in kickers (`活动回顾 · Event Recap`); `–` vs `-` in ranges; `（HSIYC)` mixing a full-width open with an ASCII close (#1); `2026年11月` vs `2026 年 11 月` (#15).

**I.9 Quotes and brackets** — `“”` vs `"` vs `「」` (all three occur), `《》` for titles, `【】` only in #9's info cards, `[ ]` only in the club banner of #6/#17.

**I.10 The corpus's extraction artefacts, which must NOT be copied into prose** — letter-spaced runs (`图 片`, `本 文 最 终 解 释 权 归`, `H I T S Z I n t e r n a t i o n a l Yo u t h C l u b`, `IIInnnfffooorrrmmmaaatttiiiooonnn`, `Wa n t t o…`), duplicated hero lines (#14 lines 7-8, 14-15, 19-20), the split number in #17 (`年4月26日，` with `2026` on the next line), and the `▂▂` decoration glyphs in #13.

---

## J. Contradictions between approved articles (do not smooth these over)

1. **Three incompatible credit schemas coexist.** Club `文字/图片/排版 + 一审/二审/三审` with `|` (12 files); Study at HITSZ `文字/编辑/初审/复审/终审` with `：` (3 files: #7, #8, #10); carnival `文字编辑/图文排版/图文审核` with `：` (1 file: #9). Even inside the club schema, `图文` replaces `文字`+`图片` in 5 files and #17 adds `视频`.
2. **The reviewer roster is not stable.** 一审 has 8 distinct values (1–3 names), 二审 has 7 (1–3 names). The same slot is filled by different people in different weeks: #6 `二审 | 柯炽炜 崔雨旸` vs #17 (same event, 2 weeks later) `二审 | 周宣彤，崔雨旸`; #6 `三审 | 周宣彤 卢锦章` vs every other file `三审 | 卢锦章`. Only `卢锦章` as final approver is invariant (16/16).
3. **Separator style is not a rule.** 7 of the 12 club blocks mix ASCII comma with `、` or `，` inside the same block (#6 additionally uses a bare space: `二审 | 柯炽炜 崔雨斸`); #4 is pure `、`; #5 has no separators because every role has one name.
4. **Bilingual heading order flips, even for the same heading pair.** #15 stacks `Preliminary Rounds` above `预赛` and `Closing` above `结语` (EN-first), while #13 stacks `结语` above `Closing` (CN-first) and #11 — the preview of the very same series as #15 — stacks `活动安排` above `Event Schedule` (CN-first). #5 is EN-first (`Phase One: The Cache Hub` / `第一阶段:知识缓存区`); #14 and #16 are CN-first.
5. **Bilingual label position flips.** #11 writes `参赛方向 / COMPETITION TRACKS` (CN line first) but `PRIZES | 奖项` and `APEC | 未来技能挑战赛` (EN-first inside one line); #16 writes `1. 活动概览 / Event Overview` but `SESSION 2 : Hands-On MUN Simulation Training` with a space before the ASCII colon.
6. **The closing club block is not mandatory and has 5 forms** (3-line with `AcademiaSphere x Nexus Hive` / 3-line with `AcademiaSphere` / 2-line / stacked logo / letter-spaced one-liner) and is absent in 7 files, including two that close with something else entirely (#5 signs `学域 · AcademiaSphere`, #16 signs with a mission statement + `END`).
7. **The TOC block is not mandatory either** (13/17) and has two headings (`精彩回顾 · Table of Contents` ×9 vs `活动资讯 · Table of Contents` ×4); #5 has `Next` without `Previous`.
8. **Ranking vocabulary changes inside a single article** (#15: `冠军/亚军/季军/第四名` for competition 1, `第一名/第二名/第三名` for competitions 2 and 3) and across the series posts (`冠军` in #11's prize section vs `第一名：` in #5's MINISO reward list).
9. **CN and EN disagree on facts** (#3 department name; #13 dropped committee topic; #3's `Canvas of Culture` vs `Canvas of Cultures`; #14's captions; #1's dropped `联合`).
10. **The same competition has two different deadlines**: `截止时间：23:59，6月21日` (#11) vs `截止：6月26日 23:59` / `Deadline: June 26, 23:59` (#1).
11. **The same delegate has two spellings**: `Abrar Mahtab` (#13) vs `Abrar Shahriar Mahtab` (#15) — and #13's award card truncates `Nazir Nayab`/`Mohammed Mazen` the same way.
12. **学域 is described differently in two approved articles**: `内设的学业支持部门` (#14) vs `发起的学业支持项目` (#5).
13. **The same speaker is titled differently**: `副教授陈阳老师`/`陈教授` (#1) vs `陈阳博士` (#2), EN `Dr. Yang Chen`.
14. **The event name differs between its preview and its recap**: `APEC Canvas of Culture` (#3 hero) vs `APEC Canvas of Cultures` (#4); `科科什尼克传说` (#3) vs `可可什尼克传说` (#4).
15. **Collaboration glyph differs**: `AcademiaSphere x Nexus Hive` (#1, #11) vs `国际青年俱乐部 × 国际交流协会` (#16).
16. **Publisher/stamp differs**: `Original 国际教育中心 哈工大深圳校区国际教育中心` (10 files) vs `哈工大深圳校区国际教育中心` without `Original` (#5, #6, #17) vs `Study at HITSZ` (4 files); 2 files carry `修改于…`, one also `标题已修改` (#17).
17. **Approved text contains typos** a validator must tolerate but a generator must not emit: `JUDING CRITERIA` ×2 (#11), `all successfull participants` (#11), `WOLRD ON STAGE` (#17), `HSYIC · 2026` (#3), `文子 | Yalalt` (#14), `（HSIYC)` (#1), `In partnerships with` (#13), duplicated heading `讲座信息 / Lecture Details` (#2), duplicated `1.招募要求 / Requirement` (#9).
18. **Contradiction inside the same article about its own section count/numbering**: #16 numbers H2 sections `1.`/`2.` and then numbers sub-blocks `1.`/`2.` again; #11 reuses `评审标准 / JUDING CRITERIA` and `内容规范 / Content Guidelines` verbatim for competitions 2 and 3.
19. **"Seven Days" is contradicted by the programme itself.** #3's hero (`Seven Days · Six Countries · One Journey`) and its EN lede (`Seven days. Six countries. One unforgettable cultural journey.`) claim seven days, and #4's title says `7天游6国` / `7天环游6国`; but #4's own schedule lists six dated sessions — `5月21日`, `5月22日`, `5月23日 (17:00 - 19:00)`, `5月24日`, `5月25日`, `5月27日` — and #3's recap enumerates exactly six stations (中国, 孟加拉国, 摩洛哥, 印度尼西亚, 吉尔吉斯斯坦, 俄罗斯). The approved corpus ships a marketing number that its own body refutes.
20. **Type/title mismatch**: #9's WeChat title and content announce `首届国际文化嘉年华` on 2025-09-29 with an application deadline of `10月14日`, while #7/#8 publish on 2025-11-05 as `11月8日即将启幕` — the same event is written as a 招募 post in September and a 预告 post in November with a completely different publisher account and credit schema.

---

## K. Machine rules distilled for the generator and the validator

**Hard (observed 100 % of the text-complete corpus):**
1. Title in CN, no EN-only title. 2. WeChat stamp line directly under the title. 3. CN lede before its EN mirror. 4. Every heading contains English; the CN heading comes with an EN heading or an inline EN word. 5. Section body order: CN paragraph(s) then EN paragraph(s), pair by pair. 6. Credit block as the last content block before the TOC, with the role labels and names copied from the brief. 7. `卢锦章` in the final-approval role (unless the brief says otherwise). 8. No invented numbers, names, dates or venues.

**Soft (allowed, choose one and stay consistent within the article):**
9. `|` vs `：` in credit labels; `、` vs `，` vs `, ` between names. 10. Stacked vs inline bilingual headings. 11. `冠军/亚军/季军` vs `第一名/第二名/第三名`. 12. TOC heading `精彩回顾` vs `活动资讯`. 13. 2-line vs 3-line closing club block (or none). 14. `slide right for more pictures` vs `左右滑动查看更多`. 15. `Special Thanks/特别感谢` vs `鸣谢/Acknowledgments`.

**Length contract for a new article:** 700–1,400 body CN characters (13 articles: min 305, median 860, max 2,261), 4–24 headings (median 11), 8–15 CN paragraphs of 30–130 characters, EN at 1.2–2.3 CN chars per EN word, and 15–45 Arabic-digit facts of which 1–7 are dates.
