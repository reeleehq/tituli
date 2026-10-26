"""The layout model: placed runs of text, and the engines that place them.

A :class:`Layout` is the single intermediate every use case produces and the
renderer consumes — a title card, a credits crawl and a calligram are all just
different ways of filling one. A :class:`Run` is the unit: a string, a baseline
origin in frame pixels, an angle, a resolved face and a colour. A block of prose
is a few runs (one per line); a calligram is one run per glyph. That is the whole
unification — the humble cases are the degenerate calligram, exactly as hoped.

Real font metrics throughout (``Face.length``), never an average-character
estimate.

>>> from tituli.frame import Frame
>>> from tituli.style import TextStyle
>>> lay = block("Hello\\nWorld", TextStyle(size=0.05), Frame.blank((1920, 1080)))
>>> len(lay.runs)                      # one run per line (a tracked style would give one per glyph)
2
>>> lay.bbox().width > 0
True
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Iterable, Literal, Sequence

from tituli import fonts
from tituli.color import RGBA, parse_color, with_alpha
from tituli.frame import Frame
from tituli.geometry import Box, Path
from tituli.style import TextStyle

if TYPE_CHECKING:  # pragma: no cover
    from tituli.render import Engine

Unit = Literal["line", "word", "glyph"]
PlateKind = Literal[
    "box",
    "gradient-bottom",
    "gradient-top",
    "corner-top-left",
    "corner-top-right",
    "corner-bottom-left",
    "corner-bottom-right",
]

_WORD_SEP = " "
# Breaking spaces only: the no-break spaces (U+00A0, U+2007, U+202F) are not in this set.
_BREAKING_SPACE = re.compile(r"[ \t\r\f\v\u2000-\u200b\u3000]+")


@dataclass(frozen=True)
class Run:
    """A string drawn from a baseline origin, possibly rotated."""

    text: str
    x: float
    y: float
    face: fonts.Face
    color: RGBA
    angle: float = 0.0  # degrees, clockwise on screen (y points down)
    opacity: float = 1.0
    tracking: float = 0.0  # extra px per glyph (only meaningful for glyph runs)
    unit: Unit = "line"
    index: int = 0
    t_in: float | None = None  # seconds; None = always visible
    t_full: float | None = None
    tags: tuple[str, ...] = ()
    #: Width the drawing engine measured for this run (tituli#7); ``None`` means
    #: measure with the face (Pillow), which is what a hand-built run does.
    #: Valid only for the ``text`` and ``face`` it was measured with: build a
    #: run by hand, or drop it (``replace(run, advance=None)``) after changing either.
    advance: float | None = None
    #: Name of the engine that measured ``advance`` (``None``: unrecorded);
    #: :func:`check_measured_by` refuses a run used with another engine.
    #: Cleared whenever ``advance`` is ``None``.
    measured_by: str | None = None

    def __post_init__(self) -> None:
        if self.advance is None and self.measured_by is not None:
            # ``replace(run, advance=None)`` drops the width, and with it the claim.
            object.__setattr__(self, "measured_by", None)

    @property
    def width(self) -> float:
        if self.advance is not None:
            return self.advance
        return self.face.length(self.text) + self.tracking * max(0, len(self.text) - 1)

    def bbox(self) -> Box:
        """Axis-aligned bounds (ignores rotation — fine for placement)."""
        return Box(
            self.x,
            self.y - self.face.ascent,
            self.x + self.width,
            self.y + self.face.descent,
        )

    def translated(self, dx: float, dy: float) -> "Run":
        return replace(self, x=self.x + dx, y=self.y + dy)


@dataclass(frozen=True)
class Plate:
    """A backdrop drawn under the runs: a scrim, a box, a rule."""

    box: Box
    color: RGBA
    kind: PlateKind = "box"
    radius: float = 0.0
    # For gradient/corner kinds: fraction of the box (x, y) held at full
    # strength before the falloff starts, measured from the strong edge.
    solid: tuple[float, float] = (0.5, 0.5)

    def translated(self, dx: float, dy: float) -> "Plate":
        return replace(self, box=self.box.translate(dx, dy))


@dataclass(frozen=True)
class Layout:
    """Everything the renderer needs: runs on top of plates, in frame pixels."""

    runs: tuple[Run, ...] = ()
    plates: tuple[Plate, ...] = ()
    meta: dict = field(default_factory=dict, compare=False)

    def bbox(self) -> Box:
        """Bounds of the runs (plates excluded)."""
        boxes = [r.bbox() for r in self.runs]
        if not boxes:
            return Box(0, 0, 0, 0)
        out = boxes[0]
        for b in boxes[1:]:
            out = out.union(b)
        return out

    def translated(self, dx: float, dy: float) -> "Layout":
        return Layout(
            tuple(r.translated(dx, dy) for r in self.runs),
            tuple(p.translated(dx, dy) for p in self.plates),
            dict(self.meta),
        )

    def moved_to(self, box: Box) -> "Layout":
        """Translate so the runs' bbox top-left lands on ``box``'s top-left."""
        bb = self.bbox()
        return self.translated(box.x0 - bb.x0, box.y0 - bb.y0)

    def __add__(self, other: "Layout") -> "Layout":
        return Layout(
            self.runs + other.runs,
            self.plates + other.plates,
            {**self.meta, **other.meta},
        )

    def with_plates(self, *plates: Plate) -> "Layout":
        return Layout(self.runs, self.plates + tuple(plates), dict(self.meta))

    def with_timing(self, t_in: float, t_full: float) -> "Layout":
        """Give every run the same reveal envelope."""
        return replace(
            self, runs=tuple(replace(r, t_in=t_in, t_full=t_full) for r in self.runs)
        )

    def staggered(self, *, start: float = 0.0, step: float, ramp: float) -> "Layout":
        """Reveal runs one after another: run ``i`` starts at ``start + i*step``."""
        runs = tuple(
            replace(r, t_in=start + i * step, t_full=start + i * step + ramp)
            for i, r in enumerate(self.runs)
        )
        return replace(self, runs=runs)

    def recolored(self, color: RGBA) -> "Layout":
        return replace(self, runs=tuple(replace(r, color=color) for r in self.runs))

    @property
    def duration_hint(self) -> float:
        """Latest ``t_full`` among the runs (0 when untimed)."""
        return max((r.t_full or 0.0) for r in self.runs) if self.runs else 0.0


# ----------------------------------------------------------------------------
# Measuring and wrapping
# ----------------------------------------------------------------------------


def _tracking_px(style: TextStyle, face: fonts.Face) -> float:
    return style.tracking * face.size


def text_advance(
    engine: "Engine | None", face: fonts.Face, text: str, *, per_glyph: bool = False
) -> float:
    """Advance of ``text``: the engine that will draw it measures it (tituli#7);
    with no engine, the face does (what :class:`~tituli.render.PillowEngine` does).

    ``per_glyph`` sums the characters one by one — how a glyph-by-glyph layout
    (``unit="glyph"``, a tracked style) places them, so the line measures what
    its glyphs occupy even for an engine that kerns across characters.
    """
    if per_glyph:
        return sum(text_advance(engine, face, ch) for ch in text)
    if engine is None:
        return face.length(text)
    try:
        measure_text = engine.length
    except AttributeError:
        raise TypeError(
            f"{type(engine).__name__} cannot measure text: an engine needs "
            "length(face, text) as well as draw_run (see tituli.render.Engine)"
        ) from None
    return measure_text(face, text)


#: What :func:`engine_name` answers for "no engine": the face measures, as Pillow does.
FACE_ENGINE = "pillow"


def engine_name(engine: "Engine | None") -> str:
    """Who measured: the engine's ``name`` (else its class name); ``None`` is the face."""
    if engine is None:
        return FACE_ENGINE
    return getattr(engine, "name", None) or type(engine).__name__


def _keep(engine: "Engine | None", width: float) -> dict:
    """The ``Run`` fields recording a width an engine measured (none without one)."""
    if engine is None:
        return {}
    return {"advance": width, "measured_by": engine_name(engine)}


def _advance(engine: "Engine | None", face: fonts.Face, text: str) -> dict:
    """:func:`_keep` for ``text`` (measures only when an engine will)."""
    return {} if engine is None else _keep(engine, text_advance(engine, face, text))


def check_measured_by(run: "Run", engine: "Engine | None") -> None:
    """Raise if ``run`` was measured by a different engine than the one in hand.

    Runs that record no ``measured_by`` (hand-built, or laid out without an
    engine) are not checked: they carry no claim. A recorded one is refused
    both ways, by the face (``engine=None``) and by another engine, since each
    would place glyphs where the measuring engine did not draw them (tituli#15).
    """
    if run.measured_by is None:
        return
    measured, using = run.measured_by, engine_name(engine)
    if measured != using:
        raise ValueError(
            f"run {run.text!r} was measured by the {measured!r} engine but is being "
            f"used with the {using!r} one; pass the engine that measured it, or "
            "lay the text out again with the one you will draw with"
        )


def measure(
    text: str,
    style: TextStyle,
    frame_height: float,
    *,
    engine: "Engine | None" = None,
) -> float:
    """Width in pixels of ``text`` set in ``style`` on a frame of that height.

    ``engine`` is the one that will draw it (default: measure with the face, as
    Pillow draws); a page measured by one engine and drawn by another can have
    wrong wrap points and column pitch.
    """
    face = style.face(frame_height)
    text = style.apply_case(text)
    return text_advance(
        engine, face, text, per_glyph=style.tracking != 0
    ) + _tracking_px(style, face) * max(0, len(text) - 1)


def _words(text: str) -> list[str]:
    """Split on breaking spaces only: a no-break space (U+00A0) binds its words.

    (``str.split()`` treats U+00A0 as whitespace, which silently undid the one
    tool a caller had to keep a pair together.)

    >>> _words("バス\u00a0bus  soup")
    ['バス\xa0bus', 'soup']
    """
    return [w for w in _BREAKING_SPACE.split(text) if w]


def _break_atoms(para: str, break_at: str | None) -> tuple[list[str], str]:
    """The unbreakable atoms of a paragraph, and the string that rejoins them.

    With ``break_at=" · "`` the paragraph ``"a 1 · b 2"`` gives atoms
    ``["a 1 ·", "b 2"]`` joined by ``" "``: the separator's visible part stays
    at the end of the line it closes, and nothing breaks inside an item.

    >>> _break_atoms("a 1 · b 2", " · ")
    (['a 1 ·', 'b 2'], ' ')
    >>> _break_atoms("カ、ス、ン", "、")         # no space in the separator, none added
    (['カ、', 'ス、', 'ン'], '')
    >>> _break_atoms(" · a ·  · b", " · ")      # empty items keep their marks
    (['·', 'a ·', '·', 'b'], ' ')
    >>> _break_atoms("a b", None)
    (['a', 'b'], ' ')
    """
    if not break_at:
        return _words(para), _WORD_SEP
    mark = break_at.strip()
    if not mark:
        raise ValueError(
            f"break_at={break_at!r} is only whitespace; a list separator needs a "
            "visible mark (' · ', ', ', '、')"
        )
    lead = break_at[: break_at.index(mark)]
    joiner = break_at[break_at.index(mark) + len(mark) :]
    chunks = [" ".join(_words(c)) for c in para.split(break_at)]
    if chunks and not chunks[-1]:
        chunks.pop()  # a trailing separator: its mark closes the item before it
    atoms = [
        (f"{c}{lead}{mark}" if c else mark) if i < len(chunks) - 1 else c
        for i, c in enumerate(chunks)
    ]
    return atoms, joiner


def wrap(
    text: str,
    style: TextStyle,
    frame_height: float,
    *,
    max_width: float,
    break_at: str | None = None,
    engine: "Engine | None" = None,
) -> list[str]:
    """Greedy word wrap on measured widths. Explicit newlines are honoured.

    ``break_at`` makes a list wrap only *between* its items: with ``" · "``,
    ``"バス bus · スープ soup"`` never ends a line on ``バス``. An item wider
    than the whole line falls back to word wrapping inside that item (it is
    never cut). A no-break space (U+00A0) binds two words in any mode.

    >>> from tituli.style import CAPTION
    >>> lines = wrap("one two three four five six", CAPTION, 1080, max_width=300)
    >>> len(lines) >= 2 and all(measure(l, CAPTION, 1080) <= 300 for l in lines)
    True
    """

    def fits(s: str) -> bool:
        return measure(s, style, frame_height, engine=engine) <= max_width

    mark = break_at.strip() if break_at else ""

    def greedy(atoms: list[str], joiner: str, *, split_wide: bool) -> list[str]:
        lines: list[str] = []
        line = ""
        for atom in atoms:
            words = _words(atom)
            if split_wide and len(words) > 1 and not fits(atom):
                # an item too wide for any line: word-wrap inside it (once —
                # a single word wider than the line takes a line of its own)
                if line:
                    lines.append(line)
                if words[-1] == mark:  # keep the separator with the word it follows
                    words[-2:] = [f"{words[-2]} {mark}"]
                inner = greedy(words, _WORD_SEP, split_wide=False)
                lines.extend(inner[:-1])
                line = inner[-1]
                continue
            trial = f"{line}{joiner}{atom}" if line else atom
            if not line or fits(trial):
                line = trial
            else:
                lines.append(line)
                line = atom
        if line:
            lines.append(line)
        return lines

    out: list[str] = []
    for para in text.split("\n"):
        atoms, joiner = _break_atoms(para, break_at)
        out.extend(greedy(atoms, joiner, split_wide=bool(break_at)) if atoms else [""])
    return out


def fit_size(
    text: str,
    style: TextStyle,
    frame_height: float,
    *,
    max_width: float,
    max_height: float | None = None,
    min_size: float = 0.012,
    step: float = 0.9,
    break_at: str | None = None,
    engine: "Engine | None" = None,
) -> TextStyle:
    """Shrink ``style.size`` until ``text`` wraps within the given bounds.

    Shrinks geometrically by ``step`` and never below ``min_size`` (a fraction
    of frame height, like ``size`` itself).
    """
    s = style
    while s.size > min_size:
        lines = wrap(
            text,
            s,
            frame_height,
            max_width=max_width,
            break_at=break_at,
            engine=engine,
        )
        widest = max(
            (measure(l, s, frame_height, engine=engine) for l in lines), default=0
        )
        face = s.face(frame_height)
        height = len(lines) * face.size * s.leading
        if widest <= max_width and (max_height is None or height <= max_height):
            return s
        s = s.with_(size=s.size * step)
    return s


# ----------------------------------------------------------------------------
# Engines
# ----------------------------------------------------------------------------


def _glyph_runs(
    text: str,
    x: float,
    y: float,
    face: fonts.Face,
    color: RGBA,
    *,
    tracking: float,
    opacity: float,
    tags: tuple[str, ...],
    start_index: int = 0,
    engine: "Engine | None" = None,
) -> list[Run]:
    """One run per glyph with tracking applied to the advances."""
    runs: list[Run] = []
    cx = x
    for i, ch in enumerate(text):
        advance = text_advance(engine, face, ch)
        runs.append(
            Run(
                ch,
                cx,
                y,
                face,
                color,
                opacity=opacity,
                unit="glyph",
                index=start_index + i,
                tags=tags,
                **_keep(engine, advance),
            )
        )
        cx += advance + tracking
    return runs


def block(
    text: str | Sequence[str],
    style: TextStyle,
    frame: Frame | float,
    *,
    max_width: float | None = None,
    x: float = 0.0,
    y: float = 0.0,
    color: RGBA | None = None,
    unit: Unit = "line",
    tags: tuple[str, ...] = (),
    break_at: str | None = None,
    engine: "Engine | None" = None,
) -> Layout:
    """Lay out prose as lines from the top-left corner ``(x, y)``.

    ``text`` is a string (wrapped to ``max_width`` when given) or pre-broken
    lines. Alignment follows ``style.align`` within ``max_width`` (or the widest
    line when no width is given). ``unit="glyph"`` emits one run per character
    (needed for tracking and for per-glyph reveals). ``break_at`` (e.g.
    ``" · "``) wraps a list only between its items — see :func:`wrap`. ``engine``
    is the one that will draw the layout: it measures the lines, and the runs
    keep that width, so a page composed from this block (``stack``, ``grid``)
    is placed by the engine's measure too.
    """
    fh = frame.height if isinstance(frame, Frame) else float(frame)
    face = style.face(fh)
    rgba = with_alpha(
        parse_color(color if color is not None else style.color), style.opacity
    )
    if isinstance(text, str):
        lines = (
            wrap(text, style, fh, max_width=max_width, break_at=break_at, engine=engine)
            if max_width
            else text.split("\n")
        )
    else:
        lines = list(text)
    lines = [style.apply_case(l) for l in lines]
    tracking = _tracking_px(style, face)
    per_glyph = unit == "glyph" or tracking != 0
    widths = [
        text_advance(engine, face, l, per_glyph=per_glyph)
        + tracking * max(0, len(l) - 1)
        for l in lines
    ]
    box_w = max_width if max_width else (max(widths) if widths else 0.0)
    line_h = face.size * style.leading
    runs: list[Run] = []
    baseline = y + face.ascent + (line_h - face.line_height) / 2
    idx = 0
    for i, (line, w) in enumerate(zip(lines, widths)):
        if style.align == "center":
            lx = x + (box_w - w) / 2
        elif style.align == "right":
            lx = x + box_w - w
        else:
            lx = x
        if not line:
            baseline += line_h
            continue
        if per_glyph:
            gr = _glyph_runs(
                line,
                lx,
                baseline,
                face,
                rgba,
                tracking=tracking,
                opacity=1.0,
                tags=tags,
                start_index=idx,
                engine=engine,
            )
            runs.extend(gr)
            idx += len(gr)
        elif unit == "word":
            cx = lx
            for word in line.split(_WORD_SEP):
                runs.append(
                    Run(
                        word,
                        cx,
                        baseline,
                        face,
                        rgba,
                        unit="word",
                        index=idx,
                        tags=tags,
                        **_advance(engine, face, word),
                    )
                )
                cx += text_advance(engine, face, word + _WORD_SEP)
                idx += 1
        else:
            runs.append(
                Run(
                    line,
                    lx,
                    baseline,
                    face,
                    rgba,
                    unit="line",
                    index=i,
                    tags=tags,
                    **_advance(engine, face, line),
                )
            )
        baseline += line_h
    return Layout(tuple(runs), meta={"line_height": line_h, "block_width": box_w})


def along_path(
    text: str,
    path: Path,
    style: TextStyle,
    frame: Frame | float,
    *,
    start: float = 0.0,
    align: Literal["start", "center", "end"] = "start",
    offset: float = 0.0,
    upright: bool = False,
    color: RGBA | None = None,
    tags: tuple[str, ...] = (),
    engine: "Engine | None" = None,
) -> Layout:
    """Set ``text`` glyph by glyph along ``path`` (the path is the baseline).

    Each glyph's origin is the point at its arc length and it is rotated to the
    tangent there — unless ``upright`` (a calligram convention: letters stay
    vertical while their *positions* follow the shape). ``offset`` shifts the
    baseline perpendicular to the path (negative = above, in screen terms).
    ``align`` positions the whole string on the path from ``start``.

    Text longer than the path keeps its spacing and runs off the end — that is
    reported in ``meta["overflow"]`` rather than silently squeezed. ``engine`` is
    the one that will draw it; it measures the glyph advances.
    """
    fh = frame.height if isinstance(frame, Frame) else float(frame)
    face = style.face(fh)
    rgba = with_alpha(
        parse_color(color if color is not None else style.color), style.opacity
    )
    text = style.apply_case(text)
    tracking = _tracking_px(style, face)
    widths = [text_advance(engine, face, ch) for ch in text]
    advances = [w + tracking for w in widths]
    total = sum(advances) - (tracking if advances else 0)
    if align == "center":
        s = start + (path.length - start - total) / 2
    elif align == "end":
        s = path.length - total
    else:
        s = start
    closed = path.closed
    if closed and align == "center":
        # centre the string on the path's start point (the top of a circle)
        s = start - total / 2
    elif not closed:
        s = max(s, 0.0) if align != "start" else s
    runs: list[Run] = []
    import math

    def at(u: float) -> float:
        return u % path.length if closed else u

    for i, (ch, adv) in enumerate(zip(text, advances)):
        glyph_w = adv - tracking
        mid = at(s + glyph_w / 2)
        ang = 0.0 if upright else path.angle(mid)
        # Anchor each glyph by its centre on the tangent at its midpoint, then
        # step back half an advance to find the baseline origin: glyphs on the
        # inside of a bend stop piling into each other.
        cx, cy = path.point(mid)
        a = math.radians(path.angle(mid))
        px = cx - math.cos(a) * glyph_w / 2
        py = cy - math.sin(a) * glyph_w / 2
        if upright:
            px, py = cx - glyph_w / 2, cy
        if offset:
            px += -math.sin(a) * offset
            py += math.cos(a) * offset
        if ch != _WORD_SEP:
            runs.append(
                Run(
                    ch,
                    px,
                    py,
                    face,
                    rgba,
                    angle=ang,
                    unit="glyph",
                    index=i,
                    tags=tags,
                    **_keep(engine, widths[i]),
                )
            )
        s += adv
    overflow = 0.0 if closed else max(0.0, s - tracking - path.length)
    if closed and total > path.length:
        overflow = total - path.length
    return Layout(tuple(runs), meta={"overflow": overflow})


def glyph_columns(
    lines: Sequence[str],
    style: TextStyle,
    frame: Frame | float,
    *,
    box: Box,
    slants: Sequence[float],
    head_offsets: Sequence[float],
    word_gap_slots: int = 1,
    size_ratio: float = 0.86,
    color: RGBA | None = None,
    tags: tuple[str, ...] = (),
    engine: "Engine | None" = None,
) -> Layout:
    """Upright glyphs stepping down slanted streaks — Apollinaire's *Il pleut*.

    Line ``k`` becomes a streak: glyph ``i`` sits at ``(u, v) = (head_offsets[k]
    + i * slants[k], i)`` on an abstract slot grid, fitted to ``box`` in one
    step, so the shape is aspect-independent. Letters stay upright. This is the
    solver muvid's ``calligram`` archetype introduced, generalised over real
    glyph metrics and any frame — the streaks are :class:`Path` lines, which is
    how it stays one preset of :func:`along_path` rather than a second family.

    ``slants`` and ``head_offsets`` are cycled if shorter than ``lines``.
    ``engine`` is the one that will draw it; it centres each glyph in its slot.
    """
    if not lines:
        return Layout()
    fh = frame.height if isinstance(frame, Frame) else float(frame)
    n = len(lines)
    slants = [slants[k % len(slants)] for k in range(n)]
    heads = [head_offsets[k % len(head_offsets)] for k in range(n)]
    slots: list[list[tuple[float, float, str]]] = []
    for k, line in enumerate(lines):
        line = style.apply_case(line)
        col: list[tuple[float, float, str]] = []
        i = 0
        for word_i, word in enumerate(line.split()):
            if word_i:
                i += word_gap_slots
            for ch in word:
                col.append((heads[k] + i * slants[k], float(i), ch))
                i += 1
        slots.append(col)
    us = [u for col in slots for u, _, _ in col]
    vs = [v for col in slots for _, v, _ in col]
    u_span = (max(us) - min(us)) if us else 1.0
    v_span = (max(vs) - min(vs)) if vs else 1.0
    pitch = min(box.height / max(v_span + 1, 1), box.width / max(u_span + 1, 1))
    px_size = max(8, round(pitch * size_ratio))
    sized = style.with_(size=px_size / fh)
    face = sized.face(fh)
    rgba = with_alpha(
        parse_color(color if color is not None else style.color), style.opacity
    )
    u0, v0 = (min(us) if us else 0.0), (min(vs) if vs else 0.0)
    runs: list[Run] = []
    idx = 0
    for k, col in enumerate(slots):
        for u, v, ch in col:
            adv = text_advance(engine, face, ch)
            x = box.x0 + (u - u0) * pitch + (pitch - adv) / 2
            y = box.y0 + (v - v0) * pitch + face.ascent
            runs.append(
                Run(
                    ch,
                    x,
                    y,
                    face,
                    rgba,
                    unit="glyph",
                    index=idx,
                    tags=tags + (f"streak:{k}",),
                    **_keep(engine, adv),
                )
            )
            idx += 1
    return Layout(tuple(runs), meta={"pitch": pitch, "streaks": n})


def fill_shape(
    text: str,
    mask: "PILImageLike",
    style: TextStyle,
    frame: Frame | float,
    *,
    box: Box,
    threshold: int = 128,
    min_span: float = 0.5,
    color: RGBA | None = None,
    tags: tuple[str, ...] = (),
    repeat: bool = True,
    engine: "Engine | None" = None,
) -> Layout:
    """Pour prose into a silhouette, row by row — the concrete-poem 'shape' case.

    ``mask`` is any Pillow image (or path): dark pixels are *outside*, light
    pixels are the shape (invert your mask if it is the other way round). It is
    fitted into ``box``; for each line of text height the horizontal spans of
    the shape are found and filled with as many words as fit, in reading order.
    With ``repeat`` the text cycles until the shape is full; otherwise leftover
    spans stay empty and leftover words are reported in ``meta["unplaced"]``. ``engine`` is the one
    that will draw it; it measures the words.
    """
    from PIL import Image

    fh = frame.height if isinstance(frame, Frame) else float(frame)
    face = style.face(fh)
    rgba = with_alpha(
        parse_color(color if color is not None else style.color), style.opacity
    )
    words = style.apply_case(text).split()
    if not words:
        return Layout()
    m = mask if isinstance(mask, Image.Image) else Image.open(mask)
    m = m.convert("L").resize((max(1, int(box.width)), max(1, int(box.height))))
    data = m.tobytes()
    W, H = m.size
    line_h = face.size * style.leading
    space = text_advance(engine, face, _WORD_SEP)
    min_px = face.size * min_span

    # Each word is measured once per call, not once per row and repeat cycle.
    @functools.cache
    def advance_of(word: str) -> float:
        return text_advance(engine, face, word)

    runs: list[Run] = []
    wi = 0
    idx = 0
    y = 0.0
    while y + line_h <= H:
        row = int(y + line_h / 2)
        offset = row * W
        # find spans of "inside" pixels on the row through the line's middle
        spans: list[tuple[int, int]] = []
        x = 0
        while x < W:
            if data[offset + x] >= threshold:
                x0 = x
                while x < W and data[offset + x] >= threshold:
                    x += 1
                spans.append((x0, x))
            else:
                x += 1
        for x0, x1 in spans:
            avail = x1 - x0
            if avail < min_px:
                continue
            # collect words that fit
            chunk: list[str] = []
            used = 0.0
            probe = wi
            while True:
                if probe >= len(words):
                    if not repeat:
                        break
                    probe = 0
                w = words[probe]
                ww = advance_of(w)
                add = ww if not chunk else space + ww
                if used + add > avail:
                    break
                chunk.append(w)
                used += add
                probe += 1
                if not repeat and probe >= len(words):
                    break
            if not chunk:
                continue
            wi = probe % len(words) if repeat else probe
            # justify-ish: centre the chunk in the span
            cx = box.x0 + x0 + (avail - used) / 2
            baseline = box.y0 + y + face.ascent + (line_h - face.line_height) / 2
            for w in chunk:
                adv = advance_of(w)
                runs.append(
                    Run(
                        w,
                        cx,
                        baseline,
                        face,
                        rgba,
                        unit="word",
                        index=idx,
                        tags=tags,
                        **_keep(engine, adv),
                    )
                )
                cx += adv + space
                idx += 1
            if not repeat and wi >= len(words):
                break
        if not repeat and wi >= len(words):
            break
        y += line_h
    unplaced = [] if repeat else words[wi:]
    return Layout(tuple(runs), meta={"unplaced": unplaced})


PILImageLike = "Image.Image | str"


def merge(layouts: Iterable[Layout]) -> Layout:
    """Concatenate layouts."""
    out = Layout()
    for lay in layouts:
        out = out + lay
    return out
