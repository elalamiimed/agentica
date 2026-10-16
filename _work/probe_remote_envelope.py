"""Map the free tier's envelope: which prompt lengths and sizes actually work."""
import sys
import time
import urllib.parse
import urllib.error
import urllib.request
from io import BytesIO

from PIL import Image

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

UA = {"User-Agent": "hsiyc-writer/1.0 (+local club article agent)"}
FILLER = "flat vector editorial illustration bold geometric shapes limited palette clean modern poster art "


def attempt(width, height, text, model="flux"):
    query = urllib.parse.urlencode({"width": width, "height": height, "model": model,
                                    "seed": 99, "nologo": "true"})
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(text, safe="") + "?" + query
    started = time.time()
    try:
        response = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120)
        payload = response.read()
        size = Image.open(BytesIO(payload)).size
        return f"200 got={size} {len(payload)}B {time.time() - started:.1f}s"
    except urllib.error.HTTPError as exc:
        return f"HTTP {exc.code}"
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


print("== A. prompt length at 1024x576 ==")
base = "a camera aperture iris with light rays"
for extra in (0, 2, 4, 6, 9):
    text = (base + " " + FILLER * extra).strip()
    print("  len %4d -> %s" % (len(text), attempt(1024, 576, text)))

print("== B. size, short prompt ==")
for width, height in ((1024, 576), (1024, 1024), (768, 1024), (1600, 900), (1240, 1754), (900, 1600)):
    print("  %4dx%-5d -> %s" % (width, height, attempt(width, height, "a lantern")))

print("== C. size, medium prompt (~200 chars) ==")
medium = ("hanging paper lanterns and silk ribbons over a globe, flat vector editorial illustration, "
          "bold geometric shapes, deep plum and gold palette, no text, no words, poster art")[:200]
for width, height in ((1024, 576), (1024, 1024), (768, 1024)):
    print("  %4dx%-5d -> %s" % (width, height, attempt(width, height, medium)))
