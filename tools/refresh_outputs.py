"""Refresh the showcase output bundles with the current renderer and validator.

Run after changing the renderer or the rules so that the shipped previews, PDFs and
check reports are not stale:

    <python> tools/refresh_outputs.py [slug ...]
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hsiyc_writer import pdfout, render  # noqa: E402
from hsiyc_writer.retrieval import Corpus  # noqa: E402
from hsiyc_writer.validate import validate  # noqa: E402

OUTPUT = ROOT / "output"

# Refreshing the shipped bundles uses the offline renderer by default: it is
# deterministic, instant, and does not spend the rationed image service on
# showcase material. Set HSIYC_ART_BACKEND=auto to try the online model too.
ART_BACKEND = os.environ.get("HSIYC_ART_BACKEND", "local")


def refresh(slug: str, corpus: Corpus) -> None:
    folder = OUTPUT / slug
    article_path = folder / f"{slug}.json"
    if not article_path.is_file():
        print(f"  skip {slug}: no article JSON")
        return
    article = json.loads(article_path.read_text(encoding="utf-8"))
    media = {p.name: p for p in (folder / "media").glob("*") if p.is_file()}
    # Warnings describe the current state, so start from a clean slate.
    (folder / "render_warning.txt").unlink(missing_ok=True)

    # The brief the article was built from is stored in run_log.json, so the bundle
    # stays re-checkable: without it, every number and name would look unsourced.
    brief: dict | None = None
    run_log = folder / "run_log.json"
    if run_log.is_file():
        try:
            stored = json.loads(run_log.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            stored = {}
        brief = dict(stored.get("brief") or {})
        if stored.get("brief_text"):
            brief.setdefault("raw_notes", stored["brief_text"])
        brief = brief or None

    report = validate(
        article,
        brief=brief,
        expected_photos=sorted(media),
        corpus_texts=[doc.text for doc in corpus.docs],
        corpus_labels=[doc.slug for doc in corpus.docs],
    )
    # Artwork and the deck are part of the bundle too, so a refresh leaves the
    # shipped folder complete rather than half-updated.
    art_manifest = render.make_bundle_art(article, folder, brief=brief, backend=ART_BACKEND)

    (folder / "check_report.txt").write_text(report.text(), encoding="utf-8")
    (folder / "check_report.json").write_text(
        json.dumps(report.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (folder / f"{slug}.md").write_text(render.to_markdown(article, report), encoding="utf-8")
    (folder / f"{slug}.preview.html").write_text(
        render.to_html(article, report, media, art_manifest), encoding="utf-8"
    )
    (folder / f"{slug}.xiumi.html").write_text(render.to_xiumi_document(article), encoding="utf-8")
    (folder / f"{slug}.xiumi.md").write_text(render.to_xiumi_notes(article, slug), encoding="utf-8")
    render.write_xiumi_photos(article, folder, media)
    pdf_path = pdfout.write_article_pdf(article, folder / f"{slug}.pdf", media, None)
    render.write_deck(article, folder, slug, art=art_manifest, photos=media)
    vibe = (art_manifest or {}).get("vibe") or {}
    print(
        f"  {slug}: score {report.score}, {len(report.errors)} error(s), "
        f"{len(report.warnings)} warning(s), pdf {pdf_path.stat().st_size:,} bytes, "
        f"art {len((art_manifest or {}).get('assets', []))} x {vibe.get('key', 'none')}"
    )


def main(argv: list[str]) -> int:
    corpus = Corpus.load()
    slugs = argv or [d.name for d in sorted(OUTPUT.iterdir()) if d.is_dir()]
    if not slugs:
        print(f"no output bundles under {OUTPUT}")
        return 0
    print(f"refreshing {len(slugs)} bundle(s) with {len(corpus)} corpus article(s)")
    for slug in slugs:
        refresh(slug, corpus)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
