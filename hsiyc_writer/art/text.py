"""Font selection and CJK-aware text layout for generated artwork.

Posters and social cards carry real headline text, and Chinese has no spaces, so
the wrapping rules the browser uses for the HTML preview do not apply here. This
module owns two things: picking a font file that can actually draw 中文 (a Latin
face renders every character as a tofu box), and breaking a line at a sensible
place without leaving punctuation stranded at the start of a line.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

FONT_DIRS = (Path(r"C:\Windows\Fonts"), Path("/usr/share/fonts"), Path("/Library/Fonts"))

# Bold first: generated artwork is display type. Every CJK candidate is listed
# before the Latin ones because a CJK face draws Latin glyphs correctly too,
# while the reverse is not true.
CJK_BOLD = ("msyhbd.ttc", "Dengb.ttf", "simhei.ttf", "msyh.ttc", "simsun.ttc", "NotoSansCJK-Bold.ttc")
CJK_REGULAR = ("msyh.ttc", "Deng.ttf", "simhei.ttf", "simsun.ttc", "NotoSansCJK-Regular.ttc")
LATIN_BOLD = ("segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "DejaVuSans-Bold.ttf")
LATIN_REGULAR = ("segoeui.ttf", "arial.ttf", "calibri.ttf", "DejaVuSans.ttf")

# Chinese typography forbids these at the start of a line and these at the end.
NO_LINE_START = "，。、；：？！）》」』】…—·%’”,.;:?!)]}"
NO_LINE_END = "（《「『【([{"


def _find(candidates: tuple[str, ...]) -> Path | None:
    for directory in FONT_DIRS:
        for name in candidates:
            path = directory / name
            if path.is_file():
                return path
    return None


@lru_cache(maxsize=1)
def cjk_font_path() -> Path | None:
    return _find(CJK_BOLD) or _find(CJK_REGULAR)


@lru_cache(maxsize=1)
def latin_font_path() -> Path | None:
    return _find(LATIN_BOLD) or _find(LATIN_REGULAR)


@lru_cache(maxsize=256)
def load(size: int, *, bold: bool = True, cjk: bool = True) -> ImageFont.FreeTypeFont | None:
    """Return a sized font, or None when the machine has no usable face.

    Callers must tolerate None and skip text rather than crash: the artwork is a
    nice-to-have, and a club laptop without the usual Windows fonts should still
    get the images.
    """
    path = (cjk_font_path() if cjk else latin_font_path()) if bold else (
        _find(CJK_REGULAR) or cjk_font_path()
    )
    if path is None:
        return None
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return None


def text_width(text: str, font) -> float:
    return font.getlength(text)


def wrap(text: str, font, max_width: float) -> list[str]:
    """Greedy wrap that is safe for Chinese: break between any two characters.

    Latin runs are kept whole so an English word never splits mid-word.
    """
    text = (text or "").strip()
    if not text or font is None:
        return [text] if text else []
    lines: list[str] = []
    current = ""
    for token in _tokens(text):
        candidate = current + token
        if current and text_width(candidate, font) > max_width:
            # A closing mark belongs with the line it follows.
            if token and token[0] in NO_LINE_START:
                current = candidate
                lines.append(current)
                current = ""
                continue
            if current[-1] in NO_LINE_END:
                lines.append(current[:-1])
                current = current[-1] + token
            else:
                lines.append(current)
                current = token.lstrip() if token == " " else token
        else:
            current = candidate
    if current:
        lines.append(current)
    return [line.strip() for line in lines if line.strip()]


def _tokens(text: str) -> list[str]:
    """Chinese characters one at a time; Latin runs and spaces as single tokens."""
    out: list[str] = []
    buffer = ""
    for char in text:
        if _is_latin(char):
            buffer += char
        else:
            if buffer:
                out.append(buffer)
                buffer = ""
            out.append(char)
    if buffer:
        out.append(buffer)
    return out


def _is_latin(char: str) -> bool:
    return char.isascii() and (char.isalnum() or char in "-'&.")


def fit_size(text: str, max_width: float, max_lines: int, *, start: int = 96,
             minimum: int = 18, bold: bool = True, max_height: float | None = None,
             line_height: float = 1.34) -> tuple[object, list[str], int]:
    """Largest font size at which ``text`` wraps into at most ``max_lines``.

    Returns ``(font, lines, size)``. Falls back to the minimum size rather than
    shrinking forever, so a pathological title still renders.
    """
    if max_width <= 0 or max_lines < 1:
        raise ValueError("text box needs positive width and at least one line")
    size = start
    while size > minimum:
        font = load(size, bold=bold)
        if font is None:
            return None, [text], 0
        lines = wrap(text, font, max_width)
        if (len(lines) <= max_lines and all(text_width(row, font) <= max_width for row in lines)
                and (max_height is None or len(lines) * size * line_height <= max_height)):
            return font, lines, size
        size -= 2
    font = load(minimum, bold=bold)
    rows = wrap(text, font, max_width) if font else [text]
    budget = max_lines if max_height is None else min(max_lines, max(0, int(max_height / (minimum * line_height))))
    clipped = rows[:budget]
    if len(rows) > budget and clipped:
        clipped[-1] += "…"
    return font, [ellipsize(row, font, max_width) for row in clipped], minimum


def ellipsize(text: str, font, max_width: float) -> str:
    if font is None or text_width(text, font) <= max_width:
        return text
    clipped = text
    while clipped and text_width(clipped + "…", font) > max_width:
        clipped = clipped[:-1]
    return clipped + "…"
