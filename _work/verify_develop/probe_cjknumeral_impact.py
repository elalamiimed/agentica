"""CJK numeral words: (a) false positive in develop.unsourced, (b) whitelist masking in validate."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hsiyc_writer import develop, validate  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_phantom_lenvalid import BRIEF, article  # noqa: E402

print("### (a) develop.unsourced: 五官 in the rewrite is read as the figure 5")
src = "活动现场气氛热烈，同学们同场竞技。"
rw = "活动现场气氛热烈，五官精致的海报很受欢迎，同学们同场竞技。"
print(f"  source : {src!r}")
print(f"  rewrite: {rw!r}")
print(f"  unsourced -> {develop.unsourced(rw, src)}")

print("\n### (b) validate: a brief containing 五官 whitelists the invented digit 5")
brief = copy.deepcopy(BRIEF)
brief["event_description"] = "活动在 A509 举行，五官精致的海报很受欢迎。"
brief.pop("participants_count", None)
art = article("哈工大（深圳）国际青年俱乐部 HSIYC 在 A509 举办活动，共 5 名选手参赛，气氛热烈。")
rep = validate.validate(copy.deepcopy(art), brief=copy.deepcopy(brief))
nums = [f.message for f in rep.findings if f.code == "FACT-NUMBER"]
print(f"  body says '5 名选手'; the brief never contains the figure 5 (only 五官)")
print(f"  FACT-NUMBER -> {nums[0] if nums else 'NONE - the invented 5 passes'}")

print("\n  control: same brief, 五官 removed")
brief2 = copy.deepcopy(brief)
brief2["event_description"] = "活动在 A509 举行，海报很受欢迎。"
rep2 = validate.validate(copy.deepcopy(art), brief=copy.deepcopy(brief2))
nums2 = [f.message for f in rep2.findings if f.code == "FACT-NUMBER"]
print(f"  FACT-NUMBER -> {nums2[0] if nums2 else 'NONE'}")

print("\n### (c) the same masking with other ordinary words")
for word, digit in (("十分感谢各位同学", "10"), ("三天", "3"), ("一起", "1")):
    b = copy.deepcopy(BRIEF)
    b["event_description"] = f"活动在 A509 举行，{word}。"
    b.pop("participants_count", None)
    a = article(f"哈工大（深圳）国际青年俱乐部 HSIYC 在 A509 举办活动，共 {digit} 名选手参赛，气氛热烈。")
    r = validate.validate(copy.deepcopy(a), brief=copy.deepcopy(b))
    msgs = [f.message for f in r.findings if f.code == "FACT-NUMBER"]
    verdict = "passes (masked)" if not any(digit in m for m in msgs) else "caught"
    print(f"  brief word {word!r} -> invented digit {digit}: {verdict}   {msgs}")
