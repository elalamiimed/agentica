"""False-positive check: FACT-RANK must stay silent on every correct bundle."""
import json
import pathlib
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from hsiyc_writer.retrieval import Corpus  # noqa: E402
from hsiyc_writer.validate import validate  # noqa: E402

corpus = Corpus.load()
texts = [d.text for d in corpus.docs]
labels = [d.slug for d in corpus.docs]

fired = 0
print("bundle                                          score  FACT-RANK  errors")
for folder in sorted(p for p in pathlib.Path("output").iterdir() if p.is_dir()):
    slug = folder.name
    article_path = folder / f"{slug}.json"
    if not article_path.is_file():
        continue
    article = json.loads(article_path.read_text(encoding="utf-8"))
    brief = None
    log = folder / "run_log.json"
    if log.is_file():
        stored = json.loads(log.read_text(encoding="utf-8"))
        # Exactly what tools/refresh_outputs.py does: the raw notes are part of the
        # material the article was built from, so they whitelist numbers too.
        brief = dict(stored.get("brief") or {})
        if stored.get("brief_text"):
            brief.setdefault("raw_notes", stored["brief_text"])
        brief = brief or None
    media = {p.name: p for p in (folder / "media").glob("*") if p.is_file()} if (folder / "media").is_dir() else {}
    report = validate(article, brief=brief, expected_photos=sorted(media),
                      corpus_texts=texts, corpus_labels=labels)
    rank = [f for f in report.findings if f.code == "FACT-RANK"]
    fired += len(rank)
    print("%-46s %5d  %9d  %6d" % (slug[:46], report.score, len(rank), len(report.errors)))
    for finding in rank:
        print("      " + finding.message[:120])

print(f"\nFACT-RANK findings on correct bundles: {fired}")
print("RESULT:", "PASS - no false positives" if fired == 0 else "FAIL - the new rule blocks good articles")
raise SystemExit(0 if fired == 0 else 1)
