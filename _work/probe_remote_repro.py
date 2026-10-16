"""Reproduce the earlier HTTP 402 with the exact prompt and size that failed."""
import sys
import urllib.parse
import urllib.error
import urllib.request

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from hsiyc_writer.art import remote, vibe as vibemod  # noqa: E402

UA = {"User-Agent": "hsiyc-writer/1.0 (+local club article agent)"}

v, evidence = vibemod.classify("世界文化之夜", "World Culture Night", "传统文化 八国学子", doc_type="回顾")
prompt = vibemod.build_prompt(v, event_hint="World Culture Night", tone=evidence["tone"])
print("prompt:", prompt[:120], "...\n")

cases = [
    ("exact failing request 1600x900", prompt, 1600, 900, "flux"),
    ("same prompt 1024x576", prompt, 1024, 576, "flux"),
    ("wide 1600x900, short prompt", "a lantern", 1600, 900, "flux"),
    ("poster 1240x1754", "a lantern", 1240, 1754, "flux"),
]
for label, text, width, height, model in cases:
    query = urllib.parse.urlencode({"width": width, "height": height, "model": model,
                                    "seed": 1234, "nologo": "true"})
    url = remote.ENDPOINT.format(prompt=urllib.parse.quote(text, safe="")) + "?" + query
    try:
        response = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120)
        payload = response.read()
        from io import BytesIO

        from PIL import Image

        size = Image.open(BytesIO(payload)).size
        print("%-32s -> %s  requested %sx%s  got %s  %dB" % (label, response.status, width, height, size, len(payload)))
    except urllib.error.HTTPError as exc:
        print("%-32s -> HTTP %s %r" % (label, exc.code, exc.read()[:80]))
    except Exception as exc:
        print("%-32s -> %s: %s" % (label, type(exc).__name__, exc))
