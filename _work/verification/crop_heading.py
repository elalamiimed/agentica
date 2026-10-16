"""Crop + upscale regions of the rendered pages so stray/misaligned marks are visible."""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
PNG = ROOT / "_work" / "verification" / "png"

jobs = [
    ("fresh-1.png", (40, 400, 300, 530), "crop_fresh_heading01.png"),
    ("apec-1.png", (40, 490, 300, 630), "crop_apec_heading01.png"),
]

for src, box, out in jobs:
    im = Image.open(PNG / src).crop(box)
    im = im.resize((im.width * 3, im.height * 3), Image.LANCZOS)
    im.save(PNG / out)
    print(out, im.size)
