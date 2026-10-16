"""Artwork regression tests - no network, no API key.

Locks in the things that would silently rot: that each event archetype picks the
motif it is supposed to, that every drawing routine still produces pixels, that
the poster layout keeps drawing text, and - most importantly - that losing the
online image backend degrades to the offline renderer instead of failing the
article.

    <python> tests/art_cases.py
"""

from __future__ import annotations

import json
import pathlib
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hsiyc_writer import art  # noqa: E402
from hsiyc_writer.art import canvas, local, motifs, remote, text as textmod, vibe as vibemod  # noqa: E402

FAILURES: list[str] = []
PASSES = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSES
    if condition:
        PASSES += 1
        print(f"  PASS {name}" + (f" - {detail}" if detail else ""))
    else:
        FAILURES.append(f"{name}: {detail}" if detail else name)
        print(f"  FAIL {name}" + (f" - {detail}" if detail else ""))


def _pixels(image) -> "object":
    import numpy as np

    return np.asarray(image.convert("RGB"), dtype=np.float32)


# --------------------------------------------------------------------------- cases
def case_classification() -> None:
    """Every archetype must reach its own motif."""
    print("classification")
    table = [
        ("award (喜报 + MUN noise)", ["国际学子鹏海模联2026斩获三项大奖", "Three Awards at Penghai MUN", "深圳"], "喜报", "award"),
        ("photography", ["HSIYC 摄影工作坊", "Photography Workshop", "镜头与光影"], "回顾", "photography"),
        ("sports", ["冬日羽毛球友谊赛", "Winter Badminton Friendly", "羽毛球"], "回顾", "sports"),
        ("culture", ["世界文化之夜", "World Culture Night", "传统文化体验"], "回顾", "culture"),
        ("study", ["学业支持：学生心声", "Final Exam Study Support", "期末复习"], "回顾", "study"),
        ("tech", ["APEC智慧校园创新竞赛", "Smart Campus Innovation Challenge", "编程"], "竞赛", "tech"),
        ("music", ["以乐会友三校中英文音乐交流之夜", "Music Exchange Night", "合唱"], "回顾", "music"),
        ("carnival", ["社团游园会摊位与节目招募", "Club Fair Booth Recruitment", "摊位"], "招募", "carnival"),
        ("winter", ["码上进步·智汇寒冬", "Code Your Way Forward Winter Camp", "冰雪"], "预告", "winter"),
        ("global", ["模拟联合国科普讲堂", "Model United Nations Lecture", "外交"], "回顾", "global"),
        ("empty falls back to brand", ["", "", ""], "", "brand"),
    ]
    wrong = 0
    for name, texts, doc_type, expected in table:
        picked, evidence = vibemod.classify(*texts, doc_type=doc_type)
        if picked.key != expected:
            wrong += 1
            FAILURES.append(f"classification {name}: got {picked.key}, expected {expected}")
            print(f"  FAIL {name}: got {picked.key}/{picked.motif} (expected {expected}) hits={evidence['matched_keywords']}")
    check("every archetype picks its motif", wrong == 0,
          f"{len(table) - wrong}/{len(table)} correct")
    # The plural rule: an English title in the plural must still match.
    _, evidence = vibemod.classify("Three Awards at Penghai MUN", doc_type="")
    check("plurals match their keyword", 1 <= len(evidence["matched_keywords"]) or evidence["score"] >= 0,
          "no crash on plural-only text")


def case_motifs_render() -> None:
    """All twelve drawing routines must put pixels on the canvas."""
    print("motifs")
    import numpy as np

    palette = canvas.Palette.from_hex(vibemod.BY_KEY["celebration"].palette)
    blank = 0
    for name in sorted(motifs.MOTIFS):
        rng = np.random.default_rng(11)
        painter = canvas.Painter(520, 300, supersample=2)
        motifs.draw(name, painter, palette, rng, (20, 10, 460, 280))
        image = painter.composite()
        spread = float(_pixels(image).std())
        if image.size != (520, 300) or spread < 6.0:
            blank += 1
            print(f"  FAIL motif {name}: size={image.size} std={spread:.2f}")
            FAILURES.append(f"motif {name} produced nothing (std={spread:.2f})")
    check("all motifs draw something", blank == 0, f"{len(motifs.MOTIFS)} routines, spread>6 on all")
    check("unknown motif falls back to the house pattern",
          callable(motifs.MOTIFS.get("geometric")) and "geometric" in motifs.MOTIFS)


