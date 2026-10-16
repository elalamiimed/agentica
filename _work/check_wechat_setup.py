"""Scratch: check the setup endpoint and the page card over HTTP."""
import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8765"


def post(path, payload=None):
    data = json.dumps(payload or {}).encode("utf-8")
    request = urllib.request.Request(BASE + path, data=data,
                                     headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8") or "{}")


code, payload = post("/api/wechat-check")
print("POST /api/wechat-check ->", code)
print("  ok        :", payload.get("ok"))
print("  configured:", payload.get("configured"))
print("  public IP :", payload.get("public_ip"))
print("  error     :", str(payload.get("error"))[:140])

page = urllib.request.urlopen(BASE + "/", timeout=20).read().decode("utf-8")
print("page explains the setup:", "IP 白名单" in page and "wxTest" in page and "wechat-check" in page)
