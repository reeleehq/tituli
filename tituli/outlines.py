"""Glyph outlines as SVG path data — the vector form of a placed :class:`Run`.

A :class:`~tituli.layout.Layout` says *where* each run goes; this module says
*what it looks like as geometry*: the font's own contours, scaled to the run's
face size, advanced along the run exactly as :meth:`Face.length` measures it,
rotated by the run's angle and translated to its baseline origin. The result is
an SVG ``d`` string in frame pixels (y down), so a caller can draw text with no
font engine at all — an animation runtime that only knows how to draw SVG, for
instance (thorwhalen/an#155: *glyphs as SVG sprites, converted at compile
time*).

>>> from tituli.fonts import EMBEDDED, resolve_face
>>> from tituli.layout import Run
>>> run = Run("Hi", 10.0, 50.0, resolve_face(EMBEDDED, size=40), (0, 0, 0, 255))
>>> out = run_outline(run)
>>> out.d.startswith("M")
True
>>> out.bbox.y1 <= 50.0 + 1 and out.bbox.y0 < 50.0   # ink sits on the baseline
True

Missing glyphs **raise** rather than drawing a box or nothing: a string the
face cannot set is the caller's decision (another face, other words), never a
silent substitution.

>>> run_outline(Run("é", 0, 0, resolve_face(EMBEDDED, size=40), (0, 0, 0, 255)))
Traceback (most recent call last):
...
tituli.outlines.MissingGlyphError: 'Aileron' Regular has no glyph for 'é' (U+00E9)

Needs ``fontTools`` (``pip install tituli[outlines]``); imported lazily, so the
rest of the package never pays for it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tituli.fonts import glyph_set, ttfont
from tituli.geometry import Box
from tituli.layout import Run, text_advance

if TYPE_CHECKING:  # pragma: no cover
    from tituli.render import Engine

#: Decimal places kept in the path data. Two is a hundredth of a pixel —
#: invisible, and it keeps the string short and byte-stable.
DFLT_PRECISION = 2
_ADVANCE_TOL_PX = 0.5  # engine-vs-face width gaps below this are rounding


class MissingGlyphError(ValueError):
    """The run's face has no glyph for one of its characters."""


@dataclass(frozen=True)
class Outline:
    """A run's contours as SVG path data, in frame pixels.

    ``bbox`` is the ink's bounds (``None`` when nothing is inked, e.g. a space).
    """

    d: str
    bbox: Box | None


def _require():
    try:
        import fontTools  # noqa: F401
    except ImportError as e:  # pragma: no cover - depends on the extra
        raise ImportError(
            "glyph outlines need fontTools: `pip install tituli[outlines]`"
        ) from e


def _number_formatter(precision: int):
    def ntos(v: float) -> str:
        s = f"{v:.{precision}f}".rstrip("0").rstrip(".")
        return "0" if s in ("", "-0") else s

    return ntos


def _glyph_names(face, text: str, font) -> list:
    """The glyph each character draws: the cmap's, or with the face's applied
    OpenType features the substituted one (the glyph its length measured)."""
    if face.applied_features:
        from tituli.features import featured_glyphs

        return featured_glyphs(face, text)
    cmap = font.getBestCmap() or {}
    return [cmap.get(ord(ch)) for ch in text]


def _check_measured_by(run: Run, engine: "Engine | None") -> None:
    """Raise if ``run.advance`` came from an engine whose glyph pitch we would not use."""
    if engine is not None or run.advance is None:
        return
    by_face = run.face.length(run.text) + run.tracking * max(0, len(run.text) - 1)
    if abs(run.advance - by_face) > _ADVANCE_TOL_PX:
        raise ValueError(
            f"run {run.text!r} was measured by an engine (advance {run.advance:.2f}px "
            f"vs {by_face:.2f}px by the face); pass that engine as "
            "run_outline(engine=...) so glyphs sit where it drew them"
        )


def run_outline(
    run: Run, *, precision: int = DFLT_PRECISION, engine: "Engine | None" = None
) -> Outline:
    """The contours of ``run`` as one SVG path, placed where the run is drawn.

    Glyph ``i`` starts at ``face.length(text[:i]) + i * tracking`` along the
    baseline — the same advances the layout measured with, kerning included,
    so the outline and the layout cannot disagree about where a glyph is.
    ``engine`` is the one the layout was measured with (default: the face). A
    run that carries an ``advance`` from another engine's measure is refused
    when ``engine`` is not given, rather than outlined with the face's advances.
    """
    _require()
    _check_measured_by(run, engine)
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen

    face = run.face
    font = ttfont(face.path, face.index)
    glyphs = glyph_set(face)  # at the face's variation instance
    names = _glyph_names(face, run.text, font)
    scale = face.size / font["head"].unitsPerEm
    a = math.radians(run.angle)
    cos, sin = math.cos(a), math.sin(a)

    recording = DecomposingRecordingPen(glyphs)
    for i, (ch, name) in enumerate(zip(run.text, names)):
        if name is None:
            raise MissingGlyphError(
                f"{face.family!r} {face.style} has no glyph for {ch!r} "
                f"(U+{ord(ch):04X})"
            )
        pen_x = text_advance(engine, face, run.text[:i]) + run.tracking * i
        # Font units are y-up; the frame is y-down and the run is rotated
        # clockwise on screen by `angle` about its baseline origin.
        transform = (
            cos * scale,
            sin * scale,
            sin * scale,
            -cos * scale,
            run.x + cos * pen_x,
            run.y + sin * pen_x,
        )
        glyphs[name].draw(TransformPen(recording, transform))

    svg = SVGPathPen(None, ntos=_number_formatter(precision))
    bounds = BoundsPen(None)
    recording.replay(svg)
    recording.replay(bounds)
    bbox = Box(*bounds.bounds) if bounds.bounds else None
    return Outline(svg.getCommands(), bbox)


__all__ = ["DFLT_PRECISION", "MissingGlyphError", "Outline", "run_outline"]
