"""Check where the section accent bars are drawn relative to their heading text,
by decompressing the real PDF content stream. Evidence, not opinion."""
import re
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PDF = next((ROOT / "_work" / "verification" / "gen").glob("*/*.pdf"))

raw = PDF.read_bytes()
streams = []
for m in re.finditer(rb"(?<!end)stream\r?\n", raw):
    start = m.end()
    end = raw.find(b"endstream", start)
    blob = raw[start:end]
    try:
        streams.append(zlib.decompress(blob))
    except zlib.error:
        pass

for idx, s in enumerate(streams):
    print(f"  stream[{idx}] {len(s):>9} bytes  head={s[:48]!r}")

content = [s for s in streams if b" re f" in s and b" Tm " in s]
page1 = content[0]
print(f"PDF: {PDF.name}   streams decompressed: {len(streams)}   "
      f"content streams: {len(content)}   page-1 stream: {len(page1)} bytes\n")

rects = []
texts = []
for line in page1.split(b"\n"):
    if line.endswith(b"re f") and b" rg " in line:
        parts = line.split()
        try:
            i = parts.index(b"rg")
            x, y, w, h = (float(v) for v in parts[i + 3:i + 7])
            rects.append((y, h, x, w))
        except (ValueError, IndexError):
            pass
    if b"Tm" in line and b"Tj" in line:
        m = re.search(rb"1 0 0 1 ([-\d.]+) ([-\d.]+) Tm", line)
        if m:
            texts.append((float(m.group(2)), len(re.search(rb"<([0-9A-Fa-f]+)>", line).group(1)) // 4))

print("filled rects (y, height, x, width) — accent bars are x=56 w=3 h=22:")
for y, h, x, w in sorted(rects, reverse=True):
    tag = "  <-- ACCENT BAR" if abs(x - 56) < 0.5 and abs(w - 3) < 0.5 else ""
    print(f"   y={y:7.2f} h={h:6.2f} x={x:6.2f} w={w:7.2f}{tag}")

print("\nfirst 6 text baselines (y, chars):")
for y, n in texts[:6]:
    print(f"   y={y:7.2f}  {n} chars")

bar_ys = sorted(y for y, h, x, w in rects if abs(x - 56) < 0.5 and abs(w - 3) < 0.5)
text_ys = [y for y, _ in texts]
print("\nnearest text baseline BELOW each accent bar (bar sits at y..y+22):")
for by in bar_ys:
    below = [ty for ty in text_ys if ty < by]
    nearest = max(below) if below else None
    gap = (by - nearest) if nearest is not None else None
    print(f"   bar y={by:7.2f} top={by+22:7.2f}  nearest text baseline below={nearest}  gap={gap}")
