"""Would the check catch a swapped winner? That is the error that gets an article returned."""
import copy
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

folder = pathlib.Path("output/apec-smart-campus-future-skills-challenge-recap")
article = json.loads((folder / "apec-smart-campus-future-skills-challenge-recap.json").read_text(encoding="utf-8"))
brief = json.loads((folder / "run_log.json").read_text(encoding="utf-8")).get("brief") or {}


def codes_for(candidate):
    report = validate(candidate, brief=brief, expected_photos=[], corpus_texts=texts, corpus_labels=labels)
    return report, [f.code for f in report.findings if f.severity != "info"]


# 1. baseline
report, codes = codes_for(copy.deepcopy(article))
print(f"baseline            : score {report.score}, findings {codes}")

# 2. swap the champion and the runner-up
swapped = copy.deepcopy(article)
for section in swapped["sections"]:
    for block in section["body"]:
        if block.get("kind") != "list":
            continue
        items = block.get("items") or []
        if len(items) >= 2:
            items[0]["value_cn"], items[1]["value_cn"] = items[1]["value_cn"], items[0]["value_cn"]
            items[0]["value_en"], items[1]["value_en"] = items[1]["value_en"], items[0]["value_en"]
report, codes = codes_for(swapped)
print(f"champion/runner swap: score {report.score}, findings {codes}")

# 3. put a person on the wrong rank entirely
moved = copy.deepcopy(article)
for section in moved["sections"]:
    for block in section["body"]:
        if block.get("kind") != "list":
            continue
        items = block.get("items") or []
        if len(items) >= 4:
            items[0]["value_cn"] = items[3]["value_cn"]      # 4th place now holds gold
            items[3]["value_cn"] = "Tugsuu Rentsennatsag"
report, codes = codes_for(moved)
print(f"gold to 4th place   : score {report.score}, findings {codes}")

# 4. invent a brand-new winner
invented = copy.deepcopy(article)
for section in invented["sections"]:
    for block in section["body"]:
        if block.get("kind") != "list":
            continue
        items = block.get("items") or []
        if items:
            items[-1]["value_cn"] = "李明轩"
            items[-1]["value_en"] = "Li Mingxuan"
report, codes = codes_for(invented)
print(f"invented 4th winner : score {report.score}, findings {codes}")
