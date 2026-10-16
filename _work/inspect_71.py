"""Inspect the 71/100 bundle: the unsourced number and the verbatim sentence."""
import json
import pathlib
import re
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

SLUG = "apec-smart-campus-future-skills-challenge-recap"
folder = pathlib.Path("output") / SLUG
article = json.loads((folder / f"{SLUG}.json").read_text(encoding="utf-8"))
run_log = json.loads((folder / "run_log.json").read_text(encoding="utf-8"))
brief = run_log.get("brief") or {}

print("=== the brief's numbers and names ===")
for key in ("participants_count", "winners", "judges", "highlights", "programme"):
    value = brief.get(key)
    if value:
        print(f"  {key}: {value}")
print("  brief_text numbers:", sorted(set(re.findall(r"\d+", run_log.get("brief_text") or ""))))

print("\n=== every numeral in the body, with context ===")
for section in article.get("sections") or []:
    for block in section.get("body") or []:
        text = str(block.get("cn") or "")
        for match in re.finditer(r"\d+", text):
            start = max(0, match.start() - 40)
            print(f"  [{section.get('number')}] ...{text[start:match.end() + 30]}...")

print("\n=== the two similarity findings, in the article ===")
report = json.loads((folder / "check_report.json").read_text(encoding="utf-8"))
for finding in report.get("findings", []):
    if finding.get("code") == "SIMILARITY":
        print(f"  {finding.get('message')[:150]}")
