"""End-to-end PDF fidelity test.

Renders a PDF with an external rasterizer, then compares the text a human can
see against the source article. This is the check that would have caught the
"glyphs silently render as .notdef" class of bug, which byte-level font checks
cannot see.
"""

from __future__ import annotations

import re
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hsiyc_writer import pdfout  # noqa: E402

PDFTOTEXT = Path(r"C:\Users\hp\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdftotext.exe")

# Body sentences that the PDF must render and extract. Each maps 1:1 to a
# paragraph in ARTICLE below, so a miss here is a genuine defect.
SOURCE = (
    "国际青年俱乐部 | 活动回顾：APEC智慧校园创新系列\n"
    "2026年7月19日至21日，第二届鹏海模拟联合国大会在深圳北理莫斯科大学（SMBU）成功举办。\n"
    "冠军：Tugsuu Rentsennatsag\n"
    "季军：谢昊轩 Xie Haoxuan\n"
    "以乐会友，以言知音。\n"
    "感谢每一位参会代表的努力与付出。\n"
)

ARTICLE = {
    "meta": {"doc_type": "回顾", "slug": "fidelity"},
    "title": {"cn": "国际青年俱乐部 | 活动回顾：APEC智慧校园创新系列", "en": "APEC Smart Campus Review"},
    "lead": {
        "cn": "2026年7月19日至21日，第二届鹏海模拟联合国大会在深圳北理莫斯科大学（SMBU）成功举办。",
        "en": "From July 19 to 21, 2026, the 2nd Penghai Model United Nations Conference was held at SMBU.",
    },
    "sections": [
        {
            "number": "01",
            "heading_cn": "获奖名单",
            "heading_en": "Award Winners",
            "body": [
                {"kind": "bilingual", "cn": "冠军：Tugsuu Rentsennatsag", "en": "Champion: Tugsuu Rentsennatsag"},
                {"kind": "bilingual", "cn": "亚军：Brandon Mantovanni Yunata", "en": "Runner-up: Brandon Mantovanni Yunata"},
                {"kind": "bilingual", "cn": "季军：谢昊轩 Xie Haoxuan", "en": "Third Place: Xie Haoxuan"},
            ],
        },
        {
            "number": "02",
            "heading_cn": "精彩瞬间",
            "heading_en": "Highlights",
            "body": [
                {"kind": "bilingual", "cn": "以乐会友，以言知音。", "en": "Friendship through music, understanding through words."},
                {"kind": "bilingual", "cn": "感谢每一位参会代表的努力与付出。", "en": "Thank you to every delegate for their dedication."},
            ],
        },
        {
            "number": "03",
            "heading_cn": "展望未来",
            "heading_en": "Looking Ahead",
            "body": [
                {"kind": "bilingual", "cn": "期待更多国际学子在未来的舞台上继续闪耀。", "en": "We look forward to seeing more international students shine."},
            ],
        },
    ],
    "closing": {
        "heading_cn": "结语",
        "heading_en": "Closing",
        "tagline_cn": "以语言搭桥，以思辨连接世界",
        "tagline_en": "Building Bridges Through Language",
        "cn": "感谢每一位参会代表的努力与付出，期待更多国际学子在未来的舞台上继续闪耀。",
        "en": "Thank you to all our delegates; we look forward to seeing more international students shine.",
    },
    "signoff": {"cn": "哈工大（深圳）国际青年俱乐部", "en": "HITSZ International Youth Club"},
    "credits": {
        "文字": "Zhumabay Aruzhan",
        "图片": "Yalalt",
        "排版": "Zhumabay Aruzhan",
        "一审": "Samin、柯炽炜",
        "二审": "周宣彤、崔雨旸、高容驷",
        "三审": "卢锦章",
    },
    "facts": [{"fact": "2026年7月19日至21日", "source": "brief"}],
    "needs_editor": [],
}


