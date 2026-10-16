"""1) Measure the shipped + fresh articles against the corpus style bands.
2) Reproduce the real render path WITH the validator report attached (as pipeline.py does).
3) Render an article with a 4-photo block to expose the photo layout."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "_work" / "verification"
(OUT / "pdf").mkdir(parents=True, exist_ok=True)

CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
ENW = re.compile(r"[A-Za-z][A-Za-z'’-]*")

APEC = ROOT / "output" / "apec-smart-campus-innovation-series-future-skills-challenge-recap" / \
    "apec-smart-campus-innovation-series-future-skills-challenge-recap.json"
FRESH = next(p for p in (OUT / "gen").glob("*/*.json") if p.name != "check_report.json")


def metrics(path, label):
    art = json.loads(path.read_text(encoding="utf-8"))
    cn_parts, en_parts, blocks_cn, blocks_cn_no_en = [], [], 0, 0
    for s in art.get("sections") or []:
        for b in s.get("body") or []:
            if b.get("kind") == "bilingual":
                if b.get("cn"):
                    blocks_cn += 1
                    cn_parts.append(b["cn"])
                    if not b.get("en"):
                        blocks_cn_no_en += 1
                if b.get("en"):
                    en_parts.append(b["en"])
            for it in b.get("items") or []:
                cn_parts.append(str(it.get("value_cn", "")) + str(it.get("label_cn", "")))
                en_parts.append(str(it.get("value_en", "")) + str(it.get("label_en", "")))
        cn_parts.append(str(s.get("heading_cn", "")))
        en_parts.append(str(s.get("heading_en", "")))
    lead, clos = art.get("lead") or {}, art.get("closing") or {}
    cn_parts += [lead.get("cn", ""), clos.get("cn", ""), clos.get("tagline_cn", "")]
    en_parts += [lead.get("en", ""), clos.get("en", ""), clos.get("tagline_en", "")]
    cn_chars = sum(len(CJK.findall(p)) for p in cn_parts)
    en_words = sum(len(ENW.findall(p)) for p in en_parts)
    secs = art.get("sections") or []
    headings = len(secs)
    no_en_head = [i + 1 for i, s in enumerate(secs) if not str(s.get("heading_en", "")).strip()]
    creds = art.get("credits") or {}
    print(f"--- {label}  ({path.name})")
    print(f"    sections/headings : {headings}          (corpus 4-24, median 11)")
    print(f"    CN chars (body)   : {cn_chars}         (corpus 305-2261, median 860; target 700-1400)")
    print(f"    EN words          : {en_words}")
    print(f"    CN:EN ratio       : {cn_chars/en_words:.2f}   (corpus 1.18-2.26, median 1.79)")
    print(f"    CN blocks w/o EN  : {blocks_cn_no_en} of {blocks_cn}")
    print(f"    headings w/o EN   : {no_en_head or 'none'}")
    print(f"    credit roles      : {list(creds.keys())}")
    print(f"    facts declared    : {len(art.get('facts') or [])}")
    print(f"    needs_editor      : {len(art.get('needs_editor') or [])}")
    print(f"    meta.model        : {art.get('meta', {}).get('model')!r}   "
          f"meta.generated_at: {art.get('meta', {}).get('generated_at')!r}")
    return art


apec = metrics(APEC, "Lead's shipped APEC article")
fresh = metrics(FRESH, "My fresh 招募 article")

# ---- does the article carry facts that are NOT in the operator brief?
brief = (ROOT / "examples" / "brief_apec_future_skills.md").read_text(encoding="utf-8")
cn_body = " ".join(
    [apec["lead"]["cn"], apec["closing"]["cn"], apec["closing"].get("tagline_cn", "")]
    + [b.get("cn", "") for s in apec["sections"] for b in s["body"]]
)
print("\n--- corpus-derived phrases present in the shipped body but absent from its brief")
for phrase in ["三场独立竞赛", "三场赛事", "创新、合作、开放", "亚太共同体", "首场赛事", "首场竞赛"]:
    print(f"    {phrase!r:18} in brief={phrase in brief}   in article body={phrase in cn_body}")

# ---- render exactly as pipeline.py does: report attached
from hsiyc_writer import validate  # noqa: E402
from hsiyc_writer.pdfout import write_article_pdf  # noqa: E402
from hsiyc_writer.retrieval import Corpus  # noqa: E402

corpus = Corpus.load()
report = validate.validate(
    apec,
    brief={"raw_notes": brief},
    corpus_texts=[d.text for d in corpus.docs],
    corpus_labels=[d.slug for d in corpus.docs],
)
print(f"\nreproduced report: score {report.score}, {len(report.errors)} errors, {len(report.warnings)} warnings")
p = write_article_pdf(apec, OUT / "pdf" / "apec_with_report.pdf", {}, report)
print("wrote", p.name, p.stat().st_size, "bytes")

# ---- 4-photo block: the layout the renderer picks for >1 photo
grid = json.loads(json.dumps(apec))
tiles = [{"file": f"photo-{i}.jpg", "caption_cn": f"现场照片 {i}", "caption_en": f"Photo {i}"}
         for i in range(1, 5)]
grid["sections"][1]["body"].append(
    {"kind": "photo_grid", "photos": tiles, "layout": "2x2",
     "cn": "左右滑动查看更多", "en": "slide right for more pictures"}
)
p2 = write_article_pdf(grid, OUT / "pdf" / "grid4.pdf", {}, None)
print("wrote", p2.name, p2.stat().st_size, "bytes")
