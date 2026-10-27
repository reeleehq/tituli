"""Rasterise a :class:`~tituli.layout.Layout` with Pillow.

The default engine is Pillow alone: un-rotated runs go straight through
``ImageDraw.text`` (FreeType under the hood); rotated runs are drawn into a tile
and rotated about their baseline origin with bicubic resampling. That is what
lets a calligram exist with no dependency beyond Pillow. The optional
:mod:`tituli.shaping` tier swaps in HarfBuzz shaping + FreeType outline transforms
for scripts and ligatures Pillow's basic layout cannot do — it is the ``engine=``
seam of :func:`render`.

Output is always a full-frame image: an **RGBA overlay** when the frame has no
background (compose it onto video later — never into the stills, or a camera
move would drag the lettering along with the picture), or an **RGB composite**
when the frame carries a colour or a picture.

>>> from tituli.frame import Frame
>>> from tituli.layout import block
>>> from tituli.style import TITLE
>>> img = render(block("Hi", TITLE, 1080), Frame.blank((640, 360)))
>>> img.mode, img.size
('RGBA', (640, 360))
"""

from __future__ import annotations

import math
from dataclasses import replace
from itertools import groupby
from typing import Callable, Iterator, Protocol

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from tituli.color import RGBA, ink_for, parse_color, relative_luminance
from tituli.frame import Frame
from tituli.geometry import Box
from tituli.fonts import Face
from tituli.layout import Layout, Plate, Run, check_measured_by, FACE_ENGINE
from tituli.style import Halo

_TILE_MARGIN_EM = 0.35  # extra room around a rotated glyph tile, in em
_RESAMPLE = Image.Resampling.BICUBIC
_ALPHA_MAX = 255
_GRADIENT_STEPS = 256
_CORNER_POWER = 2.2  # ease of a scrim's falloff (higher = holds longer, drops faster)
# A Gaussian's visible reach, in radii: how far a halo extends past its spread.
_BLUR_REACH = 3


class Engine(Protocol):
    """Draws runs, and measures them: the engine that draws a text is the one
    that must measure it (tituli#7), or wrap points and column pitch drift.

    ``name`` is the measurement identity stamped on ``Run.measured_by``: two
    engines share one only if they measure alike. Without it the class name is
    used, as it is for a subclass that overrides ``length`` but not ``name``.
    An engine that hands some faces to another may say so with an optional
    ``measurer(face) -> Engine``; the run is then stamped with that one's name
    (see :func:`tituli.layout.engine_name`)."""

    name: str

    def draw_run(self, canvas: Image.Image, run: Run, opacity: float) -> None: ...

    def length(self, face: Face, text: str) -> float:
        """Advance of ``text`` in pixels, before tracking."""
        ...


def _envelope(run: Run, t: float | None) -> float:
    """Reveal factor of a run at time ``t`` (1 when untimed or t is None)."""
    if t is None or run.t_in is None:
        return 1.0
    if t < run.t_in:
        return 0.0
    full = run.t_full if run.t_full is not None else run.t_in
    if t >= full or full <= run.t_in:
        return 1.0
    return (t - run.t_in) / (full - run.t_in)


class PillowEngine:
    """The zero-extra-dependency engine."""

    name = FACE_ENGINE

    def length(self, face: Face, text: str) -> float:
        return face.length(text)

    def draw_run(self, canvas: Image.Image, run: Run, opacity: float) -> None:
        color = _scaled_alpha(run.color, run.opacity * opacity)
        if color[3] == 0 or not run.text:
            return
        _refuse_unapplied_substitutions(run)
        font = run.face.pil
        if run.angle == 0.0 and run.tracking == 0.0:
            draw = ImageDraw.Draw(canvas)
            draw.text((run.x, run.y), run.text, font=font, fill=color, anchor="ls")
            return
        if run.angle == 0.0:  # tracked glyph run drawn per glyph
            draw = ImageDraw.Draw(canvas)
            x = run.x
            for ch in run.text:
                draw.text((x, run.y), ch, font=font, fill=color, anchor="ls")
                x += run.face.length(ch) + run.tracking
            return
        tile, origin = _rotated_tile(run, color)
        px = int(round(run.x - origin[0]))
        py = int(round(run.y - origin[1]))
        canvas.alpha_composite(tile, (px, py))


