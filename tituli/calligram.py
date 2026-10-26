"""Calligrams and concrete poems: text whose shape is part of the meaning.

Three treatments, all producing an ordinary :class:`~tituli.layout.Layout`:

* :func:`on_path` — glyphs ride a :class:`~tituli.geometry.Path` (any shape:
  circle, wave, Bézier, SVG ``d``), rotated to the tangent or kept upright;
* :func:`rain` — Apollinaire's *Il pleut*: upright letters stepping down
  fanning streaks (a preset of the same machinery, with the 1918 measurements
  as defaults);
* :func:`in_shape` — prose poured into a silhouette, the concrete-page case.

``shape=`` accepts a named preset, an SVG path string, or a
:class:`~tituli.geometry.Path`, so a caller can say ``"circle"`` and a
designer can hand over a traced outline — the same seam.

>>> from tituli.frame import Frame
>>> lay = on_path("round and round", shape="circle", frame=Frame.blank((800, 800)))
>>> len(lay.runs) == len("round and round".replace(" ", ""))
True
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Sequence

from tituli.frame import Frame
from tituli.geometry import Box, Path
from tituli.layout import Layout, along_path, fill_shape, glyph_columns
from tituli.style import CALLIGRAM, TextStyle

if TYPE_CHECKING:  # pragma: no cover
    from tituli.render import Engine

# Measured from the 1918 Mercure de France setting of "Il pleut".
IL_PLEUT_SLANTS: tuple[float, ...] = (0.186, 0.220, 0.257, 0.298, 0.353)
IL_PLEUT_HEAD_OFFSETS: tuple[float, ...] = (0.0, 7.0, 11.7, 16.4, 19.3)
IL_PLEUT_SIZE_RATIO = 0.86

_SHAPE_INSET = 0.12  # fraction of the safe box kept clear around a shape
_WAVE_AMPLITUDE = 0.12  # of the box height
_ARC_SWEEP = (200.0, 340.0)  # a gentle smile-shaped arc, degrees (screen coords)

ShapeSpec = "str | Path"


def resolve_shape(shape: "str | Path", box: Box) -> Path:
    """Turn a name, an SVG ``d`` string or a Path into a Path fitted to ``box``.

    Names: ``"line"``, ``"circle"``, ``"arc"``, ``"wave"``, ``"diagonal"``,
    ``"s-curve"``. Anything starting with ``M``/``m`` is parsed as SVG.
    """
    if isinstance(shape, Path):
        return shape.fit(box)
    name = shape.strip()
    if name[:1] in "Mm" and any(c.isdigit() for c in name):
        return Path.from_svg(name).fit(box)
    cx, cy = box.center
    r = min(box.width, box.height) / 2
    if name == "line":
        return Path.line((box.x0, cy), (box.x1, cy))
    if name == "circle":
        return Path.circle((cx, cy), r)
    if name == "arc":
        return Path.arc((cx, cy + r * 0.6), r * 1.1, *_ARC_SWEEP).fit(box)
    if name == "wave":
        return Path.wave(
            (box.x0, cy),
            (box.x1, cy),
            amplitude=box.height * _WAVE_AMPLITUDE,
            cycles=1.0,
        )
    if name == "diagonal":
        return Path.line((box.x0, box.y0), (box.x1, box.y1))
    if name == "s-curve":
        return Path.bezier(
            (box.x0, box.y1),
            (box.x0 + box.width * 0.9, box.y0 + box.height * 0.9),
            (box.x1 - box.width * 0.9, box.y0 + box.height * 0.1),
            (box.x1, box.y0),
        )
    raise ValueError(
        f"unknown shape {shape!r}; use a preset name, an SVG path string, or a Path"
    )


def on_path(
    text: str,
    *,
    shape: "str | Path" = "wave",
    frame: Frame,
    style: TextStyle = CALLIGRAM,
    box: Box | None = None,
    upright: bool = False,
    align: Literal["start", "center", "end"] = "center",
    fit_text: bool = True,
    engine: "Engine | None" = None,
) -> Layout:
    """Set ``text`` along a shape inside ``box`` (default: the safe area, inset).

    With ``fit_text`` the type is shrunk until the whole string fits the path
    length (never clipped); the resulting size is in ``meta["size"]``.
    """
    box = box or frame.safe.inset(
        frame.safe.width * _SHAPE_INSET, frame.safe.height * _SHAPE_INSET
    )
    path = resolve_shape(shape, box)
    st = style
    lay = along_path(text, path, st, frame, upright=upright, align=align, engine=engine)
    while fit_text and lay.meta.get("overflow", 0) > 0 and st.size > 0.008:
        st = st.with_(size=st.size * 0.92)
        lay = along_path(
            text, path, st, frame, upright=upright, align=align, engine=engine
        )
    return Layout(
        lay.runs, lay.plates, {**lay.meta, "size": st.size, "path_length": path.length}
    )


def rain(
    lines: Sequence[str] | str,
    *,
    frame: Frame,
    style: TextStyle = CALLIGRAM,
    box: Box | None = None,
    slants: Sequence[float] = IL_PLEUT_SLANTS,
    head_offsets: Sequence[float] = IL_PLEUT_HEAD_OFFSETS,
    size_ratio: float = IL_PLEUT_SIZE_RATIO,
    engine: "Engine | None" = None,
) -> Layout:
    """*Il pleut*: each line a streak of upright letters falling across the frame.

    Wants a portrait frame. ``slants`` (dx per step down) and ``head_offsets``
    (where each streak starts, in slot units) are shape parameters, not
    coordinates — the defaults are Apollinaire's.
    """
    if isinstance(lines, str):
        lines = [l for l in lines.split("\n") if l.strip()]
    box = box or frame.safe
    return glyph_columns(
        list(lines),
        style,
        frame,
        box=box,
        slants=slants,
        head_offsets=head_offsets,
        size_ratio=size_ratio,
        engine=engine,
    )


def in_shape(
    text: str,
    mask,
    *,
    frame: Frame,
    style: TextStyle = CALLIGRAM,
    box: Box | None = None,
    repeat: bool = True,
    engine: "Engine | None" = None,
) -> Layout:
    """Pour prose into a silhouette (light = inside). See :func:`tituli.layout.fill_shape`."""
    box = box or frame.safe
    return fill_shape(text, mask, style, frame, box=box, repeat=repeat, engine=engine)


__all__ = [
    "on_path",
    "rain",
    "in_shape",
    "resolve_shape",
    "IL_PLEUT_SLANTS",
    "IL_PLEUT_HEAD_OFFSETS",
]
