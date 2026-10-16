"""Scratch: check the page JavaScript parses and the clipboard paths are wired."""
import pathlib
import re
import subprocess
import tempfile

NODE = r"C:\Users\hp\AppData\Local\Microsoft\WinGet\Packages\OpenJS.NodeJS.LTS_Microsoft.Winget.Source_8wekyb3d8bbwe\node-v24.14.1-win-x64\node.exe"

for page in sorted(pathlib.Path("hsiyc_writer/web").glob("*.html")):
    script = "\n;\n".join(re.findall(r"(?s)<script>(.*?)</script>", page.read_text(encoding="utf-8")))
    target = pathlib.Path(tempfile.gettempdir()) / (page.stem + ".check.js")
    target.write_text(script, encoding="utf-8")
    proc = subprocess.run([NODE, "--check", str(target)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    print(page.name, ":", "JS OK" if proc.returncode == 0 else "JS FAIL " + (proc.stdout + proc.stderr)[:400])

body = pathlib.Path("hsiyc_writer/web/form.html").read_text(encoding="utf-8")
for needle in ("copyViaSelection", "execCommand", "res.xiumi_html", "xiumiManual", "pastebox",
               "ClipboardItem", "Ctrl+A", "Copy for 秀米"):
    print(f"{needle:<18} present: {needle in body}")