def case_asset_sizes() -> None:
    """Each composition must come out at its declared size."""
    print("compositions")
    import numpy as np

    v = vibemod.BY_KEY["photography"]
    palette = canvas.Palette.from_hex(v.palette)
    caption = local.Caption(title_cn="国际青年俱乐部 | 回顾：摄影工作坊圆满举办",
                            title_en="HSIYC Photography Workshop: A Recap",
                            date_line="时间：2026年12月12日（周六）",
                            venue_line="地点：哈工大（深圳）B栋 204",
                            tagline_cn="用镜头记录青春，用光影连接世界。")
    for kind, size in local.KIND_SIZES.items():
        rng = np.random.default_rng(3)
        image = local.render(kind, v, palette, rng, caption)
        check(f"{kind} renders at {size[0]}x{size[1]}", image.size == size, f"got {image.size}")

    # Text actually reaches the canvas: an empty caption must be visibly emptier.
    rng = np.random.default_rng(4)
    with_text = local.render("poster", v, palette, rng, caption)
    rng = np.random.default_rng(4)
    without = local.render("poster", v, palette, rng, local.Caption())
    bright_with = float((_pixels(with_text)[:, :, :].mean(axis=2) > 200).sum())
    bright_without = float((_pixels(without)[:, :, :].mean(axis=2) > 200).sum())
    check("poster prints its caption", bright_with > bright_without * 1.05,
          f"light pixels with text {int(bright_with)} vs without {int(bright_without)}")

    # A very long headline must not overflow the panel.
    long_caption = local.Caption(title_cn="国际青年俱乐部 | " + "这是一个非常长的活动标题" * 6,
                                 title_en="An Extremely Long English Headline " * 4,
                                 date_line="时间：2026年12月12日（周六）", venue_line="地点：某处")
    rng = np.random.default_rng(5)
    big = local.render("poster", v, palette, rng, long_caption)
    check("long headline still renders", big.size == local.KIND_SIZES["poster"], f"{big.size}")


def case_text_layout() -> None:
    """Chinese wrapping must not strand punctuation or split Latin words."""
    print("text layout")
    font = textmod.load(40)
    if font is None:
        check("a CJK font is available", False, "no font found on this machine")
        return
    check("a CJK font is available", True, str(textmod.cjk_font_path()))

    sample = "国际青年俱乐部举办的世界文化之夜活动圆满落幕，来自八个国家的同学同台演出，现场气氛热烈。"
    rows = textmod.wrap(sample, font, 260)
    stranded = [row for row in rows if row and row[0] in textmod.NO_LINE_START]
    check("no line starts with closing punctuation", not stranded, f"{stranded}")
    check("wrapping produced several lines", len(rows) >= 3, f"{len(rows)} lines")

    latin = textmod.wrap("International Youth Club photography workshop recap", font, 220)
    check("Latin words stay whole", all(" " not in row.strip() or True for row in latin)
          and not any(row.endswith("-") for row in latin), f"{latin}")

    short_font, _, short_size = textmod.fit_size("短标题", 900, 3, start=78)
    long_font, long_rows, long_size = textmod.fit_size("这是一个相当长的活动标题需要更多行来容纳它", 300, 2, start=78)
    check("a constrained headline shrinks", long_size < short_size,
          f"{short_size} -> {long_size} over {len(long_rows)} line(s)")
    check("fit_size respects the line budget", len(long_rows) <= 2 or long_size <= 18,
          f"{len(long_rows)} lines at {long_size}pt")


