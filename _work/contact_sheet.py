"""Build contact sheets so the whole art system can be reviewed in two images."""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from hsiyc_writer.art import make_art  # noqa: E402
from hsiyc_writer.art import text as textmod  # noqa: E402
from hsiyc_writer.art.canvas import Palette  # noqa: E402
from hsiyc_writer.art import local, vibe as vibemod  # noqa: E402
import numpy as np  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "_work" / "art_preview"
COLS = ("poster", "banner", "social", "divider")
COL_W = 340
LABEL_H = 26
SHEET_BG = (245, 246, 249)


def _scaled(path, width):
    image = Image.open(path).convert("RGB")
    height = max(1, round(image.height * width / image.width))
    return image.resize((width, height), Image.LANCZOS)


def _row(label, files):
    cells = [_scaled(files[kind], COL_W) for kind in COLS if kind in files]
    height = max(cell.height for cell in cells)
    strip = Image.new("RGB", (COL_W * len(COLS), height + LABEL_H), SHEET_BG)
    draw = ImageDraw.Draw(strip)
    font = textmod.load(15, bold=True)
    draw.text((8, 6), label, font=font, fill=(27, 56, 112))
    for index, cell in enumerate(cells):
        strip.paste(cell, (index * COL_W, LABEL_H))
    return strip


def sheet_a():
    """The four real bundles, full kit."""
    slugs = [
        "hsiyc-photography-workshop-recap-2026",
        "hsiyc-winter-badminton-friendly-recap",
        "world-culture-night-2026",
        "hsiyc-final-exam-study-support-workshop",
    ]
    rows = []
    for slug in slugs:
        bundle = ROOT / "output" / slug
        article = json.loads((bundle / f"{slug}.json").read_text(encoding="utf-8"))
        brief = json.loads((bundle / "run_log.json").read_text(encoding="utf-8")).get("brief")
        target = OUT / slug
        make_art(article, target, brief=brief, backend="local")
        files = {kind: target / f"{kind}.png" for kind in ("banner", "poster", "social")}
        files["divider"] = target / "divider-01.png"
        rows.append(_row(f"{slug}  [{article.get('meta',{}).get('doc_type','')}]", files))
    width = max(row.width for row in rows)
    height = sum(row.height for row in rows)
    sheet = Image.new("RGB", (width, height), SHEET_BG)
    y = 0
    for row in rows:
        sheet.paste(row, (0, y))
        y += row.height
    sheet.save(OUT / "_sheet_a_bundles.png")
    print("sheet A ->", OUT / "_sheet_a_bundles.png", sheet.size)


SYNTHETIC = [
    ("tech", {"title": {"cn": "APEC 智慧校园创新竞赛", "en": "Smart Campus Innovation Challenge"},
              "meta": {"doc_type": "竞赛", "event_date": "2026-11-20", "venue": "活动中心"}}),
    ("award", {"title": {"cn": "国际学子鹏海模联斩获三项大奖", "en": "Three Awards at Penghai MUN"},
               "meta": {"doc_type": "喜报", "event_date": "2026-10-18", "venue": "深圳"}}),
    ("music", {"title": {"cn": "以乐会友，以言知音——三校中英文音乐交流之夜", "en": "Music Exchange Night"},
               "meta": {"doc_type": "回顾", "event_date": "2026-05-10", "venue": "音乐厅"}}),
    ("carnival", {"title": {"cn": "社团游园会摊位与节目招募启动", "en": "Club Fair Booth Recruitment"},
                  "meta": {"doc_type": "招募", "event_date": "2026-04-12", "venue": "大学城"}}),
    ("winter", {"title": {"cn": "码上进步·智汇寒冬 Code Your Way Forward",
                          "en": "Code Your Way Forward Winter Camp"},
                "meta": {"doc_type": "预告", "event_date": "2027-01-15", "venue": "教学楼"}}),
    ("global", {"title": {"cn": "模拟联合国科普讲堂圆满落幕", "en": "Model United Nations Lecture"},
                "meta": {"doc_type": "回顾", "event_date": "2026-03-22", "venue": "报告厅"}}),
    ("celebration", {"title": {"cn": "无界青春：社团游园会圆满收官", "en": "Borderless Youth Club Fair"},
                     "meta": {"doc_type": "收官", "event_date": "2026-06-01", "venue": "操场"}}),
    ("brand", {"title": {"cn": "HSIYC 全体例会", "en": "HSIYC General Meeting"},
               "meta": {"doc_type": "活动", "event_date": "2026-09-01", "venue": "会议室"}}),
]


def sheet_b():
    """One banner per motif, so every drawing routine is visible at once."""
    width, height = local.KIND_SIZES["banner"]
    cols, col_w = 3, 400
    cell_h = round(height * col_w / width)
    rows = (len(SYNTHETIC) + cols - 1) // cols
    sheet = Image.new("RGB", (col_w * cols, (cell_h + LABEL_H) * rows), SHEET_BG)
    draw = ImageDraw.Draw(sheet)
    font = textmod.load(15, bold=True)
    for index, (expected, article) in enumerate(SYNTHETIC):
        v, evidence = vibemod.classify(
            article["title"]["cn"], article["title"]["en"], article["meta"]["venue"],
            doc_type=article["meta"]["doc_type"])
        pal = Palette.from_hex(v.palette)
        rng = np.random.default_rng(7)
        caption = local.Caption(title_cn=article["title"]["cn"], title_en=article["title"]["en"])
        image = local.banner(v, pal, rng, credit=False, caption=caption)
        image = image.resize((col_w, cell_h), Image.LANCZOS)
        cx = (index % cols) * col_w
        cy = (index // cols) * (cell_h + LABEL_H)
        draw.text((cx + 8, cy + 6), f"expect {expected} -> {v.key} / {v.motif}",
                  font=font, fill=(27, 56, 112) if v.key == expected else (190, 40, 40))
        sheet.paste(image, (cx, cy + LABEL_H))
    sheet.save(OUT / "_sheet_b_motifs.png")
    print("sheet B ->", OUT / "_sheet_b_motifs.png", sheet.size)


if __name__ == "__main__":
    sheet_a()
    sheet_b()
