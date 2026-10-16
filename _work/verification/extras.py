"""Extras: (1) venue change without doctoring meta, (2) render the shipped APEC
article to PDF with the real renderer so its layout/photos can be inspected.
Writes only into _work/verification/."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "_work" / "verification"
ADV = OUT / "adversarial"
BASE = ROOT / "output" / "apec-smart-campus-innovation-series-future-skills-challenge-recap" / \
    "apec-smart-campus-innovation-series-future-skills-challenge-recap.json"

base = json.loads(BASE.read_text(encoding="utf-8"))

# H2: invented venue in the body only; meta left honest
h2 = json.loads(json.dumps(base))
h2["sections"][0]["body"][1]["cn"] = h2["sections"][0]["body"][1]["cn"].replace("A509", "B201")
h2["sections"][0]["body"][1]["en"] = h2["sections"][0]["body"][1]["en"].replace("A509", "B201")
(ADV / "case_H2_invented_venue_bodyonly.json").write_text(
    json.dumps(h2, ensure_ascii=False, indent=2), encoding="utf-8")

# I: invented judge / person name with no digits anywhere
i = json.loads(json.dumps(base))
i["sections"][3]["body"][0]["cn"] = i["sections"][3]["body"][0]["cn"].replace(
    "凌怡老师", "欧阳明德老师")
i["sections"][3]["body"][0]["en"] = i["sections"][3]["body"][0]["en"].replace(
    "Professor Ling", "Professor Ouyang")
(ADV / "case_I_invented_person.json").write_text(
    json.dumps(i, ensure_ascii=False, indent=2), encoding="utf-8")

# render the shipped APEC article with the real engine, into our own tree
from hsiyc_writer.pdfout import write_article_pdf  # noqa: E402

(OUT / "pdf").mkdir(parents=True, exist_ok=True)
p = write_article_pdf(base, OUT / "pdf" / "apec_shipped_render.pdf", {}, None)
print("rendered:", p, p.stat().st_size, "bytes")
