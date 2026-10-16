# HSIYC artwork spec

The agent produces a small visual kit for every event, matched to what the event
actually is:

| Asset | Size | Contains text | Used for |
|---|---|---|---|
| `banner.png` | 1600×900 | no | article header, deck background, WeChat article cover |
| `cover.png` | 900×383 | no | WeChat cover at the ratio the app crops to anyway (2.35:1) |
| `poster.png` | 1240×1754 | yes | A4 poster for print or a group post |
| `social.png` | 1080×1080 | yes | WeChat moments / group chat card |
| `divider-01.png` … | 1600×260 | no | one band per section, for decks and layouts |
| `manifest.json` | — | — | what was made, why, and by which backend |

They land in `output/<slug>/art/`. `manifest.json` records the palette, the
motif, the prompt, and — for anything generated online — the model, seed and URL
that produced it. The poster and social card also print the event's highlights
(up to four short items from the brief) when the operator supplied them: a poster
that says what actually happened is worth posting, one with a headline alone is
not.

## How a picture is built

Every asset family draws through one engine (`_motif_panel` in `art/local.py`),
so a change to the look lands everywhere at once:

1. a gradient background with atmospheric cloud, two colour washes and a vignette;
2. an optional frame circle;
3. the motif, **scaled to fill its target box** rather than to a nominal box;
4. a **grounding shadow**, offset downward;
5. foreground dust — specks, a light beam, and a dim disc bleeding off an edge;
6. film grain.

Three of those steps exist because of a specific failure:

* **Scaling to fit.** Motifs use their box very inconsistently — lanterns hang
  from the top, confetti fills everything, a globe is a circle in the middle.
  Composing by box alone either cropped the tall ones or left the small ones
  floating in dead space. `_fit_subject` measures what was actually drawn
  (ignoring anything below alpha 48, so faint rays do not dominate the bounds)
  and scales it to fill, which also means a newly added motif cannot be added
  badly. It is used for the framed poster/social panel, and *not* for the wide
  strips: there the fit bounds swallow decorative scatter like confetti and
  shrink the real subject, so banner and cover draw straight into a generous box
  sized from the short edge and are allowed to bleed.
* **The offset shadow.** Motifs are translucent. A blur sitting directly behind
  them shows through and muddies the fill — the lanterns turned into hollow
  rings that way. Hence the downward offset.
* **Foreground dust.** Depth in a flat illustration comes from layering, not
  detail: particles in front of the subject read as air between the viewer and
  the scene.

### The trap that caused the worst bug

Pillow **replaces** pixels when you draw an RGBA fill onto an RGBA image; it does
not blend. A 47%-opacity sheen drawn over an opaque shape on the same layer sets
those pixels to alpha 120 — a hole, not a highlight. That is what made lanterns,
the trophy cup, the book covers and the stall canopies look hollow. Anything
translucent that overlaps something else needs its own layer, which is what
`canvas.Painter` is for: motifs wrap each overlapping pass in `p.begin()`.


## Three rules that are not negotiable

1. **Artwork never goes into the article.** The PDF and DOCX are the submission;
   the approved format is text plus real photographs. A drawing standing in for
   a photo of something that happened is the one mistake this system must not
   make.
2. **Every asset is labelled.** Poster, social card and banner carry a small
   `AI 生成插画（非活动照片） · AI-generated artwork (not an event photo)` line, and
   the manifest repeats the disclaimer. Turn it off with `--no-credit` only if
   the image is going somewhere the label already appears in text.
3. **Provenance is recorded.** Nothing is generated anonymously: the manifest
   names the backend, and for the online model, the exact prompt, model, seed
   and URL.

## How an event picks its look

Classification reads the article's own words — title (CN + EN), lead, section
headings, tagline, venue, doc type and the brief's highlights — and scores them
against the keyword table below. Longer keywords count for more, because they
are more specific. The doc type then adds a nudge, and if nothing matches at all
the house look is used.

The result is deliberately predictable: you can read this table and know what a
given event will look like.

