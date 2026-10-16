"""English ordinary words that number_words() reads as figures, and the masking they cause."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hsiyc_writer import validate  # noqa: E402
from hsiyc_writer.validate import number_words  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_phantom_lenvalid import article  # noqa: E402

print("### ordinary English / Chinese words read as numbers")
for text in ["one of the members", "no one came", "two of us", "the first one",
             "for one thing", "two to three people", "各位同学", "五官", "十分感谢"]:
    print(f"  {text!r:26} -> {sorted(number_words(text))}")

print("\n### masking check: does 'one' in the brief whitelist an invented 1?")
brief = {
    "doc_type": "回顾", "title_cn": "活动回顾", "title_en": "Recap",
    "event_date": "2026年11月8日", "venue": "哈工大（深圳）A509 教室",
    "organisers": ["哈工大（深圳）国际青年俱乐部（HSIYC）"],
    "participants_count": "32 名选手",
    "event_description": "The first round happened in A509. One of the members brought the banner.",
    "credits": {"文字": "Zhumabay Aruzhan", "图片": "Yalalt", "排版": "Najmia Popal",
                "一审": "Samin、柯炽炜", "二审": "周宣彤、崔雨旸、高容驷", "三审": "卢锦章"},
}
art = article("哈工大（深圳）国际青年俱乐部 HSIYC 在 A509 举办活动，共 1 名选手参赛，气氛热烈。")
rep = validate.validate(copy.deepcopy(art), brief=copy.deepcopy(brief))
msgs = [f.message for f in rep.findings if f.code == "FACT-NUMBER"]
print(f"  body says '1 名选手' (invented); brief says 'One of the members'")
print(f"  FACT-NUMBER -> {msgs[0] if msgs else 'NONE - the invented 1 passes'}")

brief2 = copy.deepcopy(brief)
brief2["event_description"] = "The first round happened in A509. A member brought the banner."
rep2 = validate.validate(copy.deepcopy(art), brief=copy.deepcopy(brief2))
msgs2 = [f.message for f in rep2.findings if f.code == "FACT-NUMBER"]
print(f"  control (no 'One ...' in the brief) -> {msgs2[0] if msgs2 else 'NONE'}")
