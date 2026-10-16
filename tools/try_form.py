"""End-to-end test of the running web app through its own form API.

Fills in the English intake form, submits it exactly as the browser does (multipart,
with photo uploads), waits for the article, and reports the result. Requires the server
to be running and a valid API key.

    <python> tools/try_form.py
"""

from __future__ import annotations

import json
import mimetypes
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "http://127.0.0.1:8765"

ANSWERS = {
    "event_description": (
        "The winter badminton friendly ran on 20 December from 15:00 to 18:00 in Court 3 of the "
        "HITSZ gymnasium. We ran it as doubles: 24 international students formed 12 pairs, and "
        "about 40 spectators came to cheer. Three matches went to a deciding game and two of the "
        "players had never played competitively before. Enkhtur Yalalt and Emil Aliyev took the "
        "final; Nazir Nayab and Mohammed Mazen were runners-up. 张老师 refereed."
    ),
    "event_name_en": "HSIYC Winter Badminton Friendly",
    "event_name_cn": "HSIYC 冬季羽毛球友谊赛",
    "doc_type": "回顾",
    "date_start": "2026-12-20",
    "time_start": "15:00",
    "time_end": "18:00",
    "venue_en": "Court 3, HITSZ Gymnasium",
    "venue_cn": "哈工大（深圳）体育馆 3 号馆",
    "organisers": "HITSZ International Youth Club (HSIYC)",
    "co_organisers": "International Education Center",
    "participants": "24 international students in 12 doubles pairs, about 40 spectators",
    "judges": "体育部 张老师 (Coach Zhang) — referee",
    "winners": "Champion — Enkhtur Yalalt / Emil Aliyev\nRunner-up — Nazir Nayab / Mohammed Mazen",
    "highlights": "Three matches went to a deciding game\nTwo players had never played competitively before",
    "results_summary": "The friendly closed the autumn semester sports programme.",
    "credit_writer": "Yalalt",
    "credit_photo": "Ferraa Ahmed",
    "credit_layout": "Najmia Popal",
    "credit_review1": "Samin、柯炽炜",
    "credit_review2": "周宣彤、崔雨旸",
    "credit_review3": "卢锦章",
}


