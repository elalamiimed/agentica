"""The 秀米 / WeChat paste export: it must survive the paste, or it is worthless.

Both 秀米 and the WeChat article editor keep only inline styles. Anything else - a
stylesheet, a class, an id, a flex container, an external file - is stripped on paste, and
the failure mode is silent: the article looks fine in the bundle and arrives in 秀米 as
unstyled paragraphs. So these cases assert the properties that decide whether the paste
works, rather than trusting that the markup looks reasonable.

    <python> tests/xiumi_cases.py
"""

from __future__ import annotations

import html
import html.parser
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hsiyc_writer import render, validate  # noqa: E402
from hsiyc_writer.pipeline import GenerationResult  # noqa: E402

ARTICLE = {
    "meta": {"doc_type": "回顾", "slug": "xiumi-case"},
    "title": {"cn": "国际青年俱乐部 | 回顾：冬季羽毛球友谊赛圆满落幕",
              "en": "HSIYC Winter Badminton Friendly"},
    "lead": {"cn": "2026年12月20日，冬季羽毛球友谊赛在体育馆举行，24 名国际学生参赛。",
             "en": "On 20 December the winter badminton friendly took place in the gymnasium."},
    "sections": [
        {
            "number": "01", "heading_cn": "赛场之上", "heading_en": "On Court",
            "body": [
                {"kind": "bilingual", "cn": "比赛采用双打赛制，12 对组合展开角逐。",
                 "en": "The friendly was played in a doubles format with 12 pairs."},
                {"kind": "photo_grid", "layout": "1x1", "photos": [
                    {"file": "badminton-01.jpg", "alt": "court",
                     "caption_cn": "决赛现场", "caption_en": "the final"},
                ]},
            ],
        },
        {
            "number": "02", "heading_cn": "获奖名单", "heading_en": "Award Winners",
            "body": [
                {"kind": "list", "items": [
                    {"label_cn": "冠军", "label_en": "Champion",
                     "value_cn": "Enkhtur Yalalt / Emil Aliyev", "value_en": "Enkhtur Yalalt / Emil Aliyev"},
                    {"label_cn": "亚军", "label_en": "Runner-up",
                     "value_cn": "Nazir Nayab / Mohammed Mazen", "value_en": "Nazir Nayab / Mohammed Mazen"},
                ]},
                {"kind": "note", "cn_note": "比赛结果以裁判记录为准。", "en_note": "Results follow the referee's record."},
                {"kind": "quote", "cn": "这是一场属于所有人的比赛。", "en": "This was a match for everyone."},
                {"kind": "divider"},
                {"kind": "photo_grid", "layout": "1x1", "photos": [
                    {"file": "badminton-02.jpg", "alt": "team", "caption_cn": "合影", "caption_en": "group photo"},
                ]},
            ],
        },
    ],
    "closing": {"heading_cn": "结语", "heading_en": "Closing",
                "tagline_cn": "以球会友", "tagline_en": "Friendship through sport",
                "cn": "感谢每一位参赛者，愿我们在下一次活动中再相见。",
                "en": "Thank you to every player."},
    "signoff": {"cn": "哈工大（深圳）国际青年俱乐部", "en": "HITSZ International Youth Club",
                "program": "HSIYC Sports Programme"},
    "credits": {"文字": "Yalalt", "图片": "Ferraa Ahmed", "排版": "Najmia Popal",
                "一审": "Samin、柯炽炜", "二审": "周宣彤、崔雨旸", "三审": "卢锦章"},
    "toc": {"previous": "国际青年俱乐部 | 秋季运动会", "next": ""},
    "facts": [], "needs_editor": [],
}

failures: list[str] = []


def check(condition: bool, label: str) -> None:
    if not condition:
        failures.append(label)


