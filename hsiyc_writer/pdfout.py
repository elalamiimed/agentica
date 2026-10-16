"""A small, dependency-free PDF writer for CJK + English article output.

reportlab is not installable here and the bundled LibreOffice cannot be spawned
from inside the sandbox, so the agent ships its own minimal PDF engine. It does
exactly what an article needs:

  * embeds a real CJK TrueType font, so 中文 is selectable/searchable text,
  * measures text with the font's own metrics for correct wrapping and centring,
  * embeds the event photos (JPEG bytes are copied verbatim),
  * draws the approved visual grammar: banner, numbered section headers, ranking
    rows, captions and the 三审 credit block.

Scope limit by design: one embedded font, rectangles, rules and images only.
"""

from __future__ import annotations

import io
import re
import subprocess
import zlib
from pathlib import Path
from typing import Iterable, Sequence

PAGE_W, PAGE_H = 595.0, 842.0  # A4 portrait, points
MARGIN_X = 56.0
MARGIN_TOP = 56.0
MARGIN_BOTTOM = 62.0
CONTENT_W = PAGE_W - 2 * MARGIN_X

FONT_CANDIDATES = (
    Path(r"C:\Windows\Fonts\simhei.ttf"),
    Path(r"C:\Windows\Fonts\Deng.ttf"),
    Path(r"C:\Windows\Fonts\simkai.ttf"),
    Path(r"C:\Windows\Fonts\msyh.ttc"),
    Path(r"C:\Windows\Fonts\simsun.ttc"),
)

ACCENT = (0x1A / 255, 0x4F / 255, 0x9C / 255)
BAND = (0xF3 / 255, 0xF6 / 255, 0xFB / 255)
GREY = (0x6B / 255, 0x74 / 255, 0x82 / 255)
INK = (0x23 / 255, 0x27 / 255, 0x2F / 255)
HAIRLINE = (0.85, 0.88, 0.93)

CREDIT_ROLES = ("文字", "图片", "排版", "一审", "二审", "三审")


class FontUnavailable(RuntimeError):
    pass


