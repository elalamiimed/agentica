"""Explain exactly where the 15 points went on the 85/100 bundle."""
import json
import pathlib
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

folder = pathlib.Path("output/apec-smart-campus-future-skills-challenge-recap")
report = json.loads((folder / "check_report.json").read_text(encoding="utf-8"))
weights = {"error": 14, "warning": 4, "info": 1}

print(f"score {report['score']}/100  ->  penalty {100 - report['score']}")
counts = {}
for finding in report["findings"]:
    counts[finding["severity"]] = counts.get(finding["severity"], 0) + 1
for severity, weight in weights.items():
    n = counts.get(severity, 0)
    if n:
        print(f"  {n} x {severity:8s} x {weight:2d} = {n * weight:3d}")

print("\nfindings:")
for finding in sorted(report["findings"], key=lambda f: weights[f["severity"]], reverse=True):
    print(f"  [{finding['severity']:7s} -{weights[finding['severity']]:2d}] {finding['code']}")
    print(f"      {finding['message'][:110]}")

print("\n=== is a rank/name MISATTRIBUTION checked? ===")
run_log = json.loads((folder / "run_log.json").read_text(encoding="utf-8"))
brief = run_log.get("brief") or {}
print("brief declares:")
for winner in brief.get("winners") or []:
    print(f"   {winner.get('rank_cn')}: {winner.get('names')}")
article = json.loads((folder / "apec-smart-campus-future-skills-challenge-recap.json").read_text(encoding="utf-8"))
print("article says:")
for section in article.get("sections") or []:
    for block in section.get("body") or []:
        if block.get("kind") != "list":
            continue
        for item in block.get("items") or []:
            print(f"   {item.get('label_cn')}: {item.get('value_cn')}")
