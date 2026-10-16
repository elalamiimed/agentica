"""Live check of the online image backend: prompt -> fetch -> harmonise -> compose."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from hsiyc_writer.art import canvas, local, remote, vibe as vibemod  # noqa: E402
from hsiyc_writer.art import text as textmod  # noqa: E402
import numpy as np  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "_work" / "art_preview" / "_remote"
OUT.mkdir(parents=True, exist_ok=True)

print("status:", remote.status(probe=True))

CASES = [
    ("photography", ["HSIYC 摄影工作坊", "Photography Workshop", "镜头 光影 构图"], "回顾"),
    ("culture", ["世界文化之夜", "World Culture Night", "传统文化 八国学子"], "回顾"),
]

made = []
for key, texts, doc_type in CASES:
    v, evidence = vibemod.classify(*texts, doc_type=doc_type)
    pal = canvas.Palette.from_hex(v.palette)
    prompt = vibemod.build_prompt(v, event_hint=texts[1], tone=evidence["tone"])
    print(f"\n== {key} -> vibe {v.key} / motif {v.motif}")
    print("   prompt:", prompt[:160], "...")
    result = remote.generate(prompt, 1600, 900)
    print(f"   got {result['image'].size} model={result['model']} seed={result['seed']} cached={result['cached']}")
    raw = result["image"].resize((760, 428), Image.LANCZOS)
    rng = np.random.default_rng(3)
    tinted = local.harmonise(result["image"], pal, rng).resize((760, 428), Image.LANCZOS)
    caption = local.Caption(title_cn=f"国际青年俱乐部 | 回顾：{texts[0]}", title_en=texts[1],
                            date_line="时间：2026年12月12日（周六）", venue_line="地点：哈工大（深圳）")
    composed = local.banner(v, pal, np.random.default_rng(3), caption=caption,
                            background=local.harmonise(result["image"], pal, np.random.default_rng(3)))
    composed_small = composed.resize((760, 428), Image.LANCZOS)
    (OUT / f"{key}_raw.png").write_bytes(b"")  # placeholder, replaced below
    result["image"].save(OUT / f"{key}_raw.png")
    tinted.save(OUT / f"{key}_tinted.png")
    composed.save(OUT / f"{key}_banner.png")
    made.append([(f"{key} raw", raw), (f"{key} harmonised", tinted), (f"{key} composed banner", composed_small)])

# Comparison sheet: rows = cases, columns = raw / tinted / composed.
cols, col_w, label_h, pad = 3, 760, 26, 10
rows = len(made)
cell_h = 428
sheet = Image.new("RGB", (col_w * cols + pad * (cols + 1), (cell_h + label_h) * rows + pad * (rows + 1)),
                  (245, 246, 249))
draw = ImageDraw.Draw(sheet)
font = textmod.load(15, bold=True)
for r, row in enumerate(made):
    for c, (label, image) in enumerate(row):
        x = pad + c * (col_w + pad)
        y = pad + r * (cell_h + label_h + pad)
        draw.text((x + 4, y + 4), label, font=font, fill=(27, 56, 112))
        sheet.paste(image, (x, y + label_h))
sheet.save(OUT / "_remote_sheet.png")
print("\nsheet ->", OUT / "_remote_sheet.png", sheet.size)
