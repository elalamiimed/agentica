"""Does the word-number fix clear the false positive without weakening the rule?"""
import json
import pathlib
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from hsiyc_writer.retrieval import Corpus  # noqa: E402
from hsiyc_writer.validate import number_words, validate  # noqa: E402

print("=== the extractor ===")
for sample in ("a five-minute integral in under 90 seconds",
               "thirty-two contestants and 4 finalists",
               "about eighty audience members",
               "九十秒内解出五十分钟的题目",
               "三十二名参赛者，四名决赛选手",
               "there were no numbers here at all"):
    print(f"  {sample!r:52s} -> {sorted(number_words(sample), key=int)}")

corpus = Corpus.load()
texts = [d.text for d in corpus.docs]
labels = [d.slug for d in corpus.docs]

SLUG = "apec-smart-campus-future-skills-challenge-recap"
folder = pathlib.Path("output") / SLUG
article = json.loads((folder / f"{SLUG}.json").read_text(encoding="utf-8"))
brief = json.loads((folder / "run_log.json").read_text(encoding="utf-8")).get("brief") or {}

report = validate(article, brief=brief, expected_photos=[], require_toc=False,
                  corpus_texts=texts, corpus_labels=labels)
codes = [f.code for f in report.findings if f.severity == "error"]
print(f"\n=== the real bundle ===\n  score {report.score}/100, errors {len(report.errors)} -> {codes or 'none'}")

# A genuinely invented number must STILL be caught.
invented = json.loads(json.dumps(article))
invented["lead"]["cn"] = str(invented["lead"].get("cn", "")) + "共有 777 名选手参加。"
report2 = validate(invented, brief=brief, expected_photos=[], corpus_texts=texts, corpus_labels=labels)
found = [f.message for f in report2.findings if f.code == "FACT-NUMBER"]
print(f"=== invented 777 ===\n  {'CAUGHT (correct)' if found else 'MISSED - RULE WEAKENED'}")
if found:
    print("  " + found[0][:120])

# And it must not be possible to whitelist a number by declaring it in facts[].
laundered = json.loads(json.dumps(invented))  # built from `invented`: it must CONTAIN the 777
laundered["facts"] = [{"fact": "共有 777 名选手参加", "source": "model"}]
report3 = validate(laundered, brief=brief, expected_photos=[], corpus_texts=texts, corpus_labels=labels)
found3 = [f.message for f in report3.findings if f.code == "FACT-NUMBER"]
print(f"=== self-declared 777 ===\n  {'still CAUGHT (correct)' if found3 else 'MISSED - SELF-WHITELIST HOLE'}")

ok = not codes and bool(found) and bool(found3)
print("\nRESULT:", "PASS" if ok else "FAIL")
raise SystemExit(0 if ok else 1)
