"""The drawing routines.

One function per motif, each an abstract picture that reads at a glance: an
aperture for photography, a shuttlecock for sport, lanterns for culture night,
a trophy for an award. They are intentionally geometric rather than literal -
the club's approved PDFs use flat navy-and-gold shapes, not stock photography.

Every motif draws through a :class:`~hsiyc_writer.art.canvas.Painter` stack, so
translucent parts blend instead of replacing each other. Motifs take a box and
must stay inside it; the compositions in ``local.py`` decide where that box is.
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image

from . import canvas
from .canvas import Layer, Painter, Palette

Box = tuple[float, float, float, float]


# --------------------------------------------------------------------------- helpers
def _rot(px: float, py: float, cx: float, cy: float, deg: float) -> tuple[float, float]:
    rad = math.radians(deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    dx, dy = px - cx, py - cy
    return (cx + dx * cos_a - dy * sin_a, cy + dx * sin_a + dy * cos_a)


def _glow(layer: Layer, centre: tuple[float, float], radius: float, colour, strength: float = 0.5) -> None:
    """Soft radial light, painted straight into an (empty) layer."""
    w, h = layer.w, layer.h
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.hypot(xx - centre[0], yy - centre[1]) / max(1.0, radius)
    alpha = np.clip(1.0 - d, 0.0, 1.0) ** 2 * (255.0 * strength)
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[:, :, 0], rgba[:, :, 1], rgba[:, :, 2] = colour[0], colour[1], colour[2]
    rgba[:, :, 3] = alpha.astype(np.uint8)
    layer.paste(Image.fromarray(rgba, "RGBA"))


def _confetti(p: Painter, rng, colours, *, count: int, box: Box, alpha: tuple[int, int] = (150, 235),
              sizes: tuple[float, float] = (7.0, 26.0)) -> None:
    layer = p.begin()
    x, y, w, h = box
    for _ in range(count):
        cx = x + rng.random() * w
        cy = y + rng.random() * h
        cw = rng.uniform(*sizes)
        ch = cw * rng.uniform(0.28, 0.55)
        layer.polygon_rotated(cx, cy, cw, ch, rng.uniform(-70, 70),
                              fill=canvas.rgba(colours[int(rng.integers(len(colours)))],
                                               int(rng.integers(*alpha))))


def _rays(layer: Layer, centre, radius: float, colour, *, count: int = 18, spread: float = 0.05,
          alpha: int = 24, jitter: float = 0.0, rng=None) -> None:
    for index in range(count):
        angle = math.radians(index * 360.0 / count + (rng.uniform(-jitter, jitter) if rng else 0.0))
        length = radius * (1.0 + (rng.uniform(0.0, 0.35) if rng else 0.0))
        layer.polygon(
            [
                centre,
                (centre[0] + math.cos(angle - spread) * length, centre[1] + math.sin(angle - spread) * length),
                (centre[0] + math.cos(angle + spread) * length, centre[1] + math.sin(angle + spread) * length),
            ],
            fill=canvas.rgba(colour, alpha),
        )


# --------------------------------------------------------------------------- motifs
def aperture(p: Painter, pal: Palette, rng, box: Box) -> None:
    """Camera iris: overlapping blades, light rays and a bright core."""
    x, y, w, h = box
    cx, cy = x + w / 2, y + h / 2
    radius = min(w, h) * 0.44
    rotation = rng.uniform(0, 360)

    layer = p.begin()
    _rays(layer, (cx, cy), radius * 2.0, pal.accent, count=14, spread=0.045, alpha=22, jitter=6, rng=rng)

    layer = p.begin()
    blades = 7
    step = 360.0 / blades
    for index in range(blades):
        start = index * step + rotation
        end = start + step - 5
        base = pal.primary if index % 2 == 0 else canvas.shade(pal.primary, 1.45)
        layer.pieslice((cx - radius, cy - radius, cx + radius, cy + radius), start, end,
                       fill=canvas.rgba(base, 216 if index % 3 else 238))
        edge = _rot(cx + radius, cy, cx, cy, start)
        layer.line([(cx, cy), edge], fill=canvas.rgba(pal.ink, 55), width=1.1)

    layer = p.begin()
    layer.circle(cx, cy, radius, outline=canvas.rgba(pal.accent, 225), width=5.5)
    layer.circle(cx, cy, radius * 0.97, outline=canvas.rgba(pal.ink, 40), width=1.3)
    layer.circle(cx, cy, radius * 0.985, outline=canvas.rgba(pal.accent, 70), width=1.0)

    layer = p.begin()
    _glow(layer, (cx, cy), radius * 0.62, canvas.shade(pal.accent, 1.15), 0.85)
    layer.circle(cx, cy, radius * 0.19, fill=canvas.rgba(canvas.shade(pal.accent, 0.82), 240))
    layer.circle(cx, cy, radius * 0.19, outline=canvas.rgba(pal.ink, 95), width=2.0)
    layer.circle(cx - radius * 0.06, cy - radius * 0.06, radius * 0.06,
                 fill=canvas.rgba(pal.ink, 190))


def shuttle(p: Painter, pal: Palette, rng, box: Box) -> None:
    """Badminton shuttlecock in flight, with motion arcs behind it."""
    x, y, w, h = box
    cx, cy = x + w / 2, y + h / 2
    span = min(w, h) * 0.86
    tilt = -22.0

    head = _rot(cx - span * 0.30, cy + span * 0.16, cx, cy, tilt)
    tail_centre = _rot(cx + span * 0.34, cy - span * 0.18, cx, cy, tilt)
    tail_half = span * 0.30

    # Motion arcs first, so the shuttle sits in front of its own wake.
    layer = p.begin()
    for index, (scale, alpha, width) in enumerate(((1.00, 46, 5), (1.22, 32, 3.5), (1.46, 20, 2.5))):
        pad = span * 0.30 * scale
        layer.arc((cx - pad - span * 0.10, cy - pad, cx + pad + span * 0.10, cy + pad),
                  118 + index * 4, 250 - index * 6, fill=canvas.rgba(pal.accent, alpha), width=width)

    layer = p.begin()
    feathers = 5
    for index in range(feathers):
        t = (index - (feathers - 1) / 2) / ((feathers - 1) / 2)
        tip_a = _rot(tail_centre[0], tail_centre[1] + t * tail_half, cx, cy, tilt)
        tip_b = _rot(tail_centre[0] + span * 0.06, tail_centre[1] + t * tail_half * 0.72 + span * 0.045,
                     cx, cy, tilt)
        layer.polygon([head, tip_a, tip_b], fill=canvas.rgba(pal.ink, 96 if index % 2 else 128))
        layer.line([head, tip_a], fill=canvas.rgba(pal.ink, 150), width=1.4)

    layer = p.begin()
    layer.circle(head[0], head[1], span * 0.115, fill=canvas.rgba(canvas.shade(pal.accent, 0.9), 250))
    layer.circle(head[0], head[1], span * 0.115, outline=canvas.rgba(pal.ink, 120), width=2)
    layer.circle(head[0] - span * 0.035, head[1] - span * 0.035, span * 0.035,
                 fill=canvas.rgba(pal.ink, 165))
    layer.line([head, tail_centre], fill=canvas.rgba(pal.accent, 200), width=3.0)

    layer = p.begin()
    for index in range(6):
        offset = span * (0.55 + index * 0.09)
        start = _rot(cx - offset, cy + offset * 0.42, cx, cy, tilt)
        end = _rot(cx - offset - span * 0.20, cy + offset * 0.42 + span * 0.07, cx, cy, tilt)
        layer.line([start, end], fill=canvas.rgba(pal.secondary, 90 - index * 10), width=3.0 - index * 0.3)


def lantern(p: Painter, pal: Palette, rng, box: Box) -> None:
    """Paper lanterns hanging from the top edge, over a soft world arc."""
    x, y, w, h = box
    unit = min(w, h)
    layer = p.begin()
    pad = unit * 0.30
    layer.arc((x - pad, y + h * 0.30, x + w + pad, y + h * 1.55), 200, 340,
              fill=canvas.rgba(pal.secondary, 90), width=max(1.0, unit * 0.012))

    for index in range(4):
        t = (index + 0.5) / 4.0
        cx = x + w * (0.14 + 0.72 * t) + rng.uniform(-w * 0.03, w * 0.03)
        size = min(w, h) * rng.uniform(0.16, 0.26)
        drop = h * rng.uniform(0.10, 0.26)
        colours = [pal.accent, pal.secondary, pal.ink, pal.accent]
        colour = colours[index % len(colours)]

        layer = p.begin()
        layer.line([(cx, y), (cx, drop + size * 0.55)], fill=canvas.rgba(pal.ink, 110), width=1.6)
        _glow(layer, (cx, drop + size * 1.15), size * 3.2, colour, 0.34)

        layer = p.begin()
        body = (cx - size, drop, cx + size, drop + size * 1.6)
        layer.ellipse(body, fill=canvas.rgba(colour, 232))

        # The highlight and the ribs get their own layer. Pillow REPLACES pixels for
        # a translucent fill on the same layer, so drawing this light ellipse over
        # the opaque body would set the centre to alpha 120 - a hole, not a sheen.
        layer = p.begin()
        layer.ellipse((cx - size * 0.62, drop + size * 0.10, cx + size * 0.62, drop + size * 1.5),
                      fill=canvas.rgba(canvas.shade(colour, 1.25), 120))
        for rib in (-0.45, 0.0, 0.45):
            layer.ellipse((cx + size * rib - size * 0.30, drop + size * 0.06,
                           cx + size * rib + size * 0.30, drop + size * 1.54),
                          outline=canvas.rgba(canvas.shade(colour, 0.72), 110), width=1.4)

        layer = p.begin()
        layer.rect((cx - size * 0.38, drop - size * 0.16, cx + size * 0.38, drop + size * 0.06),
                   fill=canvas.rgba(canvas.shade(pal.primary, 0.8), 245), radius=size * 0.06)
        layer.rect((cx - size * 0.38, drop + size * 1.54, cx + size * 0.38, drop + size * 1.76),
                   fill=canvas.rgba(canvas.shade(pal.primary, 0.8), 245), radius=size * 0.06)
        layer.line([(cx, drop + size * 1.76), (cx, drop + size * 2.15)],
                   fill=canvas.rgba(pal.accent, 180), width=2.0)

    layer = p.begin()
    for _ in range(26):
        sx = x + rng.random() * w
        sy = y + rng.random() * h
        radius = rng.uniform(1.2, 3.2)
        layer.circle(sx, sy, radius, fill=canvas.rgba(pal.ink, int(rng.integers(50, 130))))


def study(p: Painter, pal: Palette, rng, box: Box) -> None:
    """A stack of books, an open notebook and a pencil."""
    x, y, w, h = box
    unit = min(w, h)

    layer = p.begin()
    _glow(layer, (x + w * 0.68, y + h * 0.24), unit * 0.95, pal.accent, 0.40)

    layer = p.begin()
    book_w = unit * 0.72
    book_h = unit * 0.115
    bx = x + w * 0.12
    by = y + h * 0.74
    palette = [pal.primary, pal.accent, pal.secondary, canvas.shade(pal.primary, 1.5)]
    for index in range(4):
        cy = by - index * book_h * 0.92
        colour = palette[index % len(palette)]
        offset = rng.uniform(-unit * 0.03, unit * 0.03)
        layer = p.begin()
        layer.polygon_rotated(bx + book_w / 2 + offset, cy, book_w, book_h, rng.uniform(-3, 3),
                              fill=canvas.rgba(colour, 246))
        # Page block and page lines go on their own layer: drawn onto the opaque
        # cover they would replace its alpha and punch a slot through the book.
        layer = p.begin()
        layer.polygon_rotated(bx + book_w / 2 + offset, cy + book_h * 0.30, book_w * 0.96, book_h * 0.22,
                              rng.uniform(-3, 3), fill=canvas.rgba(pal.ink, 88))
        for page in range(3):
            layer.line([(bx + offset + book_w * (0.08 + page * 0.30), cy),
                        (bx + offset + book_w * (0.02 + page * 0.30), cy)],
                       fill=canvas.rgba(pal.ink, 55), width=1.0)

    layer = p.begin()
    ox = x + w * 0.30
    oy = y + h * 0.40
    page_w = unit * 0.30
    page_h = unit * 0.19
    layer.polygon([(ox, oy), (ox + page_w, oy - page_h * 0.16), (ox + page_w, oy + page_h * 0.92),
                   (ox, oy + page_h)], fill=canvas.rgba(canvas.shade(pal.ink, 0.86), 236))
    layer.polygon([(ox, oy), (ox - page_w, oy - page_h * 0.16), (ox - page_w, oy + page_h * 0.92),
                   (ox, oy + page_h)], fill=canvas.rgba(pal.ink, 250))
    layer.line([(ox, oy), (ox, oy + page_h)], fill=canvas.rgba(pal.primary, 200), width=2.4)

    layer = p.begin()
    for row in range(4):
        yy = oy + page_h * (0.22 + row * 0.18)
        layer.line([(ox - page_w * 0.82, yy - page_h * 0.14), (ox - page_w * 0.14, yy - page_h * 0.10)],
                   fill=canvas.rgba(pal.primary, 70), width=1.6)
        layer.line([(ox + page_w * 0.14, yy - page_h * 0.10), (ox + page_w * 0.82, yy - page_h * 0.14)],
                   fill=canvas.rgba(pal.primary, 70), width=1.6)

    layer = p.begin()
    px, py = x + w * 0.70, y + h * 0.60
    length = unit * 0.52
    angle = -38.0
    body_a = _rot(px - length / 2, py, px, py, angle)
    body_b = _rot(px + length / 2, py, px, py, angle)
    layer.polygon_rotated(px, py, length, unit * 0.052, angle, fill=canvas.rgba(pal.accent, 240))
    tip = _rot(px + length / 2 + unit * 0.06, py, px, py, angle)
    layer.polygon([body_b, tip, _rot(px + length / 2, py + unit * 0.026, px, py, angle)],
                  fill=canvas.rgba(canvas.shade(pal.ink, 0.55), 235))
    layer.line([body_a, _rot(px - length / 2, py - unit * 0.026, px, py, angle)],
               fill=canvas.rgba(pal.ink, 120), width=1.2)
    layer.polygon_rotated(px - length / 2 - unit * 0.03, py, unit * 0.06, unit * 0.052, angle,
                          fill=canvas.rgba(pal.secondary, 235))


def trophy(p: Painter, pal: Palette, rng, box: Box) -> None:
    """A cup inside a laurel wreath, lit by a burst."""
    x, y, w, h = box
    cx, cy = x + w / 2, y + h * 0.52
    unit = min(w, h)

    layer = p.begin()
    _rays(layer, (cx, cy), unit * 1.5, pal.accent, count=22, spread=0.035, alpha=20, rng=rng)

    layer = p.begin()
    bowl_w = unit * 0.40
    bowl_h = unit * 0.30
    layer.pieslice((cx - bowl_w / 2, cy - bowl_h * 0.92, cx + bowl_w / 2, cy + bowl_h * 0.62),
                   180, 360, fill=canvas.rgba(pal.accent, 245))
    # The inner sheen needs its own layer, or it replaces the bowl's alpha and the
    # cup reads as a translucent shell instead of polished metal.
    layer = p.begin()
    layer.pieslice((cx - bowl_w * 0.34, cy - bowl_h * 0.80, cx + bowl_w * 0.34, cy + bowl_h * 0.30),
                   180, 360, fill=canvas.rgba(canvas.shade(pal.accent, 1.28), 120))

    layer = p.begin()
    layer.rect((cx - bowl_w * 0.06, cy + bowl_h * 0.30, cx + bowl_w * 0.06, cy + bowl_h * 0.66),
               fill=canvas.rgba(pal.accent, 245))
    layer.polygon([(cx - bowl_w * 0.30, cy + bowl_h * 0.66), (cx + bowl_w * 0.30, cy + bowl_h * 0.66),
                   (cx + bowl_w * 0.38, cy + bowl_h * 0.80), (cx - bowl_w * 0.38, cy + bowl_h * 0.80)],
                  fill=canvas.rgba(pal.accent, 245))
    layer.rect((cx - bowl_w * 0.42, cy + bowl_h * 0.80, cx + bowl_w * 0.42, cy + bowl_h * 0.90),
               fill=canvas.rgba(canvas.shade(pal.accent, 0.78), 245), radius=unit * 0.01)
    for side in (-1, 1):
        rim = cx + side * bowl_w * 0.52
        layer.arc((rim - bowl_w * 0.22, cy - bowl_h * 0.72, rim + bowl_w * 0.22, cy + bowl_h * 0.30),
                  90 if side > 0 else 270, 270 if side > 0 else 90,
                  fill=canvas.rgba(pal.accent, 235), width=unit * 0.022)

    layer = p.begin()
    wreath_r = unit * 0.62
    for side in (-1, 1):
        for index in range(9):
            frac = index / 8.0
            angle = math.radians(-150 + frac * 120)
            lx = cx + side * math.cos(angle) * wreath_r
            ly = cy - math.sin(angle) * wreath_r * 0.86 + unit * 0.10
            leaf = math.degrees(angle) + (90 if side > 0 else -90)
            layer.polygon_rotated(lx, ly, unit * 0.115, unit * 0.052, leaf,
                                  fill=canvas.rgba(pal.secondary if index % 2 else pal.primary, 220))

    _confetti(p, rng, [pal.accent, pal.secondary, pal.ink], count=64,
              box=(x + w * 0.04, y + h * 0.02, w * 0.92, h * 0.5), alpha=(120, 215), sizes=(6, 18))


def circuit(p: Painter, pal: Palette, rng, box: Box) -> None:
    """Hex grid, glowing traces and chip outlines."""
    x, y, w, h = box
    unit = min(w, h)

    layer = p.begin()
    radius = unit * 0.085
    step_x = radius * 1.75
    step_y = radius * 1.52
    for row in range(int(h / step_y) + 2):
        for col in range(int(w / step_x) + 2):
            cx = x + col * step_x + (step_x / 2 if row % 2 else 0)
            cy = y + row * step_y
            points = [(cx + radius * math.cos(math.radians(60 * i + 30)),
                       cy + radius * math.sin(math.radians(60 * i + 30))) for i in range(6)]
            layer.polygon(points, outline=canvas.rgba(pal.accent, 30), width=1.0)

    layer = p.begin()
    for _ in range(7):
        px = x + rng.uniform(0.05, 0.9) * w
        py = y + rng.uniform(0.08, 0.92) * h
        points = [(px, py)]
        for _ in range(int(rng.integers(3, 6))):
            horizontal = len(points) % 2 == 1
            length = rng.uniform(unit * 0.08, unit * 0.24)
            dx, dy = (length, 0) if horizontal else (0, length)
            if rng.random() < 0.5:
                dx, dy = -dx, -dy
            px, py = max(x, min(x + w, px + dx)), max(y, min(y + h, py + dy))
            points.append((px, py))
        layer.line(points, fill=canvas.rgba(pal.secondary, 120), width=unit * 0.006)
        for point in points[1:-1]:
            layer.circle(point[0], point[1], unit * 0.012, fill=canvas.rgba(pal.accent, 200))
        layer.circle(px, py, unit * 0.022, fill=canvas.rgba(pal.accent, 245))

    layer = p.begin()
    for _ in range(3):
        cw = rng.uniform(unit * 0.20, unit * 0.32)
        ch = cw * rng.uniform(0.55, 0.75)
        cx = x + rng.uniform(0.15, 0.85) * w
        cy = y + rng.uniform(0.2, 0.8) * h
        layer.rect((cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2),
                   fill=canvas.rgba(canvas.shade(pal.primary, 1.6), 190),
                   outline=canvas.rgba(pal.accent, 130), width=1.6, radius=unit * 0.02)
        for pin in range(3):
            py = cy - ch * 0.28 + pin * ch * 0.28
            layer.line([(cx - cw / 2 - unit * 0.05, py), (cx - cw / 2, py)],
                       fill=canvas.rgba(pal.accent, 150), width=unit * 0.008)
            layer.line([(cx + cw / 2, py), (cx + cw / 2 + unit * 0.05, py)],
                       fill=canvas.rgba(pal.accent, 150), width=unit * 0.008)

    layer = p.begin()
    _glow(layer, (x + w * 0.72, y + h * 0.30), unit * 0.9, pal.accent, 0.26)
    _glow(layer, (x + w * 0.22, y + h * 0.76), unit * 0.8, pal.secondary, 0.24)


def snow(p: Painter, pal: Palette, rng, box: Box) -> None:
    """Snowflakes and bokeh in a cold haze."""
    x, y, w, h = box
    unit = min(w, h)

    layer = p.begin()
    for _ in range(22):
        cx = x + rng.random() * w
        cy = y + rng.random() * h
        radius = rng.uniform(unit * 0.02, unit * 0.08)
        layer.circle(cx, cy, radius, fill=canvas.rgba(pal.accent, int(rng.integers(20, 55))))
    haze = layer.blur(unit * 0.03)
    layer.paste(haze)

    for index in range(6):
        size = unit * (0.10 + index * 0.055) * rng.uniform(0.85, 1.15)
        cx = x + w * (0.12 + 0.76 * ((index + 0.5) / 6.0)) + rng.uniform(-w * 0.05, w * 0.05)
        cy = y + h * rng.uniform(0.16, 0.84)
        layer = p.begin()
        arms = 6
        colour = pal.ink if index % 2 else pal.accent
        alpha = int(rng.integers(120, 210))
        for arm in range(arms):
            angle = math.radians(arm * 360.0 / arms + rng.uniform(-6, 6))
            tip = (cx + math.cos(angle) * size, cy + math.sin(angle) * size)
            layer.line([(cx, cy), tip], fill=canvas.rgba(colour, alpha),
                       width=max(1.0, unit * 0.006))
            for branch in (0.45, 0.72):
                bx = cx + math.cos(angle) * size * branch
                by = cy + math.sin(angle) * size * branch
                for side in (-1, 1):
                    bangle = angle + side * math.radians(38)
                    layer.line([(bx, by), (bx + math.cos(bangle) * size * 0.30,
                                           by + math.sin(bangle) * size * 0.30)],
                               fill=canvas.rgba(colour, alpha - 30), width=max(1.0, unit * 0.004))
        layer.circle(cx, cy, size * 0.10, fill=canvas.rgba(colour, alpha))

    layer = p.begin()
    for _ in range(14):
        cx = x + rng.random() * w
        cy = y + rng.random() * h
        radius = rng.uniform(unit * 0.03, unit * 0.11)
        layer.circle(cx, cy, radius, fill=canvas.rgba(pal.ink, int(rng.integers(40, 95))))


def globe(p: Painter, pal: Palette, rng, box: Box) -> None:
    """A dotted wireframe globe with an orbit ring, over a skyline."""
    x, y, w, h = box
    unit = min(w, h)
    cx, cy = x + w * 0.5, y + h * 0.46
    radius = unit * 0.40

    layer = p.begin()
    _glow(layer, (cx, cy), radius * 2.2, pal.accent, 0.30)

    layer = p.begin()
    layer.circle(cx, cy, radius, fill=canvas.rgba(pal.primary, 120))

    layer = p.begin()
    layer.circle(cx, cy, radius, outline=canvas.rgba(pal.accent, 225), width=unit * 0.010)
    for frac in (0.24, 0.46, 0.68, 0.88):
        ry = radius * math.sqrt(max(0.0, 1 - frac * frac))
        layer.line([(cx - radius * frac, cy - ry), (cx - radius * frac, cy + ry)],
                   fill=canvas.rgba(pal.ink, 46), width=1.1)
        layer.line([(cx + radius * frac, cy - ry), (cx + radius * frac, cy + ry)],
                   fill=canvas.rgba(pal.ink, 46), width=1.1)
    for offset in (-0.62, -0.30, 0.0, 0.30, 0.62):
        half = radius * math.sqrt(max(0.0, 1 - offset * offset))
        layer.line([(cx - half, cy + radius * offset), (cx + half, cy + radius * offset)],
                   fill=canvas.rgba(pal.ink, 46), width=1.1)

    layer = p.begin()
    for _ in range(190):
        angle = rng.uniform(0, math.tau)
        dist = radius * math.sqrt(rng.random()) * 0.96
        dx, dy = cx + math.cos(angle) * dist, cy + math.sin(angle) * dist
        layer.circle(dx, dy, unit * 0.006, fill=canvas.rgba(pal.accent, int(rng.integers(70, 190))))

    layer = p.begin()
    ring_w = radius * 2.6
    layer.arc((cx - ring_w / 2, cy - ring_w * 0.16, cx + ring_w / 2, cy + ring_w * 0.16),
              190, 350, fill=canvas.rgba(pal.secondary, 190), width=unit * 0.009)
    layer.arc((cx - ring_w / 2, cy - ring_w * 0.16, cx + ring_w / 2, cy + ring_w * 0.16),
              12, 168, fill=canvas.rgba(pal.secondary, 110), width=unit * 0.007)
    layer.circle(cx + ring_w * 0.42, cy - ring_w * 0.10, unit * 0.018,
                 fill=canvas.rgba(pal.ink, 240))

    layer = p.begin()
    base_y = y + h * 0.90
    cursor = x
    while cursor < x + w:
        bw = rng.uniform(unit * 0.05, unit * 0.12)
        bh = rng.uniform(unit * 0.10, unit * 0.34)
        layer.rect((cursor, base_y - bh, cursor + bw * 0.92, base_y),
                   fill=canvas.rgba(canvas.shade(pal.primary, 0.42), 245))
        for _ in range(int(rng.integers(3, 9))):
            wx = cursor + rng.uniform(0.1, 0.8) * bw * 0.92
            wy = base_y - rng.uniform(0.1, 0.9) * bh
            layer.rect((wx, wy, wx + unit * 0.012, wy + unit * 0.012),
                       fill=canvas.rgba(pal.accent, int(rng.integers(120, 235))))
        cursor += bw


def wave(p: Painter, pal: Palette, rng, box: Box) -> None:
    """Sound ribbons, an equaliser and stage light."""
    x, y, w, h = box
    unit = min(w, h)

    layer = p.begin()
    for index, side in enumerate((-1, 1)):
        apex = (x + w * (0.5 + side * 0.30), y - h * 0.10)
        spread = w * 0.22
        layer.polygon([apex, (apex[0] - spread, y + h), (apex[0] + spread, y + h)],
                      fill=canvas.rgba(pal.accent, 26 if index == 0 else 20))

    for index, (amplitude, colour, alpha, thickness) in enumerate((
        (0.16, pal.accent, 118, 0.030),
        (0.11, pal.secondary, 92, 0.024),
        (0.075, pal.ink, 74, 0.018),
    )):
        layer = p.begin()
        cy = y + h * (0.40 + index * 0.08)
        steps = 72
        top, bottom = [], []
        for step in range(steps + 1):
            t = step / steps
            sx = x + t * w
            offset = math.sin(t * math.tau * (1.4 + index * 0.35) + index) * h * amplitude
            top.append((sx, cy + offset - unit * thickness * 0.5))
            bottom.append((sx, cy + offset + unit * thickness * 0.5))
        layer.polygon([*top, *reversed(bottom)], fill=canvas.rgba(colour, alpha))

    layer = p.begin()
    bars = 26
    bar_w = w / (bars * 1.7)
    base = y + h * 0.92
    for index in range(bars):
        t = index / (bars - 1)
        height = h * (0.06 + 0.20 * abs(math.sin(t * math.pi * 3.1 + 0.6)) * rng.uniform(0.6, 1.35))
        bx = x + w * 0.06 + t * w * 0.88
        layer.rect((bx, base - height, bx + bar_w, base),
                   fill=canvas.rgba(pal.accent if index % 3 else pal.secondary,
                                    int(rng.integers(120, 226))), radius=bar_w * 0.4)

    layer = p.begin()
    for _ in range(18):
        cx = x + rng.random() * w
        cy = y + rng.random() * h * 0.7
        radius = rng.uniform(unit * 0.006, unit * 0.022)
        layer.circle(cx, cy, radius, fill=canvas.rgba(pal.ink, int(rng.integers(60, 170))))


def flags(p: Painter, pal: Palette, rng, box: Box) -> None:
    """Bunting between poles, with stalls underneath."""
    x, y, w, h = box
    unit = min(w, h)

    layer = p.begin()
    _glow(layer, (x + w * 0.5, y + h * 0.22), unit * 1.3, pal.accent, 0.26)

    palette = [pal.accent, pal.secondary, pal.ink, pal.primary]
    for strand in range(2):
        layer = p.begin()
        top_y = y + h * (0.16 + strand * 0.20)
        sag = h * (0.14 + strand * 0.06)
        points = []
        for step in range(41):
            t = step / 40.0
            points.append((x + t * w, top_y + math.sin(t * math.pi) * sag))
        layer.line(points, fill=canvas.rgba(pal.ink, 150), width=max(1.0, unit * 0.005))
        for index in range(9):
            t = (index + 0.5) / 9.0
            fx = x + t * w
            fy = top_y + math.sin(t * math.pi) * sag
            size = unit * 0.085
            layer.polygon([(fx - size * 0.6, fy), (fx + size * 0.6, fy), (fx, fy + size)],
                          fill=canvas.rgba(palette[(index + strand) % len(palette)], 244))

    layer = p.begin()
    stalls = 3
    for index in range(stalls):
        cx = x + w * (0.20 + index * 0.30)
        sw = unit * 0.34
        sy = y + h * 0.80
        colour = palette[index % len(palette)]
        layer.pieslice((cx - sw / 2, sy - sw * 0.5, cx + sw / 2, sy + sw * 0.5), 180, 360,
                       fill=canvas.rgba(colour, 240))
        layer.rect((cx - sw / 2, sy, cx + sw / 2, sy + unit * 0.16),
                   fill=canvas.rgba(canvas.shade(colour, 0.72), 240))
        # Canopy stripes on their own layer: over the opaque awning they would cut
        # alpha-70 slots through it.
        stripe_layer = p.begin()
        for stripe in range(5):
            sx = cx - sw / 2 + (stripe + 0.5) * sw / 5
            stripe_layer.line([(sx, sy - sw * 0.42), (sx, sy)], fill=canvas.rgba(pal.ink, 70), width=1.2)
        layer = stripe_layer
        layer.rect((cx - sw * 0.06, sy + unit * 0.16, cx + sw * 0.06, sy + unit * 0.26),
                   fill=canvas.rgba(pal.ink, 120))

    _confetti(p, rng, palette, count=40, box=(x, y + h * 0.30, w, h * 0.45),
              alpha=(110, 200), sizes=(6, 16))


def confetti(p: Painter, pal: Palette, rng, box: Box) -> None:
    """A rising burst of paper and ribbons."""
    x, y, w, h = box
    unit = min(w, h)
    origin = (x + w * 0.5, y + h * 0.86)

    layer = p.begin()
    _rays(layer, origin, unit * 1.9, pal.accent, count=20, spread=0.03, alpha=22, rng=rng)

    layer = p.begin()
    for _ in range(7):
        cx = x + rng.uniform(0.1, 0.9) * w
        cy = y + rng.uniform(0.15, 0.85) * h
        radius = unit * rng.uniform(0.10, 0.22)
        start = rng.uniform(0, 360)
        layer.arc((cx - radius, cy - radius, cx + radius, cy + radius), start, start + rng.uniform(90, 220),
                  fill=canvas.rgba(pal.secondary if rng.random() < 0.5 else pal.accent, 165),
                  width=max(1.0, unit * 0.012))

    _confetti(p, rng, [pal.accent, pal.secondary, pal.ink, canvas.shade(pal.primary, 1.7)],
              count=110, box=(x, y + h * 0.06, w, h * 0.85), alpha=(140, 240), sizes=(7, 30))

    layer = p.begin()
    for _ in range(26):
        t = rng.random()
        cx = origin[0] + (rng.random() - 0.5) * w * 0.9
        cy = origin[1] - t * h * 0.8
        layer.circle(cx, cy, unit * rng.uniform(0.006, 0.02),
                     fill=canvas.rgba(pal.ink, int(rng.integers(80, 210))))


def geometric(p: Painter, pal: Palette, rng, box: Box) -> None:
    """The house look: diagonal navy bands, a gold rule and a dot grid."""
    x, y, w, h = box
    unit = min(w, h)

    layer = p.begin()
    for index, (offset, width, colour, alpha) in enumerate((
        (0.10, 0.30, pal.primary, 255),
        (0.52, 0.16, canvas.shade(pal.primary, 1.25), 255),
        (0.74, 0.09, pal.accent, 255),
    )):
        shift = x + w * offset
        layer.polygon([(shift, y), (shift + w * width, y),
                       (shift + w * width - h * 0.28, y + h), (shift - h * 0.28, y + h)],
                      fill=canvas.rgba(colour, alpha))

    layer = p.begin()
    spacing = unit * 0.085
    for row in range(int(h / spacing) + 1):
        for col in range(int(w / spacing) + 1):
            cx = x + col * spacing + (spacing / 2 if row % 2 else 0)
            cy = y + row * spacing
            layer.circle(cx, cy, max(1.0, unit * 0.008), fill=canvas.rgba(pal.secondary, 60))

    layer = p.begin()
    layer.circle(x + w * 0.78, y + h * 0.30, unit * 0.26,
                 outline=canvas.rgba(pal.accent, 235), width=unit * 0.018)
    layer.pieslice((x + w * 0.78 - unit * 0.26, y + h * 0.30 - unit * 0.26,
                    x + w * 0.78 + unit * 0.26, y + h * 0.30 + unit * 0.26), 180, 360,
                   fill=canvas.rgba(pal.accent, 235))
    for index in range(3):
        layer.line([(x + w * 0.08, y + h * (0.78 + index * 0.06)),
                    (x + w * 0.08 + w * (0.34 - index * 0.07), y + h * (0.78 + index * 0.06))],
                   fill=canvas.rgba(pal.accent if index == 0 else pal.primary, 235),
                   width=unit * (0.016 - index * 0.004))


MOTIFS = {
    "aperture": aperture,
    "shuttle": shuttle,
    "lantern": lantern,
    "study": study,
    "trophy": trophy,
    "circuit": circuit,
    "snow": snow,
    "globe": globe,
    "wave": wave,
    "flags": flags,
    "confetti": confetti,
    "geometric": geometric,
}


def draw(name: str, p: Painter, pal: Palette, rng, box: Box) -> None:
    """Draw motif ``name``, falling back to the house pattern if it is unknown."""
    MOTIFS.get(name, geometric)(p, pal, rng, box)
