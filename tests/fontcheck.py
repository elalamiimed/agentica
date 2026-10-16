"""Extract the font actually embedded in a generated PDF and prove it renders correctly.

This is the authoritative test: it reads /FontFile2 out of the PDF byte stream,
parses it as a real TrueType font, and verifies for every character in the source
article that the font maps it to a glyph whose outline is byte-identical to the
original Windows font's outline.
"""

from __future__ import annotations

import re
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hsiyc_writer import pdfout  # noqa: E402


def parse_sfnt(blob: bytes) -> dict[str, bytes]:
    num = int.from_bytes(blob[4:6], "big")
    out: dict[str, bytes] = {}
    for i in range(num):
        rec = 12 + 16 * i
        tag = blob[rec : rec + 4].decode("latin-1")
        off = int.from_bytes(blob[rec + 8 : rec + 12], "big")
        length = int.from_bytes(blob[rec + 12 : rec + 16], "big")
        out[tag] = blob[off : off + length]
    return out


def read_loca(head: bytes, loca: bytes, num_glyphs: int) -> list[int]:
    long_format = int.from_bytes(head[50:52], "big")
    if long_format:
        return [int.from_bytes(loca[4 * i : 4 * i + 4], "big") for i in range(num_glyphs + 1)]
    return [int.from_bytes(loca[2 * i : 2 * i + 2], "big") * 2 for i in range(num_glyphs + 1)]


def cmap4_lookup(cmap: bytes, code: int) -> int:
    """Format 4 lookup, following the spec layout exactly."""
    num = int.from_bytes(cmap[2:4], "big")
    sub = None
    for i in range(num):
        rec = 4 + 8 * i
        platform = int.from_bytes(cmap[rec : rec + 2], "big")
        encoding = int.from_bytes(cmap[rec + 2 : rec + 4], "big")
        if (platform, encoding) in ((3, 1), (3, 10), (0, 3), (0, 4)):
            sub = int.from_bytes(cmap[rec + 4 : rec + 8], "big")
            break
    if sub is None or int.from_bytes(cmap[sub : sub + 2], "big") != 4:
        return 0
    seg_x2 = int.from_bytes(cmap[sub + 6 : sub + 8], "big")
    seg = seg_x2 // 2
    end_base = sub + 14
    start_base = end_base + seg_x2 + 2  # +2 for reservedPad
    delta_base = start_base + seg_x2
    range_base = delta_base + seg_x2
    for i in range(seg):
        end = int.from_bytes(cmap[end_base + 2 * i : end_base + 2 * i + 2], "big")
        if code > end:
            continue
        start = int.from_bytes(cmap[start_base + 2 * i : start_base + 2 * i + 2], "big")
        if code < start:
            return 0
        delta = int.from_bytes(cmap[delta_base + 2 * i : delta_base + 2 * i + 2], "big", signed=True)
        ro = int.from_bytes(cmap[range_base + 2 * i : range_base + 2 * i + 2], "big")
        if ro == 0:
            return (code + delta) & 0xFFFF
        addr = range_base + 2 * i + ro + 2 * (code - start)
        gid = int.from_bytes(cmap[addr : addr + 2], "big")
        return (gid + delta) & 0xFFFF if gid else 0
    return 0


def embedded_font(pdf: bytes) -> bytes | None:
    match = re.search(rb"/FontFile2 (\d+) 0 R", pdf)
    if not match:
        return None
    want = int(match.group(1))
    for obj in re.finditer(rb"(\d+) 0 obj\n<<([^\n]*)>>\nstream\n", pdf):
        if int(obj.group(1)) != want:
            continue
        head = obj.group(2)
        length = re.search(rb"/Length (\d+)", head)
        if not length:
            return None
        raw = pdf[obj.end() : obj.end() + int(length.group(1))]
        return zlib.decompress(raw) if b"FlateDecode" in head else raw
    return None


def stream_of(pdf: bytes, obj_num: int) -> bytes | None:
    for obj in re.finditer(rb"(\d+) 0 obj\n<<([^\n]*)>>\nstream\n", pdf):
        if int(obj.group(1)) != obj_num:
            continue
        head = obj.group(2)
        length = re.search(rb"/Length (\d+)", head)
        if not length:
            return None
        raw = pdf[obj.end() : obj.end() + int(length.group(1))]
        return zlib.decompress(raw) if b"FlateDecode" in head else raw
    return None


def parse_to_unicode(pdf: bytes) -> dict[int, int]:
    """CID -> code point, read from the PDF's /ToUnicode CMap."""
    ref = re.search(rb"/ToUnicode (\d+) 0 R", pdf)
    if not ref:
        return {}
    blob = stream_of(pdf, int(ref.group(1)))
    if blob is None:
        return {}
    out: dict[int, int] = {}
    for cid, code in re.findall(rb"<([0-9A-Fa-f]{4})>\s*<([0-9A-Fa-f]{4,6})>", blob):
        out[int(cid, 16)] = int(code, 16)
    return out