class _Balance(html.parser.HTMLParser):
    """Reports tags that are not properly nested."""

    VOID = {"br", "img", "meta", "hr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.problems: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.problems.append(f"</{tag}> closes {self.stack[-1] if self.stack else 'nothing'}")
        else:
            self.stack.pop()


def case_paste_safe_markup() -> None:
    """The properties that decide whether 秀米 and WeChat keep the formatting."""
    print("paste-safe markup")
    doc = render.to_xiumi_html(ARTICLE)

    for forbidden in ("<style", "class=", " id=", "<div", "<ul", "<li", "<hr", "<h1", "<h2",
                      "<h3", "<table", "http://", "https://", "data:", "flex", "grid",
                      "position", "!important", "@media", "javascript:"):
        check(forbidden not in doc, f"the paste export must not contain {forbidden!r}")

    tags = set(__import__("re").findall(r"<\s*([a-zA-Z0-9]+)", doc))
    check(tags <= {"section", "p", "span", "br"}, f"unexpected tags in the paste export: {sorted(tags)}")
    check("section" in tags, "the export should be built from <section>, which both editors keep")

    # Every element that can carry a style must carry one: an unstyled <p> inherits
    # whatever the editor decides, which is how a pasted article ends up 12px grey.
    unstyled = [t for t, attrs in __import__("re").findall(r"<([a-z]+)([^>]*)>", doc)
                if t != "br" and "style=" not in attrs]
    check(not unstyled, f"every element needs its own inline style, found {unstyled[:4]}")

    parser = _Balance()
    parser.feed(doc)
    check(not parser.problems, f"unbalanced tags: {parser.problems[:3]}")
    check(not parser.stack, f"unclosed tags: {parser.stack}")


def case_text_is_all_there() -> None:
    """Nothing may be lost in the export - it is the article, not a summary of it."""
    print("no text lost")
    # Quotes are escaped in the markup (&#x27;), which is correct and renders identically;
    # compare against the unescaped text so the check is about content, not entities.
    doc = html.unescape(render.to_xiumi_html(ARTICLE))
    for text in (
        ARTICLE["title"]["cn"], ARTICLE["title"]["en"],
        ARTICLE["lead"]["cn"], ARTICLE["lead"]["en"],
        "赛场之上", "On Court", "获奖名单", "Award Winners",
        "比赛采用双打赛制，12 对组合展开角逐。",
        "The friendly was played in a doubles format with 12 pairs.",
        "冠军", "Champion", "Enkhtur Yalalt / Emil Aliyev",
        "亚军", "Runner-up", "Nazir Nayab / Mohammed Mazen",
        "比赛结果以裁判记录为准。", "Results follow the referee's record.",
        "这是一场属于所有人的比赛。", "This was a match for everyone.",
        "结语", "Closing", "以球会友", "Friendship through sport",
        "感谢每一位参赛者，愿我们在下一次活动中再相见。",
        "哈工大（深圳）国际青年俱乐部", "HITSZ International Youth Club",
        "HSIYC Sports Programme",
        "精彩回顾 · Table of Contents", "国际青年俱乐部 | 秋季运动会",
    ):
        check(text in doc, f"'{text[:36]}' is missing from the paste export")
    for role in validate.CREDIT_ROLES:
        check(f">{role}</span>" in doc and ARTICLE["credits"][role] in doc,
              f"the credit row for {role} is malformed in the paste export")


def case_photo_slots() -> None:
    """Images cannot cross the clipboard, so every position must be a labelled slot."""
    print("photo slots")
    doc = render.to_xiumi_html(ARTICLE)
    check(doc.count(render.PASTE_SLOT_LABEL) == 2, "one labelled slot per placed photo")
    check(f"{render.PASTE_SLOT_LABEL} 01" in doc and f"{render.PASTE_SLOT_LABEL} 02" in doc,
          "the slots must be numbered in reading order, because that is the upload order")
    for name in ("badminton-01.jpg", "badminton-02.jpg"):
        check(name in doc, f"the slot for {name} must name the file")
    check("决赛现场" in doc and "the final" in doc, "the slot should carry the caption too")
    slots = render._paste_photo_slots(ARTICLE)
    check(len(slots) == 2, f"two photo slots expected, got {len(slots)}")
    check(slots[0][0] == "badminton-01.jpg", "slots are in reading order")

    # An article with no photos must not invent a slot.
    no_photos = json.loads(json.dumps(ARTICLE, ensure_ascii=False))
    for section in no_photos["sections"]:
        section["body"] = [b for b in section["body"] if b.get("kind") != "photo_grid"]
    check(render.PASTE_SLOT_LABEL not in render.to_xiumi_html(no_photos),
          "an article without photos must have no slot")


def case_finished_layout() -> None:
    """The export is a designed page, not styled paragraphs - that is the whole point now.

    The club cannot use the WeChat API yet, so 秀米 is where the article is finished. A
    layout that arrives as plain text leaves the design work to a volunteer; these checks
    keep the finished furniture in place.
    """
    print("finished layout")
    doc = html.unescape(render.to_xiumi_html(ARTICLE))
    check("哈工大（深圳）国际青年俱乐部" in doc and "HITSZ INTERNATIONAL YOUTH CLUB" in doc,
          "the masthead must carry the club in both languages")
    # Section headers: number chip, Chinese title, English line, rule.
    for heading in ("赛场之上", "获奖名单", "结语"):
        check(f">{heading}</p>" in doc, f"'{heading}' must be a heading element")
    for english in ("On Court", "Award Winners", "Closing"):
        check(english in doc, f"'{english}' must appear under its heading")
    check("01</span>" in doc and "02</span>" in doc, "section numbers must be shown as chips")
    check("· · ·" in doc, "the decorative separators must be there")
    check("编辑团队 · EDITORIAL" in doc, "the credits must sit in their own card")
    check("精彩回顾 · Table of Contents" in doc, "the TOC card must survive")
    # Award rows are cards with a rank chip, not bare lines.
    check("冠军" in doc and "Enkhtur Yalalt" in doc, "the award rows must be complete")
    check(doc.count("border-left:3px solid") >= 2, "award cards keep their navy rule")
    # Captions are attached to their image, not floating.
    check("▪" in doc, "captions carry the small marker that ties them to the photo")


def case_escaping() -> None:
    """Model output is untrusted text: it must not become markup."""
    print("escaping")
    nasty = json.loads(json.dumps(ARTICLE, ensure_ascii=False))
    nasty["sections"][0]["body"][0]["cn"] = '<script>alert("x")</script> & <b>bold</b>'
    nasty["title"]["cn"] = '标题 <img src=x onerror=alert(1)>'
    doc = render.to_xiumi_html(nasty)
    check("<script" not in doc, "a script tag in the article must be escaped")
    check("<b>" not in doc, "inline html in the article must be escaped")
    check("&lt;script&gt;" in doc, "the escaped text should still be readable")
    check("onerror" not in doc or "&lt;img" in doc, "an event handler must not survive as markup")


def case_document_and_guide() -> None:
    """The file must declare UTF-8, and the guide must name the real file."""
    print("document and guide")
    doc = render.to_xiumi_document(ARTICLE)
    check(doc.startswith("<!DOCTYPE html>"), "the paste file should be a real document")
    check('<meta charset="utf-8">' in doc, "without a charset a Chinese Windows browser shows mojibake")
    check("<title>" in doc and "国际青年俱乐部" in doc, "the file should carry the article title")
    check("<body>" in doc and "</body>" in doc, "the clipboard fragment is taken from <body>")

    guide = render.to_xiumi_notes(ARTICLE, "xiumi-case")
    check("xiumi-case.xiumi.html" in guide, "the guide must name the actual file to open")
    check("badminton-01.jpg" in guide and "badminton-02.jpg" in guide,
          "the guide must list every photo to upload")
    check("【照片待插入】" in guide or render.PASTE_SLOT_LABEL in guide,
          "the guide must explain the slot box")
    check("xiumi-photos" in guide, "the guide must point at the numbered upload copies")
    check("01-badminton-01.jpg" in guide, "the guide must list the numbered upload names")
    check("No dashed box may survive" in guide, "the guide must include the pre-publish check")


def case_bundle_writes_both() -> None:
    """write_all must actually put both files in the bundle."""
    print("written into the bundle")
    work = Path(tempfile.mkdtemp(prefix="hsiyc_xiumi_"))
    try:
        result = GenerationResult(
            article=ARTICLE,
            report=validate.validate(json.loads(json.dumps(ARTICLE, ensure_ascii=False))),
            usage={}, attempts=1, log=[],
        )
        out = render.write_all(result, work, art=False, deck=False)
        for name in ("xiumi-case.xiumi.html", "xiumi-case.xiumi.md"):
            path = out / name
            check(path.is_file(), f"{name} was not written into the bundle")
            if path.is_file():
                body = path.read_text(encoding="utf-8")
                check(len(body) > 500, f"{name} looks empty")
        written = (out / "xiumi-case.xiumi.html").read_text(encoding="utf-8")
        check(render.PASTE_SLOT_LABEL in written, "the written file must carry the photo slots")
        check('<meta charset="utf-8">' in written, "the written file must declare its charset")
        check((out / "xiumi-photos").is_dir(), "the numbered upload copies must be written too")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def case_real_bundles() -> None:
    """Every bundle already on disk must re-export cleanly, including old ones."""
    print("existing bundles")
    bundles = sorted(p for p in (ROOT / "output").glob("*") if p.is_dir())
    articles = []
    for bundle in bundles:
        for candidate in bundle.glob("*.json"):
            if candidate.name in ("check_report.json",):
                continue
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if isinstance(data, dict) and data.get("sections") and data.get("title"):
                articles.append(data)
                break
    check(bool(articles), "no article JSON found under output/ to export")
    for article in articles:
        doc = render.to_xiumi_html(article)
        slug = (article.get("meta") or {}).get("slug") or "?"
        check("class=" not in doc and "<div" not in doc, f"{slug}: the export is not paste-safe")
        check(bool(doc.strip()), f"{slug}: the export is empty")
        parser = _Balance()
        parser.feed(doc)
        check(not parser.problems and not parser.stack, f"{slug}: unbalanced markup in the export")


def case_malformed_articles() -> None:
    """A crash here would waste a whole generation, so the export never raises."""
    print("malformed articles")
    for label, article in (
        ("empty object", {}),
        ("title only", {"title": {"cn": "标题"}}),
        ("null blocks", {"sections": [{"heading_cn": "x", "body": None}], "credits": None,
                         "toc": None, "closing": None, "signoff": None, "lead": None, "title": None}),
        ("odd blocks", {"sections": [{"body": [
            {"kind": "list", "items": None},
            {"kind": "photo_grid", "photos": [{}]},
            {"kind": "photo_grid", "photos": None},
            {"kind": "note"}, {"kind": "quote"}, {"kind": "divider"},
            {"kind": "bilingual"},
        ]}]}),
    ):
        try:
            doc = render.to_xiumi_html(article)
            render.to_xiumi_document(article)
            render.to_xiumi_notes(article, "s")
        except Exception as exc:  # noqa: BLE001 - the point is that nothing escapes
            check(False, f"{label}: the export raised {type(exc).__name__}: {exc}")
            continue
        check(bool(doc.strip()), f"{label}: the export should still produce markup")


def case_result_payload_carries_the_markup() -> None:
    """The page must be able to copy from a plain click, without fetching first.

    The button used to fetch the file inside the click handler. That await spends the user
    gesture before the clipboard call, which is exactly the shape Safari and some webviews
    refuse ("Failed to execute 'write' on 'Clipboard': Write permission denied"), and the
    operator sees a failure on a button that should just work. So the markup travels with
    the result payload instead.
    """
    print("the result payload carries the paste markup")
    from hsiyc_writer import web

    result = GenerationResult(
        article=ARTICLE,
        report=validate.validate(json.loads(json.dumps(ARTICLE, ensure_ascii=False))),
        usage={}, attempts=1, log=[],
    )
    payload = web.Handler._result_payload(result)
    check("xiumi_html" in payload, "the result payload must carry the paste markup")
    doc = payload.get("xiumi_html", "")
    check(bool(doc.strip()), "the paste markup in the payload must not be empty")
    check("class=" not in doc and "<div" not in doc, "the payload markup must be paste-safe")
    check(render.PASTE_SLOT_LABEL in doc, "the payload markup must carry the photo slots")
    check("卢锦章" in doc, "the payload markup must carry the credits")
    # The rest of the payload must be untouched.
    for key in ("article", "check", "usage", "attempts", "log"):
        check(key in payload, f"the result payload lost '{key}'")


def case_paste_endpoint() -> None:
    """`/api/paste/<slug>` is the link other tools pull the article from.

    There is no 秀米 API, so the only way to connect the two is for something running in the
    operator's own logged-in browser to fetch this URL. That makes its shape part of the
    contract: cross-origin headers, a private-network preflight answer, and a slug that
    cannot escape the output directory.
    """
    print("/api/paste/<slug>")
    import shutil
    import tempfile

    from hsiyc_writer import web

    work = Path(tempfile.mkdtemp(prefix="hsiyc_paste_"))
    saved = web.OUTPUT_DIR
    try:
        bundle = work / "xiumi-case"
        bundle.mkdir(parents=True)
        (bundle / "xiumi-case.json").write_text(json.dumps(ARTICLE, ensure_ascii=False),
                                                encoding="utf-8")
        web.OUTPUT_DIR = work

        class Capture(web.Handler):
            def __init__(self, path: str = "") -> None:
                self.path = path
                self.code = None
                self.body = b""
                self.content_type = ""
                self.headers: dict = {}

            def _send(self, code, body, content_type="application/json; charset=utf-8",
                      extra_headers=None):
                self.code, self.body, self.content_type = code, body, content_type
                self.headers = dict(extra_headers or {})

            def _json(self, code, payload):
                self.code = code
                self.body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        handler = Capture("/api/paste/xiumi-case")
        handler._serve_paste("xiumi-case")
        check(handler.code == 200, f"the paste endpoint should answer 200, got {handler.code}")
        text = handler.body.decode("utf-8")
        check(render.PASTE_SLOT_LABEL in text, "the served markup must carry the photo slots")
        check("class=" not in text and "<div" not in text, "the served markup must be paste-safe")
        check(handler.headers.get("Access-Control-Allow-Origin") == "*",
              "another origin has to be allowed to read it, or the bookmarklet cannot work")
        check("text/html" in handler.content_type, "it should be served as html")

        # ?meta gives the guide and title without the markup.
        meta = Capture("/api/paste/xiumi-case?meta")
        meta._serve_paste("xiumi-case")
        payload = json.loads(meta.body.decode("utf-8"))
        check(payload.get("slug") == "xiumi-case", "meta must name the bundle")
        check("paste guide" in payload.get("guide", ""), "meta must carry the guide")

        # A slug can never walk out of the output directory.
        for bad in ("../../Windows", "..", "a/b", ".hidden", ""):
            escape = Capture(f"/api/paste/{bad}")
            escape._serve_paste(bad)
            check(escape.code in (400, 403, 404),
                  f"slug {bad!r} must be refused, got {escape.code}")

        missing = Capture("/api/paste/nope")
        missing._serve_paste("nope")
        check(missing.code == 404, f"an unknown bundle should 404, got {missing.code}")

        # The preflight a browser sends before allowing a public page to reach 127.0.0.1.
        options = Capture("/api/paste/xiumi-case")
        options.do_OPTIONS()
        check(options.code == 204, f"OPTIONS should answer 204, got {options.code}")
        check(options.headers.get("Access-Control-Allow-Private-Network") == "true",
              "without this header Chrome blocks the private-network request outright")
    finally:
        web.OUTPUT_DIR = saved
        shutil.rmtree(work, ignore_errors=True)


def case_no_duplicate_closing_heading() -> None:
    """The article must not say 结语 / Closing twice in a row.

    The writer routinely ends with a 结语 section *and* fills the closing block. Every
    renderer printed both, so the finished page carried the same title twice - visible in
    the preview, the PDF, the DOCX and the 秀米 export. The closing text must survive; only
    the echoed title goes.
    """
    print("duplicate closing heading")
    duplicated = json.loads(json.dumps(ARTICLE, ensure_ascii=False))
    duplicated["sections"].append({
        "number": "07", "heading_cn": "结语", "heading_en": "Closing",
        "body": [{"kind": "bilingual", "cn": "本学期的活动到此结束。", "en": "The term ends here."}],
    })
    duplicated["closing"]["heading_cn"] = "结语"
    duplicated["closing"]["heading_en"] = "Closing"

    check(render.closing_heading(duplicated) is None,
          "a closing heading that repeats the last section must be suppressed")
    check(render.closing_heading(ARTICLE) == ("结语", "Closing"),
          "a distinct closing heading must be kept")

    doc = html.unescape(render.to_xiumi_html(duplicated))
    check(doc.count(">结语</p>") == 1,
          f"结语 must appear as a heading once, got {doc.count('>结语</p>')}")
    check("本学期的活动到此结束。" in doc, "the closing paragraph must survive the suppression")
    preview = render.to_html(duplicated)
    check(preview.count("结语") == 1, "the preview must not repeat the closing heading either")
    markdown = render.to_markdown(duplicated)
    check("## 结语 | Closing" not in markdown,
          "the markdown must not repeat the closing heading after a 结语 section")
    check(markdown.count("## 07 结语") == 1, "the section heading itself must stay")
    check("## 结语 | Closing" in render.to_markdown(ARTICLE),
          "a distinct closing heading must still be printed in the markdown")

    # An article with no sections at all still gets its closing heading.
    bare = {"title": {"cn": "标题"},
            "closing": {"heading_cn": "结语", "heading_en": "Closing", "cn": "文字"}}
    check(render.closing_heading(bare) == ("结语", "Closing"),
          "with no sections the closing heading must still be printed")


def main() -> int:
    case_paste_safe_markup()
    case_text_is_all_there()
    case_photo_slots()
    case_finished_layout()
    case_no_duplicate_closing_heading()
    case_escaping()
    case_document_and_guide()
    case_bundle_writes_both()
    case_result_payload_carries_the_markup()
    case_paste_endpoint()
    case_malformed_articles()
    case_real_bundles()

    if failures:
        print(f"\nxiumi_cases: {len(failures)} FAILURE(S)")
        for item in failures:
            print("  -", item)
        return 1
    print("\nxiumi_cases: OK - the article survives the paste, and every photo position is labelled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