def _refuse_unapplied_substitutions(run: Run) -> None:
    """Pillow draws a character's default glyph; refuse a run whose style's
    OpenType features substitute another one, rather than draw glyphs other
    than the ones its layout measured (tituli#4)."""
    face = run.face
    if not face.applied_features:
        return
    from tituli.features import FeatureError, featured_glyphs

    plain = replace(face, features=())
    if featured_glyphs(face, run.text) != featured_glyphs(plain, run.text):
        raise FeatureError(
            f"the Pillow engine cannot draw the glyphs that features "
            f"{list(face.applied_features)} substitute in {run.text!r}: render "
            "with `engine=tituli.shaping.HarfBuzzEngine()` "
            "(`pip install tituli[shaping]`), take the contours from "
            "`tituli.run_outline`, or drop the feature from the style"
        )


def _scaled_alpha(color: RGBA, factor: float) -> RGBA:
    r, g, b, a = color
    return (r, g, b, max(0, min(_ALPHA_MAX, round(a * factor))))


def _rotated_tile(run: Run, color: RGBA) -> tuple[Image.Image, tuple[float, float]]:
    """Draw the run upright in a tile, rotate about its baseline origin.

    Returns the tile and where the run's origin landed inside it.
    """
    face = run.face
    m = int(math.ceil(face.size * _TILE_MARGIN_EM))
    w = int(math.ceil(run.width)) + 2 * m
    h = face.line_height + 2 * m
    tile = Image.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 0))
    ox, oy = float(m), float(m + face.ascent)
    ImageDraw.Draw(tile).text(
        (ox, oy), run.text, font=face.pil, fill=color, anchor="ls"
    )
    # Pillow rotates counter-clockwise; our angle is clockwise on screen.
    rotated = tile.rotate(-run.angle, resample=_RESAMPLE, expand=True, center=(ox, oy))
    # Where did (ox, oy) go? With expand=True Pillow rotates about `center`
    # then shifts so the rotated bounds start at (0, 0).
    a = math.radians(run.angle)
    cos, sin = math.cos(a), math.sin(a)

    def rot(x: float, y: float) -> tuple[float, float]:
        dx, dy = x - ox, y - oy
        return (ox + dx * cos - dy * sin, oy + dx * sin + dy * cos)

    corners = [rot(0, 0), rot(w, 0), rot(0, h), rot(w, h)]
    min_x = min(c[0] for c in corners)
    min_y = min(c[1] for c in corners)
    return rotated, (ox - min_x, oy - min_y)


# ----------------------------------------------------------------------------
# Plates
# ----------------------------------------------------------------------------


def _ramp(
    length: int, *, reverse: bool = False, solid: float = 0.0, power: float = 1.0
) -> Image.Image:
    """A 1-px-wide 'L' column: 255 at the start, easing to 0 by the end."""
    vals = []
    for i in range(_GRADIENT_STEPS):
        t = i / (_GRADIENT_STEPS - 1)
        u = 0.0 if t <= solid else (t - solid) / max(1e-9, 1 - solid)
        v = (1 - u) ** power
        vals.append(round(_ALPHA_MAX * v))
    if reverse:
        vals.reverse()
    strip = Image.new("L", (1, _GRADIENT_STEPS))
    strip.putdata(vals)
    return strip.resize((1, max(1, length)), Image.Resampling.BILINEAR)


def _plate_alpha(plate: Plate, w: int, h: int) -> Image.Image:
    sx, sy = plate.solid
    if plate.kind == "gradient-bottom":  # dark at the bottom, clear at the top
        return _ramp(h, reverse=True, solid=sy, power=_CORNER_POWER).resize((w, h))
    if plate.kind == "gradient-top":
        return _ramp(h, solid=sy, power=_CORNER_POWER).resize((w, h))
    if plate.kind.startswith("corner-"):  # product of a vertical and a horizontal ramp
        v = _ramp(h, solid=sy, power=_CORNER_POWER).resize((w, h))
        hz = (
            _ramp(w, solid=sx, power=_CORNER_POWER)
            .rotate(90, expand=True)
            .resize((w, h))
        )
        alpha = ImageChops.multiply(v, hz)  # strongest at the top-left
        if "right" in plate.kind:
            alpha = alpha.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if "bottom" in plate.kind:
            alpha = alpha.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        return alpha
    return Image.new("L", (w, h), _ALPHA_MAX)