| Vibe | Triggered by (samples) | Motif | Palette |
|---|---|---|---|
| `photography` 摄影影像 | 摄影 拍照 相机 镜头 光影 photo camera lens | aperture iris | indigo `#0B1220` + amber `#E8B04B` |
| `sports` 体育竞技 | 羽毛球 篮球 运动 比赛 友谊赛 badminton sports tournament | shuttlecock | deep blue `#0C1A2E` + orange `#FF7A3D` |
| `culture` 文化传统 | 文化 传统 手艺 非遗 文化节 美食 culture craft heritage | lanterns | plum `#23102F` + gold `#E8B04B` |
| `study` 学业支持 | 学业 学习 考试 期末 辅导 讲座 study exam tutorial | books & pencil | sea blue `#0E2740` + mint `#6FD3C7` |
| `award` 荣誉喜报 | 喜报 获奖 斩获 冠军 大奖 一等奖 award prize champion | trophy & laurel | navy `#131A33` + gold `#F2C14E` |
| `tech` 科技竞赛 | 智能 智慧 创新 竞赛 编程 代码 人工智能 apec tech code | circuit | midnight `#070F22` + cyan `#35D6E8` |
| `winter` 冬日暖意 | 冬 寒冬 雪 冰雪 圣诞 元旦 winter snow new year | snowflakes | ice blue `#0F2338` + `#8FD3F4` |
| `global` 国际交流 | 模联 模拟联合国 联合国 外交 国际交流 mun diplomacy | wireframe globe | UN blue `#062A5A` + `#7EC8E3` |
| `music` 音乐交流 | 音乐 歌 合唱 乐器 吉他 音乐会 music concert band | sound ribbons | violet `#150C2E` + magenta `#E8467C` |
| `carnival` 社团嘉年华 | 游园会 社团 摊位 招新 招募 报名 club fair booth | bunting & stalls | navy `#14213D` + orange `#FF6B35` |
| `celebration` 庆典回顾 | 圆满 落幕 收官 成功举办 联欢 celebrate closing | confetti burst | navy `#101B33` + gold `#F2C14E` |
| `brand` 品牌简约 | *nothing matched — the fallback* | geometric bands | white `#F4F6FA` + navy `#1B3870` |

Doc-type nudges: `喜报 → award (+2.4)`, `收官 → celebration (+0.8)`,
`竞赛 → tech (+0.6)`, `招募 → carnival (+0.6)`, `回顾 → celebration (+0.5)`,
`预告 → carnival (+0.35)`, `活动 → brand (+0.3)`.

The `喜报` hint is deliberately strong. An award announcement usually also
mentions the competition that produced it (a MUN conference, a contest), and
without the nudge the poster would show the *venue* of the win instead of the
win.

Doc type also sets the mood, not just the motif: `预告`/`招募`/`竞赛` are treated
as *anticipation* (cooler light, more empty space), `回顾`/`收官`/`喜报` as
*celebration* (warmer light, denser confetti), everything else neutral.

## Where the rules live

* `hsiyc_writer/art/vibe.py` — the keyword table, palettes and prompt text.
* `hsiyc_writer/art/motifs.py` — the twelve drawing routines.
* `hsiyc_writer/art/local.py` — layout of poster, banner, social card, divider.

A club member who wants a new trigger word for "hackathon" does not need to
understand the rest of the code: add the word to the `tech` entry's `keywords`
tuple and the next run will pick it up. Adding a whole new visual identity means
adding one `Vibe(...)` entry plus, optionally, a motif function and a line in
`MOTIFS`.

## Backends

### `local` — always available, never online

Drawn with numpy and Pillow from the vibe's palette and motif. Deterministic:
the same article and seed give byte-identical files, which is why re-running
never surprises anyone. Runs in about a second for a full kit. This is the
default for refreshing the shipped bundles.

### `remote` — a real text-to-image model

DeepSeek has no image endpoint; `POST /images/generations` returns 404 on every
path. Images therefore come from a separate service, and the online route is
treated as a bonus:

* By default the keyless public **Pollinations** endpoint is used. Measured on
  this machine it serves roughly **one novel prompt in six** — identical
  requests are cached and always succeed, but new prompts are rationed and
  answer `HTTP 402` once the budget is gone. That is the free tier's behaviour,
  not a bug here.
* A `402` is treated as terminal: the asset falls back to the local renderer
  immediately rather than making anyone wait through retries.
* Returned images are **cropped by 7.5% at the bottom** before use, because the
  service stamps its own logo into the corner even when asked not to
  (`nologo=true`). Club material must not carry a third-party brand. The
  manifest still records the service and URL, so the source is never hidden.
* Generated images are tinted toward the vibe's palette (`harmonise`,
  strength 0.16) so an AI banner and a drawn poster look like one family.
  When an online image is used, the local motif is **not** drawn over it —
  otherwise the poster shows two subjects at once.

### Pointing it at a provider you pay for

The online backend is provider-shaped. Any OpenAI-compatible images endpoint
works without touching code:

```powershell
$env:HSIYC_ART_ENDPOINT = "https://api.example.com/v1/images/generations"
$env:HSIYC_ART_API_KEY  = "sk-..."
$env:HSIYC_ART_MODEL    = "dall-e-3"
python -m hsiyc_writer art output\my-event --backend remote
```

Both the `b64_json` and the `url` response shapes are supported.

Set `HSIYC_ART_SIZE` to a size accepted by your provider when it does not support
the deliverable's exact dimensions. The renderer crops/resizes the generated background
to the final asset size. Custom requests omit the nonstandard `seed` field; changing
the seed requests a fresh cached variant but does not promise provider determinism.
Cache identities include the endpoint, configured size, model, prompt and seed.
Custom images retain their full background (the vendor-mark crop applies only to
Pollinations), and provenance identifies them as `remote:custom`.

Composition prompts are specific to each format: landscape banners leave room on
the left; portrait posters and square cards reserve their lower half for locally
rendered typography. A failed provider is attempted only for the first failing
asset in an automatic kit, then remaining assets use the local renderer.

Headlines have both line and height limits. They shrink first, then use an ellipsis
if the minimum readable size still cannot fit. The full titles remain in the article
and manifest. Per-asset seeds keep partial regeneration identical to the corresponding
asset in a full kit; merged manifests compute their backend from all retained assets.

### Turning it off

```powershell
$env:HSIYC_ART_OFFLINE = "1"     # never touch the network, always draw locally
python -m hsiyc_writer generate -b brief.md --art none    # no artwork at all
```

## Commands

```powershell
python -m hsiyc_writer generate -b brief.md --art auto     # default
python -m hsiyc_writer generate -b brief.md --art local    # offline only
python -m hsiyc_writer generate -b brief.md --no-deck      # skip the .pptx
python -m hsiyc_writer art output\my-event --backend auto  # redo the art only
python -m hsiyc_writer art output\my-event --kind poster --light --seed 7
python -m hsiyc_writer art output\my-event --kind cover    # one asset only
```

In the browser UI the choice is the **Illustration** selector on the form, and
**Gallery** (`/gallery`) lists everything produced so far with its poster,
validator score and download links, newest first. `auto` is the default.


## Failure behaviour

Artwork is decorative and must never cost the club its article:

* `auto` never raises. If the online model fails, the asset is drawn locally and
  the reason is written into the manifest's `notes` and `run_log.json`.
* `remote` (strict) *does* raise, because that is what it was asked to do.
* If numpy or Pillow is missing, or no CJK font is installed, the bundle is
  written without artwork and `render_warning.txt` records why. The article,
  the PDF, the DOCX and the check report are unaffected.
* A partial re-render (`--kind poster`) merges into the existing manifest rather
  than discarding the assets the deck and preview already point at.

## Verification

`tests/art_cases.py` (48 checks, offline) locks in that every archetype reaches
its motif, that all twelve routines still put pixels on the canvas, that the
poster keeps printing its caption, that Chinese wrapping never strands
punctuation, that a fixed seed stays byte-identical, and that losing the online
backend degrades to the offline one. It runs as part of
`python -m hsiyc_writer selftest`.
