"""Check the 谢指导 fix: the false positive goes, the true positive stays."""
import json
import pathlib
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from hsiyc_writer.retrieval import Corpus
from hsiyc_writer.validate import validate

corpus = Corpus.load()
corpus_texts = [d.text for d in corpus.docs]
corpus_labels = [d.slug for d in corpus.docs]

# 1. The real bundle that was blocked.
folder = pathlib.Path("output/hsiyc-committee-meeting-and-dinner-2026")
article = json.loads((folder / "hsiyc-committee-meeting-and-dinner-2026.json").read_text(encoding="utf-8"))
run_log = json.loads((folder / "run_log.json").read_text(encoding="utf-8"))
brief = run_log.get("brief") or {}
report = validate(article, brief=brief, expected_photos=[], require_toc=False,
                  corpus_texts=corpus_texts, corpus_labels=corpus_labels)
codes = [f.code for f in report.findings if f.severity == "error"]
print(f"1. real bundle          : score {report.score}, errors {len(report.errors)} -> {codes or 'none'}")
print(f"   (was: FACT-NAME 谢指导)")

# 2. The exact sentence, isolated, in a minimal article.
minimal = {
    "meta": {"doc_type": "回顾", "slug": "t", "event_date": "2026-10-14", "venue": "X"},
    "title": {"cn": "测试", "en": "Test"},
    "lead": {"cn": "感谢指导老师对本次会议的精心组织。", "en": "Thanks to the guiding teachers."},
    "sections": [{"number": "01", "heading_cn": "致谢", "heading_en": "Thanks",
                  "body": [{"kind": "bilingual", "cn": "感谢指导老师与各位评委老师的付出。",
                            "en": "Thanks to the guiding teachers and judges."}]}],
    "closing": {"cn": "结束语。", "en": "End."},
    "credits": {}, "signoff": {"cn": "HSIYC", "en": "HSIYC"},
}
report2 = validate(minimal, brief={}, expected_photos=[], corpus_texts=corpus_texts,
                   corpus_labels=corpus_labels)
found2 = [f.message for f in report2.findings if f.code == "FACT-NAME"]
print(f"2. isolated 感谢指导老师 : FACT-NAME -> {found2 or 'none (correct)'}")

# 3. A genuinely fabricated name must STILL be caught - the detector is not blinded.
fabricated = json.loads(json.dumps(minimal))
fabricated["sections"][0]["body"][0]["cn"] = "本次会议由谢昊轩老师主持，取得了圆满成功。"
report3 = validate(fabricated, brief={}, expected_photos=[], corpus_texts=corpus_texts,
                   corpus_labels=corpus_labels)
found3 = [f.message for f in report3.findings if f.code == "FACT-NAME"]
print(f"3. fabricated 谢昊轩老师 : FACT-NAME -> {'CAUGHT (correct)' if found3 else 'MISSED - DETECTOR BLINDED'}")

# 4. A real name that IS in the brief must stay clean.
known = json.loads(json.dumps(minimal))
known["sections"][0]["body"][0]["cn"] = "感谢凌怡老师对本次会议的精心组织。"
report4 = validate(known, brief={"judges": ["凌怡"]}, expected_photos=[],
                   corpus_texts=corpus_texts, corpus_labels=corpus_labels)
found4 = [f.message for f in report4.findings if f.code == "FACT-NAME"]
print(f"4. known 感谢凌怡老师   : FACT-NAME -> {found4 or 'none (correct)'}")

ok = (not codes) and (not found2) and bool(found3) and (not found4)
print("\nRESULT:", "PASS - false positive fixed, true positives intact" if ok else "FAIL")
raise SystemExit(0 if ok else 1)