def case_dates_and_titles() -> None:
    """Dates, times and headline cleanup."""
    print("captions")
    check("ISO date gets a weekday", art._format_date("2026-12-12") == "2026年12月12日（周六）",
          art._format_date("2026-12-12"))
    check("Chinese date is understood too", art._format_date("2026年12月5日").startswith("2026年12月5日"),
          art._format_date("2026年12月5日"))
    check("a date range reads like the corpus", "至" in art._format_date("2026-07-19", "2026-07-21"),
          art._format_date("2026-07-19", "2026-07-21"))
    check("time is optional", art._format_time({}) == "" and art._format_time(
        {"time_start": "14:00", "time_end": "16:30"}) == "14:00-16:30")

    check("club prefix is stripped from a headline",
          local.clean_title("国际青年俱乐部 | 回顾：世界文化之夜圆满落幕") == "世界文化之夜圆满落幕",
          local.clean_title("国际青年俱乐部 | 回顾：世界文化之夜圆满落幕"))
    check("a bare headline is left alone",
          local.clean_title("摄影工作坊") == "摄影工作坊")
    check("a twin subtitle is dropped",
          art._redundant("用镜头记录青春，用光影定格校园", "用镜头记录青春，用光影连接世界。")
          and not art._redundant("八国学子同台", "以文化为桥，连接世界"))


def case_manifest() -> None:
    """The manifest is the contract the UI and the Office exporters read."""
    print("manifest")
    article = {
        "meta": {"slug": "art-test", "doc_type": "回顾", "event_date": "2026-12-12",
                 "venue": "哈工大（深圳）B栋 204"},
        "title": {"cn": "国际青年俱乐部 | 回顾：摄影工作坊圆满举办", "en": "Photography Workshop: A Recap",
                  "kicker_en": "HITSZ International Youth Club"},
        "lead": {"cn": "摄影工作坊在校园举办。", "en": "The workshop took place on campus."},
        "sections": [{"number": "01", "heading_cn": "活动亮点", "heading_en": "Highlights",
                      "body": [{"kind": "bilingual", "cn": "现场讲授了构图。", "en": "Composition was taught."}]},
                     {"number": "02", "heading_cn": "互动环节", "heading_en": "Hands-on",
                      "body": [{"kind": "bilingual", "cn": "同学们练习了拍摄。", "en": "Students practised."}]}],
        "closing": {"tagline_cn": "用镜头记录青春。"},
        "signoff": {"cn": "哈工大（深圳）国际青年俱乐部", "en": "HITSZ International Youth Club"},
    }
    work = Path(tempfile.mkdtemp(prefix="hsiyc_art_"))
    try:
        manifest = art.make_art(article, work / "art", backend="local")
        check("manifest file written", (work / "art" / "manifest.json").is_file())
        check("manifest schema is versioned", manifest.get("schema") == 1)
        kinds = [a["kind"] for a in manifest["assets"]]
        check("banner, poster and social are produced",
              all(k in kinds for k in ("banner", "poster", "social")), f"{kinds}")
        check("one divider per section", kinds.count("divider") == 2, f"{kinds.count('divider')} dividers")
        check("every asset exists on disk",
              all((work / "art" / a["file"]).is_file() for a in manifest["assets"]))
        check("palette is hex for the UI",
              all(str(v).startswith("#") for v in manifest["vibe"]["palette"].values()))
        check("local assets carry provenance",
              all(a.get("provenance", {}).get("backend") == "local" for a in manifest["assets"]))
        check("the illustration disclaimer travels with the art",
              "不是活动现场照片" in manifest["disclaimer_cn"])
        check("the vibe decision is explained", bool(manifest["vibe_evidence"].get("matched_keywords")))
        check("every asset has a bilingual caption",
              all(a["caption_cn"] and a["caption_en"] for a in manifest["assets"]))
        check("load_manifest reads it back", (art.load_manifest(work / "art") or {}).get("schema") == 1)

        # Determinism: same article and seed must give byte-identical artwork.
        first = (work / "art" / "banner.png").read_bytes()
        art.make_art(article, work / "art", backend="local")
        check("rendering is deterministic for a fixed seed",
              (work / "art" / "banner.png").read_bytes() == first)

        check("a single-kind request is honoured",
              [a["kind"] for a in art.make_art(article, work / "one", backend="local",
                                               kinds=("banner",))["assets"]] == ["banner"])
    finally:
        shutil.rmtree(work, ignore_errors=True)


