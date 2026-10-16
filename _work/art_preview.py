"""Render local artwork for several real bundles and print the vibe decisions."""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hsiyc_writer.art import capabilities, make_art, vibe_for  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "_work" / "art_preview"

print("capabilities:", json.dumps({k: v for k, v in capabilities().items() if k != "remote"},
                                  ensure_ascii=False)[:400])
print()

wanted = [
    "hsiyc-photography-workshop-recap-2026",
    "hsiyc-winter-badminton-friendly-recap",
    "world-culture-night-2026",
    "hsiyc-final-exam-study-support-workshop",
]
for slug in wanted:
    bundle = ROOT / "output" / slug
    article_path = bundle / f"{slug}.json"
    if not article_path.is_file():
        print(f"!! missing {article_path}")
        continue
    article = json.loads(article_path.read_text(encoding="utf-8"))
    brief = None
    log = bundle / "run_log.json"
    if log.is_file():
        brief = json.loads(log.read_text(encoding="utf-8")).get("brief")
    vibe, evidence = vibe_for(article, brief)
    print(f"== {slug}")
    print(f"   vibe    : {vibe.key} / {vibe.label_cn} / motif={vibe.motif} / tone={evidence['tone']}")
    print(f"   matched : {evidence['matched_keywords']}  (score {evidence['score']})")
    manifest = make_art(article, OUT / slug, brief=brief, backend="local")
    print(f"   assets  : {len(manifest['assets'])} -> {[a['file'] for a in manifest['assets']][:6]}")
    print(f"   notes   : {manifest['notes']}")
print("\ndone ->", OUT)
