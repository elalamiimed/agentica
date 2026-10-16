# Why HSIYC articles come back from the youth committee — and what the agent checks

Derived from the 17 approved articles and the contradictions between them
(`_work/analysis/TEXT_PATTERNS.md` §I and §J). Each item is a machine check in
`hsiyc_writer/validate.py`; the check code is given so a reviewer can see exactly
what was verified.

## Blocking errors

| # | Failure | Check |
|---|---|---|
| 1 | **Credit block incomplete or wrong.** A missing role, a placeholder, or the wrong reviewer names. The roster rotates weekly (一审 has 8 distinct name sets, 二审 has 7); the only invariant is 卢锦章 as final approver. | `CREDIT-MISSING`, `CREDIT-PLACEHOLDER` |
| 2 | **A Chinese paragraph with no English twin.** 131/131 CN paragraphs in the corpus are paired. | `BIL-PARAGRAPH` |
| 3 | **A Chinese-only heading.** 0/130 approved headings are Chinese-only. | `BIL-HEADING` |
| 4 | **A missing or malformed sign-off.** Must read exactly 哈工大（深圳）国际青年俱乐部 / HITSZ International Youth Club. | `SIGNOFF-FORM` |
| 5 | **A number in the body that appears in no supplied material.** Invented counts, scores or deadlines. A fact spelled as a word counts: a brief saying "a five-minute integral" whitelists the "5" the article writes, in English *or* Chinese numerals. | `FACT-NUMBER` |
| 6 | **A name filed under the wrong prize.** Knowing a winner's name is not enough — putting the champion's name against 亚军, or moving a gold medal to fourth place, is the error most likely to be returned, because the winner reads it. Compared against the brief's ranked winners list. | `FACT-RANK` |
| 7 | **A "fact" with no source**, or one sourced from a previous article rather than this event. | `FACT-UNSOURCED`, `FACT-CORPUS-LEAK` |
| 8 | **A photo placed that was never uploaded** (a broken image reference). | `PHOTO-UNKNOWN` |
| 9 | **Fewer than 3 sections**, or an empty section. | `STRUCT-SECTIONS`, `STRUCT-EMPTY` |
| 10 | **An unknown block kind** — a structural typo the renderer cannot draw. | `SCHEMA-KIND` |
| 11 | **A missing title / lead / closing / sign-off / credits block.** | `STRUCT-MISSING` |

## Warnings that reviewers do notice

| # | Failure | Check |
|---|---|---|
| 11 | **CN/EN fact drift.** EN may compress but must add no fact; the corpus itself fails this in places, so it is graded rather than blocked. | `FACT-DATE-MISMATCH`, `BIL-RATIO` |
| 12 | **An unpaired rank title** — 冠军 in CN with no "Champion" in EN. | `RANK-PAIR` |
| 13 | **Half-width punctuation inside Chinese copy** (`,` `;` `?` `!` `:` `(` `)`) or a straight quote. | `FORMAT-HALFWIDTH`, `FORMAT-QUOTE` |
| 14 | **Chinese characters or Chinese punctuation inside an English field.** | `FORMAT-CJK-IN-EN`, `FORMAT-CN-PUNCT-IN-EN` |
| 15 | **Article too short.** Approved articles run 305–2,261 CN body characters (median 860). | `LEN-SHORT`, `LEN-LONG` |
| 16 | **The same photo used twice**, or an uploaded photo never placed. | `PHOTO-DUPLICATE`, `PHOTO-UNUSED` |
| 17 | **Phrasing lifted wholesale from another approved article.** Character-bigram overlap against the corpus catches copy-paste between events. | `SIMILARITY` |
| 18 | **The 特别感谢 block without its "Special Thanks" counterpart.** | `BIL-THANKS` |
| 19 | **An incomplete TOC card** (no previous/next). | `TOC-MISSING` |
| 20 | **The headline missing the club name or the `｜` separator.** | `HEAD-FORMULA` |
| 21 | **No acknowledgement anywhere.** Approved articles thank participants, judges or partners. | `TONE-THANKS` |
| 22 | **A 预告/招募 that never uses the APEC / 亚太 framing.** | `TYPE-FRAMING` |
| 23 | **A wrong-phase verb** — a preview saying 圆满落幕, or a recap saying 即将启幕. | `TYPE-PHASE` |

## Deliberately NOT checked (the reviewers tolerate these)

Inventing errors here would reject articles the committee has already approved:

* **Credit separators.** `,` / `，` / `、` / space are all approved, and 7 of 12 blocks mix them
  inside one block. Only the role labels and the exact name strings are checked.
* **Bilingual heading order.** CN-above-EN and EN-above-CN both appear in the corpus, even for the
  same heading pair. The generator picks one and stays consistent.
* **Ranking vocabulary.** `冠军/亚军/季军` and `第一名/第二名/第三名` both appear — inside a single
  approved article, even.
* **Bilingual label position, TOC heading wording** (精彩回顾 vs 活动资讯), **2-line vs 3-line
  sign-off**, **`slide right` vs 左右滑动查看更多**, **`特别感谢` vs `鸣谢`**.
* **Spacing around Latin/numerals in CN text.** The corpus is loose here (`APEC 智慧校园创新系列`,
  `2026 年 11 月`, `A509教室` all approved). The generator avoids odd spacing; the validator does not
  flag it.
* **Soft typography.** First-line indent vs block paragraphs is fixed by the renderer, not graded.

## The rule that matters most

Everything a reviewer can check against the real world — a name, a number, a date, a venue, an
award title, a reviewer name — must come from the brief. The agent is instructed to omit rather
than invent, and to list what is missing under `needs_editor` so a human fills it in before 送审.
