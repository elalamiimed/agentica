"""Exact evidence for the ordinary-word -> phantom-figure -> whitelist chain."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hsiyc_writer import validate  # noqa: E402
from hsiyc_writer.validate import _iter_scalars, number_words  # noqa: E402


def brief_numbers(brief: dict, credits: dict, meta: dict) -> set[str]:
    out: set[str] = set()
    for source in (brief, {"credits": credits}, meta):
        for value in _iter_scalars(source):
            out |= number_words(value)
    return out


CREDITS = {"文字": "Zhumabay Aruzhan", "图片": "Yalalt", "排版": "Najmia Popal",
           "一审": "Samin、柯炽炜", "二审": "周宣彤、崔雨旸、高容驷", "三审": "卢锦章"}
META = {"doc_type": "回顾", "date": "2026年11月8日"}

BASE = {"doc_type": "回顾", "title_cn": "活动回顾", "title_en": "Recap",
        "event_date": "2026年11月8日", "venue": "哈工大（深圳）A509 教室",
        "organisers": ["哈工大（深圳）国际青年俱乐部（HSIYC）"], "credits": CREDITS}

for label, description in (
    ("description with 五官 (facial features)", "活动在 A509 举行，五官精致的海报很受欢迎。"),
    ("description without it", "活动在 A509 举行，海报很受老欢迎。"),
    ("description with 十分感谢", "活动在 A509 举行，十分感谢各位同学的参与。"),
):
    brief = dict(BASE, event_description=description)
    nums = brief_numbers(brief, CREDITS, META)
    phantom = sorted(nums & {"1", "2", "3", "5", "10"})
    print(f"{label:44} whitelisted single digits: {phantom}")

print("\nSo: whichever digits an ordinary word happens to spell become whitelisted facts.")
print("FACT-NUMBER compares the body's DIGITS against that whitelist, so the phantom")
print("entries can absorb an invented digit of the same value in the body.")
for word, digit in (("五官", "5"), ("十分", "10"), ("Two of us", "2")):
    nums = brief_numbers(dict(BASE, event_description=f"活动在 A509 举行，{word}。"), CREDITS, META)
    print(f"  brief word {word!r} -> whitelist contains {digit!r}: {digit in nums}")