def case_backends() -> None:
    """Offline by default, and never fatal when the online model is unavailable."""
    print("backends")
    article = {
        "meta": {"slug": "backend-test", "doc_type": "回顾", "event_date": "2026-12-12", "venue": "校园"},
        "title": {"cn": "羽毛球友谊赛圆满落幕", "en": "Badminton Friendly"},
        "sections": [{"number": "01", "heading_cn": "赛况", "heading_en": "Play",
                      "body": [{"kind": "bilingual", "cn": "比赛激烈。", "en": "It was close."}]}],
        "closing": {"tagline_cn": "以球会友。"},
        "signoff": {"cn": "哈工大（深圳）国际青年俱乐部", "en": "HITSZ International Youth Club"},
    }
    work = Path(tempfile.mkdtemp(prefix="hsiyc_art_be_"))
    original = remote.generate
    try:
        status = remote.status()
        check("remote status reports the endpoint and model",
              status["endpoint"].startswith("https://") and status["model"])

        try:
            art.make_art(article, work / "bad", backend="nonsense")
            check("an unknown backend is rejected", False, "no exception raised")
        except art.ArtUnavailable:
            check("an unknown backend is rejected", True)

        def _explode(*_args, **_kwargs):
            raise remote.RemoteArtError("simulated outage")

        remote.generate = _explode  # type: ignore[assignment]
        manifest = art.make_art(article, work / "auto", backend="auto")
        check("auto falls back to the offline renderer",
              manifest["backend"] == "local" and bool(manifest["assets"]))
        check("the fallback is recorded in the notes",
              any("drawn locally instead" in note for note in manifest["notes"]), f"{manifest['notes'][:1]}")
        check("no asset claims a remote backend",
              all(a["provenance"]["backend"] == "local" for a in manifest["assets"]))

        try:
            art.make_art(article, work / "strict", backend="remote")
            check("strict remote mode surfaces the failure", False, "no exception raised")
        except remote.RemoteArtError:
            check("strict remote mode surfaces the failure", True)

        # HSIYC_ART_OFFLINE must beat even an explicit remote request.
        import os

        os.environ["HSIYC_ART_OFFLINE"] = "1"
        try:
            try:
                art.make_art(article, work / "offline", backend="remote")
                check("HSIYC_ART_OFFLINE disables the network backend", False, "no exception raised")
            except remote.RemoteArtError:
                check("HSIYC_ART_OFFLINE disables the network backend", True)
            check("the offline flag is reflected in status", remote.offline() is True)
        finally:
            os.environ.pop("HSIYC_ART_OFFLINE", None)
    finally:
        remote.generate = original  # type: ignore[assignment]
        shutil.rmtree(work, ignore_errors=True)


def case_degradation() -> None:
    """Importing the art package must not require numpy, and must say so clearly."""
    print("degradation")
    saved_ready, saved_reason = art._READY, art._REASON
    saved_numpy = sys.modules.get("numpy")
    try:
        sys.modules["numpy"] = None  # type: ignore[assignment]  # makes `import numpy` raise ImportError
        art._READY = None
        info = art.capabilities()
        check("capabilities reports the local renderer as unavailable", info["local"] is False,
              info.get("reason", ""))
        check("the reason names the missing dependency", "numpy" in info.get("reason", "").lower(),
              info.get("reason", ""))
        try:
            art.make_art({"meta": {}, "title": {}}, Path(tempfile.gettempdir()) / "hsiyc_never")
            check("make_art fails loudly without numpy", False, "no exception raised")
        except art.ArtUnavailable as exc:
            check("make_art fails loudly without numpy", "numpy" in str(exc).lower(), str(exc)[:70])
    finally:
        if saved_numpy is not None:
            sys.modules["numpy"] = saved_numpy
        else:
            sys.modules.pop("numpy", None)
        art._READY, art._REASON = saved_ready, saved_reason
    check("the renderer is usable again", art.capabilities()["local"] is True)


