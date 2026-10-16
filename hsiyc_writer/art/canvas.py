"""Pixel primitives for the generative artwork.

Everything here is deliberately small and boring: gradients, noise, masks, and a
supersampled drawing surface. The quality of the output comes from compositing
these, not from any one of them.

Supersampling matters more than it looks. Pillow has no antialiasing, so a
circle drawn straight onto a 1600x900 canvas has visibly stepped edges. Every
shape is therefore drawn at 2x and reduced with LANCZOS, which is why motif code
never touches raw pixel coordinates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import text as textmod

RGB = tuple[int, int, int]


# --------------------------------------------------------------------------- palette
@dataclass(frozen=True)
class Palette:
    """A vibe's colours, resolved to RGB for drawing."""

    background: RGB
    primary: RGB
    accent: RGB
    secondary: RGB
    ink: RGB

    @classmethod
    def from_hex(cls, values: dict[str, str]) -> "Palette":
        return cls(
            background=hex_rgb(values["background"]),
            primary=hex_rgb(values["primary"]),
            accent=hex_rgb(values["accent"]),
            secondary=hex_rgb(values["secondary"]),
            ink=hex_rgb(values["ink"]),
        )

    def as_hex(self) -> dict[str, str]:
        return {
            "background": "#%02X%02X%02X" % self.background,
            "primary": "#%02X%02X%02X" % self.primary,
            "accent": "#%02X%02X%02X" % self.accent,
            "secondary": "#%02X%02X%02X" % self.secondary,
            "ink": "#%02X%02X%02X" % self.ink,
        }


# --------------------------------------------------------------------------- colour
def hex_rgb(value: str) -> RGB:
    value = value.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def rgba(colour: RGB, alpha: int = 255) -> tuple[int, int, int, int]:
    """A colour tuple. Alpha defaults to opaque, which is what most callers want."""
    return (colour[0], colour[1], colour[2], max(0, min(255, int(alpha))))


def mix(a: RGB, b: RGB, t: float) -> RGB:
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))  # type: ignore[return-value]


def shade(colour: RGB, factor: float) -> RGB:
    """factor < 1 darkens toward black, > 1 lightens toward white."""
    if factor <= 1:
        return mix(colour, (0, 0, 0), 1 - factor)
    return mix(colour, (255, 255, 255), min(1.0, factor - 1))


# --------------------------------------------------------------------------- gradients
def _axis(w: int, h: int, angle_deg: float) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    rad = math.radians(angle_deg)
    t = xx * math.cos(rad) + yy * math.sin(rad)
    span = t.max() - t.min()
    return (t - t.min()) / (span if span else 1.0)


def gradient(w: int, h: int, stops: list[tuple[float, RGB]], angle_deg: float = 90) -> np.ndarray:
    """Multi-stop linear gradient as an HxWx3 float array."""
    t = _axis(w, h, angle_deg)
    positions = np.array([s[0] for s in stops], dtype=np.float32)
    out = np.zeros((h, w, 3), dtype=np.float32)
    for channel in range(3):
        values = np.array([s[1][channel] for s in stops], dtype=np.float32)
        out[:, :, channel] = np.interp(t, positions, values)
    return out


def radial(w: int, h: int, inner: RGB, outer: RGB, *, centre: tuple[float, float] = (0.5, 0.5),
           radius: float = 1.0, power: float = 1.0) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = centre[0] * w, centre[1] * h
    # Normalise by the longest half-diagonal so the falloff stays circular.
    span = math.hypot(max(cx, w - cx), max(cy, h - cy)) * radius
    d = np.clip(np.hypot(xx - cx, yy - cy) / (span if span else 1.0), 0.0, 1.0) ** power
    out = np.zeros((h, w, 3), dtype=np.float32)
    for channel in range(3):
        out[:, :, channel] = inner[channel] + (outer[channel] - inner[channel]) * d
    return out


