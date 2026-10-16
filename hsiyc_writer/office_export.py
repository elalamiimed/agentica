"""Office-format exporters: a presentation deck (.pptx) and a submission tracker (.xlsx).

The bundle in :mod:`hsiyc_writer.render` already carries JSON, Markdown, HTML, DOCX and
PDF. Two things it cannot carry are the formats the club actually hands around: a deck
for presenting the event (or slicing into social posts) and one workbook that summarises
every article the club has ready for 送审.

Both exporters keep the approved visual language - navy ``#1B3870`` headings, grey
``#6B7482`` secondary text, body ``#4C4C4C`` - and both treat the article JSON as the
only source of truth: an empty field is omitted, never filled in with a plausible guess.

The interpreter the project runs on ships without ``python-pptx``; a second site-packages
directory that has it is appended to ``sys.path`` at call time (see
:func:`_import_optional`). Importing this module never fails because a library is
missing - only the export that needs it raises, and it says exactly what to fix.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

from .render import _pair_text, ACCENT, CJK_FONT, INK, LATIN_FONT

# The DOCX/PDF renderers use #1A4F9C; the deck follows the measured brand navy instead,
# because a projected slide has no white page around it to soften a royal blue.
NAVY = ACCENT                 # #1B3870 - headings, bands, table headers
GREY = "#6B7482"              # #6B7482 - secondary text (English, captions, meta)
PAPER = "#FFFFFF"
INK = INK                     # #4C4C4C - body copy

# 16:9, the only aspect the club's screens and WeChat cards agree on.
SLIDE_W_IN, SLIDE_H_IN = 13.333, 7.5
MARGIN_IN = 0.75
BAND_IN = 0.55                # the navy rule along the top of every content slide

_CJK_FONT_FILES = (
    Path(r"C:\Windows\Fonts\msyh.ttc"),
    Path(r"C:\Windows\Fonts\msyh.ttf"),
    Path(r"C:\Windows\Fonts\simhei.ttf"),
)
_LINE_FACTOR = 1.35           # PowerPoint single spacing for a CJK face, in em

EXTRA_SITE_PACKAGES = os.environ.get("HSIYC_EXTRA_SITE_PACKAGES") or (
    r"C:\Users\hp\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\Lib\site-packages"
)

# What each optional library gives the club, and the one line that fixes it when it is
# absent. Kept next to the import helper so a failure message never goes stale.
_MODULES = {
    "pptx": ("PowerPoint slides", "pip install python-pptx"),
    "openpyxl": ("Excel workbooks", "pip install openpyxl"),
    "docx": ("Word documents", "pip install python-docx"),
}


class OfficeUnavailable(RuntimeError):
    """A library an export needs is not importable from this interpreter."""


# --------------------------------------------------------------------------- imports
def _import_optional(name: str):
    """Import a module, falling back to the bundled site-packages once.

    The directory is *appended*, never inserted, so the interpreter's own packages always
    win - the system ``lxml``/``Pillow`` are the ones this code was tested against.
    """
    try:
        return importlib.import_module(name)
    except ImportError:
        pass
    extra = Path(EXTRA_SITE_PACKAGES)
    if extra.is_dir() and EXTRA_SITE_PACKAGES not in sys.path:
        sys.path.append(EXTRA_SITE_PACKAGES)
        try:
            return importlib.import_module(name)
        except ImportError:
            return None
    return None


def _require(name: str):
    module = _import_optional(name)
    if module is None:
        what, fix = _MODULES.get(name, (name, f"pip install {name}"))
        raise OfficeUnavailable(
            f"the {what} exporter needs the '{name}' library, which is not importable. "
            f"Fix: {fix} - or point HSIYC_EXTRA_SITE_PACKAGES at a site-packages "
            f"directory that contains it (currently {EXTRA_SITE_PACKAGES})."
        )
    return module


def capabilities() -> dict:
    """Which Office formats this interpreter can actually produce."""
    return {name: _import_optional(name) is not None for name in _MODULES}


# --------------------------------------------------------------------------- helpers
def _txt(value: Any) -> str:
    """Article fields are read as text; ``None`` is empty, and so is a blank string."""
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    return text.strip()


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _sections(article: Any) -> list[dict]:
    source = article.get("sections") if isinstance(article, dict) else None
    if not isinstance(source, (list, tuple)):
        return []
    return [s for s in source if isinstance(s, dict)]


def _blocks(section: dict) -> list[dict]:
    source = section.get("body")
    if not isinstance(source, (list, tuple)):
        return []
    return [b for b in source if isinstance(b, dict)]


def _count_cjk(value: Any) -> int:
    return sum(1 for ch in str(value or "") if "\u4e00" <= ch <= "\u9fff")


def _body_cjk(article: dict) -> int:
    """Chinese characters in the body copy - the same span the validator counts."""
    total = _count_cjk(_dict(article.get("lead")).get("cn"))
    for section in _sections(article):
        for block in _blocks(section):
            kind = block.get("kind")
            if kind in ("bilingual", "quote"):
                total += _count_cjk(block.get("cn"))
            elif kind == "list":
                for item in block.get("items") or []:
                    if isinstance(item, dict):
                        total += _count_cjk(item.get("value_cn")) + _count_cjk(item.get("label_cn"))
            elif kind == "note":
                total += _count_cjk(block.get("cn_note"))
    closing = _dict(article.get("closing"))
    return total + _count_cjk(closing.get("cn")) + _count_cjk(closing.get("tagline_cn"))


def _photo_count(article: dict) -> int:
    total = 0
    for section in _sections(article):
        for block in _blocks(section):
            if block.get("kind") == "photo_grid":
                total += len([p for p in (block.get("photos") or []) if isinstance(p, dict)])
    return total


# --------------------------------------------------------------------------- metrics
class _Metrics:
    """Text measurement, so a slide is sized from real glyph widths, not from guessing.

    PIL renders with the same CJK face the deck asks PowerPoint for, so the advance
    widths match what the reader sees. If the font cannot be read the fallback (1.0 em
    per CJK glyph, 0.5 em per Latin) merely over-estimates, which is the safe direction:
    text is capped a little earlier than strictly necessary, never later.
    """

    def __init__(self, size: float):
        self.size = float(size)
        self._font = None
        self._widths: dict[str, float] = {}
        for path in _CJK_FONT_FILES:
            try:
                from PIL import ImageFont

                self._font = ImageFont.truetype(str(path), 100)
                break
            except Exception:  # noqa: BLE001 - measuring is an optimisation, not a need
                self._font = None

    def width(self, text: str) -> float:
        if self._font is not None:
            try:
                cached = self._widths.get(text)
                if cached is None:
                    cached = float(self._font.getlength(text)) * self.size / 100.0
                    if len(self._widths) < 4096:
                        self._widths[text] = cached
                return cached
            except Exception:  # noqa: BLE001
                pass
        return sum(self.size if ord(ch) > 0x2E80 else self.size * 0.5 for ch in text)

    def line_height(self) -> float:
        return self.size * _LINE_FACTOR

    def wrapped_lines(self, text: str, width_pt: float) -> int:
        """How many lines ``text`` occupies in a box ``width_pt`` wide."""
        if not text:
            return 0
        if self.width(text) <= width_pt:
            return 1
        lines = 1
        current = 0.0
        for ch in text:
            if ch == "\n":
                lines += 1
                current = 0.0
                continue
            advance = self.width(ch)
            if current + advance > width_pt and current > 0:
                lines += 1
                current = 0.0
            current += advance
        return lines

    def height(self, text: str, width_pt: float, space_after_pt: float = 0.0) -> float:
        return self.wrapped_lines(text, width_pt) * self.line_height() + space_after_pt


def _split_cn(text: str, limit: int, sentence_only: bool = False) -> tuple[str, str]:
    """Break Chinese copy into two parts as near ``limit`` characters as the grammar allows.

    Returns ``("", text)`` when there is nothing sensible to break on - the caller then
    moves the whole paragraph to the next slide instead of cutting a sentence in half.
    """
    if len(text) <= limit:
        return text, ""
    window = text[:limit]
    for mark in ("。", "！", "？", "；", "”", "…"):
        cut = window.rfind(mark)
        if cut >= max(24, limit // 3):
            return text[: cut + 1], text[cut + 1 :].lstrip()
    if sentence_only:
        return "", text
    comma = window.rfind("，")
    if comma >= max(24, limit // 3):
        return text[: comma + 1], text[comma + 1 :].lstrip()
    return text[:limit], text[limit:]


def _split_en(text: str, target: int) -> tuple[str, str]:
    """The same split for the English twin, on a word or sentence boundary."""
    if not text or target <= 0 or len(text) <= target:
        return text, ""
    for mark in (". ", "! ", "? ", "; "):
        cut = text.rfind(mark, 0, target + 8)
        if cut >= max(24, target // 3):
            return text[: cut + 1].rstrip(), text[cut + 1 :].lstrip()
    cut = text.rfind(" ", 0, target)
    if cut < 0:
        return text, ""
    return text[:cut].rstrip(), text[cut + 1 :].lstrip()


def _fit_block(specs: list[dict], width_pt: float, height_pt: float,
               floor: float = 0.62) -> tuple[list[dict], float]:
    """Shrink a stack of paragraphs until it fits its block, and say how tall it ends up.

    Titles, taglines and sign-offs have no continuation slide to move onto, so the only
    honest options are "make it smaller" or "let it run off the slide". The estimate is
    deliberately pessimistic - line breaks are found against nine tenths of the real
    width, because PowerPoint's line breaking differs from ours in the last few percent
    and this is the direction where being wrong costs nothing but a point of type size.
    """
    if not specs:
        return specs, 0.0
    reference = _Metrics(11.0)
    wrap_width = width_pt * 0.9

    def measure(scale: float) -> float:
        total = 0.0
        for spec in specs:
            size = max(8.0, float(spec.get("size") or 18) * scale)
            text = _txt(spec.get("text"))
            paragraphs = text.split("\n")
            lines = sum(reference.wrapped_lines(part, wrap_width) for part in paragraphs) or 1
            total += lines * size * _LINE_FACTOR
            total += float(spec.get("space_before") or 0) + float(spec.get("space_after") or 0)
        return total

    scale = 1.0
    while scale > floor and measure(scale) > height_pt:
        scale = round(scale - 0.03, 2)
    if scale >= 0.999:
        return specs, min(measure(1.0), height_pt)
    fitted = []
    for spec in specs:
        shrink = dict(spec)
        shrink["size"] = max(8.0, float(spec.get("size") or 18) * scale)
        for key in ("space_before", "space_after"):
            if spec.get(key):
                shrink[key] = float(spec[key]) * scale
        fitted.append(shrink)
    return fitted, min(measure(scale), height_pt)


# --------------------------------------------------------------------------- pptx
def _set_font(run, size_pt: float, *, bold: bool = False, color: str | None = None,
              italic: bool = False, spacing_pt: float | None = None) -> None:
    """One run, styled for both scripts: Latin face plus the CJK face PowerPoint needs.

    python-pptx only writes ``a:latin``; without the explicit ``a:ea`` a Chinese run is
    rendered by whatever fallback font the viewer's machine happens to have.
    """
    from pptx.dml.color import RGBColor
    from pptx.oxml.ns import qn
    from pptx.util import Pt

    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.italic = italic
    run.font.name = LATIN_FONT
    if color:
        run.font.color.rgb = RGBColor.from_string(color.lstrip("#").upper())
    rPr = run._r.get_or_add_rPr()
    for tag, face in (("a:ea", CJK_FONT), ("a:cs", CJK_FONT)):
        node = rPr.find(qn(tag))
        if node is None:
            node = rPr.makeelement(qn(tag), {})
            rPr.append(node)
        node.set("typeface", face)
    if spacing_pt:
        rPr.set("spc", str(int(round(spacing_pt * 100))))


def _textbox(slide, x_in: float, y_in: float, w_in: float, h_in: float, *, anchor=None):
    """A real text box with wrapping on and autofit off, so our own maths is the layout."""
    from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE
    from pptx.util import Inches

    box = slide.shapes.add_textbox(Inches(x_in), Inches(y_in), Inches(w_in), Inches(h_in))
    frame = box.text_frame
    frame.word_wrap = True
    frame.auto_size = MSO_AUTO_SIZE.NONE
    frame.margin_left = 0
    frame.margin_right = 0
    frame.margin_top = 0
    frame.margin_bottom = 0
    frame.vertical_anchor = anchor if anchor is not None else MSO_ANCHOR.TOP
    return frame


def _write(frame, paragraphs: Sequence[dict]) -> None:
    """Fill a frame from ``{text,size,bold,color,italic,align,space_before,space_after}``.

    A paragraph whose text is empty is skipped, never rendered as a blank line: every
    element on a slide exists because a field in the article exists.
    """
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Pt

    first = True
    for spec in paragraphs:
        text = _txt(spec.get("text"))
        if not text:
            continue
        para = frame.paragraphs[0] if first else frame.add_paragraph()
        first = False
        align = spec.get("align")
        if align:
            para.alignment = getattr(PP_ALIGN, align)
        if spec.get("space_before"):
            para.space_before = Pt(float(spec["space_before"]))
        if spec.get("space_after"):
            para.space_after = Pt(float(spec["space_after"]))
        run = para.add_run()
        run.text = text
        _set_font(
            run,
            float(spec.get("size") or 18),
            bold=bool(spec.get("bold")),
            color=spec.get("color"),
            italic=bool(spec.get("italic")),
            spacing_pt=spec.get("spacing"),
        )


def _band(slide, height_in: float = BAND_IN, color: str = NAVY) -> None:
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Inches

    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, 0, Inches(SLIDE_W_IN), Inches(height_in)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor.from_string(color.lstrip("#").upper())
    shape.line.fill.background()
    shape.shadow.inherit = False


def _picture(slide, path: Path, *, max_w: float, max_h: float, x: float, y: float,
             center_x: bool = False) -> float:
    """Place an image inside a box, keeping its aspect ratio. Returns the height used."""
    from pptx.util import Inches

    try:
        from PIL import Image

        with Image.open(path) as image:
            px_w, px_h = image.size
    except Exception:  # noqa: BLE001 - an unreadable file is skipped like a missing one
        return 0.0
    if not px_w or not px_h:
        return 0.0
    scale = min(max_w / px_w, max_h / px_h)
    w_in, h_in = px_w * scale, px_h * scale
    left = (SLIDE_W_IN - w_in) / 2.0 if center_x else x + (max_w - w_in) / 2.0
    slide.shapes.add_picture(str(path), Inches(left), Inches(y), Inches(w_in), Inches(h_in))
    return h_in


def _table_style(table, style_id: str) -> None:
    """Pin the table style.

    python-pptx defaults to ``mediumStyle2Accent1``, which paints a blue of its own
    choosing over the header row and fights the club navy. Naming the style explicitly
    keeps the table on-brand in PowerPoint, LibreOffice and Keynote alike.
    """
    from pptx.oxml.ns import qn

    tbl_pr = table._tbl.find(qn("a:tblPr"))
    if tbl_pr is None:
        return
    tbl_pr.set("firstRow", "1")
    tbl_pr.set("bandRow", "0")
    for node in tbl_pr.findall(qn("a:tableStyleId")):
        tbl_pr.remove(node)
    node = tbl_pr.makeelement(qn("a:tableStyleId"), {})
    node.text = style_id
    tbl_pr.append(node)


def _fill_cell(cell, color: str) -> None:
    from pptx.dml.color import RGBColor

    cell.fill.solid()
    cell.fill.fore_color.rgb = RGBColor.from_string(color.lstrip("#").upper())


def _add_table(slide, rows: Sequence[tuple[str, str]], x: float, y: float, w: float,
               size_pt: float = 13.0, header: tuple[str, str] | None = None) -> float:
    """A real PowerPoint table (never an image), navy-headered. Returns the height used."""
    from pptx.enum.text import MSO_ANCHOR
    from pptx.util import Inches

    n_rows = len(rows) + (1 if header else 0)
    row_h = 0.46
    shape = slide.shapes.add_table(
        n_rows, 2, Inches(x), Inches(y), Inches(w), Inches(row_h * n_rows)
    )
    table = shape.table
    _table_style(table, "{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}")  # "No Style, Table Grid"
    table.columns[0].width = Inches(w * 0.34)
    table.columns[1].width = Inches(w * 0.66)

    def fill_cell(cell, text: str, *, bold: bool, color: str, background: str) -> None:
        cell.text = text
        cell.margin_left = Inches(0.10)
        cell.margin_right = Inches(0.10)
        cell.margin_top = Inches(0.02)
        cell.margin_bottom = Inches(0.02)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        _fill_cell(cell, background)
        for para in cell.text_frame.paragraphs:
            for run in para.runs:
                _set_font(run, size_pt, bold=bold, color=color)

    index = 0
    if header:
        table.rows[0].height = Inches(row_h)
        for column, text in enumerate(header):
            fill_cell(table.cell(0, column), text, bold=True, color=PAPER, background=NAVY)
        index = 1
    for offset, (label, value) in enumerate(rows):
        table.rows[index + offset].height = Inches(row_h)
        background = PAPER if offset % 2 == 0 else "#F6F7FA"
        fill_cell(table.cell(index + offset, 0), label, bold=True, color=NAVY,
                  background=background)
        fill_cell(table.cell(index + offset, 1), value, bold=False, color=INK,
                  background=background)
    return row_h * n_rows


# --------------------------------------------------------------------------- content
def _asset_path(art: Any, kind: str) -> Path | None:
    """Find a named asset in a manifest, accepting the shapes the club actually writes.

    ``hsiyc_writer.art`` emits ``{"assets": [{"kind": "banner", "file": "banner.png"}, …]}``;
    a hand-written manifest is more likely to be ``{"banner": "banner.png"}`` or
    ``{"assets": {"banner": {"path": …}}}``. All three are read here, and anything else is
    ignored rather than guessed at, so an unrecognised manifest degrades to a clean deck.
    """
    if not art:
        return None

    def candidate(value: Any) -> Path | None:
        if isinstance(value, str) and value.strip():
            return Path(value)
        if isinstance(value, dict):
            for key in ("file", "path", "file_path", "src", "image"):
                if isinstance(value.get(key), str) and value[key].strip():
                    return Path(value[key])
        return None

    def named(entry: Any) -> Path | None:
        if not isinstance(entry, dict):
            return None
        if str(entry.get("kind") or entry.get("role") or "") != kind:
            return None
        return candidate(entry)

    if isinstance(art, dict):
        # The asset list first: a dict that carries one is the art module's own schema.
        for container in (art.get("assets"), art.get("images")):
            if isinstance(container, list):
                for entry in container:
                    found = named(entry)
                    if found is not None:
                        return found
            if isinstance(container, dict) and kind in container:
                found = candidate(container[kind])
                if found is not None:
                    return found
        direct = candidate(art.get(kind))
        if direct is not None:
            return direct
    if isinstance(art, list):
        for entry in art:
            found = named(entry)
            if found is not None:
                return found
    return None


def _resolve(path: Path | None, roots: Sequence[Path]) -> Path | None:
    """A manifest may name an asset relative to the workspace or to its own folder."""
    if path is None:
        return None
    if path.is_file():
        return path
    for root in roots:
        for candidate in (root / path, root / path.name):
            if candidate.is_file():
                return candidate
    return None


def _section_flows(section: dict) -> list[list[dict]]:
    """One section as page-flows: a bilingual run, or a list, or a photo, per flow.

    A flow is the smallest unit that must not be left dangling - a Chinese paragraph and
    its English twin, or a ranking list and its header. Photos are their own flow: a
    missing file simply makes one vanish, which must not disturb the pagination above it.
    """
    flows: list[list[dict]] = []
    pending: list[dict] = []
    for block in _blocks(section):
        kind = block.get("kind")
        if kind in ("bilingual", "note", "quote"):
            cn = _txt(block.get("cn") or block.get("cn_note"))
            en = _txt(block.get("en") or block.get("en_note"))
            if cn or en:
                pending.append({"kind": "bilingual", "cn": cn, "en": en,
                                "quote": kind == "quote"})
        elif kind == "list":
            items = [i for i in (block.get("items") or []) if isinstance(i, dict)]
            items = [i for i in items
                     if any(_txt(i.get(key)) for key in
                            ("label_cn", "label_en", "value_cn", "value_en"))]
            if items:
                if pending:
                    flows.append(pending)
                    pending = []
                flows.append([{"kind": "list", "items": items}])
        elif kind == "photo_grid":
            photos = [p for p in (block.get("photos") or [])
                      if isinstance(p, dict) and _txt(p.get("file"))]
            if photos:
                if pending:
                    flows.append(pending)
                    pending = []
                flows.append([{"kind": "photo", "photo": photos[0]}])
    if pending:
        flows.append(pending)
    return flows


def _title_slide(prs, article: dict, art: Any, roots: Sequence[Path]) -> None:
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import MSO_ANCHOR
    from pptx.util import Inches

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    meta = _dict(article.get("meta"))
    title = _dict(article.get("title"))

    banner = _resolve(_asset_path(art, "banner"), roots)
    used_banner = False
    if banner is not None:
        try:
            # Added first, so it sits behind every text box (z-order is insertion order).
            slide.shapes.add_picture(str(banner), 0, 0, Inches(SLIDE_W_IN), Inches(SLIDE_H_IN))
            used_banner = True
        except Exception:  # noqa: BLE001 - a bad image must not lose the deck
            used_banner = False
    if not used_banner:
        _band(slide, SLIDE_H_IN)  # full-bleed navy ground for the title
        rule = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, 0, Inches(SLIDE_H_IN - 0.09), Inches(SLIDE_W_IN), Inches(0.09)
        )
        rule.fill.solid()
        rule.fill.fore_color.rgb = RGBColor.from_string("2F7AD1")
        rule.line.fill.background()
        rule.shadow.inherit = False

    head = _textbox(slide, 1.0, 0.85, SLIDE_W_IN - 2.0, 1.3)
    _write(head, [
        {"text": "哈工大（深圳）国际青年俱乐部 · HSIYC", "size": 13, "bold": True,
         "color": PAPER, "spacing": 2.4},
        {"text": "HITSZ INTERNATIONAL YOUTH CLUB", "size": 10, "color": "#C7D0E0",
         "spacing": 2.0, "space_before": 4},
    ])

    date = _txt(meta.get("event_date")) or _txt(meta.get("event_end_date"))
    venue = _txt(meta.get("venue"))
    meta_bits = [bit for bit in (
        f"时间 Time: {date}" if date else "",
        f"地点 Venue: {venue}" if venue else "",
    ) if bit]

    # The title block sits in the lower two-thirds: that is where a 16:9 poster puts its
    # reading line, and it keeps the title clear of the club letterhead. Its height is
    # measured before the frame is placed, so a long headline and subtitle simply move the
    # block up, and a very long one shrinks instead of colliding with the date line.
    budget = (6.05 - 2.0) * 72.0
    specs: list[dict] = []
    if _txt(title.get("cn")):
        specs.append({"text": title["cn"], "size": 34, "bold": True, "color": PAPER,
                      "align": "CENTER"})
    if _txt(title.get("en")):
        specs.append({"text": title["en"], "size": 17, "italic": True, "color": "#D5DCEA",
                      "align": "CENTER", "space_before": 14})
    if _txt(title.get("subtitle_cn")):
        specs.append({"text": title["subtitle_cn"], "size": 14, "color": "#B9C6DC",
                      "align": "CENTER", "space_before": 10})
    if _txt(title.get("kicker_en")):
        specs.append({"text": title["kicker_en"], "size": 10.5, "bold": True,
                      "color": "#9FB0CC", "align": "CENTER", "spacing": 1.8,
                      "space_before": 12})
    specs, block_pt = _fit_block(specs, (SLIDE_W_IN - 2.0) * 72.0, budget)
    frame = _textbox(slide, 1.0, 2.35 - block_pt / 144.0, SLIDE_W_IN - 2.0, block_pt / 72.0,
                     anchor=MSO_ANCHOR.MIDDLE)
    _write(frame, specs)

    if meta_bits:
        meta_frame = _textbox(slide, 1.0, 6.35, SLIDE_W_IN - 2.0, 0.5)
        _write(meta_frame, [{"text": " ｜ ".join(meta_bits), "size": 12, "color": "#D5DCEA",
                             "align": "CENTER"}])


def _section_slide(prs, section: dict, items: Sequence[dict], *, continued: bool,
                   photos: dict[str, Path]):
    """Draw one section page; returns the drawn slide (the tests check its bounds)."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _band(slide)
    x = MARGIN_IN
    width = SLIDE_W_IN - 2 * MARGIN_IN
    y = BAND_IN + 0.34

    heading_cn = _txt(section.get("heading_cn"))
    heading_en = _txt(section.get("heading_en"))
    number = _txt(section.get("number"))
    if continued:
        heading_cn = f"{heading_cn}（续）" if heading_cn else "（续）"
        heading_en = f"{heading_en} (continued)" if heading_en else "Continued"
    head = _textbox(slide, x, y, width, 1.25)
    specs = [{"text": f"{number}　{heading_cn}".strip() if number else heading_cn,
              "size": 27, "bold": True, "color": PAPER}]
    if heading_en:
        specs.append({"text": heading_en, "size": 13, "color": "#C7D0E0", "spacing": 0.8,
                      "space_before": 3})
    _write(head, specs)
    y += (0.78 if heading_en else 0.52) + 0.16

    for item in items:
        kind = item.get("kind")
        if kind == "bilingual":
            height = item["_h"] / 72.0
            frame = _textbox(slide, x, y, width, height)
            specs = []
            if item.get("cn"):
                specs.append({"text": item["cn"], "size": 15, "color": INK,
                              "italic": bool(item.get("quote")),
                              "space_after": 4 if item.get("en") else 0})
            if item.get("en"):
                specs.append({"text": item["en"], "size": 13, "color": GREY, "italic": True})
            _write(frame, specs)
            y += height + 0.12
        elif kind == "list":
            height = _add_table(slide, item["_rows"], x, y, width * 0.72, size_pt=12.5,
                                header=("项目 Item", "名单 Name"))
            y += height + 0.16
        elif kind == "photo":
            photo = _dict(item.get("photo"))
            name = _txt(photo.get("file"))
            found = photos.get(name)
            if found is not None and Path(found).is_file():
                y += _picture(slide, Path(found), max_w=width, max_h=item.get("_photo_h", 3.2),
                              x=x, y=y) + 0.06
            caption = " ｜ ".join(bit for bit in (_txt(photo.get("caption_cn")),
                                                 _txt(photo.get("caption_en"))) if bit)
            if caption:
                _write(_textbox(slide, x, y, width, 0.4),
                       [{"text": caption, "size": 10.5, "color": GREY}])
                y += 0.34
    return slide


