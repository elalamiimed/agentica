"""Output rendering: JSON, Markdown (paste into the WeChat editor), HTML preview, DOCX, PDF.

The HTML preview reproduces the approved in-article visual grammar (numbered
bilingual section headers, 2x2 photo grids with the "slide right for more
pictures" hint, ranking lists, 三审 credit block, 精彩回顾 TOC card, club sign-off)
so an editor can see the article roughly as it will look before it ever reaches
the youth committee.
"""

from __future__ import annotations

import html
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable, Sequence

from .config import PROJECT_DIR
from .validate import CREDIT_ROLES, Report

LIBREOFFICE_CLI = Path(
    r"C:\Users\hp\AppData\Local\Programs\DeepSeek Harness\resources\app.asar.unpacked"
    r"\dsh\node_modules\@deepseek-ai\libreoffice-kit\lib\cli.js"
)
NODE_EXE = Path(
    r"C:\Users\hp\AppData\Local\Programs\DeepSeek Harness\resources\runtime"
    r"\primary-runtime\dependencies\node\bin\node.exe"
)

CJK_FONT = "微软雅黑"
LATIN_FONT = "Segoe UI"

# Measured from the approved articles (_work/analysis/design_tokens.json):
# brand navy for text and rules, a distinct navy for card borders, greyscale body.
SECTION_BAND = "#f6f7fa"
ACCENT = "#1B3870"        # brand navy (measured range #083169-#2A395A)
ACCENT_RGB = (0x1B, 0x38, 0x70)  # the same navy as an RGB triple, for python-docx
CARD_NAVY = "#20314B"     # card-border navy - deliberately a different value
LINE = "#E2E6EE"
INK = "#4C4C4C"           # body text
H1_INK = "#141414"
BYLINE = "#7F7F7F"


