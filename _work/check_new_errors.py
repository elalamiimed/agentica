"""What is the error my probe reports on two bundles that their stored report calls clean?"""
import json
import pathlib
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from hsiyc_writer.retrieval import Corpus  # noqa: E402
from hsiyc_writer.validate import validate  # noqa: E402

corpus = Corpus.load()
texts = [d.text for d in corpus.docs]
labels = [d.slug for d in corpus.docs]

for slug in ("hsiyc-final-exam-study-support-workshop", "hsiyc-photography-workshop-recap-2026"):
    folder = pathlib.Path("output") / slug
    article = json.loads((folder / f"{slug}.json").read_text(encoding="utf-8"))
    brief = json.loads((folder / "run_log.json").read_text(encoding="utf-8")).get("brief")
    media = sorted(p.name for p in (folder / "media").glob("*") if p.is_file())

    stored = json.loads((folder / "check_report.json").read_text(encoding="utf-8"))
    fresh = validate(article, brief=brief, expected_photos=media, corpus_texts=texts, corpus_labels=labels)

    print(f"=== {slug}")
    print(f"  stored: {stored['score']}/100 errors={stored['errors']}  media={len(media)}")
    print(f"  fresh : {fresh.score}/100 errors={len(fresh.errors)}  media={len(media)}")
    for finding in fresh.findings:
        if finding.severity == "error":
            print(f"    ERROR {finding.code}: {finding.message[:150]}")
    stored_codes = {f['code'] for f in stored['findings'] if f['severity'] == 'error'}
    fresh_codes = {f.code for f in fresh.findings if f.severity == 'error'}
    print(f"    stored error codes: {stored_codes or 'none'}")
    print(f"    fresh  error codes: {fresh_codes or 'none'}")
