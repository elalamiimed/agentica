"""Verify the gallery endpoints against the running server."""
import json
import sys
import urllib.request

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8765"

for path in ("/gallery", "/", "/api/bundles", "/legacy"):
    try:
        response = urllib.request.urlopen(BASE + path, timeout=20)
        body = response.read()
        print("%-14s HTTP %s %8s bytes %s" % (path, response.status, f"{len(body):,}",
                                              response.headers.get("Content-Type", "")[:34]))
    except Exception as exc:
        print("%-14s FAILED %s: %s" % (path, type(exc).__name__, exc))

data = json.loads(urllib.request.urlopen(BASE + "/api/bundles", timeout=20).read())
print(f"\nbundles: {data['count']}")
for item in data["bundles"]:
    poster = "yes" if item["poster"] else "NO"
    print("  %-44s score=%-4s errors=%-2s vibe=%-12s poster=%-3s files=%d" % (
        item["slug"][:44], item["score"], item["errors"], item["vibe"], poster, len(item["files"])))

# The poster URL the gallery hands the browser must actually serve an image.
first = next((b for b in data["bundles"] if b["poster"]), None)
if first:
    response = urllib.request.urlopen(BASE + first["poster"], timeout=30)
    payload = response.read()
    print("\nposter URL %s -> HTTP %s %s bytes %s" % (
        first["poster"], response.status, f"{len(payload):,}", response.headers.get("Content-Type")))
