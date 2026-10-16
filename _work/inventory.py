"""Inventory the shipped bundles: which files, how much artwork, which vibe."""
import json
import pathlib
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

root = pathlib.Path("output")
for folder in sorted(p for p in root.iterdir() if p.is_dir()):
    files = {p.suffix for p in folder.iterdir() if p.is_file()}
    manifest_path = folder / "art" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    vibe = (manifest.get("vibe") or {}).get("key", "-")
    motif = (manifest.get("vibe") or {}).get("motif", "-")
    assets = manifest.get("assets", [])
    pdf = next(folder.glob("*.pdf"), None)
    print("  %-46s pptx=%-5s art=%2d  %-12s %-10s %-9s pdf=%s" % (
        folder.name[:46],
        ".pptx" in files,
        len(assets),
        vibe,
        motif,
        manifest.get("backend", "-"),
        f"{pdf.stat().st_size:,}B" if pdf else "-",
    ))