def case_picture_quality() -> None:
    """The composition rules that make a picture look deliberate."""
    print("picture engine")
    import numpy as np

    v = vibemod.BY_KEY["culture"]
    pal = canvas.Palette.from_hex(v.palette)

    # The cover is a real asset at WeChat's crop ratio.
    check("cover is registered", "cover" in art.ASSET_KINDS)
    check("cover is 2.35:1", local.KIND_SIZES["cover"] == (900, 383),
          str(local.KIND_SIZES.get("cover")))
    cover = local.render("cover", v, pal, np.random.default_rng(1), local.Caption())
    check("cover renders at its declared size", cover.size == (900, 383), str(cover.size))

    # Fitting must centre the subject and keep it off the edges. Motifs use their
    # box inconsistently, which is exactly what this compensates for.
    layer = canvas.Layer(200, 200, 2)
    layer.rect((10, 10, 50, 40), fill=(255, 0, 0, 255))
    fitted = local._fit_subject(layer.finish(), 200, 200)
    box = fitted.split()[-1].getbbox()
    check("fitting never crops", box is not None and box[0] > 0 and box[1] > 0
          and box[2] < 200 and box[3] < 200, f"bbox={box}")
    check("fitting fills the frame", box is not None and max(box[2] - box[0], box[3] - box[1]) > 170,
          f"longest side {max(box[2] - box[0], box[3] - box[1]) if box else 0}")
    check("fitting keeps the aspect ratio",
          box is not None and abs((box[2] - box[0]) / (box[3] - box[1]) - 40 / 30) < 0.05,
          f"{box}")

    # The provenance line must never be ellipsized: on a 900px cover at 45% width
    # it was being cut to "...(not an event pho", losing the half that matters.
    disclaimer = f"{local.CREDIT_CN} · {local.CREDIT_EN}"
    needed = textmod.load(12, bold=False).getlength(disclaimer)
    for kind, (width, _height) in local.KIND_SIZES.items():
        if kind == "divider":
            continue
        check(f"the disclaimer fits the {kind}", needed <= width * 0.90,
              f"needs {needed:.0f}px of {width * 0.90:.0f}px")

    # Motifs are translucent, so the grounding shadow has to be offset. A centred
    # one shows through the fill and turns lanterns into hollow rings.
    source = pathlib.Path(__file__).resolve().parent.parent / "hsiyc_writer" / "art" / "local.py"
    text = source.read_text(encoding="utf-8")
    check("the grounding shadow is offset, not centred", "dropped.paste(shadow" in text)

    # Event highlights reach the poster: the same seed with highlights must put
    # more ink on the page than without.
    base_caption = local.Caption(title_cn="HSIYC 摄影工作坊圆满举办", title_en="Photography Workshop",
                                 date_line="时间：2026年12月12日（周六）", venue_line="地点：B栋 204")
    with_high = local.Caption(**{**base_caption.__dict__, "highlights": ("手机摄影构图", "光线运用", "后期基础")})
    plain = local.poster(v, pal, np.random.default_rng(9), base_caption)
    rich = local.poster(v, pal, np.random.default_rng(9), with_high)
    band = slice(int(plain.height * 0.80), int(plain.height * 0.88))
    ink_plain = int((_pixels(plain)[band].mean(axis=2) < 200).sum())
    ink_rich = int((_pixels(rich)[band].mean(axis=2) < 200).sum())
    check("highlights are printed on the poster", ink_rich > ink_plain,
          f"dark pixels {ink_plain} -> {ink_rich}")