# --------------------------------------------------------------------------- helpers
def _e(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _photo_lookup(result) -> dict[str, Path]:
    """Map bare file name -> absolute path for every uploaded photo we can find."""
    found: dict[str, Path] = {}
    roots: list[Path] = []
    upload_dir = PROJECT_DIR / "_work" / "uploads"
    if upload_dir.is_dir():
        roots.append(upload_dir)
    if result.output_dir:
        roots.append(Path(result.output_dir))
    for name in _placed_photo_names(result.article):
        for root in roots:
            candidate = root / name
            if candidate.is_file():
                found[name] = candidate
                break
        else:
            for root in roots:
                matches = list(root.rglob(name))
                if matches:
                    found[name] = matches[0]
                    break
    return found


def _placed_photo_names(article: dict) -> list[str]:
    names: list[str] = []
    for section in article.get("sections") or []:
        for block in section.get("body") or []:
            if block.get("kind") == "photo_grid":
                for photo in block.get("photos") or []:
                    if photo.get("file"):
                        names.append(str(photo["file"]))
    return names


def _pair_text(cn, en, sep: str = " ") -> str:
    """Join a bilingual pair once - a Latin name is often identical in both fields."""
    cn = (cn or "").strip()
    en = (en or "").strip()
    if not cn:
        return en
    if not en or en == cn:
        return cn
    return f"{cn}{sep}{en}"


# The approved corpus contains NO multi-photo grid: photos are one full-bleed
# image per block, or a carousel frame. A grouped block therefore renders as a
# single full-width image (the first photo). A grid is off-brand and is not
# produced at all.
PHOTO_CLASS = "fullbleed"


# --------------------------------------------------------------------------- markdown
def to_markdown(article: dict, report: Report | None = None) -> str:
    out: list[str] = []
    title = article.get("title") or {}
    out.append(f"# {title.get('cn', '')}")
    if title.get("en"):
        out.append(f"### {title['en']}")
    kicker = title.get("kicker_en")
    if kicker:
        out.append(f"> {kicker}")

    lead = article.get("lead") or {}
    if lead.get("cn"):
        out.append(lead["cn"])
    if lead.get("en"):
        out.append(f"*{lead['en']}*")

    for section in article.get("sections") or []:
        number = f"{section.get('number')} " if section.get("number") else ""
        out.append(f"\n## {number}{section.get('heading_cn', '')} | {section.get('heading_en', '')}")
        for block in section.get("body") or []:
            kind = block.get("kind")
            if kind == "bilingual":
                if block.get("cn"):
                    out.append(block["cn"])
                if block.get("en"):
                    out.append(f"*{block['en']}*")
            elif kind == "list":
                for item in block.get("items") or []:
                    label = _pair_text(item.get("label_cn"), item.get("label_en"))
                    value = _pair_text(item.get("value_cn"), item.get("value_en"))
                    out.append(f"- **{label}**：{value}" if label else f"- {value}")
            elif kind == "photo_grid":
                layout = block.get("layout") or ""
                out.append(f"\n> [照片 {len(block.get('photos') or [])} 张 / photo grid {layout}]")
                for photo in block.get("photos") or []:
                    caption = " / ".join(
                        x for x in (photo.get("caption_cn"), photo.get("caption_en")) if x
                    )
                    out.append(f"> - {photo.get('file', '')}" + (f" — {caption}" if caption else ""))
                out.append("> slide right for more pictures\n")
            elif kind == "note":
                if block.get("cn_note"):
                    out.append(block["cn_note"])
                if block.get("en_note"):
                    out.append(f"*{block['en_note']}*")
            elif kind == "quote":
                if block.get("cn"):
                    out.append(f"> {block['cn']}")
                if block.get("en"):
                    out.append(f"> *{block['en']}*")
            elif kind == "divider":
                out.append("---")

    closing = article.get("closing") or {}
    heading = closing_heading(article)
    if heading:
        out.append(f"\n## {heading[0]} | {heading[1]}")
    if closing.get("tagline_cn"):
        out.append(f"**{closing['tagline_cn']}**")
    if closing.get("tagline_en"):
        out.append(f"**{closing['tagline_en']}**")
    if closing.get("cn"):
        out.append(closing["cn"])
    if closing.get("en"):
        out.append(f"*{closing['en']}*")

    signoff = article.get("signoff") or {}
    out.append(f"\n**{signoff.get('cn', '')}**")
    out.append(f"**{signoff.get('en', '')}**")
    if signoff.get("program"):
        out.append(f"**{signoff['program']}**")

    credits = article.get("credits") or {}
    if any(credits.get(role) for role in CREDIT_ROLES):
        out.append("\n---")
        for role in CREDIT_ROLES:
            if credits.get(role):
                out.append(f"{role} | {credits[role]}")

    toc = article.get("toc") or {}
    if toc.get("previous") or toc.get("next"):
        out.append("\n---")
        out.append("### 精彩回顾 · Table of Contents")
        if toc.get("previous"):
            out.append(f"Previous: {toc['previous']}")
        if toc.get("next"):
            out.append(f"Next: {toc['next']}")

    needs = article.get("needs_editor") or []
    if needs:
        out.append("\n---")
        out.append("### ⚠️ 需人工确认 / For the editor")
        out.extend(f"- {item}" for item in needs)

    if report is not None:
        out.append("\n---")
        out.append(f"### 送审前自检 / Pre-submission check — score {report.score}/100")
        out.append(f"{len(report.errors)} error(s), {len(report.warnings)} warning(s), {len(report.infos)} note(s)")
        for finding in report.sorted_findings():
            if finding.severity == "info":
                continue
            marker = "x" if finding.severity == "error" else "!"
            out.append(f"- [{marker}] {finding.code}: {finding.message}" + (f" ({finding.location})" if finding.location else ""))
    return "\n\n".join(out)


# --------------------------------------------------------------------------- html
_CSS = f"""
:root {{ --accent: {ACCENT}; --line: {LINE}; --band: {SECTION_BAND}; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #eef1f6; font-family: "{CJK_FONT}", "{LATIN_FONT}", sans-serif; color: {INK}; }}
.page {{ max-width: 760px; margin: 0 auto; background: #fff; padding: 0 0 40px; box-shadow: 0 2px 18px rgba(0,0,0,.12); }}
.banner {{ background: linear-gradient(135deg, var(--accent), #2f7ad1); color: #fff; padding: 26px 34px 22px; }}
.banner .club {{ font-size: 13px; letter-spacing: .22em; opacity: .92; }}
.banner .club-en {{ font-size: 11px; letter-spacing: .16em; opacity: .78; margin-top: 3px; }}
.banner h1 {{ font-size: 26px; line-height: 1.42; margin: 16px 0 6px; font-weight: 700; }}
.banner .h1-en {{ font-size: 15px; font-weight: 500; opacity: .95; line-height: 1.5; }}
.banner .kicker {{ display: inline-block; margin-top: 14px; font-size: 11px; letter-spacing: .18em; text-transform: uppercase; border: 1px solid rgba(255,255,255,.65); border-radius: 999px; padding: 4px 12px; }}
.body-wrap {{ padding: 26px 34px 0; }}
.lead-cn {{ font-size: 16.5px; line-height: 1.95; margin: 0 0 14px; }}
.lead-en {{ font-size: 13.5px; line-height: 1.85; color: #5A6270; margin: 0 0 8px; font-style: italic; }}
h2.sec {{ display: flex; align-items: center; gap: 12px; margin: 34px 0 16px; font-size: 19px; }}
h2.sec .num {{ background: var(--accent); color: #fff; border-radius: 6px; padding: 3px 10px; font-size: 15px; letter-spacing: .04em; }}
h2.sec .cn {{ font-weight: 700; }}
h2.sec .en {{ font-size: 12.5px; color: #6b7482; font-weight: 500; letter-spacing: .06em; text-transform: uppercase; }}
h3.sub {{ font-size: 15.5px; margin: 24px 0 10px; padding-left: 12px; border-left: 4px solid var(--accent); }}
h3.sub .en {{ display: block; font-size: 11.5px; color: #6b7482; letter-spacing: .08em; text-transform: uppercase; font-weight: 500; margin-top: 2px; }}
p.cn {{ font-size: 16px; line-height: 2.0; margin: 0 0 12px; text-align: justify; }}
p.en {{ font-size: 13.5px; line-height: 1.85; color: #5A6270; margin: 0 0 20px; text-align: justify; }}
.grid {{ display: grid; gap: 8px; margin: 8px 0 6px; }}
.grid.cols-2 {{ grid-template-columns: 1fr 1fr; }}
.grid.cols-3 {{ grid-template-columns: 1fr 1fr 1fr; }}
.grid img {{ width: 100%; height: 190px; object-fit: cover; border-radius: 6px; display: block; background: #dfe4ec; }}
.grid .ph {{ height: 190px; border-radius: 6px; background: repeating-linear-gradient(45deg, #e8ecf3, #e8ecf3 12px, #f4f6fa 12px, #f4f6fa 24px); border: 1px dashed #b9c4d6; display: flex; align-items: center; justify-content: center; color: #7c879a; font-size: 12px; text-align: center; padding: 8px; }}
/* Approved photo grammar: one full-bleed image per block, no gutter or radius. */
.fullbleed {{ margin: 10px 0 4px; }}
.fullbleed img {{ width: 100%; aspect-ratio: 1.46 / 1; object-fit: cover; display: block; background: #dfe4ec; }}
.fullbleed .ph {{ width: 100%; aspect-ratio: 1.46 / 1; background: repeating-linear-gradient(45deg, #e8ecf3, #e8ecf3 12px, #f4f6fa 12px, #f4f6fa 24px); border: 1px dashed #b9c4d6; display: flex; align-items: center; justify-content: center; color: #7c879a; font-size: 12px; }}
.caption {{ font-size: 11.5px; color: #6b7482; margin: 2px 0 12px; line-height: 1.6; }}
.slide-hint {{ font-size: 12px; color: #8b93a3; letter-spacing: .04em; margin: 4px 0 18px; }}
ul.ranks {{ list-style: none; padding: 0; margin: 6px 0 18px; }}
ul.ranks li {{ background: var(--band); border-left: 4px solid var(--accent); padding: 11px 16px; margin-bottom: 8px; border-radius: 0 6px 6px 0; }}
ul.ranks .rank {{ font-weight: 700; color: var(--accent); }}
ul.ranks .rank-en {{ font-size: 12px; color: #6b7482; margin-left: 6px; }}
ul.ranks .who {{ display: block; margin-top: 3px; font-size: 14.5px; }}
.note {{ background: #fff8e8; border: 1px solid #f0dfb4; border-radius: 8px; padding: 14px 18px; margin: 10px 0 18px; }}
.note .en {{ font-size: 12.5px; color: #6b6250; margin-top: 6px; }}
blockquote {{ margin: 10px 0 20px; padding: 12px 18px; border-left: 4px solid var(--accent); background: var(--band); font-size: 15px; line-height: 1.9; }}
blockquote .en {{ font-size: 13px; color: #5A6270; margin-top: 8px; }}
hr.sep {{ border: 0; border-top: 1px solid var(--line); margin: 30px 0; }}
.closing h2 {{ font-size: 19px; margin: 34px 0 14px; }}
.closing .tagline {{ font-size: 17px; font-weight: 700; color: var(--accent); margin: 0 0 4px; }}
.closing .tagline-en {{ font-size: 13px; color: #6b7482; margin: 0 0 16px; letter-spacing: .04em; }}
.signoff {{ text-align: center; margin: 34px 0 10px; }}
.signoff .cn {{ font-size: 16px; font-weight: 700; }}
.signoff .en {{ font-size: 12.5px; color: #6b7482; letter-spacing: .05em; margin-top: 4px; }}
.signoff .program {{ font-size: 12.5px; color: var(--accent); margin-top: 4px; letter-spacing: .06em; }}
.credits {{ border-top: 1px solid var(--line); margin-top: 30px; padding-top: 18px; font-size: 13.5px; line-height: 2.1; color: #3d4451; }}
.credits b {{ display: inline-block; min-width: 52px; color: var(--accent); }}
.toc-card {{ background: var(--band); border: 1px solid var(--line); border-radius: 8px; padding: 16px 20px; margin-top: 26px; }}
.toc-card h4 {{ margin: 0 0 12px; font-size: 14px; letter-spacing: .06em; }}
.toc-card .cols {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; font-size: 13px; }}
.toc-card .lbl {{ color: #6b7482; font-size: 11.5px; letter-spacing: .08em; text-transform: uppercase; margin-bottom: 4px; }}
.check-panel {{ margin: 26px auto 0; max-width: 760px; background: #fff; border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,.08); padding: 22px 26px; font-size: 13.5px; }}
.check-panel h3 {{ margin: 0 0 10px; font-size: 16px; }}
.score {{ font-size: 30px; font-weight: 700; }}
.score.good {{ color: #1a8f4c; }} .score.bad {{ color: #c0392b; }}
.finding {{ padding: 7px 0; border-bottom: 1px dashed #e3e7ee; }}
.finding .code {{ font-family: ui-monospace, Consolas, monospace; font-size: 12px; color: #6b7482; }}
.sev-error {{ color: #c0392b; font-weight: 700; }}
.sev-warning {{ color: #b7791f; font-weight: 700; }}
.sev-info {{ color: #4a5568; }}
.thumb-hint {{ font-size: 12.5px; color: #6b7482; margin: 10px 0 0; }}
input[type=checkbox] {{ margin-right: 8px; }}
"""


def _art_gallery(art: dict | None) -> str:
    """Render the generated artwork inside the preview page.

    The artwork is a separate deliverable: it never goes into the article PDF or
    DOCX, because those are what the youth committee reads and the approved
    format is text plus real photographs. The preview is where a reviewer sees
    the poster next to the words it belongs to.
    """
    if not art or not art.get("assets"):
        return ""
    cards = []
    for asset in art["assets"]:
        if asset.get("kind") == "divider":
            continue
        caption_cn = _e(str(asset.get("caption_cn", "")))
        caption_en = _e(str(asset.get("caption_en", "")))
        origin = (asset.get("provenance") or {}).get("backend", "")
        tag = "AI 生成" if str(origin).startswith("remote") else "程序绘制"
        cards.append(
            '<figure style="margin:0">'
            f'<img src="art/{_e(str(asset.get("file", "")))}" alt="{caption_cn}" '
            'style="width:100%;border-radius:6px;display:block;border:1px solid #e3e8f0">'
            f'<figcaption style="font-size:11.5px;color:#6b7482;margin-top:6px;line-height:1.5">'
            f'{caption_cn} · {caption_en}<br><span style="color:#94a0b4">{_e(tag)}</span></figcaption>'
            "</figure>"
        )
    if not cards:
        return ""
    vibe = art.get("vibe") or {}
    dividers = sum(1 for a in art["assets"] if a.get("kind") == "divider")
    backend = _e(str(art.get("backend", "")))
    meta_line = " · ".join(x for x in (
        _e(str(vibe.get("label_cn", ""))), _e(str(vibe.get("label_en", ""))),
        f"motif: {_e(str(vibe.get('motif', '')))}", f"{backend}",
        f"{dividers} section band(s)" if dividers else "",
    ) if x)
    return (
        '<div style="max-width:900px;margin:26px auto 0;padding:0 26px">'
        '<h3 style="margin:0 0 4px;font-size:16px;color:#1B3870">活动视觉 · Event artwork</h3>'
        f'<p style="font-size:12px;color:#6b7482;margin:0 0 12px">{meta_line}</p>'
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px">'
        + "".join(cards) +
        "</div>"
        f'<p style="font-size:11.5px;color:#6b7482;margin:12px 0 0">'
        f'{_e(str(art.get("disclaimer_cn", "")))} {_e(str(art.get("disclaimer_en", "")))}</p>'
        "</div>"
    )


# ------------------------------------------------------- 秀米 / WeChat paste export
# Both the 秀米 editor and the WeChat article editor strip anything they cannot hold as
# an inline style: a <style> block, a class, an id, flex/grid/position, an external
# resource. What survives is <section> (the block both editors themselves emit) with
# style="..." on it, and plain text tags inside. So this export is written to one rule -
# every tag carries its own style, nothing refers to anything outside itself.
#
# Images cannot travel through the clipboard at all: a path on the operator's disk means
# nothing to a web editor, a data: URI is stripped, and WeChat re-hosts every image on
# its own CDN anyway. Each photo position therefore becomes a labelled slot that names
# the exact file, so the layout volunteer knows what to upload and where.
PASTE_FONT = ("-apple-system,BlinkMacSystemFont,'Helvetica Neue','PingFang SC',"
              "'Hiragino Sans GB','Microsoft YaHei',sans-serif")
PASTE_CN = (f"font-size:16px;line-height:1.9;color:{INK};letter-spacing:.5px;"
            f"margin:0 0 12px;text-align:justify;")
PASTE_EN = ("font-size:13.5px;line-height:1.8;color:#5A6270;letter-spacing:.2px;"
            "margin:0 0 18px;text-align:justify;")
PASTE_SLOT = ("border:1px dashed #b9c4d6;background:#f7f9fc;padding:18px 16px;"
              "text-align:center;color:#7c879a;font-size:12px;line-height:1.7;"
              "margin:14px 0 0;border-radius:6px;")
# The one string the layout volunteer looks for before publishing.
PASTE_SLOT_LABEL = "待插入照片"


def closing_heading(article: dict) -> tuple[str, str] | None:
    """The closing heading, or ``None`` when the last section already carries it.

    The writer routinely ends an article with a 结语 section *and* fills the closing block,
    which put the same title on the page twice in a row - visible in the preview, the PDF,
    the DOCX and the 秀米 export alike. The closing text is always kept; only the repeated
    title is dropped.
    """
    closing = article.get("closing") or {}
    cn = str(closing.get("heading_cn") or "").strip()
    en = str(closing.get("heading_en") or "").strip()
    sections = article.get("sections") or []
    if cn and sections:
        last = sections[-1] if isinstance(sections[-1], dict) else {}
        if cn == str(last.get("heading_cn") or "").strip():
            return None
    if not cn and not en:
        return None
    return (cn or "结语", en or "Closing")


def _paste_photo_slots(article: dict) -> list[str]:
    """Every photo the article places, in reading order: (filename, caption)."""
    slots: list[tuple[str, str]] = []
    for section in article.get("sections") or []:
        for block in section.get("body") or []:
            if block.get("kind") != "photo_grid":
                continue
            for photo in block.get("photos") or []:
                name = str(photo.get("file") or "").strip()
                caption = " / ".join(
                    x for x in (photo.get("caption_cn"), photo.get("caption_en")) if x
                )
                slots.append((name, caption))
    return slots


def to_xiumi_html(article: dict, images: dict[str, str] | None = None) -> str:
    """The article as markup that survives being pasted into 秀米 or the WeChat editor.

    No <style>, no class, no id, no <div>, nothing external - only <section> and <p> with
    inline styles, which is exactly what both editors keep. Open the file, select all,
    copy, paste into 秀米: the headings, the bilingual rhythm, the award rows and the
    credits arrive laid out. Photographs arrive as labelled slots, because no image can
    cross a clipboard into a web editor.

    ``images`` maps a photo's filename to a hosted URL. When a photo has one - which is
    what ``wechat.py`` produces by uploading to WeChat first - the real image is emitted
    instead of the slot, and the same markup becomes the body of a 公众号 draft.
    """
    images = images or {}
    title = article.get("title") or {}
    lead = article.get("lead") or {}
    closing = article.get("closing") or {}
    signoff = article.get("signoff") or {}
    credits = article.get("credits") or {}
    toc = article.get("toc") or {}
    p: list[str] = []

    p.append('<!-- HSIYC · 秀米 / 微信 paste export. Open in a browser, select all, copy, '
             'paste into the 秀米 editor. Photograph slots are labelled; upload each photo '
             'in 秀米 and delete its slot. -->')
    p.append(f'<section style="font-size:16px;line-height:1.9;color:{INK};'
             f'letter-spacing:.5px;font-family:{PASTE_FONT};word-break:break-word;">')

    # ------------------------------------------------------------------ masthead
    p.append(f'<section style="text-align:center;padding:4px 0 0;">'
             f'<p style="font-size:12.5px;letter-spacing:3px;color:{ACCENT};margin:0;'
             f'font-weight:700;">哈工大（深圳）国际青年俱乐部</p>'
             f'<p style="font-size:10px;letter-spacing:2.4px;color:#9aa8bf;margin:5px 0 0;">'
             f'HITSZ INTERNATIONAL YOUTH CLUB</p></section>')
    p.append(f'<section style="width:34px;height:3px;background:{ACCENT};'
             f'margin:16px auto 20px;border-radius:2px;"></section>')

    # --------------------------------------------------------------------- title
    if title.get("cn"):
        p.append(f'<p style="font-size:21px;line-height:1.5;font-weight:700;color:{ACCENT};'
                 f'text-align:center;letter-spacing:1px;margin:0 0 10px;">{_e(title["cn"])}</p>')
    if title.get("en"):
        p.append(f'<p style="font-size:12.5px;line-height:1.7;color:#8a93a3;text-align:center;'
                 f'letter-spacing:.3px;margin:0 0 6px;">{_e(title["en"])}</p>')
    p.append(_xiumi_dots())

    # ---------------------------------------------------------------------- lead
    if lead.get("cn"):
        p.append(f'<p style="font-size:16.5px;line-height:2;color:{INK};text-align:justify;'
                 f'margin:0 0 14px;">{_e(lead["cn"])}</p>')
    if lead.get("en"):
        p.append(f'<p style="font-size:13px;line-height:1.9;color:#8a93a3;text-align:justify;'
                 f'margin:0 0 10px;">{_e(lead["en"])}</p>')

    # ------------------------------------------------------------------ sections
    photo_index = 0
    for position, section in enumerate(article.get("sections") or [], 1):
        number = str(section.get("number") or f"{position:02d}")
        p.append(_xiumi_heading(number, _e(section.get("heading_cn", "")),
                                _e(section.get("heading_en", ""))))

        for block in section.get("body") or []:
            kind = block.get("kind")
            if kind == "bilingual":
                if block.get("cn"):
                    p.append(f'<p style="{PASTE_CN}">{_e(block["cn"])}</p>')
                if block.get("en"):
                    p.append(f'<p style="{PASTE_EN}">{_e(block["en"])}</p>')
            elif kind == "list":
                for item in block.get("items") or []:
                    label_cn = _e(item.get("label_cn", ""))
                    label_en = _e(item.get("label_en", ""))
                    value_cn = _e(item.get("value_cn", ""))
                    value_en = "" if item.get("value_en") == item.get("value_cn") else _e(item.get("value_en", ""))
                    if not value_cn and value_en:
                        value_cn, value_en = value_en, ""
                    chip = (f'<span style="display:inline-block;background:{ACCENT};color:#fff;'
                            f'font-size:12px;font-weight:700;letter-spacing:1px;'
                            f'padding:2px 10px;border-radius:11px;">{label_cn}</span>')
                    if label_en:
                        chip += (f'<span style="font-size:11px;color:#9aa8bf;letter-spacing:1px;'
                                 f'margin-left:6px;">{label_en}</span>')
                    row = chip + f'<br><span style="font-size:15px;color:{INK};line-height:1.8;">{value_cn}</span>'
                    if value_en:
                        row += f'<br><span style="font-size:12.5px;color:#8a93a3;">{value_en}</span>'
                    p.append(f'<section style="background:{SECTION_BAND};'
                             f'border-left:3px solid {ACCENT};padding:12px 16px;'
                             f'margin:0 0 10px;border-radius:0 4px 4px 0;">{row}</section>')
            elif kind == "photo_grid":
                for photo in block.get("photos") or []:
                    photo_index += 1
                    name_raw = str(photo.get("file") or "photo")
                    caption = " / ".join(
                        x for x in (photo.get("caption_cn"), photo.get("caption_en")) if x
                    )
                    url = images.get(name_raw) or images.get(Path(name_raw).name)
                    if url:
                        p.append(f'<section style="margin:14px 0 0;">'
                                 f'<img src="{_e(url)}" alt="{_e(photo.get("alt") or name_raw)}" '
                                 f'style="width:100%;display:block;border-radius:6px;"></section>')
                    else:
                        p.append(f'<section style="{PASTE_SLOT}">'
                                 f'<span style="display:inline-block;background:{ACCENT};color:#fff;'
                                 f'font-size:11px;font-weight:700;letter-spacing:1px;padding:2px 9px;'
                                 f'border-radius:10px;">{PASTE_SLOT_LABEL} {photo_index:02d}</span>'
                                 f'<br><span style="color:#5a6472;font-size:12px;margin-top:6px;'
                                 f'display:inline-block;">{_e(name_raw)}</span></section>')
                    if caption:
                        p.append(f'<p style="font-size:11.5px;color:#8a93a3;line-height:1.6;'
                                 f'text-align:center;margin:6px 0 14px;">'
                                 f'<span style="color:{ACCENT};">▪</span> {_e(caption)}</p>')
            elif kind == "note":
                inner = ""
                if block.get("cn_note"):
                    inner += (f'<p style="font-size:13.5px;line-height:1.85;color:#6b6250;'
                              f'margin:0;">{_e(block["cn_note"])}</p>')
                if block.get("en_note"):
                    inner += (f'<p style="font-size:12px;line-height:1.75;color:#8a8272;'
                              f'margin:6px 0 0;">{_e(block["en_note"])}</p>')
                p.append(f'<section style="background:#fffaf0;border:1px solid #f0e2c4;'
                         f'border-left:3px solid #e3c37a;padding:13px 16px;margin:12px 0 18px;'
                         f'border-radius:0 4px 4px 0;">{inner}</section>')
            elif kind == "quote":
                inner = ""
                if block.get("cn"):
                    inner += (f'<p style="font-size:15.5px;line-height:1.95;color:{INK};'
                              f'text-align:center;margin:0;">{_e(block["cn"])}</p>')
                if block.get("en"):
                    inner += (f'<p style="font-size:12.5px;line-height:1.85;color:#8a93a3;'
                              f'text-align:center;margin:8px 0 0;">{_e(block["en"])}</p>')
                p.append(f'<section style="border-top:1px solid {LINE};'
                         f'border-bottom:1px solid {LINE};padding:16px 18px;margin:14px 0 20px;">'
                         f'{inner}</section>')
            elif kind == "divider":
                p.append(_xiumi_dots("28px 0"))

    # ------------------------------------------------------------------- closing
    heading = closing_heading(article)
    if heading:
        p.append(_xiumi_heading("", _e(heading[0]), _e(heading[1])))
    if closing.get("tagline_cn"):
        p.append(f'<p style="font-size:17px;font-weight:700;color:{ACCENT};text-align:center;'
                 f'letter-spacing:1px;margin:0 0 6px;">{_e(closing["tagline_cn"])}</p>')
    if closing.get("tagline_en"):
        p.append(f'<p style="font-size:12px;color:#9aa8bf;text-align:center;letter-spacing:1px;'
                 f'margin:0 0 16px;">{_e(closing["tagline_en"])}</p>')
    if closing.get("cn"):
        p.append(f'<p style="{PASTE_CN}">{_e(closing["cn"])}</p>')
    if closing.get("en"):
        p.append(f'<p style="{PASTE_EN}">{_e(closing["en"])}</p>')

    # ------------------------------------------------------------------ sign-off
    p.append(_xiumi_dots())
    p.append(f'<section style="text-align:center;margin:0 0 8px;">'
             f'<p style="font-size:15px;font-weight:700;color:{ACCENT};letter-spacing:1px;'
             f'margin:0;">{_e(signoff.get("cn", ""))}</p>'
             f'<p style="font-size:10.5px;color:#9aa8bf;letter-spacing:1.4px;margin:5px 0 0;">'
             f'{_e(signoff.get("en", ""))}</p>')
    if signoff.get("program"):
        p.append(f'<p style="font-size:11px;color:{ACCENT};letter-spacing:.8px;margin:6px 0 0;">'
                 f'{_e(signoff["program"])}</p>')
    p.append("</section>")

    # ------------------------------------------------------------------- credits
    rows = "".join(
        f'<p style="font-size:12.5px;line-height:1.95;color:#3d4451;margin:0;">'
        f'<span style="color:{ACCENT};font-weight:700;letter-spacing:1px;">{_e(role)}</span>'
        f'<span style="color:#c8d2e2;margin:0 8px;">|</span>{_e(credits[role])}</p>'
        for role in CREDIT_ROLES if credits.get(role)
    )
    if rows:
        p.append(f'<section style="border:1px solid {LINE};background:#fbfcfe;'
                 f'border-radius:6px;padding:14px 18px;margin:24px 0 0;">'
                 f'<p style="font-size:11px;letter-spacing:2px;color:#9aa8bf;margin:0 0 8px;">'
                 f'编辑团队 · EDITORIAL</p>{rows}</section>')

    # ----------------------------------------------------------------------- toc
    if toc.get("previous") or toc.get("next"):
        p.append(f'<section style="background:{SECTION_BAND};border:1px solid {LINE};'
                 f'padding:14px 18px;margin:16px 0 0;border-radius:6px;">'
                 f'<p style="font-size:12.5px;font-weight:700;color:{ACCENT};'
                 f'letter-spacing:1px;margin:0 0 10px;">精彩回顾 · Table of Contents</p>'
                 f'<p style="font-size:12px;line-height:1.8;color:#5A6270;margin:0;">'
                 f'<span style="color:#9aa8bf;">Previous</span>&nbsp;&nbsp;'
                 f'{_e(toc.get("previous", "")) or "—"}</p>'
                 f'<p style="font-size:12px;line-height:1.8;color:#5A6270;margin:6px 0 0;">'
                 f'<span style="color:#9aa8bf;">Next</span>&nbsp;&nbsp;'
                 f'{_e(toc.get("next", "")) or "—"}</p></section>')

    p.append("</section>")
    return "\n".join(p)


def _xiumi_dots(margin: str = "24px 0") -> str:
    """A hairline-and-dots separator: the decorative breathing room 秀米 layouts use."""
    return (f'<section style="text-align:center;margin:{margin};">'
            f'<span style="font-size:11px;color:#c8d2e2;letter-spacing:9px;">· · ·</span>'
            f'</section>')


def _xiumi_heading(number: str, heading_cn: str, heading_en: str) -> str:
    """A centred section header with the number above and a rule beneath.

    This is the shape Chinese club articles use, and it is built only from inline styles
    and block elements, so 秀米 and the WeChat editor both keep it.
    """
    parts = [f'<section style="text-align:center;margin:34px 0 18px;">']
    if number:
        parts.append(f'<span style="display:inline-block;background:{SECTION_BAND};'
                     f'color:{ACCENT};font-size:11px;font-weight:700;letter-spacing:2px;'
                     f'padding:2px 12px;border-radius:10px;">{_e(number)}</span>')
    parts.append(f'<p style="font-size:18px;font-weight:700;color:{ACCENT};letter-spacing:1.5px;'
                 f'margin:10px 0 0;line-height:1.5;">{heading_cn}</p>')
    if heading_en:
        parts.append(f'<p style="font-size:10.5px;color:#9aa8bf;letter-spacing:2px;'
                     f'margin:5px 0 0;text-transform:uppercase;">{heading_en}</p>')
    parts.append(f'<section style="width:30px;height:2px;background:#c9d4e6;'
                 f'margin:12px auto 0;border-radius:1px;"></section>')
    parts.append("</section>")
    return "".join(parts)


def to_xiumi_document(article: dict) -> str:
    """The paste markup as a standalone file.

    The charset declaration matters: without it a browser opened on a Chinese Windows
    install guesses the code page and renders the whole article as mojibake - exactly the
    kind of thing that gets pasted before anyone notices.
    """
    title = _e((article.get("title") or {}).get("cn", "HSIYC 文章"))
    return (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{title}</title>\n</head>\n<body>\n"
        + to_xiumi_html(article)
        + "\n</body>\n</html>\n"
    )


def to_xiumi_notes(article: dict, slug: str = "article",
                   base_url: str = "http://127.0.0.1:8765") -> str:
    """The one-page handover for whoever lays the article out in 秀米."""
    title = (article.get("title") or {}).get("cn", "")
    slots = _paste_photo_slots(article)
    lines = [
        f"# 秀米 / 微信排版 · paste guide — {title}",
        "",
        "## 1. Paste the text",
        "",
        f"1. Open `{slug}.xiumi.html` in a browser (double-click the file).",
        "2. Select all (Ctrl+A), copy (Ctrl+C).",
        "3. In 秀米, open 图文编辑 and paste (Ctrl+V) into the body.",
        "   — or, in the web UI, press **Copy for 秀米** on the result page.",
        "4. Apply the club's own 秀米 template if you use one; the pasted markup keeps",
        "   only inline styles, so a template can restyle it freely.",
        "",
        "### Optional: one click inside 秀米 instead of copy/paste",
        "",
        "秀米 has no API to call, but anything running in *your own logged-in browser* can pull",
        "the article from this machine. Save this as a bookmark, then click it on the 秀米",
        "editor page (Chrome asks once for permission to reach your local network):",
        "",
        "```",
        "javascript:(async()=>{const r=await fetch('"
        f"{base_url}/api/paste/{slug}"
        "');const h=await r.text();"
        "document.execCommand('insertHTML',false,h);})()",
        "```",
        "",
        f"The same URL, `{base_url}/api/paste/{slug}`, is a plain link any other tool can use.",
        "",
        "## 2. Put the photos in",
        "",
        "Images cannot travel through a clipboard into 秀米 — a file on your disk means",
        "nothing to a web editor, and WeChat re-hosts every image on its own CDN. Each",
        "photo position pastes as a dashed box:",
        "",
        f"> [{PASTE_SLOT_LABEL} 01]  <filename>  +  its caption",
        "",
        "Upload each file in 秀米 where its box sits, then delete the box. The photos in",
        "`xiumi-photos/` are numbered in the order they appear in the article, so uploading",
        "them in filename order puts them in the right places.",
    ]
    if slots:
        lines += ["", "| # | upload this | caption |", "|---|---|---|"]
        for index, (name, caption) in enumerate(slots, 1):
            lines.append(f"| {index} | `{index:02d}-{name or 'photo'}` | {caption or '—'} |")
        lines += ["", "The originals are in `media/`."]
    else:
        lines += ["", "No photo was placed in this article."]
    lines += [
        "",
        "## 3. Before 发布",
        "",
        "- No dashed box may survive.",
        "- The 三审 block must be in the same order as `check_report.txt`.",
        "- The article PDF/DOCX in this folder is the version that goes for review;",
        "  the 秀米 layout is the version that goes to readers.",
        "",
    ]
    return "\n".join(lines)


def write_xiumi_photos(article: dict, out: Path, photos: dict[str, Path] | None = None) -> list[Path]:
    """Numbered copies of the placed photos, in article order, under ``xiumi-photos/``.

    Uploading photos is the slowest manual step left in the 秀米 workflow. Numbering them in
    the order the article uses them means the file picker's default sort is already the right
    order, and each dashed slot in the pasted article names its number.
    """
    ordered = _paste_photo_slots(article)
    if not ordered:
        return []
    photos = photos or {}
    out = Path(out)
    numbered = out / "xiumi-photos"
    written: list[Path] = []
    try:
        numbered.mkdir(exist_ok=True)
    except OSError:
        return []
    for index, (name, _caption) in enumerate(ordered, 1):
        source = photos.get(name) or (out / "media" / Path(name).name)
        try:
            if source.is_file():
                target = numbered / f"{index:02d}-{Path(name).name}"
                shutil.copy2(source, target)
                written.append(target)
        except OSError:
            pass
    return written


def to_html(article: dict, report: Report | None = None, photos: dict[str, Path] | None = None,
            art: dict | None = None) -> str:
    photos = photos or {}
    title = article.get("title") or {}
    lead = article.get("lead") or {}
    parts: list[str] = []
    parts.append("<!DOCTYPE html>")
    parts.append('<html lang="zh-CN"><head><meta charset="utf-8">')
    parts.append(f"<title>{_e(title.get('cn', 'HSIYC 文章'))}</title>")
    parts.append(f"<style>{_CSS}</style></head><body>")

    parts.append('<div class="page">')
    parts.append('<div class="banner">')
    parts.append('<div class="club">哈工大（深圳）国际青年俱乐部 · HSIYC</div>')
    parts.append('<div class="club-en">HITSZ INTERNATIONAL YOUTH CLUB</div>')
    parts.append(f"<h1>{_e(title.get('cn',''))}</h1>")
    if title.get("en"):
        parts.append(f'<div class="h1-en">{_e(title["en"])}</div>')
    if title.get("subtitle_cn"):
        parts.append(f'<div class="h1-en">{_e(title["subtitle_cn"])}</div>')
    if title.get("kicker_en"):
        parts.append(f'<div class="kicker">{_e(title["kicker_en"])}</div>')
    parts.append("</div>")
    parts.append(_art_gallery(art))

    parts.append('<div class="body-wrap">')
    if lead.get("cn"):
        parts.append(f'<p class="lead-cn">{_e(lead["cn"])}</p>')
    if lead.get("en"):
        parts.append(f'<p class="lead-en">{_e(lead["en"])}</p>')

    for section in article.get("sections") or []:
        number = _e(section.get("number", ""))
        parts.append('<h2 class="sec">')
        if number:
            parts.append(f'<span class="num">{number}</span>')
        parts.append(f'<span><span class="cn">{_e(section.get("heading_cn",""))}</span>'
                     f'<span class="en"> | {_e(section.get("heading_en",""))}</span></span>')
        parts.append("</h2>")

        for block in section.get("body") or []:
            kind = block.get("kind")
            if kind == "bilingual":
                if block.get("cn"):
                    parts.append(f'<p class="cn">{_e(block["cn"])}</p>')
                if block.get("en"):
                    parts.append(f'<p class="en">{_e(block["en"])}</p>')
            elif kind == "list":
                parts.append('<ul class="ranks">')
                for item in block.get("items") or []:
                    rank = _e(item.get("label_cn", ""))
                    rank_en = _e(item.get("label_en", ""))
                    # A Latin name is usually the same in both fields; show it once.
                    who_en = "" if item.get("value_en") == item.get("value_cn") else _e(item.get("value_en", ""))
                    who = _e(item.get("value_cn", ""))
                    if not who and who_en:
                        who, who_en = who_en, ""
                    row = f'<span class="rank">{rank}</span>'
                    if rank_en:
                        row += f'<span class="rank-en">{rank_en}</span>'
                    row += f'<span class="who">{who}</span>'
                    if who_en:
                        row += f'<span class="who" style="font-size:12.5px;color:#6b7482">{who_en}</span>'
                    parts.append(f"<li>{row}</li>")
                parts.append("</ul>")
            elif kind == "photo_grid":
                tiles = block.get("photos") or []
                if not tiles:
                    continue
                captions: list[str] = []
                # Approved grammar: one full-bleed image per block. A grouped block is
                # rendered as a single full-width image (plus a carousel hint), never as
                # a 2x2/3-up grid, which does not exist in the corpus.
                for photo in tiles:
                    name = str(photo.get("file", ""))
                    path = photos.get(name)
                    parts.append('<div class="fullbleed">')
                    if path and path.is_file():
                        parts.append(f'<img src="{_e(path.as_uri())}" alt="{_e(photo.get("alt") or name)}">')
                    else:
                        parts.append(f'<div class="ph">照片待插入<br>{_e(name) or "photo"}</div>')
                    parts.append("</div>")
                    caption = " / ".join(x for x in (photo.get("caption_cn"), photo.get("caption_en")) if x)
                    if caption:
                        captions.append(caption)
                if captions:
                    parts.append('<div class="caption">' + _e(" ｜ ".join(captions)) + "</div>")
                parts.append('<div class="slide-hint">slide right for more pictures</div>')
            elif kind == "note":
                parts.append('<div class="note">')
                if block.get("cn_note"):
                    parts.append(f'<div>{_e(block["cn_note"])}</div>')
                if block.get("en_note"):
                    parts.append(f'<div class="en">{_e(block["en_note"])}</div>')
                parts.append("</div>")
            elif kind == "quote":
                parts.append("<blockquote>")
                if block.get("cn"):
                    parts.append(f'<div>{_e(block["cn"])}</div>')
                if block.get("en"):
                    parts.append(f'<div class="en">{_e(block["en"])}</div>')
                parts.append("</blockquote>")
            elif kind == "divider":
                parts.append('<hr class="sep">')

    closing = article.get("closing") or {}
    parts.append('<div class="closing">')
    heading = closing_heading(article)
    if heading:
        parts.append(f'<h2>{_e(heading[0])} &nbsp;|&nbsp; {_e(heading[1])}</h2>')
    if closing.get("tagline_cn"):
        parts.append(f'<div class="tagline">{_e(closing["tagline_cn"])}</div>')
    if closing.get("tagline_en"):
        parts.append(f'<div class="tagline-en">{_e(closing["tagline_en"])}</div>')
    if closing.get("cn"):
        parts.append(f'<p class="cn">{_e(closing["cn"])}</p>')
    if closing.get("en"):
        parts.append(f'<p class="en">{_e(closing["en"])}</p>')
    parts.append("</div>")

    signoff = article.get("signoff") or {}
    parts.append('<div class="signoff">')
    parts.append(f'<div class="cn">{_e(signoff.get("cn",""))}</div>')
    parts.append(f'<div class="en">{_e(signoff.get("en",""))}</div>')
    if signoff.get("program"):
        parts.append(f'<div class="program">{_e(signoff["program"])}</div>')
    parts.append("</div>")

    credits = article.get("credits") or {}
    parts.append('<div class="credits">')
    for role in CREDIT_ROLES:
        value = credits.get(role)
        if value:
            label = "三审" if role == "三审" else role
            parts.append(f"<div><b>{_e(label)}</b> | {_e(value)}</div>")
    parts.append("</div>")

    toc = article.get("toc") or {}
    if toc.get("previous") or toc.get("next"):
        parts.append('<div class="toc-card"><h4>精彩回顾 · Table of Contents</h4><div class="cols">')
        parts.append(f'<div><div class="lbl">Previous</div>{_e(toc.get("previous",""))}</div>')
        parts.append(f'<div><div class="lbl">Next</div>{_e(toc.get("next",""))}</div>')
        parts.append("</div></div>")
    parts.append("</div></div>")

    needs = article.get("needs_editor") or []
    if needs:
        parts.append('<div class="check-panel"><h3>⚠️ 需人工确认 / For the editor before 送审</h3><ul>')
        parts.extend(f"<li>{_e(item)}</li>" for item in needs)
        parts.append("</ul></div>")

    if report is not None:
        grade = "good" if report.ok else "bad"
        parts.append('<div class="check-panel"><h3>送审前自检 / Pre-submission check</h3>')
        parts.append(f'<div class="score {grade}">{report.score}<span style="font-size:14px;color:#6b7482"> / 100</span></div>')
        parts.append(
            f'<p>{len(report.errors)} error(s), {len(report.warnings)} warning(s), '
            f'{len(report.infos)} note(s)'
            + (" — structurally ready; a human still reads it." if report.ok else " — fix the errors before sending.")
            + "</p>"
        )
        for finding in report.sorted_findings():
            if finding.severity == "info":
                continue
            parts.append(
                f'<div class="finding"><span class="sev-{finding.severity}">'
                f'{"ERROR" if finding.severity == "error" else "WARN"}</span> '
                f'<span class="code">{_e(finding.code)}</span> — {_e(finding.message)}'
                + (f' <em>({_e(finding.location)})</em>' if finding.location else "")
                + (f'<div style="color:#6b7482;font-size:12.5px">→ {_e(finding.hint)}</div>' if finding.hint else "")
                + "</div>"
            )
        if report.stats:
            stats = " · ".join(f"{k}: {v}" for k, v in report.stats.items())
            parts.append(f'<p style="color:#6b7482;font-size:12.5px">{_e(stats)}</p>')
        parts.append("</div>")

    parts.append("</body></html>")
    return "\n".join(parts)


# --------------------------------------------------------------------------- docx
def to_docx(article: dict, path: Path, report: Report | None = None, photos: dict[str, Path] | None = None) -> Path:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor

    photos = photos or {}
    doc = Document()

    normal = doc.styles["Normal"]
    normal.font.name = LATIN_FONT
    normal.font.size = Pt(11)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), CJK_FONT)

    def para(text: str, size: int = 11, bold: bool = False, italic: bool = False,
             color: tuple[int, int, int] | None = None, align=None, space_after: int = 6) -> None:
        p = doc.add_paragraph()
        run = p.add_run(text)
        run.font.size = Pt(size)
        run.bold = bold
        run.italic = italic
        run.font.name = LATIN_FONT
        run._element.rPr.rFonts.set(qn("w:eastAsia"), CJK_FONT)
        if color:
            run.font.color.rgb = RGBColor(*color)
        if align is not None:
            p.alignment = align
        p.paragraph_format.space_after = Pt(space_after)
        return None

    title = article.get("title") or {}
    para("哈工大（深圳）国际青年俱乐部 · HSIYC", 9, color=(0x6B, 0x74, 0x82), align=WD_ALIGN_PARAGRAPH.CENTER)
    para(title.get("cn", ""), 18, bold=True, color=ACCENT_RGB, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
    if title.get("en"):
        para(title["en"], 12, italic=True, color=(0x4A, 0x52, 0x61), align=WD_ALIGN_PARAGRAPH.CENTER, space_after=14)

    lead = article.get("lead") or {}
    if lead.get("cn"):
        para(lead["cn"], 11.5)
    if lead.get("en"):
        para(lead["en"], 10, italic=True, color=(0x4A, 0x52, 0x61), space_after=12)

    for section in article.get("sections") or []:
        heading = f"{section.get('number','')} {section.get('heading_cn','')} | {section.get('heading_en','')}".strip()
        para(heading, 14, bold=True, color=ACCENT_RGB, space_after=8)
        for block in section.get("body") or []:
            kind = block.get("kind")
            if kind == "bilingual":
                if block.get("cn"):
                    para(block["cn"], 11.5)
                if block.get("en"):
                    para(block["en"], 10, italic=True, color=(0x4A, 0x52, 0x61), space_after=10)
            elif kind == "list":
                for item in block.get("items") or []:
                    label = _pair_text(item.get("label_cn"), item.get("label_en"))
                    value = _pair_text(item.get("value_cn"), item.get("value_en"))
                    para(f"{label}：{value}" if label else value, 11, bold=bool(label))
            elif kind == "photo_grid":
                tiles = block.get("photos") or []
                table_cols = 2 if len(tiles) != 1 else 1
                rows = (len(tiles) + table_cols - 1) // table_cols or 1
                table = doc.add_table(rows=rows, cols=table_cols)
                for idx, photo in enumerate(tiles):
                    cell = table.cell(idx // table_cols, idx % table_cols)
                    name = str(photo.get("file", ""))
                    photo_path = photos.get(name)
                    cell.paragraphs[0].text = ""
                    if photo_path and photo_path.is_file():
                        cell.paragraphs[0].add_run().add_picture(str(photo_path), width=Inches(3.0))
                    else:
                        cell.paragraphs[0].add_run(f"[照片 {name}]")
                    caption = " / ".join(x for x in (photo.get("caption_cn"), photo.get("caption_en")) if x)
                    if caption:
                        cell.add_paragraph(caption)
                para("slide right for more pictures", 9, color=(0x8B, 0x93, 0xA3), space_after=10)
            elif kind == "note":
                if block.get("cn_note"):
                    para(block["cn_note"], 11)
                if block.get("en_note"):
                    para(block["en_note"], 10, italic=True, color=(0x4A, 0x52, 0x61))
            elif kind == "quote":
                if block.get("cn"):
                    para(f"“{block['cn']}”", 12, italic=True)
                if block.get("en"):
                    para(block["en"], 10, italic=True, color=(0x4A, 0x52, 0x61))
            elif kind == "divider":
                para("— — —", 10, color=(0xC8, 0xD5, 0xE8), align=WD_ALIGN_PARAGRAPH.CENTER)

    closing = article.get("closing") or {}
    heading = closing_heading(article)
    if heading:
        para(f"{heading[0]} | {heading[1]}", 14, bold=True,
         color=ACCENT_RGB, space_after=8)
    if closing.get("tagline_cn"):
        para(closing["tagline_cn"], 12.5, bold=True, color=ACCENT_RGB)
    if closing.get("tagline_en"):
        para(closing["tagline_en"], 10.5, italic=True, color=(0x6B, 0x74, 0x82))
    if closing.get("cn"):
        para(closing["cn"], 11.5)
    if closing.get("en"):
        para(closing["en"], 10, italic=True, color=(0x4A, 0x52, 0x61), space_after=14)

    signoff = article.get("signoff") or {}
    para(signoff.get("cn", ""), 12, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    para(signoff.get("en", ""), 10, color=(0x6B, 0x74, 0x82), align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    if signoff.get("program"):
        para(signoff["program"], 10, color=ACCENT_RGB, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=14)

    credits = article.get("credits") or {}
    if any(credits.get(role) for role in CREDIT_ROLES):
        para("———————", 10, color=(0xC8, 0xD5, 0xE8), align=WD_ALIGN_PARAGRAPH.CENTER)
        for role in CREDIT_ROLES:
            if credits.get(role):
                para(f"{role} | {credits[role]}", 10.5, space_after=2)

    toc = article.get("toc") or {}
    if toc.get("previous") or toc.get("next"):
        para("精彩回顾 · Table of Contents", 11, bold=True, color=ACCENT_RGB, space_after=4)
        if toc.get("previous"):
            para(f"Previous：{toc['previous']}", 10)
        if toc.get("next"):
            para(f"Next：{toc['next']}", 10)

    needs = article.get("needs_editor") or []
    if needs:
        para("需人工确认 / Before 送审", 11, bold=True, color=(0xB7, 0x79, 0x1F), space_after=4)
        for item in needs:
            para(f"• {item}", 10)

    if report is not None:
        para(f"送审前自检 / Pre-submission check — {report.score}/100 "
             f"({len(report.errors)} errors, {len(report.warnings)} warnings)", 10.5, bold=True,
             color=(0x1A, 0x8F, 0x4C) if report.ok else (0xC0, 0x39, 0x2B))
        for finding in report.sorted_findings():
            if finding.severity == "info":
                continue
            para(f"[{finding.severity.upper()}] {finding.code}: {finding.message}"
                 + (f" ({finding.location})" if finding.location else ""), 9.5)

    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    return path


# --------------------------------------------------------------------------- pdf
def docx_to_pdf(docx_path: Path, out_dir: Path | None = None) -> Path | None:
    """Convert with the bundled LibreOffice kit. Returns None when unavailable."""
    if not (NODE_EXE.is_file() and LIBREOFFICE_CLI.is_file()):
        return None
    out_dir = out_dir or docx_path.parent
    try:
        proc = subprocess.run(
            [str(NODE_EXE), str(LIBREOFFICE_CLI), "convert",
             "--input", str(docx_path), "--output", str(out_dir / (docx_path.stem + ".pdf"))],
            capture_output=True, text=True, timeout=300,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    if proc.returncode != 0:
        return None
    pdf = out_dir / (docx_path.stem + ".pdf")
    return pdf if pdf.is_file() else None


# --------------------------------------------------------------------------- bundle
def _warn(out: Path, message: str) -> None:
    """Record a non-fatal render problem without losing the rest of the bundle."""
    path = out / "render_warning.txt"
    prefix = "\n" if path.is_file() and path.stat().st_size else ""
    with path.open("a", encoding="utf-8") as handle:
        handle.write(prefix + message)


def make_bundle_art(article: dict, out: Path, *, brief: dict | None = None,
                    backend: str = "auto", kinds: tuple[str, ...] | None = None) -> dict | None:
    """Generate the artwork for a bundle folder. Never raises.

    Returns the manifest, or None if the drawing stack is unavailable - in which
    case the reason lands in ``render_warning.txt`` and the article is untouched.
    """
    try:
        from .art import make_art

        return make_art(article, out / "art", brief=brief, backend=backend, kinds=kinds)
    except Exception as exc:  # artwork must never cost the club its article
        _warn(out, f"artwork skipped: {type(exc).__name__}: {exc}")
        return None


def write_deck(article: dict, out: Path, slug: str, *, art: dict | None = None,
               photos: dict[str, Path] | None = None) -> bool:
    """Write the presentation deck. Optional: python-pptx is not everywhere."""
    try:
        from .office_export import export_deck

        export_deck(article, out / f"{slug}.pptx", art=art, photos=photos)
        return True
    except Exception as exc:
        _warn(out, f"deck render failed: {type(exc).__name__}: {exc}")
        return False


def write_all(result, root: Path, *, art_backend: str = "auto", art: bool = True,
              art_kinds: tuple[str, ...] | None = None, deck: bool = True) -> Path:
    """Write the full deliverable bundle for one run into its own folder.

    ``art`` is on by default and writes separate image files under ``art/``. It
    is deliberately *not* embedded into the article PDF or DOCX: those are the
    submission, and the approved format is text plus real photographs. The
    poster and social card are for promoting the event, and the banner dresses
    the presentation deck.
    """
    article = result.article
    slug = str((article.get("meta") or {}).get("slug") or "hsiyc-article")
    out = Path(root) / slug
    out.mkdir(parents=True, exist_ok=True)
    # Warnings describe THIS run. Clearing the file first stops a message from an
    # earlier failed attempt making a healthy bundle look broken.
    (out / "render_warning.txt").unlink(missing_ok=True)

    photos = _photo_lookup(result)
    # `media` exists as a path whether or not anything was found: the article can place a
    # photo the bundle does not have, and the numbered copies below must not crash on it.
    media = out / "media"
    if photos:
        media.mkdir(exist_ok=True)
        for name, src in photos.items():
            try:
                target = media / Path(name).name
                if src.resolve() != target.resolve():
                    shutil.copy2(src, target)
            except OSError:
                pass

    # Numbered copies in article order: uploading them in filename order in 秀米 puts the
    # photos in the right places, which is the slowest manual step left in that workflow.
    write_xiumi_photos(article, out, photos)

    # Artwork is rendered before the log is written so the bundle records which
    # backend actually produced it.
    art_manifest: dict | None = None
    art_error = ""
    if art:
        art_manifest = make_bundle_art(article, out, brief=getattr(result, "brief", None),
                                       backend=art_backend, kinds=art_kinds)
        if art_manifest is None:
            art_error = "artwork unavailable (see render_warning.txt)"

    (out / f"{slug}.json").write_text(
        json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / f"{slug}.md").write_text(
        to_markdown(article, result.report), encoding="utf-8"
    )
    (out / f"{slug}.preview.html").write_text(
        to_html(article, result.report, photos, art_manifest), encoding="utf-8"
    )
    # The 秀米 / WeChat paste export. Written for every bundle: it is the file the layout
    # volunteer actually needs, and it is immutable - the article JSON is the source.
    (out / f"{slug}.xiumi.html").write_text(to_xiumi_document(article), encoding="utf-8")
    (out / f"{slug}.xiumi.md").write_text(to_xiumi_notes(article, slug), encoding="utf-8")
    (out / "check_report.txt").write_text(result.report.text(), encoding="utf-8")
    (out / "check_report.json").write_text(
        json.dumps(result.report.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    run_meta = {
        "generated_at": (article.get("meta") or {}).get("generated_at", ""),
        "doc_type": (article.get("meta") or {}).get("doc_type", ""),
        "exemplars": result.exemplars,
        "attempts": result.attempts,
        "usage": result.usage,
        "log": result.log,
        "needs_editor": article.get("needs_editor", []),
        # Keep the material the article was built from, so the bundle can be
        # re-checked later (tools/refresh_outputs.py) and so a reviewer can see
        # exactly which facts the operator supplied.
        "brief": result.brief,
        "brief_text": getattr(result, "brief_text", ""),
        "art": None if art_manifest is None else {
            "backend": art_manifest.get("backend"),
            "requested_backend": art_manifest.get("requested_backend"),
            "seed": art_manifest.get("seed"),
            "vibe": (art_manifest.get("vibe") or {}).get("key"),
            "motif": (art_manifest.get("vibe") or {}).get("motif"),
            "assets": [a.get("file") for a in art_manifest.get("assets", [])],
            "notes": art_manifest.get("notes", []),
        },
        "art_error": art_error,
    }
    (out / "run_log.json").write_text(json.dumps(run_meta, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        to_docx(article, out / f"{slug}.docx", result.report, photos)
    except Exception as exc:  # a missing DOCX must not lose the rest of the bundle
        (out / "render_warning.txt").write_text(f"DOCX render failed: {exc}", encoding="utf-8")

    # The PDF comes from the built-in engine, not from a DOCX round-trip: the
    # bundled LibreOffice cannot be spawned from inside the file sandbox.
    try:
        from .pdfout import write_article_pdf

        write_article_pdf(article, out / f"{slug}.pdf", photos, result.report)
    except Exception as exc:
        _warn(out, f"PDF render failed: {exc}")

    # A presentation deck for the club to show or slice into social posts.
    if deck:
        write_deck(article, out, slug, art=art_manifest, photos=photos)

    return out