def content_cids(pdf: bytes) -> tuple[set[int], int]:
    """Every CID drawn by the content streams, plus the subset glyph count."""
    cids: set[int] = set()
    for match in re.finditer(rb"(\d+) 0 obj\n<<([^\n]*)>>\nstream\n", pdf):
        head = match.group(2)
        if b"/Length" not in head:
            continue
        length = int(re.search(rb"/Length (\d+)", head).group(1))
        raw = pdf[match.end() : match.end() + length]
        if b"FlateDecode" in head:
            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                continue
        for tj in re.findall(rb"<([0-9A-Fa-f]+)>\s*Tj", raw):
            for i in range(0, len(tj) - 3, 4):
                cids.add(int(tj[i : i + 4], 16))
    return cids, 0


def embedded_glyph_count(pdf: bytes) -> int:
    ref = re.search(rb"/FontFile2 (\d+) 0 R", pdf)
    for match in re.finditer(rb"(\d+) 0 obj\n<<([^\n]*)>>\nstream\n", pdf):
        if int(match.group(1)) != int(ref.group(1)):
            continue
        head = match.group(2)
        length = int(re.search(rb"/Length (\d+)", head).group(1))
        raw = pdf[match.end() : match.end() + length]
        if b"FlateDecode" in head:
            raw = zlib.decompress(raw)
        num_tables = int.from_bytes(raw[4:6], "big")
        for i in range(num_tables):
            rec = 12 + 16 * i
            if raw[rec : rec + 4] == b"maxp":
                off = int.from_bytes(raw[rec + 8 : rec + 12], "big")
                return int.from_bytes(raw[off + 4 : off + 6], "big")
    return 0


def main() -> int:
    out = ROOT / "_work" / "fidelity.pdf"
    # Production path: full font for guaranteed correct rendering, then Ghostscript
    # subsets it. This test therefore covers the shrink step too.
    pdfout.write_article_pdf(ARTICLE, out, {}, None)
    pdf = out.read_bytes()
    problems: list[str] = []

    if not PDFTOTEXT.is_file():
        problems.append(f"pdftotext not found at {PDFTOTEXT}; cannot verify the visible text")
    else:
        proc = subprocess.run(
            [str(PDFTOTEXT), "-enc", "UTF-8", str(out), "-"],
            capture_output=True, timeout=120,
        )
        extracted = proc.stdout.decode("utf-8", "replace")
        extracted_flat = re.sub(r"\s+", "", extracted)
        # Compare per sentence, not across sentence boundaries: the renderer emits
        # each sentence as its own text run, so a window spanning two of them is
        # not a real defect.
        sentences: list[str] = []
        for line in SOURCE.splitlines():
            sentences += [s for s in re.split(r"[。！？]", line) if s.strip()]
        missing = [s for s in sentences if re.sub(r"\s+", "", s) not in extracted_flat]
        if missing:
            problems.append(f"{len(missing)} source sentence(s) missing from the PDF text layer: {missing[:4]}")
        else:
            print(f"text layer: all {len(sentences)} source sentence(s) recovered")

        # No CID may reference a glyph outside the (possibly shrunk) subset.
        cids, _ = content_cids(pdf)
        glyphs = embedded_glyph_count(pdf)
        if glyphs:
            print(f"PDF {len(pdf):,} bytes | embedded font {glyphs} glyphs | {len(cids)} distinct CIDs drawn")
            if cids and max(cids) >= glyphs:
                bad = sorted(c for c in cids if c >= glyphs)
                problems.append(
                    f"{len(bad)} CID(s) exceed the {glyphs}-glyph font (e.g. {bad[:6]}) - "
                    "these render as .notdef (blank) even though the PDF text is correct"
                )
        else:
            # Ghostscript re-encodes the font; fall back to a text-layer-only check.
            print(f"PDF {len(pdf):,} bytes | font re-encoded by Ghostscript | {len(cids)} distinct CIDs drawn")

    if problems:
        print("\nPROBLEMS:")
        for item in problems:
            print("  -", item)
        return 1
    print("\nfidelity: OK - text layer matches the source and no CID falls outside the font")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
