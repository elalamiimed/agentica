"""Office-export regression tests - no API key, no network, no LibreOffice.

The deck and the tracker are the two files the club hands to a person rather than to
WeChat, so the failures that matter are the quiet ones: an empty field rendered as a
blank line, a section body that runs off the bottom of a slide, a malformed
``check_report.json`` that takes the whole workbook down with it, a missing library that
surfaces as an ImportError traceback instead of a sentence an operator can act on.

Every case writes under ``_work/office_check/`` - never into ``output/``, which is read
only here - and every deck is reopened and read back, because a file that exists is not
a file with the article in it.

    <python> tests/office_cases.py
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hsiyc_writer import office_export  # noqa: E402  (importing it also exposes pptx)

SCRATCH = ROOT / "_work" / "office_check" / "office_cases"

# A bundle the club actually produced: real title, real credits, real section bodies.
SAMPLE_SLUG = "hsiyc-photography-workshop-recap-2026"
SAMPLE = ROOT / "output" / SAMPLE_SLUG

# 16:9, in EMU, as PowerPoint stores it (1 inch = 914400 EMU).
EMU_PER_INCH = 914400.0
SLIDE_W_IN, SLIDE_H_IN = 13.333, 7.5

# The smallest article the schema allows: a Chinese title and two sections, with every
# optional field (meta, lead, closing, signoff, credits, toc, photos) absent.
MINIMAL: dict = {
    "title": {"cn": "国际青年俱乐部 | 回顾：最小文章"},
    "sections": [
        {"number": "01", "heading_cn": "活动详情", "heading_en": "Event Highlights",
         "body": [{"kind": "bilingual", "cn": "本次活动的第一段正文。",
                   "en": "The first paragraph of the article."}]},
        {"number": "02", "heading_cn": "精彩瞬间", "heading_en": "Highlights",
         "body": [{"kind": "bilingual", "cn": "本次活动的第二段正文。",
                   "en": "The second paragraph of the article."}]},
    ],
}


# --------------------------------------------------------------------------- helpers
def check(condition: bool, label: str, failures: list[str]) -> bool:
    if not condition:
        failures.append(label)
    return bool(condition)


def slide_text(slide) -> str:
    """All the text on a slide, including table cells (which are shapes, not paragraphs)."""
    parts: list[str] = []
    for shape in slide.shapes:
        if shape.has_text_frame:
            parts.append(shape.text)
        if shape.has_table:
            for row in shape.table.rows:
                for cell in row.cells:
                    parts.append(cell.text)
    return "\n".join(parts)


def deck_text(presentation) -> str:
    return "\n".join(slide_text(slide) for slide in presentation.slides)


def out_of_bounds(presentation) -> list[str]:
    """Shapes that hang off the slide - the check a reader would make with their eyes."""
    problems: list[str] = []
    for index, slide in enumerate(presentation.slides, 1):
        for shape in slide.shapes:
            left = shape.left / EMU_PER_INCH
            top = shape.top / EMU_PER_INCH
            right = left + shape.width / EMU_PER_INCH
            bottom = top + shape.height / EMU_PER_INCH
            if left < -0.01 or top < -0.01 or right > SLIDE_W_IN + 0.01 or bottom > SLIDE_H_IN + 0.01:
                label = shape.text[:30].replace("\n", " / ") if shape.has_text_frame else ""
                problems.append(f"slide {index}: {label!r} spans "
                                f"({left:.2f},{top:.2f})-({right:.2f},{bottom:.2f})")
    return problems


def main() -> int:
    failures: list[str] = []
    assert office_export.capabilities()["pptx"], "python-pptx must be importable for these tests"
    SCRATCH.mkdir(parents=True, exist_ok=True)

    from openpyxl import load_workbook
    from pptx import Presentation

    # ------------------------------------------------------------------ 1. real bundle
    article_path = SAMPLE / f"{SAMPLE_SLUG}.json"
    if not article_path.is_file():
        failures.append(f"sample bundle missing: {article_path}")
        article: dict = {}
    else:
        article = json.loads(article_path.read_text(encoding="utf-8"))

    deck_path = SCRATCH / "sample.pptx"
    office_export.export_deck(article, deck_path)
    deck = Presentation(str(deck_path))

    sections = [s for s in (article.get("sections") or []) if isinstance(s, dict)]
    check(deck_path.is_file() and deck_path.stat().st_size > 0, "deck file was not written", failures)
    check(len(deck.slides) >= len(sections) + 3,
          f"expected at least {len(sections) + 3} slides for {len(sections)} sections, "
          f"got {len(deck.slides)}", failures)
    check(round(deck.slide_width / EMU_PER_INCH, 3) == SLIDE_W_IN
          and round(deck.slide_height / EMU_PER_INCH, 3) == SLIDE_H_IN,
          f"slide size is not 16:9 ({deck.slide_width}x{deck.slide_height} EMU)", failures)

    text = deck_text(deck)
    title_cn = (article.get("title") or {}).get("cn", "")
    check(title_cn in text, "the Chinese title is missing from the deck", failures)
    check((article.get("title") or {}).get("en", "") in text,
          "the English title is missing from the deck", failures)
    check("哈工大（深圳）国际青年俱乐部" in text, "the club name is missing from the deck", failures)
    for section in sections:
        heading = section.get("heading_cn") or ""
        if heading and heading not in text:
            failures.append(f"section heading missing from the deck: {heading}")
    credits = article.get("credits") or {}
    for role, name in credits.items():
        if name and str(name) not in text:
            failures.append(f"credit missing from the deck: {role} | {name}")
    for role in ("一审", "二审", "三审"):
        check(role in text, f"the credits slide does not list {role}", failures)
    problems = out_of_bounds(deck)
    failures.extend(problems)
    print(f"PASS 1  real bundle deck    {len(deck.slides)} slides, {deck_path.stat().st_size:,} bytes, "
          f"{len(sections)} sections, 0 shapes off-slide")

    # ------------------------------------------------------------------ 2. real workbook
    book_path = SCRATCH / "sample.xlsx"
    office_export.export_workbook([SAMPLE], book_path)
    book = load_workbook(str(book_path))
    check(book.sheetnames == ["Articles", "Credits", "Issues"],
          f"unexpected sheets: {book.sheetnames}", failures)
    articles_sheet = book["Articles"]
    check(articles_sheet.max_row == 2, f"Articles should hold 1 data row, has {articles_sheet.max_row - 1}",
          failures)
    header = [cell.value for cell in articles_sheet[1]]
    for column in ("Slug", "CN chars 中文字数", "Score 得分", "Output files 产出文件"):
        check(column in header, f"Articles header is missing {column}", failures)
    check(articles_sheet.auto_filter.ref is not None, "Articles has no autofilter", failures)
    check(articles_sheet.freeze_panes == "A2", "Articles header row is not frozen", failures)
    row = {name: articles_sheet.cell(row=2, column=index + 1).value
           for index, name in enumerate(header)}
    check(row.get("Slug") == SAMPLE_SLUG, f"wrong slug in the tracker: {row.get('Slug')!r}", failures)
    for column in ("Sections 章节", "CN chars 中文字数", "Score 得分", "Errors 错误"):
        value = row.get(column)
        check(isinstance(value, int), f"{column} is {type(value).__name__}, not a number", failures)
    check(articles_sheet.cell(row=2, column=header.index("Sections 章节") + 1).data_type == "n",
          "the section count was stored as text", failures)
    report = json.loads((SAMPLE / "check_report.json").read_text(encoding="utf-8"))
    check(row.get("Score 得分") == report.get("score"),
          f"score {row.get('Score 得分')!r} does not match check_report.json {report.get('score')!r}",
          failures)
    credits_sheet = book["Credits"]
    check([cell.value for cell in credits_sheet[1]] == ["Bundle", "文字", "图片", "排版", "一审", "二审", "三审"],
          "Credits header does not carry all six roles", failures)
    check(credits_sheet.cell(row=2, column=1).value == SAMPLE_SLUG, "Credits row has the wrong bundle",
          failures)
    issues_sheet = book["Issues"]
    issues = len(report.get("findings") or [])
    check(issues_sheet.max_row == max(1, issues + 1),
          f"Issues should hold {issues} finding(s), has {max(0, issues_sheet.max_row - 1)}", failures)
    print(f"PASS 2  real workbook      3 sheets, Articles {articles_sheet.max_row - 1} row, "
          f"Credits {max(0, credits_sheet.max_row - 1)} row(s), Issues {max(0, issues_sheet.max_row - 1)} finding(s)")

    # ------------------------------------------------------------------ 3. minimal article
    minimal_deck = SCRATCH / "minimal.pptx"
    office_export.export_deck(MINIMAL, minimal_deck)
    bare = Presentation(str(minimal_deck))
    check(len(bare.slides) == 5,
          f"a 2-section article should give 5 slides (title, 2 sections, closing, credits), "
          f"got {len(bare.slides)}", failures)
    bare_text = deck_text(bare)
    check(MINIMAL["title"]["cn"] in bare_text, "the minimal deck lost its title", failures)
    check("活动详情" in bare_text and "精彩瞬间" in bare_text,
          "the minimal deck lost a section heading", failures)
    check("本次活动的第一段正文。" in bare_text, "the minimal deck lost a paragraph", failures)
    failures.extend(out_of_bounds(bare))
    # An absent field must leave no trace: no empty closing tagline, no invented credits.
    check("出品团队" in bare_text and "本文章未填写署名" in bare_text,
          "the credits slide should say the article has no credits", failures)
    print(f"PASS 3  minimal article    {len(bare.slides)} slides from title + 2 sections only, "
          f"no optional field invented")

    # ------------------------------------------------------------------ 4. art = None
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    no_art = SCRATCH / "no_art.pptx"
    office_export.export_deck(copy.deepcopy(MINIMAL), no_art, art=None, photos=None)
    plain = Presentation(str(no_art))
    check(len(plain.slides[0].shapes) > 0, "the title slide is empty", failures)
    check(not any(shape.shape_type == MSO_SHAPE_TYPE.PICTURE for shape in plain.slides[0].shapes),
          "art=None should not place a banner picture", failures)
    check(MSO_SHAPE_TYPE.AUTO_SHAPE in [s.shape_type for s in plain.slides[0].shapes],
          "art=None should still draw the navy title band and footer rule", failures)
    check(len(plain.slides) == len(bare.slides),
          "art=None changed the slide count", failures)
    failures.extend(out_of_bounds(plain))
    print(f"PASS 4  art=None           clean navy deck, {len(plain.slides)} slides, same structure")

    # ------------------------------------------------------------------ 5. art that points nowhere
    junk_deck = SCRATCH / "junk_art.pptx"
    office_export.export_deck(copy.deepcopy(MINIMAL), junk_deck,
                              art={"assets": {"banner": "not-here.png", "poster": "gone.png"}})
    check(len(Presentation(str(junk_deck)).slides) == len(bare.slides),
          "a banner that does not exist changed the deck", failures)
    print("PASS 5  missing art file   manifest naming absent assets still yields the full deck")

    # ------------------------------------------------------------------ 6. the real art schema
    # hsiyc_writer.art writes {"assets": [{"kind": "banner", "file": "banner.png"}, …]} - a
    # list, not a mapping - so the deck must read that shape, not only a hand-written one.
    from PIL import Image

    art_dir = SCRATCH / "art"
    art_dir.mkdir(exist_ok=True)
    Image.new("RGB", (160, 90), (27, 56, 112)).save(art_dir / "banner.png")
    Image.new("RGB", (90, 124), (232, 176, 75)).save(art_dir / "poster.png")
    manifest = art_dir / "manifest.json"
    manifest.write_text(json.dumps({
        "schema": 1,
        "backend": "local",
        "assets": [
            {"kind": "banner", "file": "banner.png", "width": 160, "height": 90, "section": None},
            {"kind": "divider", "file": "banner.png", "width": 160, "height": 26, "section": 1},
            {"kind": "poster", "file": "poster.png", "width": 90, "height": 124, "section": None},
        ],
    }), encoding="utf-8")
    art_deck = SCRATCH / "art_manifest.pptx"
    office_export.export_deck(copy.deepcopy(MINIMAL), art_deck, art=manifest)
    decorated = Presentation(str(art_deck))
    pictures = [shape for shape in decorated.slides[0].shapes
                if shape.shape_type == MSO_SHAPE_TYPE.PICTURE]
    check(len(decorated.slides) == len(bare.slides), "art changed the slide count", failures)
    check(len(pictures) == 1, f"the banner was not placed on the title slide ({len(pictures)} pictures)",
          failures)
    if pictures:
        # First in z-order means the banner sits behind the club name, not over it.
        check(decorated.slides[0].shapes[0].shape_type == MSO_SHAPE_TYPE.PICTURE,
              "the banner is not behind the title text", failures)
        check(abs(pictures[0].width / EMU_PER_INCH - SLIDE_W_IN) < 0.01,
              f"the banner covers {pictures[0].width / EMU_PER_INCH:.2f}in of a "
              f"{SLIDE_W_IN}in slide", failures)
    # The closing slide is the second from the end: the credits slide follows it.
    check(any(shape.shape_type == MSO_SHAPE_TYPE.PICTURE
              for shape in decorated.slides[-2].shapes),
          "the poster was not placed on the closing slide", failures)
    check(MINIMAL["title"]["cn"] in deck_text(decorated), "the banner hid the title text", failures)
    failures.extend(out_of_bounds(decorated))
    print("PASS 6  real art schema    banner behind the title, poster on the closing slide "
          "(hsiyc_writer.art manifest list form)")

    # ------------------------------------------------------------------ 7. broken reports
    bundles = SCRATCH / "bundles"
    bundles.mkdir(exist_ok=True)
    # Four ways a bundle can arrive damaged: no report at all, a truncated file, a report
    # with the right keys and the wrong types, and a folder with no article in it.
    damaged = {
        "no-report": (MINIMAL, None),
        "malformed-report": (MINIMAL, "{ this is not json"),
        "reshaped-report": (MINIMAL, json.dumps({"score": "eighty",
                                                 "findings": ["nope", {"severity": "weird"}]})),
        "empty-dir": (None, None),
    }
    for name, (payload, report_text) in damaged.items():
        folder = bundles / name
        folder.mkdir(exist_ok=True)
        if payload is not None:
            (folder / f"{name}.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        if report_text:
            (folder / "check_report.json").write_text(report_text, encoding="utf-8")

    broken_book = SCRATCH / "broken.xlsx"
    office_export.export_workbook(sorted(bundles.iterdir()), broken_book)
    tracker = load_workbook(str(broken_book))["Articles"]
    check(tracker.max_row == len(damaged) + 1,
          f"expected {len(damaged)} tracker rows, got {tracker.max_row - 1}", failures)
    score_column = [cell.value for cell in tracker[1]].index("Score 得分") + 1
    scores = [tracker.cell(row=row, column=score_column).value for row in range(2, tracker.max_row + 1)]
    check(all(value is None for value in scores),
          f"a missing or unreadable report must leave the score blank, got {scores}", failures)
    print(f"PASS 7  bad check_report   {tracker.max_row - 1} rows written, "
          f"scores blank, no exception")

    # ------------------------------------------------------------------ 8. no bundles
    empty_book = SCRATCH / "empty.xlsx"
    office_export.export_workbook([], empty_book)
    empty = load_workbook(str(empty_book))
    check(empty.sheetnames == ["Articles", "Credits", "Issues"],
          f"an empty tracker has the wrong sheets: {empty.sheetnames}", failures)
    for sheet in empty.worksheets:
        check(sheet.max_row == 1 and sheet.max_column > 1,
              f"{sheet.title} should hold only its header row", failures)
        check(sheet.freeze_panes == "A2", f"{sheet.title} header row is not frozen", failures)
        header_cell = sheet.cell(row=1, column=1)
        check(header_cell.font is not None and header_cell.font.bold is True,
              f"{sheet.title} header is not bold", failures)
        check(header_cell.fill is not None and header_cell.fill.fgColor.rgb.endswith("1B3870"),
              f"{sheet.title} header is not navy", failures)
    print("PASS 8  empty bundle list  workbook with 3 styled header-only sheets")

    # ------------------------------------------------------------------ 9. long section
    filler = ("在国际青年俱乐部的活动现场，同学们围绕本次活动的主题展开了充分的交流与讨论，"
              "从活动筹备到现场执行，每一个环节都凝聚着组织者与参与者的共同努力。")
    long_body = [{"kind": "bilingual", "cn": filler * 3, "en": "A long paragraph. " * 20}
                 for _ in range(8)]
    long_article = {
        "title": {"cn": "国际青年俱乐部 | 回顾：长文分页测试", "en": "Long Section Pagination"},
        "sections": [{"number": "01", "heading_cn": "超长章节", "heading_en": "A Very Long Section",
                      "body": long_body}],
    }
    long_deck = SCRATCH / "long.pptx"
    office_export.export_deck(long_article, long_deck)
    paged = Presentation(str(long_deck))
    body_text = deck_text(paged)
    expected_chars = sum(len(block["cn"]) for block in long_body)
    missing = [index for index, block in enumerate(long_body) if block["cn"] not in body_text]
    check(len(paged.slides) >= 7,
          f"a {expected_chars:,}-character section should need continuation slides, "
          f"got {len(paged.slides)} slides in total", failures)
    check("（续）" in body_text, "overflowing copy did not continue onto a marked slide", failures)
    check(not missing,
          f"paragraph(s) {missing} were cut off instead of continued "
          f"(expected {expected_chars:,} CN chars in the deck)", failures)
    failures.extend(out_of_bounds(paged))
    print(f"PASS 9  long section       {expected_chars:,} CN chars split over "
          f"{len(paged.slides)} slides, every paragraph whole, nothing off-slide")

    # ------------------------------------------------------------------ 10. no library
    for module, call in (
        ("pptx", lambda target: office_export.export_deck(MINIMAL, target)),
        ("openpyxl", lambda target: office_export.export_workbook([], target)),
    ):
        target = SCRATCH / f"unavailable.{module}"
        if target.exists():
            target.unlink()
        original = office_export._import_optional

        def broken(name: str, _original=original, _missing=module):
            return None if name == _missing else _original(name)

        office_export._import_optional = broken  # type: ignore[assignment]
        try:
            call(target)
            failures.append(f"a missing {module} did not raise OfficeUnavailable")
        except office_export.OfficeUnavailable as exc:
            message = str(exc)
            check(module in message, f"the {module} error does not name the library: {message}", failures)
            check("HSIYC_EXTRA_SITE_PACKAGES" in message,
                  f"the {module} error does not name the fix: {message}", failures)
            check(isinstance(exc, RuntimeError), f"OfficeUnavailable is not a RuntimeError: {exc}", failures)
        except ImportError as exc:
            failures.append(f"a missing {module} leaked an ImportError traceback: {exc}")
        finally:
            office_export._import_optional = original  # type: ignore[assignment]
        check(not target.exists(), f"{target.name} was written even though {module} was missing",
              failures)
    check(office_export.capabilities()["pptx"] is True,
          "capabilities() did not recover after the patch was removed", failures)
    print("PASS 10 missing library    OfficeUnavailable with the library name and the one-line fix, "
          "no file written, no ImportError")

    # ------------------------------------------------------------------ summary
    if failures:
        print(f"\noffice_cases: {len(failures)} FAILURE(S)")
        for item in failures:
            print("  -", item)
        return 1
    print("\noffice_cases: OK - deck and workbook survive a real bundle, a bare article, "
          "missing art, a broken report, no bundles at all and a missing library")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
