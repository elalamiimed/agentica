"""Final state check: server, test suite contents, and bundle scores."""
import json
import pathlib
import re
import sys
import urllib.request

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

try:
    status = json.loads(urllib.request.urlopen("http://127.0.0.1:8765/api/status", timeout=10).read())
    art = status.get("art") or {}
    print(f"server : UP http://127.0.0.1:8765 | corpus {status['corpus_size']} | art.local {art.get('local')}")
except Exception as exc:
    print(f"server : DOWN ({type(exc).__name__})")

source = pathlib.Path("hsiyc_writer/cli.py").read_text(encoding="utf-8")
match = re.search(r"tests = \[(.*?)\]", source, re.S)
names = re.findall(r'"([^"]+)"', match.group(1))
print(f"tests  : {len(names)} files -> {', '.join(names)}")

print("bundles:")
errors_total = 0
for folder in sorted(p for p in pathlib.Path("output").iterdir() if p.is_dir()):
    report_path = folder / "check_report.json"
    if not report_path.is_file():
        print(f"  {folder.name[:44]:44s} (no check report)")
        continue
    report = json.loads(report_path.read_text(encoding="utf-8"))
    errors_total += int(report.get("errors", 0))
    warnings = report.get("warnings", 0)
    print(f"  {folder.name[:44]:44s} {report.get('score')}/100  errors={report.get('errors')} warnings={warnings}")
print(f"total errors across bundles: {errors_total}")
