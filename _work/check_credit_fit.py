"""Check the artwork disclaimer fits inside every asset width."""
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from hsiyc_writer.art import local, text as textmod  # noqa: E402

label = f"{local.CREDIT_CN} · {local.CREDIT_EN}"
font = textmod.load(12, bold=False)
needed = font.getlength(label)
print(f"disclaimer needs {needed:.0f}px at 12pt")
ok = True
for kind, (width, _height) in local.KIND_SIZES.items():
    if kind == "divider":          # dividers carry no credit line
        continue
    available = width * 0.90
    fits = needed <= available
    ok = ok and fits
    print(f"  {kind:8s} width {width:5d}  available {available:7.0f}px  "
          f"{'fits' if fits else 'TRUNCATED'}")
print("RESULT:", "PASS" if ok else "FAIL")
raise SystemExit(0 if ok else 1)
