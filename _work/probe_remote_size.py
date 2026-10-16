"""Isolate whether size matters, using an already-cached prompt (no generation budget)."""
import sys
import urllib.parse
import urllib.request
from io import BytesIO

from PIL import Image

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

UA = {"User-Agent": "hsiyc-writer/1.0 (+local club article agent)"}
CACHED = "a blue circle"

for width, height in ((1024, 576), (1024, 1024), (768, 1024), (1600, 900), (1240, 1754), (512, 512)):
    query = urllib.parse.urlencode({"width": width, "height": height, "model": "flux",
                                    "seed": 42, "nologo": "true"})
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(CACHED) + "?" + query
    try:
        response = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90)
        payload = response.read()
        print("  %4dx%-5d -> 200 got=%s %dB" % (width, height, Image.open(BytesIO(payload)).size, len(payload)))
    except Exception as exc:
        print("  %4dx%-5d -> %s %s" % (width, height, type(exc).__name__, getattr(exc, "code", "")))
