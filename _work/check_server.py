"""Scratch: confirm the running server serves the fixed page and is healthy."""
import json
import urllib.request

BASE = "http://127.0.0.1:8765"
page = urllib.request.urlopen(BASE + "/", timeout=20).read().decode("utf-8")
needed = ("copyViaSelection", "execCommand", "xiumiManual", "res.xiumi_html", "Copy for 秀米")
print("served page has every copy path:", all(x in page for x in needed))
for needle in needed:
    print(f"  {needle:<18} {needle in page}")
status = json.load(urllib.request.urlopen(BASE + "/api/status", timeout=20))
print("status:", status["corpus_size"], "articles,", status["text_model"])
