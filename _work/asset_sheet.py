"""Tile one bundle's poster, social card and cover into a single review image."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from hsiyc_writer.art import text as textmod  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
SLUG = sys.argv[1] if len(sys.argv) > 1 else "world-culture-night-2026"
ART = ROOT / "output" / SLUG / "art"

HEIGHT = 760
LABEL = 26
tiles = []
for name in ("poster", "social", "cover"):
    path = ART / f"{name}.png"
    if not path.is_file():
        print(f"missing {path}")
        continue
    image = Image.open(path).convert("RGB")
    width = max(1, round(image.width * HEIGHT / image.height))
    tiles.append((name, image.resize((width, HEIGHT), Image.LANCZOS)))

sheet = Image.new("RGB", (sum(t.width for _, t in tiles) + 12 * (len(tiles) + 1), HEIGHT + LABEL + 12),
                  (245, 246, 249))
draw = ImageDraw.Draw(sheet)
font = textmod.load(15, bold=True)
x = 12
for name, tile in tiles:
    draw.text((x + 4, 6), f"{SLUG} / {name}.png", font=font, fill=(27, 56, 112))
    sheet.paste(tile, (x, LABEL))
    x += tile.width + 12
out = ROOT / "_work" / "art_preview" / f"_assets_{SLUG}.png"
sheet.save(out)
print("sheet ->", out, sheet.size)