def parse_cid_to_gid(pdf: bytes) -> dict[int, int] | None:
    """CID -> glyph id in the subset, from /CIDToGIDMap (an identity name is impossible here)."""
    ref = re.search(rb"/CIDToGIDMap (\d+) 0 R", pdf)
    if not ref:
        return None
    blob = stream_of(pdf, int(ref.group(1)))
    if blob is None:
        return None
    return {i: int.from_bytes(blob[2 * i : 2 * i + 2], "big") for i in range(len(blob) // 2)}


def outline_without_hints(blob: bytes) -> bytes:
    """A glyph's outline data with its TrueType instructions removed.

    The subsetter strips hinting on purpose (the instructions reference tables and
    glyph ids a subset does not carry), so compare like with like.
    """
    if len(blob) < 10:
        return blob
    contours = int.from_bytes(blob[0:2], "big", signed=True)
    if contours <= 0:
        return blob
    body = 10 + 2 * contours
    if len(blob) < body + 2:
        return blob
    ilen = int.from_bytes(blob[body : body + 2], "big")
    if ilen == 0:
        return blob
    return blob[:body] + b"\x00\x00" + blob[body + 2 + ilen :]


def main() -> int:
    source = (
        "哈工大（深圳）国际青年俱乐部 HSIYC 活动回顾：2026年7月19日至21日，"
        "第二届鹏海模拟联合国大会在深圳北理莫斯科大学举办。冠军：谢昊轩 Xie Haoxuan。"
    )
    pdf_path = ROOT / "_work" / "fontcheck.pdf"
    pdfout.write_article_pdf(
        {
            "title": {"cn": "国际青年俱乐部 | 字体校验", "en": "Font Check"},
            "lead": {"cn": source, "en": source},
            "sections": [
                {
                    "heading_cn": "活动详情",
                    "heading_en": "Event Highlights",
                    "body": [{"kind": "bilingual", "cn": source, "en": source}],
                }
            ],
            "closing": {"cn": "结语", "en": "Closing"},
            "signoff": {"cn": "哈工大（深圳）国际青年俱乐部", "en": "HITSZ International Youth Club"},
            "credits": {"三审": "卢锦章"},
        },
        pdf_path,
        {},
        None,
        shrink=False,  # inspect the agent's own font embedding, before Ghostscript
    )
    pdf = pdf_path.read_bytes()
    blob = embedded_font(pdf)
    if blob is None:
        print("FAIL: could not extract /FontFile2 from the PDF")
        return 1
    tables = parse_sfnt(blob)
    missing = [t for t in ("head", "hhea", "maxp", "loca", "glyf", "hmtx") if t not in tables]
    if missing:
        print("FAIL: embedded font is missing tables:", missing)
        return 1
    num_glyphs = int.from_bytes(tables["maxp"][4:6], "big")
    loca = read_loca(tables["head"], tables["loca"], num_glyphs)

    to_unicode = parse_to_unicode(pdf)
    cid_to_gid = parse_cid_to_gid(pdf)
    print(f"PDF {len(pdf):,} bytes | embedded font {len(blob):,} bytes | {num_glyphs} glyphs")
    print(f"glyf {len(tables['glyf']):,} B | loca monotonic: "
          f"{all(loca[i] <= loca[i+1] for i in range(len(loca)-1))} | last {loca[-1]:,}")
    print(f"/ToUnicode entries: {len(to_unicode)} | /CIDToGIDMap entries: "
          f"{len(cid_to_gid) if cid_to_gid else 'absent'}")
    if "cmap" in tables:
        print(f"embedded cmap bytes: {len(tables['cmap'])} (empty is expected and intended)")
    if not cid_to_gid:
        print("FAIL: the PDF has no /CIDToGIDMap stream, so glyph resolution is unspecified")
        return 1

    code_to_cid = {code: cid for cid, code in to_unicode.items()}
    original = pdfout.load_font()
    checked = ok = 0
    failures: list[str] = []
    for ch in dict.fromkeys(source):
        code = ord(ch)
        if code == 0x20:
            continue
        checked += 1
        cid = code_to_cid.get(code)
        if cid is None:
            failures.append(f"U+{code:04X} {ch!r}: not in /ToUnicode")
            continue
        gid = cid_to_gid.get(cid, 0)
        if gid == 0:
            failures.append(f"U+{code:04X} {ch!r}: CID {cid} maps to glyph 0 in /CIDToGIDMap")
            continue
        if gid >= num_glyphs:
            failures.append(f"U+{code:04X} {ch!r}: gid {gid} beyond glyph count {num_glyphs}")
            continue
        bounds = original._glyph_bounds(original.gid(code))
        if bounds is None:
            failures.append(f"U+{code:04X} {ch!r}: no outline in the source font")
            continue
        want = outline_without_hints(original.data[bounds[0] : bounds[1]])
        got = tables["glyf"][loca[gid] : loca[gid + 1]]
        if got[: len(want)] != want:
            failures.append(
                f"U+{code:04X} {ch!r}: outline mismatch (source {len(want)}B, embedded {len(got)}B)"
            )
            continue
        ok += 1

    print(f"characters verified against the original font: {ok}/{checked}")
    if failures:
        print(f"\nFAILURES ({len(failures)}):")
        for item in failures[:20]:
            print("  -", item)
        return 1
    print("\nfontcheck: OK - every character maps to the correct outline and back to its code point")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