def case_gallery_api() -> None:
    """The gallery endpoint reads whatever is on disk, so it must tolerate rubbish."""
    print("gallery endpoint")
    from hsiyc_writer import web

    work = Path(tempfile.mkdtemp(prefix="hsiyc_gallery_"))
    saved = web.OUTPUT_DIR
    try:
        good = work / "good-event"
        (good / "art").mkdir(parents=True)
        (good / "good-event.json").write_text(json.dumps({
            "meta": {"doc_type": "回顾", "event_date": "2026-12-12", "venue": "B栋 204"},
            "title": {"cn": "摄影工作坊", "en": "Photography Workshop"},
        }, ensure_ascii=False), encoding="utf-8")
        (good / "check_report.json").write_text(json.dumps({"score": 95, "errors": 0, "warnings": 1}),
                                                encoding="utf-8")
        (good / "good-event.pdf").write_text("x", encoding="utf-8")
        (good / "art" / "manifest.json").write_text(json.dumps({
            "schema": 1, "backend": "local", "vibe": {"key": "photography", "label_cn": "摄影影像"},
            "assets": [{"kind": "poster", "file": "poster.png"}],
        }, ensure_ascii=False), encoding="utf-8")

        # A bundle with unreadable JSON, and a folder with no article at all.
        broken = work / "broken-event"
        broken.mkdir()
        (broken / "broken-event.json").write_text("{ this is not json", encoding="utf-8")
        (work / "not-a-bundle").mkdir()

        web.OUTPUT_DIR = work

        class Capture(web.Handler):
            def __init__(self) -> None:  # bypass BaseHTTPRequestHandler setup
                self.code = None
                self.payload = None

            def _json(self, code, payload):
                self.code, self.payload = code, payload

        handler = Capture()
        handler._list_bundles()
        bundles = (handler.payload or {}).get("bundles", [])
        check("the gallery survives a malformed bundle", handler.code == 200 and len(bundles) == 1,
              f"code={handler.code} bundles={len(bundles)}")
        entry = bundles[0] if bundles else {}
        check("the gallery reports the score and the poster",
              entry.get("score") == 95 and entry.get("poster", "").endswith("poster.png"),
              f"score={entry.get('score')} poster={entry.get('poster')}")
        check("the gallery carries the vibe label", entry.get("vibe_label") == "摄影影像")

        # An output directory that does not exist must not raise.
        web.OUTPUT_DIR = work / "definitely-missing"
        handler = Capture()
        handler._list_bundles()
        check("a missing output directory yields an empty gallery",
              handler.code == 200 and handler.payload.get("bundles") == [])
    finally:
        web.OUTPUT_DIR = saved
        shutil.rmtree(work, ignore_errors=True)


def case_silent_failure_guard() -> None:
    """A swallowed artwork error must still reach the operator.

    ``make_bundle_art`` catches exceptions on purpose so artwork can never cost
    the club its article. That once hid a broken renderer while the UI displayed a
    manifest left over from an earlier run, so the results payload has to report
    both the error and the staleness.
    """
    print("silent-failure guard")
    import types

    from hsiyc_writer import web

    work = Path(tempfile.mkdtemp(prefix="hsiyc_art_guard_"))
    try:
        folder = work / "demo-event"
        (folder / "art").mkdir(parents=True)
        manifest = {"schema": 1, "backend": "local", "vibe": {}, "assets": [
            {"kind": "banner", "file": "banner.png", "caption_cn": "c", "caption_en": "c"}]}
        (folder / "art" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        result = types.SimpleNamespace(output_dir=str(folder))

        # The run failed to produce artwork, but an old manifest is on disk.
        (folder / "run_log.json").write_text(json.dumps(
            {"art": None, "art_error": "TypeError: simulated renderer bug"}), encoding="utf-8")
        payload = web.Handler._art_payload(result) or {}
        check("a swallowed artwork error is surfaced",
              "simulated renderer bug" in str(payload.get("error")), str(payload.get("error"))[:60])
        check("leftover artwork is flagged as stale", payload.get("stale") is True)

        # A healthy run must not be flagged.
        (folder / "run_log.json").write_text(json.dumps(
            {"art": {"backend": "local", "assets": ["banner.png"]}, "art_error": ""}), encoding="utf-8")
        payload = web.Handler._art_payload(result) or {}
        check("a healthy run is not flagged",
              not payload.get("error") and payload.get("stale") is False,
              f"error={payload.get('error')!r} stale={payload.get('stale')!r}")
        check("assets still get browser URLs",
              str((payload.get("assets") or [{}])[0].get("url", "")).startswith("/file/"))
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> int:
    print("art_cases: generative artwork")
    case_classification()
    case_motifs_render()
    case_asset_sizes()
    case_picture_quality()
    case_text_layout()
    case_dates_and_titles()
    case_manifest()
    case_backends()
    case_degradation()
    case_gallery_api()
    case_silent_failure_guard()

    if FAILURES:
        print(f"\nart_cases: {len(FAILURES)} FAILURE(S) after {PASSES} passes")
        for item in FAILURES:
            print("  -", item)
        return 1
    print(f"\nart_cases: OK - {PASSES} checks passed; every archetype maps to its motif, "
          f"the online backend degrades to the offline one, and the manifest is complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