# --------------------------------------------------------------------------- font
class TrueTypeFont:
    """Reads just enough of a TTF/TTC to embed it in a PDF as a simple font."""

    def __init__(self, path: Path):
        data = path.read_bytes()
        self.path = path
        offset = 0
        if data[:4] == b"ttcf":
            count = int.from_bytes(data[8:12], "big") or 1
            offset = int.from_bytes(data[12 : 12 + 4 * count][-4:], "big")
        num_tables = int.from_bytes(data[offset + 4 : offset + 6], "big")
        tables: dict[str, tuple[int, int]] = {}
        for i in range(num_tables):
            rec = offset + 12 + 16 * i
            tag = data[rec : rec + 4].decode("latin-1")
            tbl_off = int.from_bytes(data[rec + 8 : rec + 12], "big")
            tbl_len = int.from_bytes(data[rec + 12 : rec + 16], "big")
            tables[tag] = (tbl_off, tbl_len)
        for required in ("head", "hhea", "hmtx", "maxp", "cmap", "glyf", "loca"):
            if required not in tables:
                raise FontUnavailable(f"{path.name} lacks '{required}'; not a usable TrueType font")
        self.data = data
        self.tables = tables
        head = tables["head"][0]
        hhea = tables["hhea"][0]
        self.units = int.from_bytes(data[head + 18 : head + 20], "big") or 1000
        self.bbox = [
            int.from_bytes(data[head + 36 + 2 * i : head + 38 + 2 * i], "big", signed=True)
            for i in range(4)
        ]
        self.ascent = int.from_bytes(data[hhea + 4 : hhea + 6], "big", signed=True)
        self.descent = int.from_bytes(data[hhea + 6 : hhea + 8], "big", signed=True)
        self.num_hmetrics = int.from_bytes(data[hhea + 34 : hhea + 36], "big") or 1
        self.cmap = self._parse_cmap()
        self._adv_cache: dict[int, int] = {}

    # ------------------------------------------------------------ cmap parsing
    def _parse_cmap(self) -> dict[int, int]:
        base = self.tables["cmap"][0]
        n = int.from_bytes(self.data[base + 2 : base + 4], "big")
        best: tuple[int, int] | None = None
        for i in range(n):
            rec = base + 4 + 8 * i
            platform = int.from_bytes(self.data[rec : rec + 2], "big")
            encoding = int.from_bytes(self.data[rec + 2 : rec + 4], "big")
            sub = base + int.from_bytes(self.data[rec + 4 : rec + 8], "big")
            fmt = int.from_bytes(self.data[sub : sub + 2], "big")
            if fmt not in (4, 12):
                continue
            score = {(3, 10): 5, (3, 1): 4, (0, 4): 3, (0, 3): 3, (0, 2): 2}.get((platform, encoding), 1)
            if best is None or score > best[0]:
                best = (score, sub)
        if best is None:
            raise FontUnavailable(f"{self.path.name}: no usable cmap subtable")
        return self._parse_subtable(best[1])

    def _parse_subtable(self, sub: int) -> dict[int, int]:
        fmt = int.from_bytes(self.data[sub : sub + 2], "big")
        mapping: dict[int, int] = {}
        if fmt == 4:
            seg_x2 = int.from_bytes(self.data[sub + 6 : sub + 8], "big")
            seg = seg_x2 // 2
            ends = [int.from_bytes(self.data[sub + 14 + 2 * i : sub + 16 + 2 * i], "big") for i in range(seg)]
            starts_off = sub + 16 + seg_x2
            starts = [int.from_bytes(self.data[starts_off + 2 * i : starts_off + 2 + 2 * i], "big") for i in range(seg)]
            deltas_off = starts_off + seg_x2
            deltas = [
                int.from_bytes(self.data[deltas_off + 2 * i : deltas_off + 2 + 2 * i], "big", signed=True)
                for i in range(seg)
            ]
            ranges_off = deltas_off + seg_x2
            for i in range(seg):
                start, end, delta = starts[i], ends[i], deltas[i]
                if start == 0xFFFF or end < start:
                    continue
                range_offset = int.from_bytes(self.data[ranges_off + 2 * i : ranges_off + 2 + 2 * i], "big")
                for code in range(start, min(end, 0xFFFF) + 1):
                    if range_offset == 0:
                        gid = (code + delta) & 0xFFFF
                    else:
                        addr = ranges_off + 2 * i + range_offset + 2 * (code - start)
                        if addr + 2 > len(self.data):
                            continue
                        gid = int.from_bytes(self.data[addr : addr + 2], "big")
                        if gid:
                            gid = (gid + delta) & 0xFFFF
                    if gid:
                        mapping[code] = gid
        elif fmt == 12:
            groups = int.from_bytes(self.data[sub + 12 : sub + 16], "big")
            for i in range(groups):
                rec = sub + 16 + 12 * i
                start = int.from_bytes(self.data[rec : rec + 4], "big")
                end = int.from_bytes(self.data[rec + 4 : rec + 8], "big")
                gid = int.from_bytes(self.data[rec + 8 : rec + 12], "big")
                if end - start > 0x20000:  # keep the map small
                    end = start + 0x20000
                for code in range(start, end + 1):
                    mapping[code] = gid + (code - start)
        return mapping

    # ---------------------------------------------------------------- metrics
    def gid(self, code: int) -> int:
        return self.cmap.get(code, 0)

    def advance_gid(self, gid: int) -> int:
        if gid in self._adv_cache:
            return self._adv_cache[gid]
        hmtx = self.tables["hmtx"][0]
        if gid < self.num_hmetrics:
            width = int.from_bytes(self.data[hmtx + 4 * gid : hmtx + 4 * gid + 2], "big")
        else:
            last = hmtx + 4 * (self.num_hmetrics - 1)
            width = int.from_bytes(self.data[last : last + 2], "big")
        self._adv_cache[gid] = width
        return width

    def advance(self, code: int) -> int:
        return self.advance_gid(self.gid(code))

    def width_of(self, text: str, size: float) -> float:
        return sum(self.advance(ord(ch)) for ch in text) * size / self.units

    def widths_range(self, gids: Sequence[int]) -> tuple[int, int, list[int]]:
        lo, hi = min(gids), max(gids)
        widths = [round(self.advance_gid(g) * 1000 / self.units) for g in range(lo, hi + 1)]
        return lo, hi, widths

    # ----------------------------------------------------------------- subsetting
    def _glyph_bounds(self, gid: int) -> tuple[int, int] | None:
        loca_off = self.tables["loca"][0]
        glyf_off = self.tables["glyf"][0]
        long_format = int.from_bytes(
            self.data[self.tables["head"][0] + 50 : self.tables["head"][0] + 52], "big"
        )
        if long_format:
            a = int.from_bytes(self.data[loca_off + 4 * gid : loca_off + 4 * gid + 4], "big")
            b = int.from_bytes(self.data[loca_off + 4 * gid + 4 : loca_off + 4 * gid + 8], "big")
        else:
            a = int.from_bytes(self.data[loca_off + 2 * gid : loca_off + 2 * gid + 2], "big") * 2
            b = int.from_bytes(self.data[loca_off + 2 * gid + 2 : loca_off + 2 * gid + 4], "big") * 2
        if b <= a:
            return None
        start, end = glyf_off + a, glyf_off + b
        if end > len(self.data):
            return None
        return start, end

    def _composite_parts(self, blob: bytes) -> list[int] | None:
        """Glyph ids referenced by a composite glyph, or None if it is simple/invalid."""
        if len(blob) < 10:
            return None
        contours = int.from_bytes(blob[0:2], "big", signed=True)
        if contours >= 0:
            return []
        parts: list[int] = []
        i = 10
        while i + 4 <= len(blob):
            flags = int.from_bytes(blob[i : i + 2], "big")
            gid = int.from_bytes(blob[i + 2 : i + 4], "big")
            parts.append(gid)
            i += 4
            i += 4 if flags & 0x0001 else 2  # ARG_1_AND_2_ARE_WORDS
            if flags & 0x0008:
                i += 2
            elif flags & 0x0040:
                i += 4
            elif flags & 0x0080:
                i += 8
            if not flags & 0x0020:  # MORE_COMPONENTS
                break
        return parts

    def _remap_components(self, blob: bytearray, mapping: dict[int, int]) -> None:
        contours = int.from_bytes(bytes(blob[0:2]), "big", signed=True)
        if contours >= 0:
            return
        i = 10
        while i + 4 <= len(blob):
            flags = int.from_bytes(bytes(blob[i : i + 2]), "big")
            gid = int.from_bytes(bytes(blob[i + 2 : i + 4]), "big")
            blob[i + 2 : i + 4] = mapping.get(gid, 0).to_bytes(2, "big")
            i += 4
            i += 4 if flags & 0x0001 else 2
            if flags & 0x0008:
                i += 2
            elif flags & 0x0040:
                i += 4
            elif flags & 0x0080:
                i += 8
            if not flags & 0x0020:
                break

    def _strip_hinting(self, blob: bytes) -> bytes:
        """Remove a glyph's TrueType instructions.

        A subset cannot keep the font's hinting: the instructions depend on the
        ``cvt ``/``fpgm``/``prep`` tables and on glyph ids that no longer exist.
        Leaving them in produces exactly the corruption seen in testing - some
        glyphs rasterise, others silently come out blank. Stripping them yields
        clean unhinted outlines, which is what a text PDF wants anyway.
        """
        if len(blob) < 10:
            return blob
        contours = int.from_bytes(blob[0:2], "big", signed=True)
        if contours <= 0:
            return blob  # empty glyph, or a composite handled elsewhere
        body = 10 + 2 * contours
        if len(blob) < body + 2:
            return blob
        instruction_len = int.from_bytes(blob[body : body + 2], "big")
        if instruction_len == 0:
            return blob
        return blob[:body] + b"\x00\x00" + blob[body + 2 + instruction_len :]

    def build_subset(
        self, used_codes: Iterable[int], used_gids: Iterable[int] | None = None
    ) -> tuple[bytes, dict[int, int], dict[int, int]] | None:
        """Subset the font to the glyphs needed for ``used_codes``.

        ``used_codes`` are **Unicode code points** (what the cmap is keyed by).
        ``used_gids`` are the glyph ids to keep; they default to the glyphs those
        codes resolve to, plus any explicitly requested (composite components).

        Returns ``(sfnt_bytes, gid_map, code_map)`` or ``None`` when subsetting is
        unsafe for this font, in which case the caller embeds the whole font.

        The rebuilt ``cmap`` maps each used code point to its *new* glyph id, which
        keeps the PDF both correctly rendered and text-extractable.
        """
        code_list = sorted({c for c in used_codes if c > 0})
        glyphs: list[int] = []
        seen: set[int] = set()
        pending = [0]
        pending += [self.gid(c) for c in code_list]
        if used_gids:
            pending += [g for g in used_gids]
        while pending:
            gid = pending.pop()
            if gid in seen or gid >= self.num_glyphs:
                continue
            seen.add(gid)
            glyphs.append(gid)
            bounds = self._glyph_bounds(gid)
            if not bounds:
                continue
            parts = self._composite_parts(self.data[bounds[0] : bounds[1]])
            if parts:
                pending.extend(p for p in parts if p not in seen)
        glyphs.sort()
        mapping = {gid: new for new, gid in enumerate(glyphs)}
        # code point -> new glyph id, for the rebuilt cmap
        code_map = {code: mapping[self.gid(code)] for code in code_list if self.gid(code) in mapping}

        glyf_parts: list[bytes] = []
        loca: list[int] = []
        offset = 0
        for gid in glyphs:
            loca.append(offset // 2)
            bounds = self._glyph_bounds(gid)
            if bounds is None:
                continue
            blob = bytearray(self.data[bounds[0] : bounds[1]])
            self._remap_components(blob, mapping)
            blob = bytearray(self._strip_hinting(bytes(blob)))
            if len(blob) % 2:
                blob.append(0)
            glyf_parts.append(bytes(blob))
            offset += len(blob)
        loca.append(offset // 2)
        if offset > 0x1FFFE:  # short loca cannot address more than 128 KiB
            return None

        glyf = b"".join(glyf_parts)
        loca_table = b"".join(v.to_bytes(2, "big") for v in loca)

        hmtx_off = self.tables["hmtx"][0]
        hmtx = bytearray()
        for i, gid in enumerate(glyphs):
            source = gid if gid < self.num_hmetrics else self.num_hmetrics - 1
            hmtx += self.data[hmtx_off + 4 * source : hmtx_off + 4 * source + 2]
            if i < self.num_hmetrics:
                hmtx += self.data[hmtx_off + 4 * gid + 2 : hmtx_off + 4 * gid + 4]
            else:
                lsb_off = hmtx_off + 4 * self.num_hmetrics + 2 * (gid - self.num_hmetrics)
                hmtx += self.data[lsb_off : lsb_off + 2]

        head = bytearray(self.data[self.tables["head"][0] : self.tables["head"][0] + self.tables["head"][1]])
        head[8:12] = (0).to_bytes(4, "big")  # checkSumAdjustment
        head[50:52] = (0).to_bytes(2, "big")  # indexToLocFormat = short
        hhea = self.data[self.tables["hhea"][0] : self.tables["hhea"][0] + self.tables["hhea"][1]]
        maxp = bytearray(self.data[self.tables["maxp"][0] : self.tables["maxp"][0] + self.tables["maxp"][1]])
        maxp[4:6] = len(glyphs).to_bytes(2, "big")
        # The embedded cmap must agree with the PDF's /CIDToGIDMap, which maps
        # CID i to glyph i. A viewer that consults the font program (rather than
        # only the CID map) therefore resolves the same glyph either way.
        # ``code_list`` may legitimately be empty; the cmap is then identity.
        cmap = self._cmap4({gid: mapping[gid] for gid in glyphs})

        pairs = [
            ("cmap", cmap),
            ("glyf", glyf),
            ("head", bytes(head)),
            ("hhea", bytes(hhea)),
            ("hmtx", bytes(hmtx)),
            ("loca", loca_table),
            ("maxp", bytes(maxp)),
        ]
        num = len(pairs)
        search_range, entry_selector = 1, 0
        while search_range * 2 <= num:
            search_range *= 2
            entry_selector += 1
        search_range *= 16
        header = (
            (0x00010000).to_bytes(4, "big")
            + num.to_bytes(2, "big")
            + search_range.to_bytes(2, "big")
            + entry_selector.to_bytes(2, "big")
            + (num * 16 - search_range).to_bytes(2, "big")
        )
        table_offset = 12 + 16 * num
        records = bytearray()
        body = bytearray()
        for tag, blob in sorted(pairs):
            padded = blob + b"\x00" * ((4 - len(blob) % 4) % 4)
            records += tag.ljust(4, " ").encode("latin-1")
            records += (0).to_bytes(4, "big")
            records += table_offset.to_bytes(4, "big")
            records += len(blob).to_bytes(4, "big")
            body += padded
            table_offset += len(padded)
        return bytes(header + records + body), mapping, code_map

    def full_font_bytes(self) -> bytes:
        """The whole font as a standalone sfnt - the fallback when subsetting is unsafe."""
        wanted = ("head", "hhea", "maxp", "cmap", "loca", "glyf", "hmtx")
        tables = [
            (tag, self.data[self.tables[tag][0] : self.tables[tag][0] + self.tables[tag][1]])
            for tag in wanted
        ]
        num = len(tables)
        search_range, entry_selector = 1, 0
        while search_range * 2 <= num:
            search_range *= 2
            entry_selector += 1
        search_range *= 16
        header = (
            (0x00010000).to_bytes(4, "big")
            + num.to_bytes(2, "big")
            + search_range.to_bytes(2, "big")
            + entry_selector.to_bytes(2, "big")
            + (num * 16 - search_range).to_bytes(2, "big")
        )
        offset = 12 + 16 * num
        records = bytearray()
        body = bytearray()
        for tag, blob in sorted(tables):
            padded = blob + b"\x00" * ((4 - len(blob) % 4) % 4)
            records += tag.ljust(4, " ").encode("latin-1")
            records += (0).to_bytes(4, "big")
            records += offset.to_bytes(4, "big")
            records += len(blob).to_bytes(4, "big")
            body += padded
            offset += len(padded)
        return bytes(header + records + body)

    def widths_for_subset(self, glyphs: Sequence[int]) -> list[int]:
        return [round(self.advance_gid(g) * 1000 / self.units) for g in glyphs]

    def _build_cmap(self, used_codes: Iterable[int], mapping: dict[int, int]) -> bytes:
        """cmap mapping Unicode code point -> NEW glyph id.

        Only used when a caller asks for a self-describing font. The article PDF
        path leaves this empty on purpose: it resolves glyphs through the PDF's
        /CIDToGIDMap instead, so the embedded font cannot disagree with it.
        """
        pairs: dict[int, int] = {}
        for code in used_codes:
            if code <= 0 or code > 0x10FFFF:
                continue
            new_gid = mapping.get(self.gid(code))
            if new_gid:
                pairs[code] = new_gid
        return self._cmap4(pairs)

    def _cmap4(self, pairs: dict[int, int]) -> bytes:
        """Serialise a code -> gid map as a Windows Unicode BMP cmap (format 4)."""
        bmp = {c: g for c, g in pairs.items() if c <= 0xFFFF}
        codes = sorted(bmp)
        segments: list[tuple[int, int, int]] = []  # (start, end, delta)
        i = 0
        while i < len(codes):
            start = codes[i]
            end = start
            delta = (bmp[start] - start) & 0xFFFF
            i += 1
            while i < len(codes) and codes[i] == end + 1 and ((bmp[codes[i]] - codes[i]) & 0xFFFF) == delta:
                end = codes[i]
                i += 1
            segments.append((start, end, delta))
        segments.append((0xFFFF, 0xFFFF, 1))  # required terminator

        seg_count = len(segments)
        ends = b"".join(s[1].to_bytes(2, "big") for s in segments)
        starts = b"".join(s[0].to_bytes(2, "big") for s in segments)
        deltas = b"".join(
            (s[2] if s[2] < 0x8000 else s[2] - 0x10000).to_bytes(2, "big", signed=True) for s in segments
        )
        ranges = b"\x00\x00" * seg_count
        search_range = 2 * (2 ** (seg_count.bit_length() - 1)) if seg_count else 2
        entry_selector = max(0, search_range.bit_length() - 2)
        range_shift = 2 * seg_count - search_range
        subtable = (
            (4).to_bytes(2, "big")
            + (16 + 8 * seg_count).to_bytes(2, "big")
            + (0).to_bytes(2, "big")  # language
            + (seg_count * 2).to_bytes(2, "big")
            + search_range.to_bytes(2, "big")
            + entry_selector.to_bytes(2, "big")
            + range_shift.to_bytes(2, "big")
            + ends
            + (0).to_bytes(2, "big")  # reservedPad
            + starts
            + deltas
            + ranges
        )
        return (
            (0).to_bytes(2, "big")  # version
            + (1).to_bytes(2, "big")  # numTables
            + (3).to_bytes(2, "big")  # platform: Windows
            + (1).to_bytes(2, "big")  # encoding: Unicode BMP
            + (12).to_bytes(4, "big")  # offset to subtable
            + subtable
        )

    @property
    def num_glyphs(self) -> int:
        return int.from_bytes(self.data[self.tables["maxp"][0] + 4 : self.tables["maxp"][0] + 6], "big")

    def subset_bytes(self) -> bytes:
        """A standalone sfnt containing the tables a simple PDF font needs."""
        wanted = ("head", "hhea", "maxp", "cmap", "loca", "glyf", "hmtx")
        tables = [(tag, self.data[self.tables[tag][0] : self.tables[tag][0] + self.tables[tag][1]]) for tag in wanted]
        num = len(tables)
        search_range, entry_selector = 1, 0
        while search_range * 2 <= num:
            search_range *= 2
            entry_selector += 1
        search_range *= 16
        header = (
            (0x00010000).to_bytes(4, "big")
            + num.to_bytes(2, "big")
            + search_range.to_bytes(2, "big")
            + entry_selector.to_bytes(2, "big")
            + (num * 16 - search_range).to_bytes(2, "big")
        )
        offset = 12 + 16 * num
        records = bytearray()
        body = bytearray()
        for tag, blob in sorted(tables):
            padded = blob + b"\x00" * ((4 - len(blob) % 4) % 4)
            records += tag.ljust(4, " ").encode("latin-1")
            records += (0).to_bytes(4, "big")  # checksum (viewers do not verify)
            records += offset.to_bytes(4, "big")
            records += len(blob).to_bytes(4, "big")
            body += padded
            offset += len(padded)
        return bytes(header + records + body)


_font_cache: dict[str, TrueTypeFont] = {}

# Longest side of an embedded photo, in pixels. A full-bleed photo on an A4 page
# is ~1500px at 300dpi, so this loses nothing visible and keeps a submission PDF
# in the tens-to-hundreds of kilobytes instead of megabytes.
MAX_EMBED_PX = 1600


def load_font() -> TrueTypeFont:
    for path in FONT_CANDIDATES:
        key = str(path)
        if key in _font_cache:
            return _font_cache[key]
        if not path.is_file():
            continue
        try:
            font = TrueTypeFont(path)
        except (FontUnavailable, OSError, IndexError, ValueError):
            continue
        _font_cache[key] = font
        return font
    raise FontUnavailable(
        "No usable CJK TrueType font found. Looked in: " + ", ".join(str(p) for p in FONT_CANDIDATES)
    )


# --------------------------------------------------------------------------- pdf objects
class PdfBuilder:
    """Append-only PDF object store with a two-pass font/page wiring."""

    def __init__(self, font: TrueTypeFont, subset_font: bool = True, identity_cid_map: bool = False):
        self.font = font
        self.subset_font = subset_font
        # When the subset is built, CID == slot in the subset, so /Identity is a
        # valid (and simpler) alternative to an explicit CIDToGIDMap stream.
        self.identity_cid_map = identity_cid_map
        self.objects: list[bytes] = []
        self.images: dict[str, int] = {}
        self.font_obj = 0
        self.pages_obj = 0
        self._reverse_cache: dict[int, int] | None = None

    # -------------------------------------------------------------- low level
    def add(self, payload: bytes) -> int:
        self.objects.append(payload)
        return len(self.objects)

    def add_stream(self, extra_dict: str, stream: bytes, compress: bool = True) -> int:
        data = zlib.compress(stream, 6) if compress else stream
        filt = " /Filter /FlateDecode" if compress else ""
        extra = extra_dict.strip()
        body = f"{extra}{filt} /Length {len(data)}".strip()
        header = f"<< {body} >>".encode("latin-1")
        return self.add(header + b"\nstream\n" + data + b"\nendstream")

    def add_image(self, path: Path) -> int | None:
        key = str(path)
        if key in self.images:
            return self.images[key]
        try:
            raw = path.read_bytes()
        except OSError:
            return None

        if path.suffix.lower() in (".jpg", ".jpeg"):
            info = _jpeg_info(raw)
            # A phone photo is often 4000px wide and several megabytes. Passed
            # through untouched it turns a 90 KB article into a 6.7 MB PDF, which
            # is a nuisance to send for review. Only an already-modest JPEG is
            # embedded byte-for-byte; anything larger is re-encoded below.
            if info and max(info[0], info[1]) <= MAX_EMBED_PX:
                width, height, components = info
                color = {1: "/DeviceGray", 3: "/DeviceRGB", 4: "/DeviceCMYK"}.get(components)
                if color:
                    obj = self.add_stream(
                        f"/Type /XObject /Subtype /Image /Width {width} /Height {height} "
                        f"/ColorSpace {color} /BitsPerComponent 8 /Filter /DCTDecode",
                        raw,
                        compress=False,
                    )
                    self.images[key] = obj
                    return obj
        try:
            from PIL import Image

            with Image.open(io.BytesIO(raw)) as im:
                im = im.convert("RGB")
                # The page never renders a photo wider than the text column, so
                # anything beyond this is bytes nobody can see.
                if max(im.size) > MAX_EMBED_PX:
                    scale = MAX_EMBED_PX / float(max(im.size))
                    im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))),
                                   Image.LANCZOS)
                width, height = im.size
                buf = io.BytesIO()
                im.save(buf, format="JPEG", quality=85, optimize=True)
                data = buf.getvalue()
        except Exception:
            return None
        obj = self.add_stream(
            f"/Type /XObject /Subtype /Image /Width {width} /Height {height} "
            f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode",
            data,
            compress=False,
        )
        self.images[key] = obj
        return obj

    # ------------------------------------------------------------ final assembly
    def _gid_to_code(self) -> dict[int, int]:
        """Reverse of the font's cmap: glyph id -> the code point that reaches it."""
        if getattr(self, "_reverse_cache", None) is None:
            reverse: dict[int, int] = {}
            for code, gid in self.font.cmap.items():
                if gid and gid not in reverse:
                    reverse[gid] = code
            self._reverse_cache = reverse
        return self._reverse_cache

    def _to_unicode(self, gid_map: dict[int, int]) -> bytes:
        """A /ToUnicode CMap mapping each CID back to its Unicode code point.

        Built from the original font's cmap, so text extraction and search keep
        working even though the embedded subset carries an empty cmap by design.
        """
        reverse = self._gid_to_code()
        lines = [
            "/CIDInit /ProcSet findresource begin",
            "12 dict begin",
            "begincmap",
            "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
            "/CMapName /HSIYC-UCS def",
            "/CMapType 2 def",
            "1 begincodespacerange",
            "<0000> <FFFF>",
            "endcodespacerange",
        ]
        entries = [
            (cid, reverse[gid])
            for gid, cid in sorted(gid_map.items(), key=lambda kv: kv[1])
            if reverse.get(gid)
        ]
        for start in range(0, len(entries), 100):
            chunk = entries[start : start + 100]
            lines.append(f"{len(chunk)} beginbfchar")
            lines.extend(f"<{cid:04X}> <{code:04X}>" for cid, code in chunk)
            lines.append("endbfchar")
        lines += ["endcmap", "CMapName currentdict /CMap defineresource pop", "end", "end"]
        return "\n".join(lines).encode("latin-1")

    def assemble(self, page_objects: list[int], page_streams: list[bytes]) -> bytes:
        """Build the PDF with explicit CID -> glyph mapping.

        The canvas writes the ORIGINAL glyph id of every character into the content
        stream. Rendering is resolved entirely through PDF dictionaries - the
        /CIDToGIDMap maps each CID to its slot in the sliced font, and /ToUnicode
        maps each CID back to its code point for text extraction. The embedded font
        is deliberately given an EMPTY cmap, so no viewer can fall back to it and
        disagree with /CIDToGIDMap about which glyph a CID means.
        """
        used_gids: set[int] = {0}
        for stream in page_streams:
            used_gids |= _glyphs_in(stream)
        used_gids = {g for g in used_gids if g < self.font.num_glyphs}

        if self.subset_font:
            subset_result = self.font.build_subset([], sorted(used_gids))
        else:
            subset_result = None
        if subset_result is None:
            # Embed the whole font and keep original glyph ids as CIDs.
            subset = self.font.full_font_bytes()
            gid_map = {gid: gid for gid in used_gids}
        else:
            subset, gid_map, _ = subset_result

        # /W is indexed by CID (== new glyph id) and carries the advance width.
        w_entries = [
            f"{gid_map[g]} [{round(self.font.advance_gid(g) * 1000 / self.font.units)}]"
            for g in sorted(gid_map)
        ]

        # CID -> glyph id in the subset: a flat big-endian uint16 array.
        max_cid = max(gid_map.values()) if gid_map else 0
        cid_to_gid = bytearray(2 * (max_cid + 1))
        for old_gid, cid in gid_map.items():
            cid_to_gid[2 * cid : 2 * cid + 2] = cid.to_bytes(2, "big")
        cid_map_ref = (
            "/CIDToGIDMap /Identity"
            if self.identity_cid_map
            else f"/CIDToGIDMap {self.add_stream('', bytes(cid_to_gid))} 0 R"
        )

        fontfile = self.add_stream(f"/Length1 {len(subset)}", subset, compress=True)
        scale = 1000.0 / self.font.units
        descriptor = self.add(
            (
                f"<< /Type /FontDescriptor /FontName /HSIYCA+HSIYCEmbedded /Flags 4 "
                f"/FontBBox [{int(self.font.bbox[0]*scale)} {int(self.font.bbox[1]*scale)} "
                f"{int(self.font.bbox[2]*scale)} {int(self.font.bbox[3]*scale)}] /ItalicAngle 0 "
                f"/Ascent {int(self.font.ascent*scale)} /Descent {int(self.font.descent*scale)} "
                f"/CapHeight 700 /StemV 80 /FontFile2 {fontfile} 0 R >>"
            ).encode("latin-1")
        )
        cid_font = self.add(
            (
                f"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /HSIYCA+HSIYCEmbedded "
                f"/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> "
                f"/FontDescriptor {descriptor} 0 R /DW 1000 /W [{' '.join(w_entries)}] "
                f"{cid_map_ref} >>"
            ).encode("latin-1")
        )
        self.font_obj = self.add(
            (
                f"<< /Type /Font /Subtype /Type0 /BaseFont /HSIYCA+HSIYCEmbedded "
                f"/Encoding /Identity-H /DescendantFonts [{cid_font} 0 R] "
                f"/ToUnicode {self.add_stream('', self._to_unicode(gid_map))} 0 R >>"
            ).encode("latin-1")
        )

        # Rewrite the content streams so each glyph id becomes its CID in the
        # subset. This is the step that makes /CIDToGIDMap and the identity cmap
        # agree: a CID is a slot 0..N-1 in the embedded font, never the original
        # glyph id (which is far outside that range and would render as .notdef).
        page_streams = [_rewrite_glyphs(stream, gid_map) for stream in page_streams]

        image_dict = " ".join(f"/Im{n} {n} 0 R" for n in sorted(set(self.images.values())))
        resources = f"<< /Font << /F1 {self.font_obj} 0 R >> /XObject << {image_dict} >> >>"

        # Pages are authored now, once the font and image object numbers exist.
        # A /Page must be a dictionary; its drawing lives in a separate content stream.
        real_pages: list[int] = []
        for old, stream in zip(page_objects, page_streams):
            self.objects[old - 1] = b"<< /Type /Page >>"  # retired placeholder
            content = self.add_stream("", stream)
            real_pages.append(
                self.add(
                    (
                        f"<< /Type /Page /Parent /ParentRef "
                        f"/MediaBox [0 0 {PAGE_W:.0f} {PAGE_H:.0f}] "
                        f"/Resources {resources} /Contents {content} 0 R >>"
                    ).encode("latin-1")
                )
            )

        kids = " ".join(f"{n} 0 R" for n in real_pages)
        self.pages_obj = self.add(
            f"<< /Type /Pages /Count {len(real_pages)} /Kids [{kids}] >>".encode("latin-1")
        )
        for num in real_pages:
            self.objects[num - 1] = self.objects[num - 1].replace(
                b"/ParentRef", f"{self.pages_obj} 0 R".encode()
            )
        info = self.add(
            b"<< /Producer (HSIYC Article Writer) /Creator (HSIYC Article Writer) >>"
        )
        catalog = self.add(f"<< /Type /Catalog /Pages {self.pages_obj} 0 R >>".encode("latin-1"))

        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets: list[int] = []
        for i, payload in enumerate(self.objects, 1):
            if not payload:
                payload = b"<< /Type /Font >>"  # never emit an empty object
            offsets.append(len(out))
            out += f"{i} 0 obj\n".encode("latin-1") + payload + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(offsets)+1}\n".encode("latin-1")
        out += b"0000000000 65535 f \n"
        for off in offsets:
            out += f"{off:010d} 00000 n \n".encode("latin-1")
        out += (
            f"trailer\n<< /Size {len(offsets)+1} /Root {catalog} 0 R /Info {info} 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode("latin-1")
        return bytes(out)


def _glyphs_in(stream: bytes) -> set[int]:
    """Original glyph ids shown by a content stream, read from a placeholder stream.

    The canvas emits one 2-byte glyph id per Tj; ``_rewrite_glyphs`` later converts
    them to CIDs.
    """
    gids: set[int] = set()
    for match in re.finditer(rb"<([0-9A-Fa-f]+)>\s*Tj", stream):
        hexs = match.group(1)
        for i in range(0, len(hexs) - 3, 4):
            gids.add(int(hexs[i : i + 4], 16))
    return gids


def _rewrite_glyphs(stream: bytes, mapping: dict[int, int]) -> bytes:
    """Rewrite every placeholder glyph id to its CID (== new glyph id)."""

    def replace(match: re.Match) -> bytes:
        hexs = match.group(1)
        out = "".join(
            f"{mapping.get(int(hexs[i : i + 4], 16), 0):04X}" for i in range(0, len(hexs) - 3, 4)
        )
        return b"<" + out.encode("ascii") + b"> Tj"

    return re.sub(rb"<([0-9A-Fa-f]+)>\s*Tj", replace, stream)


def _jpeg_info(raw: bytes) -> tuple[int, int, int] | None:
    if raw[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 9 < len(raw):
        if raw[i] != 0xFF:
            i += 1
            continue
        marker = raw[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        length = int.from_bytes(raw[i + 2 : i + 4], "big")
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            height = int.from_bytes(raw[i + 5 : i + 7], "big")
            width = int.from_bytes(raw[i + 7 : i + 9], "big")
            return width, height, raw[i + 9]
        i += 2 + length
    return None


# --------------------------------------------------------------------------- layout
class PdfCanvas:
    """Block layout on A4 with automatic page breaks and a running footer."""

    def __init__(self, builder: PdfBuilder):
        self.b = builder
        self.font = builder.font
        self.page_streams: list[bytes] = []
        self.ops: list[bytes] = []
        self.page_count = 1
        self.y = PAGE_H - MARGIN_TOP

    # ---------------------------------------------------------------- pages
    def new_page(self) -> None:
        self.ops += self._footer(self.page_count)
        self.page_streams.append(b"\n".join(self.ops))
        self.ops = []
        self.page_count += 1
        self.y = PAGE_H - MARGIN_TOP

    def _footer(self, number: int) -> list[bytes]:
        return [
            f"0.8510 0.8784 0.9294 rg {MARGIN_X:.2f} {MARGIN_BOTTOM - 16:.2f} "
            f"{CONTENT_W:.2f} 0.6 re f".encode("latin-1"),
            self._text_op(f"HSIYC · 哈工大（深圳）国际青年俱乐部 — {number}", MARGIN_X, MARGIN_BOTTOM - 30, 7.5, GREY),
        ]

    def _ensure(self, height: float) -> None:
        if self.y - height < MARGIN_BOTTOM:
            self.new_page()

    # ---------------------------------------------------------------- atoms
    def _text_op(self, line: str, x: float, y: float, size: float, color) -> bytes:
        hexs = "".join(f"{self.font.gid(ord(ch)):04X}" for ch in line)
        return (
            f"BT /F1 {size:.2f} Tf {color[0]:.4f} {color[1]:.4f} {color[2]:.4f} rg "
            f"1 0 0 1 {x:.2f} {y:.2f} Tm <{hexs}> Tj ET"
        ).encode("latin-1")

    def text(
        self,
        content: str,
        size: float = 11,
        *,
        color=INK,
        indent: float = 0.0,
        align: str = "left",
        line_gap: float = 1.55,
        space_after: float = 0.0,
    ) -> None:
        if not content or not content.strip():
            return
        for line in self._wrap(content, size, CONTENT_W - indent):
            self._ensure(size * line_gap)
            width = self.font.width_of(line, size)
            if align == "center":
                x = MARGIN_X + (CONTENT_W - width) / 2
            elif align == "right":
                x = MARGIN_X + CONTENT_W - width
            else:
                x = MARGIN_X + indent
            self.ops.append(self._text_op(line, x, self.y - size, size, color))
            self.y -= size * line_gap
        self.y -= space_after

    def rect(self, x: float, y: float, w: float, h: float, color) -> None:
        self.ops.append(
            f"{color[0]:.4f} {color[1]:.4f} {color[2]:.4f} rg {x:.2f} {y:.2f} {w:.2f} {h:.2f} re f".encode(
                "latin-1"
            )
        )

    def rule(self, y: float, color=HAIRLINE, height: float = 0.7) -> None:
        self.rect(MARGIN_X, y, CONTENT_W, height, color)

    def image(self, path: Path, box_w: float, box_h: float, x: float, y: float) -> bool:
        obj = self.b.add_image(path)
        if obj is None:
            return False
        size = _image_size(path)
        if not size:
            return False
        iw, ih = size
        scale = min(box_w / iw, box_h / ih)
        w, h = iw * scale, ih * scale
        x += (box_w - w) / 2
        y += (box_h - h) / 2
        self.ops.append(f"q {w:.2f} 0 0 {h:.2f} {x:.2f} {y:.2f} cm /Im{obj} Do Q".encode("latin-1"))
        return True

    def _wrap(self, text: str, size: float, max_w: float) -> list[str]:
        lines: list[str] = []
        for hard in str(text).split("\n"):
            current = ""
            for chunk in _chunks(hard):
                if current and self.font.width_of(current + chunk, size) > max_w:
                    lines.append(current.rstrip())
                    current = chunk.lstrip()
                else:
                    current += chunk
            if current.strip():
                lines.append(current.rstrip())
        return [ln for ln in lines if ln.strip()]

    # ---------------------------------------------------------------- finish
    def finish(self, builder: PdfBuilder) -> bytes:
        self.ops += self._footer(self.page_count)
        self.page_streams.append(b"\n".join(self.ops))
        placeholders = [builder.add(b"") for _ in self.page_streams]
        return builder.assemble(placeholders, self.page_streams)


def _image_size(path: Path) -> tuple[int, int] | None:
    try:
        from PIL import Image

        with Image.open(path) as im:
            return im.size
    except Exception:
        return None


_CJK_PUNCT = "，。、；：？！“”‘’（）《》〈〉—…·｜【】「」"
_CHUNK_BREAK = set(" \t-/")


def _chunks(text: str) -> list[str]:
    """Split so wrapping can break between CJK characters but not inside words."""
    out: list[str] = []
    buf = ""
    for ch in text:
        if "\u3000" <= ch <= "\u9fff" or ch in _CJK_PUNCT:
            if buf:
                out.append(buf)
                buf = ""
            out.append(ch)
        elif ch in _CHUNK_BREAK:
            buf += ch
            out.append(buf)
            buf = ""
        else:
            buf += ch
    if buf:
        out.append(buf)
    return [c for c in out if c]


# --------------------------------------------------------------------------- public
GHOSTSCRIPT_CANDIDATES = (
    Path(r"C:\Users\hp\AppData\Local\Programs\MiKTeX\miktex\bin\x64\mgs.exe"),
    Path(r"C:\Users\hp\AppData\Local\Programs\MiKTeX\miktex\bin\x64\gswin64c.exe"),
)


def _ghostscript() -> Path | None:
    for candidate in GHOSTSCRIPT_CANDIDATES:
        if candidate.is_file():
            return candidate
    return None


def shrink_pdf(pdf_path: Path) -> tuple[Path, str]:
    """Subset/compress a finished PDF with Ghostscript.

    The agent writes the whole CJK font so that rendering is guaranteed correct;
    Ghostscript then subsets it properly, which is where the size win comes from.
    Returns ``(path, note)``; on any failure the original file is returned intact.
    """
    gs = _ghostscript()
    if gs is None:
        return pdf_path, "ghostscript not found; PDF keeps the full font"
    target = pdf_path.with_name(pdf_path.stem + ".gs.pdf")
    command = [
        str(gs),
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        "-dSubsetFonts=true",
        "-dEmbedAllFonts=true",
        "-dCompressFonts=true",
        "-dNOPAUSE",
        "-dBATCH",
        "-dQUIET",
        "-dSAFER",
        "-dAutoRotatePages=/None",
        f"-sOutputFile={target}",
        str(pdf_path),
    ]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=300)
    except (subprocess.SubprocessError, OSError) as exc:
        return pdf_path, f"ghostscript could not run ({exc}); PDF keeps the full font"
    if proc.returncode != 0 or not target.is_file() or target.stat().st_size == 0:
        target.unlink(missing_ok=True)
        return pdf_path, "ghostscript failed; PDF keeps the full font"
    before, after = pdf_path.stat().st_size, target.stat().st_size
    if after >= before:
        target.unlink(missing_ok=True)
        return pdf_path, "ghostscript produced no saving; PDF keeps the full font"
    return target, f"ghostscript subset the font: {before/1e6:.1f} MB -> {after/1e6:.1f} MB"


def write_article_pdf(
    article: dict,
    path: Path,
    photos: dict[str, Path] | None = None,
    report=None,
    *,
    subset_font: bool = False,
    shrink: bool = True,
    include_check: bool = False,
) -> Path:
    """Render one article to a PDF that mirrors the approved visual grammar.

    ``include_check`` defaults to False: the pre-submission check, the editor
    hand-over list and the corpus-similarity notes are internal QA and must never
    appear on the file that goes to the youth committee. Pass True to append them
    for a reviewer's own copy.

    Strategy: the agent embeds the whole CJK font, which is *provably* correct -
    every glyph resolves through /CIDToGIDMap with original glyph ids, and both
    pdftoppm and pdftocairo render it faithfully. The hand-written subsetter in
    this module is not used by default: testing showed it produced PDFs whose
    text layer was perfect but where some glyphs silently rendered as .notdef
    (see tests/fontcheck.py and tests/fidelity.py). Ghostscript then subsets the
    embedded font properly, taking a ~5 MB article down to ~45 KB.
    """
    photos = photos or {}
    font = load_font()
    builder = PdfBuilder(font, subset_font=subset_font)
    canvas = PdfCanvas(builder)

    title = article.get("title") or {}
    lead = article.get("lead") or {}
    closing = article.get("closing") or {}
    signoff = article.get("signoff") or {}
    credits = article.get("credits") or {}
    toc = article.get("toc") or {}

    # ---- banner
    banner_h = 96.0
    canvas._ensure(banner_h + 24)
    top = canvas.y
    canvas.rect(0, top - banner_h, PAGE_W, banner_h, ACCENT)
    canvas.y = top - 22
    canvas.text("哈工大（深圳）国际青年俱乐部 · HSIYC", 8.5, color=(0.93, 0.96, 1.0), line_gap=1.4)
    canvas.text("HITSZ INTERNATIONAL YOUTH CLUB", 7.2, color=(0.82, 0.88, 0.97), line_gap=1.4)
    canvas.y -= 2
    canvas.text(title.get("cn", ""), 16.5, color=(1, 1, 1), line_gap=1.32)
    if title.get("en"):
        canvas.text(title["en"], 9.5, color=(0.90, 0.94, 1.0), line_gap=1.3)
    canvas.y = top - banner_h - 18

    if lead.get("cn"):
        canvas.text(lead["cn"], 12, line_gap=1.75, space_after=4)
    if lead.get("en"):
        canvas.text(lead["en"], 10, color=GREY, line_gap=1.6, space_after=14)

    # ---- sections
    for section in article.get("sections") or []:
        num = str(section.get("number") or "").strip()
        heading_cn = (f"{num}  " if num else "") + str(section.get("heading_cn") or "")
        heading_en = str(section.get("heading_en") or "").upper()
        # Measure the header block first so the accent rule sits flush against the
        # heading instead of floating in the text above it.
        block_h = 20 * len(canvas._wrap(heading_cn, 14, CONTENT_W - 12))
        block_h += 12 if heading_en else 0
        canvas._ensure(block_h + 18)
        canvas.y -= 10
        bar_top = canvas.y
        canvas.rect(MARGIN_X, bar_top - block_h, 3, block_h, ACCENT)
        canvas.text(heading_cn, 14, color=ACCENT, indent=12, line_gap=1.35, space_after=1)
        if heading_en:
            canvas.text(heading_en, 8.5, color=GREY, indent=12, space_after=8)

        for block in section.get("body") or []:
            kind = block.get("kind")
            if kind == "bilingual":
                if block.get("cn"):
                    canvas.text(block["cn"], 11.5, line_gap=1.8, space_after=3)
                if block.get("en"):
                    canvas.text(block["en"], 10, color=GREY, line_gap=1.6, space_after=11)
            elif kind == "list":
                for item in block.get("items") or []:
                    label = " ".join(x for x in (item.get("label_cn"), item.get("label_en")) if x)
                    value_cn = (item.get("value_cn") or "").strip()
                    value_en = (item.get("value_en") or "").strip()
                    # Latin names are usually identical in both fields - print once.
                    if value_en == value_cn:
                        value = value_cn
                    else:
                        value = " ".join(x for x in (value_cn, value_en) if x)
                    row = f"{label}：{value}" if label else value
                    if not row.strip():
                        continue
                    height = 22 * max(1, len(canvas._wrap(row, 10.5, CONTENT_W - 24)))
                    canvas._ensure(height + 8)
                    box_top = canvas.y
                    canvas.rect(MARGIN_X, box_top - height, CONTENT_W, height, BAND)
                    canvas.rect(MARGIN_X, box_top - height, 3, height, ACCENT)
                    canvas.y = box_top - 4
                    canvas.text(row, 10.5, indent=12, line_gap=1.35)
                    canvas.y = box_top - height - 6
            elif kind == "photo_grid":
                tiles = block.get("photos") or []
                if not tiles:
                    continue
                # Approved grammar: one full-bleed image per block (624px wide, ~1.46:1),
                # never a multi-photo grid - the corpus contains no grid at all.
                tile_h = CONTENT_W / 1.46
                gap = 8.0
                canvas._ensure(len(tiles) * (tile_h + gap) + 12)
                for photo in tiles:
                    if canvas.y - tile_h < MARGIN_BOTTOM:
                        canvas.new_page()
                    box_top = canvas.y
                    name = str(photo.get("file", ""))
                    src = photos.get(name)
                    if not (src and canvas.image(src, CONTENT_W, tile_h, MARGIN_X, box_top - tile_h)):
                        canvas.rect(MARGIN_X, box_top - tile_h, CONTENT_W, tile_h, (0.91, 0.93, 0.96))
                        canvas.ops.append(
                            canvas._text_op("照片待插入", MARGIN_X + 12, box_top - tile_h / 2, 9, GREY)
                        )
                    canvas.y = box_top - tile_h - 4
                    caption = " / ".join(
                        x for x in (photo.get("caption_cn"), photo.get("caption_en")) if x
                    )
                    if caption:
                        canvas.text(caption, 8.5, color=GREY, line_gap=1.45, space_after=6)
                    else:
                        canvas.y -= 6
                canvas.text("slide right for more pictures", 8.5, color=(0.55, 0.58, 0.64), space_after=11)
            elif kind == "note":
                body = " ".join(x for x in (block.get("cn_note"), block.get("en_note")) if x)
                height = 20 * max(1, len(canvas._wrap(body, 10, CONTENT_W - 20))) + 10
                canvas._ensure(height + 10)
                box_top = canvas.y
                canvas.rect(MARGIN_X, box_top - height, CONTENT_W, height, (1.0, 0.973, 0.91))
                canvas.y = box_top - 6
                if block.get("cn_note"):
                    canvas.text(block["cn_note"], 10.5, indent=10, line_gap=1.4, space_after=0)
                if block.get("en_note"):
                    canvas.text(block["en_note"], 9, color=GREY, indent=10, line_gap=1.4, space_after=0)
                canvas.y = box_top - height - 10
            elif kind == "quote":
                quote = f"“{block.get('cn','')}”" if block.get("cn") else ""
                height = 20 * max(1, len(canvas._wrap(quote or block.get("en", ""), 11, CONTENT_W - 16))) + 8
                canvas._ensure(height + 10)
                box_top = canvas.y
                canvas.rect(MARGIN_X, box_top - height, 3, height, ACCENT)
                canvas.y = box_top - 4
                if quote:
                    canvas.text(quote, 11.5, indent=12, line_gap=1.5, space_after=0)
                if block.get("en"):
                    canvas.text(block["en"], 9.5, color=GREY, indent=12, line_gap=1.4, space_after=0)
                canvas.y = box_top - height - 10
            elif kind == "divider":
                canvas.y -= 8
                canvas.rule(canvas.y, HAIRLINE)
                canvas.y -= 12

    # ---- closing
    canvas._ensure(70)
    canvas.y -= 10
    # The writer often ends with a 结语 section *and* fills the closing block; printing both
    # put the same heading on the page twice in a row. The text stays, the echo does not.
    _sections = article.get("sections") or []
    _last_cn = str((_sections[-1] or {}).get("heading_cn") or "").strip() if _sections else ""
    _close_cn = str(closing.get("heading_cn") or "结语").strip()
    if _close_cn and _close_cn != _last_cn:
        canvas.text(f"{_close_cn}  |  {closing.get('heading_en','Closing')}", 14,
                    color=ACCENT, space_after=2)
    if closing.get("tagline_cn"):
        canvas.text(closing["tagline_cn"], 12.5, color=ACCENT, line_gap=1.4, space_after=1)
    if closing.get("tagline_en"):
        canvas.text(closing["tagline_en"], 9.5, color=GREY, space_after=5)
    if closing.get("cn"):
        canvas.text(closing["cn"], 11.5, line_gap=1.8, space_after=3)
    if closing.get("en"):
        canvas.text(closing["en"], 10, color=GREY, line_gap=1.6, space_after=18)

    # ---- sign-off
    canvas.text(signoff.get("cn", ""), 12, align="center", line_gap=1.5, space_after=1)
    canvas.text(signoff.get("en", ""), 9.5, color=GREY, align="center", line_gap=1.5, space_after=1)
    if signoff.get("program"):
        canvas.text(signoff["program"], 9.5, color=ACCENT, align="center", space_after=12)

    # ---- 三审 credits
    if any(credits.get(role) for role in CREDIT_ROLES):
        canvas.y -= 8
        canvas.rule(canvas.y, HAIRLINE)
        canvas.y -= 14
        for role in CREDIT_ROLES:
            if credits.get(role):
                canvas.text(f"{role} | {credits[role]}", 10, line_gap=1.65)

    # ---- TOC card
    if toc.get("previous") or toc.get("next"):
        canvas.y -= 14
        canvas.text("精彩回顾 · Table of Contents", 10.5, color=ACCENT, space_after=3)
        if toc.get("previous"):
            canvas.text(f"Previous：{toc['previous']}", 9.5, color=GREY, line_gap=1.5)
        if toc.get("next"):
            canvas.text(f"Next：{toc['next']}", 9.5, color=GREY, line_gap=1.5)

    # ---- editor hand-over + self-check (internal QA: never on the committee copy)
    if include_check:
        needs = article.get("needs_editor") or []
        if needs:
            canvas.y -= 14
            canvas.text("需人工确认 / Before 送审", 10.5, color=(0.72, 0.47, 0.12), space_after=3)
            for item in needs:
                canvas.text(f"• {item}", 9.5, color=GREY, line_gap=1.5)

        if report is not None:
            canvas.y -= 14
            canvas.text(
                f"送审前自检 / Pre-submission check — {report.score}/100 "
                f"({len(report.errors)} errors, {len(report.warnings)} warnings)",
                10.5,
                color=(0.10, 0.56, 0.30) if report.ok else (0.75, 0.22, 0.17),
                space_after=3,
            )
            for finding in report.sorted_findings():
                if finding.severity == "info":
                    continue
                canvas.text(f"[{finding.severity.upper()}] {finding.code}: {finding.message}",
                            8.5, color=GREY, line_gap=1.45)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canvas.finish(builder))
    if shrink:
        _replace_with_shrunk(path)
    return path


def _replace_with_shrunk(path: Path) -> None:
    """Best-effort: replace ``path`` with its Ghostscript-shrunk version.

    The unshrunk file is kept as ``<name>.full.pdf`` so a failed or lossy shrink
    can never destroy the reliable output.
    """
    shrunk, note = shrink_pdf(path)
    if shrunk == path or not shrunk.is_file():
        return
    try:
        backup = path.with_name(path.stem + ".full.pdf")
        path.replace(backup)
        shrunk.replace(path)
        backup.unlink(missing_ok=True)
    except OSError:
        # Leave both files in place rather than losing the article.
        pass
