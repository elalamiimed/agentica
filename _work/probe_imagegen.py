"""Probe what image-generation routes are actually reachable from the app's interpreter."""
import json
import os
import socket
import sys
import urllib.error
import urllib.request

# Never hard-code a key here: this file is committed. It is read the way the app reads it.
KEY = os.environ.get("DEEPSEEK_API_KEY", "").strip()
if not KEY:
    _key_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "hsiyc_writer", ".deepseek_key")
    if os.path.isfile(_key_file):
        KEY = open(_key_file, encoding="utf-8-sig").read().strip()
if not KEY:
    sys.exit("no DEEPSEEK_API_KEY in the environment and no hsiyc_writer/.deepseek_key file")
UA = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}


def head(url, method="GET", headers=None, data=None, timeout=30):
    req = urllib.request.Request(url, method=method, data=data)
    for k, v in {**UA, **(headers or {})}.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            return r.status, dict(r.headers), body
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()
    except Exception as e:
        return None, {}, f"{type(e).__name__}: {e}".encode()


print("== 1. DeepSeek reachable at all? ==")
st, hd, body = head("https://api.deepseek.com/models", headers={"Authorization": f"Bearer {KEY}"})
print("   /models ->", st, body[:200])

print("== 2. DeepSeek image endpoints ==")
payload = json.dumps({"model": "deepseek-chat", "prompt": "a red apple", "n": 1, "size": "1024x1024"}).encode()
for path in ("/images/generations", "/v1/images/generations", "/beta/images/generations"):
    st, hd, body = head(
        "https://api.deepseek.com" + path,
        method="POST",
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
        data=payload,
    )
    print(f"   {path} -> {st} {body[:180]}")

print("== 3. External free image generators ==")
tries = [
    ("pollinations", "https://image.pollinations.ai/prompt/a%20red%20apple?width=512&height=512&nologo=true"),
    ("pollinations-model", "https://image.pollinations.ai/prompt/campus%20night?width=512&height=512&model=flux"),
    ("picsum", "https://picsum.photos/512/512"),
    ("placehold", "https://placehold.co/512x512.png"),
    ("unsplash-source", "https://source.unsplash.com/512x512/?campus"),
]
for name, url in tries:
    st, hd, body = head(url, timeout=40)
    ct = hd.get("Content-Type", "")
    print(f"   {name:20s} -> {st} ct={ct[:40]} bytes={len(body)}")

print("== 4. DNS/TLS sanity ==")
for host in ("api.deepseek.com", "image.pollinations.ai", "huggingface.co", "api.openai.com"):
    try:
        print(f"   {host:24s} -> {socket.gethostbyname(host)}")
    except Exception as e:
        print(f"   {host:24s} -> {type(e).__name__}: {e}")

print("== 5. python version ==", sys.version)
