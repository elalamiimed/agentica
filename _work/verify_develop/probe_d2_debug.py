"""D2 debug: where does the number whitelist for validate.validate come from?"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hsiyc_writer import form, validate  # noqa: E402
from hsiyc_writer.validate import _iter_scalars, number_words  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_de_integration import ANSWERS, DESC, minimal_article  # noqa: E402


def whitelist_numbers(brief: dict, credits: dict, meta: dict) -> tuple[set[str], dict[str, set[str]]]:
    out: set[str] = set()
    per: dict[str, set[str]] = {}
    for name, source in (("brief", brief), ("credits", {"credits": credits}),
                         ("meta", meta), ("meta_as_date", {"date": " ".join(_iter_scalars(meta))})):
        got: set[str] = set()
        for value in _iter_scalars(source):
            got |= set(validate.STANDALONE_NUMBER_RE.findall(value))
            got |= number_words(value)
        per[name] = got
        out |= got
    return out, per


def main() -> int:
    answers = dict(ANSWERS)
    answers["event_description"] = DESC + " 137 volunteers helped on the day."
    brief = form.answers_to_structured_brief(answers)
    article = minimal_article("137")
    credits = article["credits"]
    meta = article["meta"]

    total, per = whitelist_numbers(brief, credits, meta)
    print("whitelisted numbers, by source:")
    for name, got in per.items():
        print(f"  {name:14} {sorted(got)}")
    print(f"\nfull whitelist : {sorted(total)}")
    print(f"'137' whitelisted: {'137' in total}")
    print(f"'211' whitelisted: {'211' in total}")

    print("\nbody numbers:")
    cn, en = validate.collect_texts(copy.deepcopy(article))
    cn_blob, en_blob = "\n".join(cn), "\n".join(en).lower()
    body = set(validate.STANDALONE_NUMBER_RE.findall(cn_blob)) | set(
        validate.STANDALONE_NUMBER_RE.findall(en_blob))
    print(f"  {sorted(body)}")
    print(f"  unexplained: {sorted(body - total - {'1','2','3','01','02','03'})}")

    print("\nfull report codes:")
    report = validate.validate(copy.deepcopy(article), brief=brief)
    for f in report.sorted_findings():
        print(f"  [{f.severity}] {f.code}: {f.message[:110]}")

    print("\n--- control: description cleared from the brief ---")
    bare = dict(brief)
    bare["event_description"] = ""
    report = validate.validate(copy.deepcopy(article), brief=bare)
    for f in report.sorted_findings():
        if f.code.startswith("FACT"):
            print(f"  [{f.severity}] {f.code}: {f.message[:110]}")

    print("\n--- does the description alone whitelist 211 too? ---")
    answers2 = dict(ANSWERS)
    answers2["event_description"] = DESC + " 211 volunteers helped on the day."
    brief2 = form.answers_to_structured_brief(answers2)
    total2, _ = whitelist_numbers(brief2, credits, meta)
    print(f"  '211' whitelisted when the description says 211: {'211' in total2}")
    report2 = validate.validate(minimal_article("211"), brief=brief2)
    print("  FACT findings:", [f.message for f in report2.findings if f.code.startswith("FACT")])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