def draw_plate(canvas: Image.Image, plate: Plate) -> None:
    """Composite one plate (scrim, box or rule) onto the canvas."""
    x0, y0, x1, y1 = plate.box.intersection(
        Box(0, 0, canvas.width, canvas.height)
    ).rounded()
    w, h = max(0, x1 - x0), max(0, y1 - y0)
    if w == 0 or h == 0:
        return
    r, g, b, a = plate.color
    layer = Image.new("RGBA", (w, h), (r, g, b, 0))
    alpha = _plate_alpha(plate, w, h)
    if plate.kind == "box" and plate.radius > 0:
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, w - 1, h - 1), radius=plate.radius, fill=_ALPHA_MAX
        )
        alpha = ImageChops.multiply(alpha, mask)
    alpha = alpha.point(lambda v: v * a // _ALPHA_MAX)
    layer.putalpha(alpha)
    canvas.alpha_composite(layer, (x0, y0))


def _halo_color(halo: Halo, ink: RGBA) -> RGBA:
    """The halo's colour, or the opposite of the ink when it names none."""
    if halo.color is not None:
        return parse_color(halo.color)
    return parse_color(ink_for(luminance=relative_luminance(ink)))


def glow(
    alpha: Image.Image, *, spread: int, blur: float, gain: float, opacity: float
) -> Image.Image:
    """The halo's alpha (mode ``L``) from the glyphs' alpha: dilated, blurred, boosted.

    ``spread`` and ``blur`` are in pixels. Dilation is a box blur of radius
    ``spread`` read back steeply: a pixel within ``spread`` of a stroke has at
    least one column of ink in its box, so scaling by the box's width saturates
    it, and the glow keeps the letters' shapes. A box blur is running sums, so
    its cost does not grow with the radius (a max filter's does).

    >>> dot = Image.new("L", (9, 9), 0)
    >>> dot.putpixel((4, 4), 255)
    >>> g = glow(dot, spread=2, blur=0, gain=1, opacity=1)
    >>> g.getbbox(), g.getpixel((4, 4)) > 0
    ((2, 2, 7, 7), True)
    """
    out = alpha
    if spread > 0:
        width = 2 * spread + 1
        out = out.filter(ImageFilter.BoxBlur(spread))
        out = out.point(lambda v: min(_ALPHA_MAX, v * width))
    if blur > 0:
        out = out.filter(ImageFilter.GaussianBlur(blur))
    return out.point(lambda v: round(min(_ALPHA_MAX, v * gain) * opacity))


def draw_halo(
    canvas: Image.Image, text: Image.Image, halo: Halo, *, em: float, ink: RGBA
) -> None:
    """Composite onto ``canvas`` the halo of the glyphs drawn on ``text`` (same size).

    Only the region the glyphs and their glow reach is filtered, so a caption
    on a 4K frame costs what the caption covers.
    """
    alpha = text.getchannel("A")
    ink_box = alpha.getbbox()
    if ink_box is None:
        return
    spread = max(0, round(halo.spread * em))
    blur = halo.blur * em
    reach = spread + math.ceil(_BLUR_REACH * blur)
    x0, y0 = max(0, ink_box[0] - reach), max(0, ink_box[1] - reach)
    x1 = min(canvas.width, ink_box[2] + reach)
    y1 = min(canvas.height, ink_box[3] + reach)
    shine = glow(
        alpha.crop((x0, y0, x1, y1)),
        spread=spread,
        blur=blur,
        gain=halo.gain,
        opacity=halo.opacity,
    )
    r, g, b, a = _halo_color(halo, ink)
    layer = Image.new("RGBA", shine.size, (r, g, b, 0))
    layer.putalpha(shine.point(lambda v: v * a // _ALPHA_MAX))
    canvas.alpha_composite(layer, (x0, y0))


def _faded(image: Image.Image, factor: float) -> Image.Image:
    """``image`` (RGBA) with its alpha scaled by ``factor``."""
    if factor >= 1:
        return image
    out = image.copy()
    out.putalpha(image.getchannel("A").point(lambda v: round(v * factor)))
    return out


def _halo_group(run: Run) -> tuple:
    """Runs glow together when they share a halo, a reveal and a type size."""
    return (run.halo, run.t_in, run.t_full, run.face.size)


def _draw_runs(
    canvas: Image.Image, runs: list[Run], engine: Engine, t: float | None
) -> None:
    for run in runs:
        f = _envelope(run, t)
        if f > 0:
            engine.draw_run(canvas, run, f)


# ----------------------------------------------------------------------------
# Entry points
# ----------------------------------------------------------------------------


def render_overlay(
    layout: Layout,
    size: tuple[int, int],
    *,
    t: float | None = None,
    engine: Engine | None = None,
) -> Image.Image:
    """The layout on a transparent canvas of ``size`` (RGBA)."""
    engine = engine or PillowEngine()
    for run in layout.runs:
        check_measured_by(run, engine)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    for plate in layout.plates:
        draw_plate(canvas, plate)
    # Consecutive runs sharing a halo, a reveal and a size glow together, under
    # their own text only. The group is drawn fully revealed, halo then text, and
    # faded as one: a halo built from half-faded glyphs saturates early and shows
    # the letters first as dark silhouettes.
    for (halo, *_), group in groupby(layout.runs, key=_halo_group):
        runs = list(group)
        if halo is None:
            _draw_runs(canvas, runs, engine, t)
            continue
        f = _envelope(runs[0], t)
        if f == 0:
            continue
        text = Image.new("RGBA", size, (0, 0, 0, 0))
        _draw_runs(text, runs, engine, None)
        group_layer = Image.new("RGBA", size, (0, 0, 0, 0))
        draw_halo(group_layer, text, halo, em=runs[0].face.size, ink=runs[0].color)
        group_layer.alpha_composite(text)
        box = group_layer.getbbox()
        if box is not None:
            canvas.alpha_composite(_faded(group_layer.crop(box), f), box[:2])
    return canvas


def render(
    layout: Layout,
    frame: Frame,
    *,
    t: float | None = None,
    engine: Engine | None = None,
) -> Image.Image:
    """Render onto the frame: RGBA overlay if it has no background, else RGB.

    ``engine`` is the rasteriser seam (default Pillow; see :mod:`tituli.shaping`).
    """
    overlay = render_overlay(layout, frame.size, t=t, engine=engine)
    if frame.image is not None:
        base = frame.image.convert("RGBA")
        base.alpha_composite(overlay)
        return base.convert("RGB")
    if frame.color is not None:
        base = Image.new("RGBA", frame.size, frame.color)
        base.alpha_composite(overlay)
        return base.convert("RGB")
    return overlay


def frames(
    layout: Layout,
    frame: Frame,
    *,
    duration: float,
    fps: float = 30.0,
    engine: Engine | None = None,
    hold_after: float = 0.0,
) -> Iterator[Image.Image]:
    """Yield one image per video frame, honouring the runs' reveal envelopes.

    ``duration`` is the whole clip; the last reveal completes at
    ``layout.duration_hint`` and the layout then holds. Frames are rendered
    lazily so a long clip never sits in memory at once.
    """
    n = int(round(duration * fps))
    for i in range(n):
        yield render(layout, frame, t=i / fps, engine=engine)


def make_engine(name: str = "pillow") -> Engine:
    """Resolve an engine by name: ``"pillow"`` (default) or ``"harfbuzz"``."""
    if name == PillowEngine.name:
        return PillowEngine()
    if name == "harfbuzz":
        from tituli.shaping import HarfBuzzEngine

        return HarfBuzzEngine()
    raise ValueError(f"unknown engine {name!r}; choose 'pillow' or 'harfbuzz'")
