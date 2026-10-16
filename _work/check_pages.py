"""Parse-check the inline JavaScript in the served pages (no browser needed)."""
import pathlib
import re
import subprocess
import sys
import tempfile

NODE = r"C:\Users\hp\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe"
status = 0
for page in ("hsiyc_writer/web/form.html", "hsiyc_writer/web/index.html",
             "hsiyc_writer/web/gallery.html"):
    html = pathlib.Path(page).read_text(encoding="utf-8")
    blocks = re.findall(r"<script[^>]*>(.*?)</script>", html, re.S)
    print(f"{page}: {len(blocks)} script block(s)")
    for index, block in enumerate(blocks):
        with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, encoding="utf-8") as handle:
            handle.write(block)
            path = handle.name
        proc = subprocess.run([NODE, "--check", path], capture_output=True, text=True)
        if proc.returncode == 0:
            print(f"   block {index}: syntax OK ({len(block):,} chars)")
        else:
            status = 1
            print(f"   block {index}: SYNTAX ERROR")
            print("   " + (proc.stderr or "").strip().replace("\n", "\n   ")[:600])

    # The artwork UI must actually be wired up, not merely present in CSS.
    for needle in ("art_backends", "$('art')", "fd.append('art'", "res.art", "fd.append('deck'"):
        if needle in html:
            print(f"   wired: {needle}")
        elif page.endswith("form.html"):
            status = 1
            print(f"   MISSING WIRING: {needle}")

raise SystemExit(status)
