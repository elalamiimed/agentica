"""D2 (rigorous) + the phantom-numeral bug, on the REAL pipeline path."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hsiyc_writer import form, validate  # noqa: E402
from hsiyc_writer.validate import (  # noqa: E402
    STANDALONE_NUMBER_RE, _chinese_number_words, number_words,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_de_integration import ANSWERS, DESC, minimal_article  # noqa: E402


def check_like_pipeline(article: dict, brief: dict, brief_text: str = "") -> list[str]:
    """Reproduce pipeline._check's whitelist: brief + raw_notes(brief_text)."""
    brief_for_check = dict(brief or {})
    if brief_text:
        brief_for_check.setdefault("raw_notes", brief_text)
    report = validate.validate(copy.deepcopy(article), brief=brief_for_check)
    return [f.message for f in report.findings if f.code == "FACT-NUMBER"]


def main() -> int:
    print("################ D2: fabricated figure in the description box, REAL path")
    for number in ("137", "211"):
        answers = dict(ANSWERS)
        answers["event_description"] = DESC + f" {number} volunteers helped on the day."
        brief = form.answers_to_structured_brief(answers)
        brief_text = form.answers_to_brief(answers)
        findings = check_like_pipeline(minimal_article(number), brief, brief_text)
        hit = any(number in msg for msg in findings)
        print(f"  body says {number}; description says {number}: "
              f"FACT-NUMBER mentions it -> {hit}   ({findings or 'clean'})")

    answers = dict(ANSWERS)  # description unchanged: no 211 anywhere
    brief = form.answers_to_structured_brief(answers)
    brief_text = form.answers_to_brief(answers)
    findings = check_like_pipeline(minimal_article("211"), brief, brief_text)
    print(f"  body says 211; description does NOT:      "
          f"FACT-NUMBER mentions it -> {any('211' in m for m in findings)}   ({findings})")

    print("\n################ the phantom numeral: which characters do it?")
    probes = ["各位同学", "各位", "十分感谢", "五官", "一起", "一点", "两国", "三天",
              "四次", "六楼", "七折", "八方", "九州", "十字", "五分之一"]
    for t in probes:
        got = sorted(_chinese_number_words(t))
        if got:
            print(f"  {t:8} -> {got}   (STANDALONE digits: {sorted(STANDALONE_NUMBER_RE.findall(t))})")

    print("\n################ isolating the 4 and 6 in the test article")
    article = minimal_article("137")
    cn, en = validate.collect_texts(copy.deepcopy(article))
    cn_blob = "\n".join(cn)
    brief = form.answers_to_structured_brief(
        dict(ANSWERS, event_description=DESC + " 137 volunteers helped on the day."))
    brief_nums: set[str] = set()
    for value in validate._iter_scalars(brief):
        brief_nums |= set(STANDALONE_NUMBER_RE.findall(value)) | number_words(value)
    word_hits = {n for n in number_words(cn_blob) if n not in brief_nums}
    digit_hits = {n for n in STANDALONE_NUMBER_RE.findall(cn_blob) if n not in brief_nums}
    print(f"  digit numbers in body not in brief: {sorted(digit_hits)}")
    print(f"  WORD numbers in body not in brief : {sorted(word_hits)}")
    import re as _re
    for ch in ("四", "六", "五"):
        for m in _re.finditer(f"[零一二两三四五六七八九十百千万]*{ch}[零一二两三四五六七八九十百千万]*", cn_blob):
            if m.group(0):
                print(f"    {ch}: run {m.group(0)!r} -> {sorted(_chinese_number_words(m.group(0)))}  "
                      f"context ...{cn_blob[max(0,m.start()-6):m.end()+6]}...")
                break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