def glow(w: int, h: int, colour: RGB, *, centre: tuple[float, float], radius: float,
         strength: float = 0.6) -> np.ndarray:
    """Additive light bloom, returned as a multiplier-friendly float array."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = centre[0] * w, centre[1] * h
    span = max(1.0, radius * max(w, h))
    d = np.clip(np.hypot(xx - cx, yy - cy) / span, 0.0, 1.0)
    falloff = (1.0 - d) ** 2 * strength
    return falloff[:, :, None] * np.array(colour, dtype=np.float32)[None, None, :]


# --------------------------------------------------------------------------- noise
def value_noise(w: int, h: int, scale: int = 32, seed: int = 0) -> np.ndarray:
    """Smooth 0..1 noise: random low-res grid, bicubic upscale."""
    scale = max(2, int(scale))
    small = np.random.default_rng(seed).random((max(2, h // scale + 2), max(2, w // scale + 2)))
    image = Image.fromarray((small * 255).astype(np.uint8), "L").resize((w, h), Image.BICUBIC)
    return np.asarray(image, dtype=np.float32) / 255.0


def fbm(w: int, h: int, *, scale: int = 64, octaves: int = 4, seed: int = 0,
        persistence: float = 0.5) -> np.ndarray:
    total = np.zeros((h, w), dtype=np.float32)
    amplitude, norm = 1.0, 0.0
    for octave in range(max(1, octaves)):
        total += amplitude * value_noise(w, h, max(2, scale // (2 ** octave)), seed + octave * 977)
        norm += amplitude
        amplitude *= persistence
    return total / (norm or 1.0)


def vignette(w: int, h: int, strength: float = 0.35, power: float = 2.2) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w / 2.0, h / 2.0
    d = np.hypot((xx - cx) / cx, (yy - cy) / cy) / math.sqrt(2.0)
    return 1.0 - strength * np.clip(d, 0.0, 1.0) ** power


def to_image(array: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(array, 0, 255).astype(np.uint8), "RGB")


def to_array(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.float32)


# --------------------------------------------------------------------------- surface
class Layer:
    """A transparent drawing surface that works in final-size coordinates.

    Shapes are rasterised at ``supersample``x and reduced on :meth:`finish`, so
    callers pass the same numbers they would for a flat canvas and still get
    smooth diagonals and circles.
    """

    def __init__(self, width: int, height: int, supersample: int = 2):
        self.w, self.h, self.ss = width, height, supersample
        self.img = Image.new("RGBA", (width * supersample, height * supersample), (0, 0, 0, 0))
        self.draw = ImageDraw.Draw(self.img, "RGBA")

    # -- geometry helpers ---------------------------------------------------
    @property
    def s(self) -> int:
        return self.ss

    def _p(self, x: float, y: float) -> tuple[float, float]:
        return (x * self.ss, y * self.ss)

    def _box(self, box) -> list[float]:
        return [box[0] * self.ss, box[1] * self.ss, box[2] * self.ss, box[3] * self.ss]

    def _pts(self, points) -> list[tuple[float, float]]:
        return [(x * self.ss, y * self.ss) for x, y in points]

    # -- shapes -------------------------------------------------------------
    def ellipse(self, box, fill=None, outline=None, width: float = 1) -> None:
        self.draw.ellipse(self._box(box), fill=fill, outline=outline, width=max(1, int(width * self.ss)))

    def circle(self, cx: float, cy: float, r: float, fill=None, outline=None, width: float = 1) -> None:
        self.ellipse((cx - r, cy - r, cx + r, cy + r), fill, outline, width)

    def rect(self, box, fill=None, outline=None, width: float = 1, radius: float = 0) -> None:
        if radius:
            self.draw.rounded_rectangle(self._box(box), radius=radius * self.ss, fill=fill,
                                        outline=outline, width=max(1, int(width * self.ss)))
        else:
            self.draw.rectangle(self._box(box), fill=fill, outline=outline, width=max(1, int(width * self.ss)))

    def polygon(self, points, fill=None, outline=None, width: float = 1) -> None:
        self.draw.polygon(self._pts(points), fill=fill, outline=outline, width=max(1, int(width * self.ss)))

    def line(self, points, fill=None, width: float = 1) -> None:
        self.draw.line(self._pts(points), fill=fill, width=max(1, int(width * self.ss)), joint="curve")

    def arc(self, box, start: float, end: float, fill=None, width: float = 1) -> None:
        self.draw.arc(self._box(box), start, end, fill=fill, width=max(1, int(width * self.ss)))

    def pieslice(self, box, start: float, end: float, fill=None, outline=None, width: float = 1) -> None:
        self.draw.pieslice(self._box(box), start, end, fill=fill, outline=outline,
                           width=max(1, int(width * self.ss)))

    def polygon_rotated(self, cx: float, cy: float, w: float, h: float, angle_deg: float,
                        fill=None, outline=None) -> None:
        rad = math.radians(angle_deg)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        corners = []
        for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
            corners.append((cx + dx * cos_a - dy * sin_a, cy + dx * sin_a + dy * cos_a))
        self.polygon(corners, fill=fill, outline=outline)

    def dashed_line(self, start, end, fill, *, width: float = 1, dash: float = 10, gap: float = 8) -> None:
        x0, y0 = start
        x1, y1 = end
        length = math.hypot(x1 - x0, y1 - y0)
        if length <= 0:
            return
        ux, uy = (x1 - x0) / length, (y1 - y0) / length
        cursor = 0.0
        while cursor < length:
            stop = min(cursor + dash, length)
            self.line([(x0 + ux * cursor, y0 + uy * cursor), (x0 + ux * stop, y0 + uy * stop)],
                      fill=fill, width=width)
            cursor = stop + gap

    # -- text ---------------------------------------------------------------
    def text(self, x: float, y: float, string: str, size: float, fill,
             anchor: str = "la", bold: bool = True) -> None:
        """Draw one line. ``size`` is the final-size point size, not the 2x one."""
        font = textmod.load(max(6, int(round(size * self.ss))), bold=bold)
        if font is None or not string:
            return
        self.draw.text(self._p(x, y), string, font=font, fill=fill, anchor=anchor)

    def lines(self, x: float, y: float, rows: list[str], size: float, fill, *,
              line_height: float = 1.35, bold: bool = True, anchor: str = "la") -> None:
        step = size * line_height
        for index, row in enumerate(rows):
            self.text(x, y + index * step, row, size, fill, anchor=anchor, bold=bold)

    def paste(self, image: Image.Image) -> None:
        """Composite a final-size RGBA image back onto the supersampled surface.

        Lets a motif blur part of itself (a glow) without giving up the
        supersampling that the sharp shapes still need.
        """
        target = (self.w * self.ss, self.h * self.ss)
        if image.size != target:
            image = image.resize(target, Image.BILINEAR)
        self.img.alpha_composite(image.convert("RGBA"))

    # -- compose ------------------------------------------------------------
    def finish(self) -> Image.Image:
        if self.ss == 1:
            return self.img
        return self.img.resize((self.w, self.h), Image.LANCZOS)

    def blur(self, radius: float) -> Image.Image:
        return self.finish().filter(ImageFilter.GaussianBlur(max(0.1, radius)))


def alpha_composite(base: Image.Image, *layers: Image.Image | None) -> Image.Image:
    result = base.convert("RGBA")
    for layer in layers:
        if layer is None:
            continue
        result = Image.alpha_composite(result, layer.convert("RGBA"))
    return result


class Painter:
    """An ordered stack of layers.

    Pillow *replaces* pixels when you draw an RGBA fill onto an RGBA image; it
    does not blend. A 25%-opacity sunbeam drawn over a solid shape would erase
    the shape rather than light it. So anything translucent gets its own layer
    and the stack is composited in order, which is how the softer parts of the
    artwork (glows, rays, haze) get their depth.
    """

    def __init__(self, width: int, height: int, supersample: int = 2):
        self.w, self.h, self.ss = width, height, supersample
        self.layers: list[Image.Image] = []
        self.layer = Layer(width, height, supersample)

    def begin(self) -> Layer:
        """Close the current layer and start a fresh one."""
        self.layers.append(self.layer.finish())
        self.layer = Layer(self.w, self.h, self.ss)
        return self.layer

    def composite(self) -> Image.Image:
        stack = [*self.layers, self.layer.finish()]
        result = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        for image in stack:
            result = Image.alpha_composite(result, image)
        return result


def soft_shadow(layer: Layer, radius: float, opacity: float = 0.35) -> Image.Image:
    """Blurred copy of a layer's own alpha, for glow and depth."""
    return shadow_of(layer.finish(), radius, opacity)


def shadow_of(image: Image.Image, radius: float, opacity: float = 0.35) -> Image.Image:
    """A blurred dark copy of an image's own alpha.

    Composited *under* the subject, this is what lifts flat vector shapes off a
    gradient background. Without it every motif looks printed onto the colour
    rather than standing in front of it.
    """
    mask = image.convert("RGBA").split()[-1].filter(ImageFilter.GaussianBlur(max(0.1, radius)))
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow.putalpha(mask.point(lambda value: int(value * opacity)))
    return shadow


def finish_image(image: Image.Image, *, grain: float = 0.0, vig: float = 0.0,
                 seed: int = 0) -> Image.Image:
    """Final polish pass: film grain and a vignette, both optional."""
    array = to_array(image)
    if vig:
        array *= vignette(image.width, image.height, vig)[:, :, None]
    if grain:
        noise = np.random.default_rng(seed).normal(0.0, grain, array.shape[:2]).astype(np.float32)
        array += noise[:, :, None]
    return to_image(array)