def _layout_section(section: dict, metrics: _Metrics, width_pt: float,
                    first_h_pt: float, next_h_pt: float) -> list[list[dict]]:
    """Paginate one section's body into slide-sized pages.

    A page is a list of placed items; ``_h`` on each is its measured height in points, so
    the drawing pass never re-measures. Long paragraphs are split at a sentence boundary
    and the tail continues on the next slide - never clipped, never shrunk to nothing.
    """
    pages: list[list[dict]] = []
    page: list[dict] = []
    used = 0.0
    cap = first_h_pt

    def flush() -> None:
        nonlocal page, used, cap
        if page:
            pages.append(page)
        page = []
        used = 0.0
        cap = next_h_pt

    for flow in _section_flows(section):
        for item in flow:
            kind = item.get("kind")
            if kind == "bilingual":
                remaining_cn, remaining_en = item["cn"], item["en"]
                while remaining_cn or remaining_en:
                    line_pt = metrics.line_height()
                    # Both twins are measured at the Chinese size: the English run is set
                    # 2pt smaller, so measuring it with the larger metrics can only
                    # over-estimate, which is the direction that cannot overflow.
                    cn_h = metrics.height(remaining_cn, width_pt, 4) if remaining_cn else 0.0
                    en_h = metrics.height(remaining_en, width_pt) if remaining_en else 0.0
                    need = (cn_h + en_h) * 1.1 + 8.0
                    if used + need <= cap or not page:
                        page.append({"kind": "bilingual", "cn": remaining_cn, "en": remaining_en,
                                     "quote": item.get("quote"), "_h": need})
                        used += need
                        remaining_cn = remaining_en = ""
                        continue
                    # Split the pair, keeping the English twin proportional to the Chinese.
                    room = max(cap - used, line_pt + 8.0)
                    chars = max(1, int(room / line_pt))
                    head_cn, tail_cn = _split_cn(remaining_cn, max(chars - 1, 1),
                                                 sentence_only=True)
                    if not head_cn:      # nothing but a partial sentence left: start a page
                        flush()
                        continue
                    if remaining_en:
                        share = len(head_cn) / max(1, len(remaining_cn))
                        target = max(1, int(len(remaining_en) * share))
                        head_en, tail_en = _split_en(remaining_en, target)
                    else:
                        head_en, tail_en = "", ""
                    split_h = (cn_h + en_h) * 1.1 + 8.0
                    page.append({"kind": "bilingual", "cn": head_cn, "en": head_en,
                                 "quote": item.get("quote"), "_h": split_h})
                    used += split_h
                    remaining_cn, remaining_en = tail_cn, tail_en
                    flush()
            elif kind == "list":
                rows: list[tuple[str, str]] = []
                for entry in item["items"]:
                    label = _pair_text(_txt(entry.get("label_cn")), _txt(entry.get("label_en")))
                    value = _pair_text(_txt(entry.get("value_cn")), _txt(entry.get("value_en")))
                    if label or value:
                        rows.append((label, value))
                row_pt = 0.46 * 72.0
                header_pt = row_pt if not page else 0.0
                while rows:
                    if used + header_pt + len(rows) * row_pt + 10.0 <= cap:
                        page.append({"kind": "list", "_rows": rows,
                                     "_h": header_pt + len(rows) * row_pt + 10.0})
                        used += header_pt + len(rows) * row_pt + 10.0
                        rows = []
                        break
                    if used > 0:          # the table needs the whole next page
                        flush()
                        header_pt = row_pt
                        continue
                    fits = max(1, int((cap - header_pt - 10.0) // row_pt))
                    chunk, rows = rows[:fits], rows[fits:]
                    if rows:
                        chunk = chunk + [("…", f"还有 {len(rows)} 项 / {len(rows)} more")]
                    page.append({"kind": "list", "_rows": chunk,
                                 "_h": header_pt + len(chunk) * row_pt + 10.0})
                    used += header_pt + len(chunk) * row_pt + 10.0
                    flush()
                    header_pt = row_pt
            elif kind == "photo":
                need = 3.2 * 72.0 + 30.0
                if used and used + need > cap:
                    flush()
                page.append({"kind": "photo", "photo": item.get("photo"),
                             "_photo_h": 3.2, "_h": need})
                used += need
    flush()
    return [page for page in pages if page]


def _closing_slide(prs, article: dict, art: Any, roots: Sequence[Path]) -> None:
    from pptx.enum.text import MSO_ANCHOR

    closing = _dict(article.get("closing"))
    signoff = _dict(article.get("signoff"))
    heading_cn = _txt(closing.get("heading_cn")) or "结语"
    heading_en = _txt(closing.get("heading_en")) or "Closing"

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _band(slide, SLIDE_H_IN)
    text_w = SLIDE_W_IN - 2 * MARGIN_IN
    poster = _resolve(_asset_path(art, "poster"), roots)
    if poster is not None:
        try:
            # Poster art on the right, the club's own words on the left.
            _picture(slide, poster, max_w=4.6, max_h=5.4, x=8.1, y=1.1)
            text_w = 6.9
        except Exception:  # noqa: BLE001 - keep the words, lose the picture
            text_w = SLIDE_W_IN - 2 * MARGIN_IN

    # The closing slide carries a tagline, two paragraphs and the sign-off; the stack is
    # measured first, so a long closing paragraph shrinks and centres instead of running
    # past the slide or colliding with the table of contents line.
    specs: list[dict] = [{"text": f"{heading_cn}  |  {heading_en}", "size": 24, "bold": True,
                          "color": PAPER}]
    if _txt(closing.get("tagline_cn")):
        specs.append({"text": closing["tagline_cn"], "size": 25, "bold": True,
                      "color": "#FFEE8A", "space_before": 20})
    if _txt(closing.get("tagline_en")):
        specs.append({"text": closing["tagline_en"], "size": 13, "italic": True,
                      "color": "#D5DCEA", "space_before": 8})
    if _txt(closing.get("cn")):
        specs.append({"text": closing["cn"], "size": 14, "color": "#E4E9F2", "space_before": 20})
    if _txt(closing.get("en")):
        specs.append({"text": closing["en"], "size": 12, "italic": True, "color": "#B9C6DC",
                      "space_before": 8})
    if _txt(signoff.get("cn")):
        specs.append({"text": signoff["cn"], "size": 14, "bold": True, "color": PAPER,
                      "space_before": 30})
    if _txt(signoff.get("en")):
        specs.append({"text": signoff["en"], "size": 11, "color": "#C7D0E0", "space_before": 4})
    if _txt(signoff.get("program")):
        specs.append({"text": signoff["program"], "size": 11, "color": "#9FB0CC",
                      "space_before": 4})
    specs, block_pt = _fit_block(specs, text_w * 72.0, 5.0 * 72.0 - 16.0, floor=0.58)
    frame = _textbox(slide, MARGIN_IN, 1.0 + (5.0 * 72.0 - block_pt) / 144.0, text_w,
                     min(5.0, block_pt / 72.0), anchor=MSO_ANCHOR.MIDDLE)
    _write(frame, specs)

    toc = _dict(article.get("toc"))
    bits = []
    if _txt(toc.get("previous")):
        bits.append(f"精彩回顾 Previous: {toc['previous']}")
    if _txt(toc.get("next")):
        bits.append(f"Next: {toc['next']}")
    if bits:
        toc_frame = _textbox(slide, MARGIN_IN, 6.4, SLIDE_W_IN - 2 * MARGIN_IN, 0.6)
        _write(toc_frame, [{"text": " ｜ ".join(bits), "size": 11, "color": "#9FB0CC"}])


def _credits_slide(prs, article: dict) -> None:
    from .validate import CREDIT_ROLES

    credits = _dict(article.get("credits"))
    rows = [(role, _txt(credits.get(role))) for role in CREDIT_ROLES]
    rows = [row for row in rows if row[1]]

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _band(slide)
    head = _textbox(slide, MARGIN_IN, BAND_IN + 0.34, SLIDE_W_IN - 2 * MARGIN_IN, 0.9)
    _write(head, [
        {"text": "出品团队 | Credits", "size": 27, "bold": True, "color": PAPER},
        {"text": "三审三校 Three-stage review", "size": 12, "color": "#C7D0E0",
         "space_before": 4},
    ])
    if rows:
        _add_table(slide, rows, MARGIN_IN, BAND_IN + 1.5,
                   (SLIDE_W_IN - 2 * MARGIN_IN) * 0.72, size_pt=14.0,
                   header=("角色 Role", "署名 Name"))
    else:
        # No credits in the JSON: say so, rather than inventing a roster.
        _write(_textbox(slide, MARGIN_IN, BAND_IN + 1.6, SLIDE_W_IN - 2 * MARGIN_IN, 0.6),
               [{"text": "本文章未填写署名 / No credits recorded for this article",
                 "size": 14, "color": "#C7D0E0"}])


def export_deck(article: dict, path: Path, *, art: Any = None,
                photos: dict[str, Path] | None = None) -> Path:
    """Write the 16:9 presentation deck for one article bundle.

    Every string comes from ``article``; ``art`` may add a title-slide banner and a
    closing-slide poster, and ``photos`` supplies the files a ``photo_grid`` block names.
    Both are optional - a deck is always produced, because slides that are merely plain
    are still usable and a missing deck is not.
    """
    pptx = _require("pptx")
    from pptx.util import Inches

    photos = photos or {}
    roots: list[Path] = [Path.cwd()]
    for value in (Path(path), Path(path).parent, Path(path).parent.parent):
        if value not in roots:
            roots.append(value)
    if isinstance(art, (str, os.PathLike)):
        manifest = Path(art)
        roots.insert(0, manifest.parent)
        try:
            art = json.loads(manifest.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            art = None

    article = article if isinstance(article, dict) else {}
    width_pt = (SLIDE_W_IN - 2 * MARGIN_IN) * 72.0
    metrics = _Metrics(15.0)

    prs = pptx.Presentation()
    prs.slide_width = Inches(SLIDE_W_IN)
    prs.slide_height = Inches(SLIDE_H_IN)

    _title_slide(prs, article, art, roots)

    first_h = (SLIDE_H_IN - (BAND_IN + 0.34) - 0.45) * 72.0     # ~6.15in of body room
    next_h = (SLIDE_H_IN - (BAND_IN + 0.34) - 0.65) * 72.0
    for section in _sections(article):
        pages = _layout_section(section, metrics, width_pt, first_h, next_h)
        if not pages:
            pages = [[]]        # a heading-only slide is still that section's page
        for index, page in enumerate(pages):
            _section_slide(prs, section, page, continued=index > 0, photos=photos)

    _closing_slide(prs, article, art, roots)
    _credits_slide(prs, article)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(path))
    return path


# --------------------------------------------------------------------------- xlsx
_ARTICLE_HEADERS = [
    "Slug", "Doc type 类型", "Event date 日期", "Venue 地点",
    "Title CN 中文标题", "Title EN", "Sections 章节",
    "CN chars 中文字数", "Photos 图片", "Score 得分",
    "Errors 错误", "Warnings 警告", "Needs editor 待确认",
    "Output files 产出文件",
]
_CREDIT_HEADERS = ["Bundle", "文字", "图片", "排版", "一审", "二审", "三审"]
_ISSUE_HEADERS = ["Bundle", "Severity 级别", "Code 代码", "Message 说明", "Hint 建议"]
_SEVERITY_CN = {"error": "错误 error", "warning": "警告 warning", "info": "提示 info"}
_BUNDLE_FILES = ("check_report.json", "check_report.txt", "run_log.json")
# Columns that must stay numeric so the club can sort and average them in Excel.
_NUMERIC_COLUMNS = (7, 8, 9, 10, 11, 12, 13)


def _as_int(value: Any) -> int | None:
    """A number if the report gave one, otherwise ``None`` - which is what blank cells are."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value.strip().replace(",", "")))
        except ValueError:
            return None
    return None


def _article_file(bundle: Path) -> Path | None:
    """The article JSON inside a bundle: ``<slug>.json``, never a report or a log."""
    ignore = {"check_report.json", "run_log.json", "manifest.json"}
    candidates = sorted(
        path for path in bundle.glob("*.json")
        if path.name not in ignore and not path.name.endswith(".check.json")
    )
    for candidate in candidates:
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        if isinstance(payload, dict) and ("title" in payload or "sections" in payload):
            return candidate
    return candidates[0] if candidates else None


def _load_bundle(bundle: Path) -> dict:
    """Everything the tracker needs from one bundle directory; never raises.

    A bundle is a directory a human may have edited, so every read is defensive: a missing
    or reshaped ``check_report.json`` yields blank cells, and an unparseable article JSON
    yields a row that still names the folder it came from.
    """
    row: dict[str, Any] = {
        "slug": bundle.name, "doc_type": "", "event_date": "", "venue": "",
        "title_cn": "", "title_en": "", "sections": None, "cn_chars": None, "photos": None,
        "score": None, "errors": None, "warnings": None, "needs": None,
        "outputs": "", "credits": {}, "issues": [],
    }
    article_path = _article_file(bundle)
    if article_path is not None:
        try:
            article = json.loads(article_path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            article = None
        if isinstance(article, dict):
            meta = _dict(article.get("meta"))
            title = _dict(article.get("title"))
            row["slug"] = _txt(meta.get("slug")) or article_path.stem
            row["doc_type"] = _txt(meta.get("doc_type"))
            row["event_date"] = _txt(meta.get("event_date")) or _txt(meta.get("event_end_date"))
            row["venue"] = _txt(meta.get("venue"))
            row["title_cn"] = _txt(title.get("cn"))
            row["title_en"] = _txt(title.get("en"))
            row["sections"] = len(_sections(article))
            row["cn_chars"] = _body_cjk(article)
            row["photos"] = _photo_count(article)
            needs = article.get("needs_editor")
            row["needs"] = len(needs) if isinstance(needs, (list, tuple)) else None
            credits = article.get("credits")
            if isinstance(credits, dict):
                row["credits"] = {str(key): _txt(value) for key, value in credits.items()}

    report_path = bundle / "check_report.json"
    if report_path.is_file():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            report = None
        if isinstance(report, dict):
            row["score"] = _as_int(report.get("score"))
            row["errors"] = _as_int(report.get("errors"))
            row["warnings"] = _as_int(report.get("warnings"))
            findings = report.get("findings")
            if isinstance(findings, list):
                for finding in findings:
                    if not isinstance(finding, dict):
                        continue
                    severity = _txt(finding.get("severity")).lower()
                    row["issues"].append({
                        "slug": row["slug"],
                        "severity": _SEVERITY_CN.get(severity, severity or "info"),
                        "code": _txt(finding.get("code")),
                        "message": _txt(finding.get("message")),
                        "hint": _txt(finding.get("hint")),
                    })

    present = [name for name in _BUNDLE_FILES if (bundle / name).is_file()]
    for pattern in ("*.docx", "*.pdf", "*.md"):
        present += sorted(path.name for path in bundle.glob(pattern))
    if (bundle / "render_warning.txt").is_file():
        present.append("render_warning.txt")
    row["outputs"] = ", ".join(present)
    return row


def _hex(color: str) -> str:
    """plain six-digit hex for whichever library is being written to.

    python-pptx requires ``RRGGBB``; openpyxl only accepts ``AARRGGBB``. The palette is
    shared, so the conversion lives in one place instead of at every call site.
    """
    value = color.lstrip("#").upper()
    return value if len(value) == 6 else value[-6:]


def _sheet(workbook, title: str, headers: Sequence[str], widths: Sequence[float]):
    """A frozen, filtered sheet with the club's navy header band."""
    from openpyxl.styles import Alignment, Font, PatternFill

    sheet = workbook.create_sheet(title)
    sheet.append(list(headers))
    fill = PatternFill("solid", fgColor="FF" + _hex(NAVY))
    for cell in sheet[1]:
        cell.font = Font(name=LATIN_FONT, bold=True, color="FF" + _hex(PAPER), size=11)
        cell.fill = fill
        cell.alignment = Alignment(vertical="center", horizontal="left")
    sheet.row_dimensions[1].height = 24
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[sheet.cell(row=1, column=index).column_letter].width = width
    sheet.freeze_panes = "A2"
    return sheet


def _autofilter(sheet, columns: int, data_rows: int) -> None:
    if data_rows > 0:
        last = sheet.cell(row=1, column=columns).column_letter
        sheet.auto_filter.ref = f"A1:{last}{data_rows + 1}"


def export_workbook(bundle_dirs: Iterable[Path | str], path: Path) -> Path:
    """Write the club's submission tracker for every bundle it is given.

    One row per bundle in "Articles", the six-role roster in "Credits" (so a missing 三审
    is visible at a glance) and every validator finding in "Issues". An empty
    ``bundle_dirs`` still produces a valid, styled workbook with headers only - the
    tracker is opened before the first article exists, not after.
    """
    openpyxl = _require("openpyxl")
    from openpyxl.styles import Alignment, Font

    if isinstance(bundle_dirs, (str, os.PathLike)):
        bundle_dirs = [bundle_dirs]
    rows = [_load_bundle(Path(entry)) for entry in (bundle_dirs or [])]
    rows.sort(key=lambda row: row["slug"].lower())

    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)

    articles = _sheet(workbook, "Articles", _ARTICLE_HEADERS,
                      [34, 10, 14, 24, 40, 34, 9, 13, 9, 8, 8, 9, 12, 46])
    for row in rows:
        articles.append([
            row["slug"], row["doc_type"], row["event_date"], row["venue"],
            row["title_cn"], row["title_en"], row["sections"], row["cn_chars"],
            row["photos"], row["score"], row["errors"], row["warnings"],
            row["needs"], row["outputs"],
        ])
    for line in articles.iter_rows(min_row=2, max_row=articles.max_row):
        for cell in line:
            cell.font = Font(name=LATIN_FONT, size=10)
            if cell.column in _NUMERIC_COLUMNS:
                cell.alignment = Alignment(horizontal="right")
            elif cell.column == len(_ARTICLE_HEADERS):
                cell.alignment = Alignment(vertical="top", wrap_text=True)
    _autofilter(articles, len(_ARTICLE_HEADERS), len(rows))

    credits = _sheet(workbook, "Credits", _CREDIT_HEADERS, [34, 20, 20, 20, 20, 20, 20])
    for row in rows:
        credits.append([row["slug"]]
                       + [row["credits"].get(role, "") for role in _CREDIT_HEADERS[1:]])
        missing = [role for role in _CREDIT_HEADERS[1:] if not row["credits"].get(role)]
        if missing:
            line = credits.max_row
            for index, role in enumerate(_CREDIT_HEADERS[1:], start=2):
                if role in missing:
                    # An unfilled role is the thing the club most needs to see.
                    credits.cell(row=line, column=index).font = Font(
                        name=LATIN_FONT, size=10, italic=True, color="FFB7791F"
                    )
    for line in credits.iter_rows(min_row=2, max_row=credits.max_row):
        for cell in line:
            if not (cell.font and cell.font.italic):
                cell.font = Font(name=LATIN_FONT, size=10)
    _autofilter(credits, len(_CREDIT_HEADERS), len(rows))

    issues = _sheet(workbook, "Issues", _ISSUE_HEADERS, [34, 16, 22, 70, 60])
    for row in rows:
        for issue in row["issues"]:
            issues.append([issue["slug"], issue["severity"], issue["code"],
                           issue["message"], issue["hint"]])
    for line in issues.iter_rows(min_row=2, max_row=issues.max_row):
        for cell in line:
            cell.font = Font(name=LATIN_FONT, size=10)
            if cell.column >= 4:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
    _autofilter(issues, len(_ISSUE_HEADERS), max(0, issues.max_row - 1))

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(str(path))
    return path
