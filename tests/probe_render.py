"""Offline smoke test: render the sample article to PDF/HTML/Markdown and check it.

Needs no API key and no network, so it can run on any machine:
    <python> tests/probe_render.py

The PDF check is behavioural rather than structural: Ghostscript rewrites the
finished file into compressed object streams, so grepping for /Type /Page is not
meaningful. Instead the file must be openable by a real rasterizer, must produce
the expected page count, and must still expose its text.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hsiyc_writer import pdfout, render, validate  # noqa: E402

PDFINFO = Path(r"C:\Users\hp\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdfinfo.exe")
PDFTOTEXT = Path(r"C:\Users\hp\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdftotext.exe")

SAMPLE = {
    "meta": {"doc_type": "回顾", "slug": "probe-render", "generated_at": "2026-10-13T21:40:00", "model": "offline"},
    "title": {
        "cn": "国际青年俱乐部 | 测试文章：渲染引擎验证",
        "en": "HSIYC Test Article: Render Engine Check",
        "kicker_en": "APEC | TEST",
    },
    "lead": {
        "cn": "这是一段中文测试文字，用来验证排版引擎能否正确处理中英文混排、标点符号与自动换行。整段文字应当跨越数行并正确折行，不应出现字符重叠或超出页面边界的情况。",
        "en": "This is an English test paragraph verifying that the typesetting engine handles mixed CJK/Latin text, punctuation and automatic line wrapping without overflowing the page margins.",
    },
    "sections": [
        {
            "number": "01",
            "heading_cn": "活动详情",
            "heading_en": "Event Highlights",
            "body": [
                {
                    "kind": "bilingual",
                    "cn": "2026年7月19日至21日，第二届鹏海模拟联合国大会在深圳北理莫斯科大学（SMBU）举办，各校优秀代表齐聚一堂。",
                    "en": "From July 19–21, 2026, the 2nd Penghai Model United Nations Conference was held at Shenzhen MSU-BIT University (SMBU).",
                },
                {
                    "kind": "list",
                    "items": [
                        {"label_cn": "冠军", "label_en": "Champion", "value_cn": "Tugsuu Rentsennatsag", "value_en": "Tugsuu Rentsennatsag"},
                        {"label_cn": "亚军", "label_en": "Runner-up", "value_cn": "Brandon Mantovanni Yunata"},
                        {"label_cn": "季军", "label_en": "Third Place", "value_cn": "谢昊轩 Xie Haoxuan"},
                    ],
                },
                {
                    "kind": "photo_grid",
                    "layout": "2x2",
                    "photos": [
                        {"file": "venue.jpg", "caption_cn": "活动现场", "caption_en": "On site"},
                        {"file": "delegates.jpg", "caption_cn": "代表合影", "caption_en": "Delegates"},
                        {"file": "award.jpg"},
                    ],
                },
                {
                    "kind": "note",
                    "cn_note": "特别感谢凌怡老师在决赛中担任裁判，并在筹备期间给予我们宝贵的指导和建议。",
                    "en_note": "Special thanks to Professor Ling for judging the finals and for his guidance during preparation.",
                },
                {
                    "kind": "quote",
                    "cn": "以语言搭桥，以思辨连接世界。",
                    "en": "Building bridges through language.",
                },
            ],
        },
        {
            "number": "02",
            "heading_cn": "获奖名单",
            "heading_en": "Award Winners",
            "body": [
                {"kind": "bilingual", "cn": "经过评委团的严格评审，最终名次如下。", "en": "After careful deliberation by the judging panel, the results are as follows."},
            ],
        },
    ],
    "closing": {
        "heading_cn": "结语",
        "heading_en": "Closing",
        "tagline_cn": "以语言搭桥，以思辨连接世界",
        "tagline_en": "Building Bridges Through Language",
        "cn": "感谢每一位参会代表的努力与付出，期待更多国际学子在未来的舞台上继续闪耀。",
        "en": "Thank you to all our delegates for their dedication, and we look forward to seeing more international students shine.",
    },
    "signoff": {
        "cn": "哈工大（深圳）国际青年俱乐部",
        "en": "HITSZ International Youth Club",
        "program": "AcademiaSphere",
    },
    "credits": {
        "文字": "Zhumabay Aruzhan, Yalalt",
        "图片": "Najmia Popal, Ferraa Ahmed",
        "排版": "Zhumabay Aruzhan, Yalalt",
        "一审": "Samin、柯炽炜",
        "二审": "周宣彤、崔雨旸、高容驷",
        "三审": "卢锦章",
    },
    "toc": {
        "previous": "国际青年俱乐部 × 国际交流协会｜第一届模拟联合国科普讲堂",
        "next": "扬帆启新程，筑梦向未来 | 2026级国际新生入学教育",
    },
    "facts": [{"fact": "2026年7月19日至21日", "source": "brief"}],
    "needs_editor": ["确认获奖者中文姓名", "补充活动照片 4 张"],
}


def main() -> int:
    out_dir = ROOT / "_work" / "probe"
    out_dir.mkdir(parents=True, exist_ok=True)

    report = validate.validate(
        SAMPLE,
        brief={"event_date": "2026年7月19日至21日"},
        expected_photos=["venue.jpg", "delegates.jpg", "award.jpg"],
        require_photos=True,
    )
    print(report.text("offline render probe"))
    print()

    (out_dir / "probe.md").write_text(render.to_markdown(SAMPLE, report), encoding="utf-8")
    (out_dir / "probe.preview.html").write_text(render.to_html(SAMPLE, report, {}), encoding="utf-8")
    print("markdown:", (out_dir / "probe.md").stat().st_size, "bytes")
    print("html    :", (out_dir / "probe.preview.html").stat().st_size, "bytes")

    pdf_path = pdfout.write_article_pdf(SAMPLE, out_dir / "probe.pdf", {}, report)
    raw = pdf_path.read_bytes()
    print(f"pdf     : {len(raw):,} bytes")

    problems: list[str] = []
    if not raw.startswith(b"%PDF-1."):
        problems.append("bad PDF magic")

    pages = None
    if PDFINFO.is_file():
        proc = subprocess.run([str(PDFINFO), str(pdf_path)], capture_output=True, timeout=120)
        info = proc.stdout.decode("utf-8", "replace")
        match = re.search(r"Pages:\s+(\d+)", info)
        pages = int(match.group(1)) if match else None
        print(f"pages   : {pages}")
        if pages is None:
            problems.append("pdfinfo could not read the page count (unopenable PDF)")
        elif pages < 1:
            problems.append("PDF reports zero pages")
    else:
        problems.append(f"pdfinfo not found at {PDFINFO}; cannot verify the PDF opens")

    if PDFTOTEXT.is_file():
        proc = subprocess.run(
            [str(PDFTOTEXT), "-enc", "UTF-8", str(pdf_path), "-"], capture_output=True, timeout=120
        )
        text = proc.stdout.decode("utf-8", "replace")
        for probe in ("国际青年俱乐部", "SMBU", "slide right for more pictures"):
            if probe not in text:
                problems.append(f"text layer is missing {probe!r}")
        if not problems:
            print("text    : ok")
    else:
        problems.append(f"pdftotext not found at {PDFTOTEXT}")

    (out_dir / "probe.report.json").write_text(
        json.dumps(report.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if problems:
        print("\nPROBLEMS:", *problems, sep="\n  - ")
        return 1
    print("\nrender probe: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
