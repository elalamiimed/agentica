"""Scratch: exercise the 公众号 draft endpoint over HTTP in dry-run mode."""
import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8765"


def post(path, payload):
    request = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8") or "{}")


status = json.load(urllib.request.urlopen(BASE + "/api/status", timeout=20))
print("wechat_configured:", status["wechat_configured"], "(false until the club sets credentials)")

page = urllib.request.urlopen(BASE + "/", timeout=20).read().decode("utf-8")
print("page has the draft card code:", "wechat-draft" in page and "wxDraft" in page)

print("\ndry run over HTTP:")
code, payload = post("/api/wechat-draft", {"dir": "output/hsiyc-winter-badminton-friendly-recap",
                                           "send": False})
print("HTTP", code)
for line in payload.get("progress", []):
    print("  ·", line)
print("  sent:", payload.get("sent"), "| notes:", payload.get("notes"))

print("\nsend=true without credentials must be refused:")
code, payload = post("/api/wechat-draft", {"dir": "output/hsiyc-winter-badminton-friendly-recap",
                                           "send": True})
print("HTTP", code, "-", str(payload.get("error"))[:120])

print("\nescaping the output directory must be refused:")
code, payload = post("/api/wechat-draft", {"dir": "C:/Windows", "send": False})
print("HTTP", code, "-", payload.get("error"))
