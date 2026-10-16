"""Characterise the free image endpoint: rate limits, models, probe parameters."""
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

UA = {"User-Agent": "hsiyc-writer/1.0 (+local club article agent)"}
BASE = "https://image.pollinations.ai/prompt/a%20blue%20circle?width=1024&height=576&nologo=true&seed=42"


def probe(label, url):
    started = time.time()
    try:
        response = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90)
        payload = response.read()
        print("%-32s -> %s %-12s %7dB %5.1fs" % (
            label, response.status, response.headers.get("Content-Type", "")[:12],
            len(payload), time.time() - started))
        return True
    except urllib.error.HTTPError as exc:
        print("%-32s -> HTTP %s (%4.1fs) %r" % (label, exc.code, time.time() - started, exc.read()[:90]))
    except Exception as exc:
        print("%-32s -> %s: %s" % (label, type(exc).__name__, exc))
    return False


probe("plain retry", BASE)
probe("with referrer", BASE + "&referrer=hsiyc")
probe("model=turbo", BASE + "&model=turbo")
probe("plain again", BASE)
time.sleep(20)
probe("plain after 20s wait", BASE)