def get_json(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(path: str, payload: dict) -> tuple[int, dict]:
    request = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8") or "{}")


def post_form(answers: dict, photos: list[Path], art: str = "local") -> tuple[int, dict]:
    boundary = "----HSIYC" + uuid.uuid4().hex
    body = bytearray()

    def field(name: str, value: str) -> None:
        body.extend(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n"
            f"{value}\r\n".encode("utf-8")
        )

    field("answers", json.dumps(answers, ensure_ascii=False))
    field("repair_rounds", "1")
    # Default to the offline renderer here: the end-to-end test should be
    # reproducible and must not depend on the rationed image service.
    field("art", art)
    field("deck", "1")
    for photo in photos:
        mime = mimetypes.guess_type(photo.name)[0] or "application/octet-stream"
        body.extend(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"photos\"; "
            f"filename=\"{photo.name}\"\r\nContent-Type: {mime}\r\n\r\n".encode("utf-8")
        )
        body.extend(photo.read_bytes())
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    request = urllib.request.Request(
        BASE + "/api/generate-form",
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8") or "{}")


def main() -> int:
    print("1. server status")
    status = get_json("/api/status")
    print(f"   key={status['key_present']} corpus={status['corpus_size']} model={status['text_model']}")

    print("2. the form schema")
    schema = get_json("/api/form")
    total = sum(len(g["fields"]) for g in schema["groups"])
    print(f"   {total} questions in {len(schema['groups'])} groups, "
          f"{sum(1 for g in schema['groups'] for f in g['fields'] if f['required'])} required")

    print("3. validating an empty form (must be rejected)")
    code, payload = post_json("/api/form/validate", {"answers": {}})
    print(f"   HTTP {code} ok={payload.get('ok')} errors={len(payload.get('errors') or [])} "
          f"missing={len(payload.get('required_keys') or [])}")
    if payload.get("ok"):
        print("   FAIL: an empty form was accepted")
        return 1

    print("4. validating a complete form (must be accepted)")
    code, payload = post_json("/api/form/validate", {"answers": ANSWERS})
    print(f"   HTTP {code} ok={payload.get('ok')} warnings={payload.get('warnings')}")
    if not payload.get("ok"):
        print("   FAIL:", payload.get("errors"))
        return 1

    # The description box decides whether a rewrite is worth spending tokens on, so its
    # guard rails are checked here for free: a stub must be refused.
    print("4b. the description box (stub text must be refused without an API call)")
    code, payload = post_json("/api/develop", {"text": "hi"})
    print(f"   HTTP {code} error={payload.get('error')}")
    if code != 400:
        print("   FAIL: a stub description should be refused with HTTP 400")
        return 1

    photos = sorted((ROOT / "_work" / "webphotos").glob("*.png"))
    print(f"5. generating from the form with {len(photos)} photo(s)")
    code, payload = post_form(ANSWERS, photos)
    if code != 200:
        print(f"   FAIL: HTTP {code} {payload}")
        return 1
    job_id = payload["job_id"]
    print(f"   job {job_id}")

    started = time.time()
    state = {}
    while time.time() - started < 600:
        time.sleep(3)
        state = get_json(f"/api/job/{job_id}")
        if state.get("progress"):
            print(f"   [{time.time() - started:5.0f}s] {state['progress'][-1]}")
        if state.get("status") in ("done", "error"):
            break
    if state.get("status") != "done":
        print("   FAIL:", state.get("error"))
        return 1

    result = state["result"]
    check = result["check"]
    stats = check["stats"]
    print()
    print(f"   score        : {check['score']}/100 "
          f"({check['errors']} errors, {check['warnings']} warnings)")
    print(f"   title        : {result['article']['title']['cn']}")
    print(f"   sections     : {stats['sections']}")
    print(f"   CN chars     : {stats['chinese_characters']}")
    print(f"   CN:EN ratio  : {stats['cn_per_en_word']}")
    print(f"   photos       : {stats['photos_placed']}")
    print(f"   credits      : {stats['credit_roles_filled']}/6")
    print(f"   tokens/time  : {result['usage'].get('total_tokens')} / {result['usage'].get('elapsed_s')}s")
    print(f"   output       : {state['output_dir']}")

    # The brief must carry every name and figure the operator typed.
    brief = result.get("brief_text") or ""
    missing = [v for v in ("Enkhtur Yalalt", "Emil Aliyev", "Nazir Nayab", "Mohammed Mazen",
                           "卢锦章", "24 international students", "Court 3",
                           "ran on 20 December")
               if v not in brief]
    print(f"   brief carries every answer: {not missing}" + (f" (missing {missing})" if missing else ""))

    errors = [f for f in check["findings"] if f["severity"] == "error"]
    if errors:
        print("\n   errors:")
        for e in errors:
            print(f"     - {e['code']}: {e['message']}")
    findings = {f["code"] for f in check["findings"] if f["severity"] != "info"}
    invented = [c for c in findings if c in ("FACT-NAME", "FACT-NUMBER")]
    print(f"   invented-fact findings: {invented or 'none'}")

    # The 秀米 paste markup must arrive with the result, so the Copy button can work from a
    # plain click (fetching it inside the handler spends the user gesture first).
    pasted = result.get("xiumi_html") or ""
    problems = [bad for bad in ("class=", "<div", "<style", "http://") if bad in pasted]
    print(f"   秀米 paste markup: {len(pasted):,} chars, "
          f"{pasted.count('【照片待插入】')} photo slot(s), problems={problems or 'none'}")
    if not pasted or problems:
        print("   FAIL: the paste markup is missing or not paste-safe")
        return 1

    xiumi_file = Path(state["output_dir"]) / f"{Path(state['output_dir']).name}.xiumi.html"
    print(f"   xiumi file   : {'written' if xiumi_file.is_file() else 'MISSING'}")
    if not xiumi_file.is_file():
        print("   FAIL: the bundle has no .xiumi.html")
        return 1

    art = result.get("art") or {}
    assets = art.get("assets") or []
    # An artwork failure must fail this test. A swallowed artwork error plus a
    # manifest left on disk from an earlier run once made a broken pipeline look
    # like a clean pass, so both states are checked explicitly.
    if art.get("error"):
        print(f"   ARTWORK FAILED : {art['error']}")
        return 1
    if art.get("stale"):
        print("   ARTWORK STALE  : these assets are from an earlier run")
        return 1
    print(f"   artwork      : {len(assets)} asset(s), backend={art.get('backend')}, "
          f"vibe={(art.get('vibe') or {}).get('key')}/{(art.get('vibe') or {}).get('motif')}")
    kinds = sorted({a.get("kind", "") for a in assets})
    print(f"   art kinds    : {kinds or 'none'}")
    if assets:
        print(f"   art URL smoke: {assets[0].get('url')}")
        for asset in assets[:3]:
            url = str(asset.get("url") or "")
            if not url:
                continue
            try:
                with urllib.request.urlopen(BASE + url, timeout=30) as response:
                    size = len(response.read())
                print(f"     served {asset.get('file'):<18} HTTP {response.status} {size:,} bytes")
            except Exception as exc:
                print(f"     FAIL serving {asset.get('file')}: {type(exc).__name__}: {exc}")
                return 1
    return 0 if not invented and not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
