"""Build adversarial article variants for the HSIYC validator. Writes only into
_work/verification/adversarial/. Never touches output/ or hsiyc_writer/."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "output" / "apec-smart-campus-innovation-series-future-skills-challenge-recap" / \
    "apec-smart-campus-innovation-series-future-skills-challenge-recap.json"
OUT = ROOT / "_work" / "verification" / "adversarial"
OUT.mkdir(parents=True, exist_ok=True)

base = json.loads(BASE.read_text(encoding="utf-8"))


def dump(name, art):
    (OUT / f"{name}.json").write_text(json.dumps(art, ensure_ascii=False, indent=2), encoding="utf-8")


# ---- control: byte-identical copy of the shipped article
dump("case_E_control", base)

# ---- A: invented winner name (a person who appears in no brief at all)
a = json.loads(json.dumps(base))
a["sections"][3]["body"][1]["items"].append(
    {"label_cn": "特别奖", "label_en": "Special Prize",
     "value_cn": "王梓涵 Wang Zihan", "value_en": "王梓涵 Wang Zihan"}
)
dump("case_A_invented_winner", a)

# ---- B: a bilingual block whose English twin is missing
b = json.loads(json.dumps(base))
b["sections"][0]["body"][0].pop("en", None)
dump("case_B_missing_en", b)

# ---- C: credit block without 三审
c = json.loads(json.dumps(base))
c["credits"].pop("三审", None)
dump("case_C_no_final_review", c)

# ---- D: Chinese-only heading
d = json.loads(json.dumps(base))
d["sections"][1]["heading_en"] = ""
dump("case_D_cn_only_heading", d)

# ---- F: invented number declared in facts[] with a plausible source (self-sourced)
f = json.loads(json.dumps(base))
f["sections"][1]["body"][0]["cn"] = f["sections"][1]["body"][0]["cn"].replace(
    "32 名参赛者", "57 名参赛者")
f["sections"][1]["body"][0]["en"] = f["sections"][1]["body"][0]["en"].replace(
    "32 competitors", "57 competitors")
f["facts"].append({"fact": "预赛共有 57 名参赛者",
                   "source": "STRUCTURED BRIEF participants_count / RAW NOTES 参与人数"})
dump("case_F_invented_number_self_sourced", f)

# ---- G: same invented number, but NOT declared in facts[] (positive control)
g = json.loads(json.dumps(base))
g["sections"][1]["body"][0]["cn"] = g["sections"][1]["body"][0]["cn"].replace(
    "32 名参赛者", "57 名参赛者")
g["sections"][1]["body"][0]["en"] = g["sections"][1]["body"][0]["en"].replace(
    "32 competitors", "57 competitors")
dump("case_G_invented_number_undeclared", g)

# ---- H: invented venue (number change the brief cannot explain)
h = json.loads(json.dumps(base))
h["sections"][0]["body"][1]["cn"] = h["sections"][0]["body"][1]["cn"].replace("A509", "B201")
h["sections"][0]["body"][1]["en"] = h["sections"][0]["body"][1]["en"].replace("A509", "B201")
h["meta"]["venue"] = "哈工大（深圳）B201 教室"
dump("case_H_invented_venue", h)

# ---- sanity: weekday of the dates asserted in the briefs
from datetime import date
for iso in ("2026-03-28", "2026-03-20", "2026-11-08"):
    y, m, dd = map(int, iso.split("-"))
    print(iso, date(y, m, dd).strftime("%A"))
print("variants written:", sorted(p.name for p in OUT.glob("*.json")))
