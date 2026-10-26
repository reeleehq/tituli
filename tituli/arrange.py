"""Layout combinators: several blocks composed into one :class:`Layout`.

``title_card`` and ``note`` each set one block. A page with a headline, a row of
glossed glyphs, a wrapped list and a footnote is several blocks — and composing
them by hand means measuring each ``bbox()``, translating, and compositing one
rendered image per block. These combinators take :class:`Layout`\\ s and return
one ``Layout``, so the page renders once and ``tituli.video.overlay`` can time
it like any other overlay.

* :func:`stack` — blocks top to bottom, aligned left/centre/right;
* :func:`grid` — blocks in uniform cells, row-major (one row by default);
* :func:`glossed` — the glossed-glyph row: big glyph over a small reading,
  centred per column (a grid of two-block stacks).

Gaps are fractions of frame **height**, like every size in tituli. A combinator
given a :class:`~tituli.frame.Frame` places its result with ``frame.place`` (so
the title-safe area and any delivery reservation bind); given a bare height, or
``anchor=None``, it leaves the result at the origin for an outer combinator to
place — nesting is the point.

>>> from tituli.frame import Frame
>>> from tituli.layout import block
>>> from tituli.style import TextStyle
>>> f = Frame.blank((1920, 1080))
>>> head = block("Heading", TextStyle(size=0.06), f)
>>> body = block("body text", TextStyle(size=0.03), f)
>>> page = stack([head, body], frame=f, gap=0.02)
>>> [r.text for r in page.runs]
['Heading', 'body text']
>>> b0, b1 = (r.bbox() for r in page.runs)
>>> round(b1.y0 - b0.y1) == round(0.02 * 1080)      # the gap, in frame height
True
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Literal, Sequence

from tituli.frame import Frame
from tituli.geometry import Box
from tituli.layout import Layout, block
from tituli.style import GLOSS, GLOSS_GLYPH, TextStyle

if TYPE_CHECKING:  # pragma: no cover
    from tituli.render import Engine

HAlign = Literal["left", "center", "right"]

DEFAULT_STACK_GAP = 0.02  # fraction of frame height between stacked blocks
DEFAULT_GRID_GAP = 0.03  # between grid cells, both axes
DEFAULT_GLOSS_GAP = 0.012  # between a glyph and its gloss
DEFAULT_GLOSS_COLUMN_GAP = 0.08  # between glossed columns


def _height(frame: Frame | float) -> float:
    return frame.height if isinstance(frame, Frame) else float(frame)


_LOSS_KEYS = ("overflow", "unplaced")  # what a part reports it could not set


def _measurable(items: Sequence[Layout]) -> None:
    """Refuse items a combinator cannot move honestly.

    A layout with plates but no runs has no size to place by; a frame-anchored
    scrim (``corner-*``/``gradient-*``, as ``caption`` makes) is cut to the
    frame edge its block hugs, so moving it with the block would leave it
    hanging off nothing. Compose the text, then add the scrim to the page.
    """
    bad = [i for i, lay in enumerate(items) if lay.plates and not lay.runs]
    if bad:
        raise ValueError(
            f"items {bad} have plates but no runs, so they cannot be measured "
            "and would be left off the page; add the plate to a block with text "
            "(Layout.with_plates) instead"
        )
    anchored = [
        i for i, lay in enumerate(items) if any(p.kind != "box" for p in lay.plates)
    ]
    if anchored:
        raise ValueError(
            f"items {anchored} carry frame-anchored scrims (corner/gradient "
            "plates, e.g. from caption()); they belong to the frame edge, not "
            "the block. Stack the text (block/glossed), then add a scrim to the page"
        )


def _combined(parts: Sequence[Layout], runs, plates, **own) -> Layout:
    """One layout from ``parts``: their loss reports summed, never overwritten.

    (``Layout.__add__`` merges meta last-wins, which would let a later part's
    empty ``unplaced`` erase an earlier part's report, and would carry an
    inner card's ``anchor`` onto a page placed somewhere else.)
    """
    meta: dict = {"parts": tuple(dict(p.meta) for p in parts), **own}
    for key in _LOSS_KEYS:
        found = [p.meta[key] for p in parts if key in p.meta]
        if found:
            meta[key] = (
                [x for f in found for x in f]
                if all(isinstance(f, (list, tuple)) for f in found)
                else sum(float(f) for f in found)
            )
    return Layout(tuple(runs), tuple(plates), meta)


def _gaps(gap: float | Sequence[float], n: int) -> list[float]:
    """One gap per seam between ``n`` items (a scalar is repeated)."""
    if isinstance(gap, (int, float)):
        return [float(gap)] * max(0, n - 1)
    gaps = [float(g) for g in gap]
    if len(gaps) != max(0, n - 1):
        raise ValueError(
            f"gap has {len(gaps)} values for {n} items; give one per seam "
            f"({max(0, n - 1)}) or a single number"
        )
    return gaps


def _x_in(width: float, item_width: float, align: HAlign) -> float:
    if align == "left":
        return 0.0
    if align == "right":
        return width - item_width
    if align == "center":
        return (width - item_width) / 2
    raise ValueError(f"unknown align {align!r}; choose 'left', 'center' or 'right'")


def _placed(
    lay: Layout, frame: Frame | float, anchor: str | Sequence[str] | None
) -> Layout:
    """Move ``lay`` (its runs' bbox at the origin) to where ``frame`` puts it."""
    if anchor is None or not isinstance(frame, Frame) or not lay.runs:
        return lay
    bb = lay.bbox()
    region = frame.safe
    if bb.width > region.width + 0.5 or bb.height > region.height + 0.5:
        raise ValueError(
            f"the composed page is {bb.width:.0f}x{bb.height:.0f} px but the "
            f"title-safe area is {region.width:.0f}x{region.height:.0f} px; it "
            "would run off the frame. Give long blocks a max_width, use smaller "
            "styles or gaps, or split it over two pages"
        )
    where, box = frame.place((bb.width, bb.height), anchor=anchor)
    out = lay.moved_to(box)
    return replace(out, meta={**out.meta, "anchor": where, "box": box})


def _at_origin(lay: Layout) -> Layout:
    bb = lay.bbox()
    return lay.translated(-bb.x0, -bb.y0)


def stack(
    items: Sequence[Layout],
    *,
    frame: Frame | float,
    gap: float | Sequence[float] = DEFAULT_STACK_GAP,
    align: HAlign = "center",
    anchor: str | Sequence[str] | None = "center",
) -> Layout:
    """Blocks top to bottom, ``gap`` apart, aligned within the widest.

    ``gap`` is a fraction of frame height: one number for every seam, or one
    per seam (``len(items) - 1`` values) when the page needs a rhythm. A block
    with no runs is kept as a zero-height item, so per-seam gaps still line up.
    Box plates travel with their block; a frame-anchored scrim raises (see
    ``_measurable``). A page larger than the title-safe area raises rather
    than run off the frame. Parts' loss reports (``overflow``/``unplaced``)
    are summed into the result's meta, and each part's meta is kept under
    ``meta["parts"]``.

    >>> from tituli.layout import block
    >>> from tituli.style import TextStyle
    >>> a = block("wide line of text", TextStyle(size=0.05), 1080)
    >>> b = block("x", TextStyle(size=0.05), 1080)
    >>> s = stack([a, b], frame=1080, align="left")
    >>> s.runs[0].bbox().x0 == s.runs[1].bbox().x0
    True
    """
    _measurable(items)
    fh = _height(frame)
    gaps = _gaps(gap, len(items))
    width = max((lay.bbox().width for lay in items if lay.runs), default=0.0)
    runs, plates = [], []
    y = 0.0
    for i, lay in enumerate(items):
        if lay.runs:
            bb = lay.bbox()
            moved = _at_origin(lay).translated(_x_in(width, bb.width, align), y)
            runs += moved.runs
            plates += moved.plates
            y += bb.height
        if i < len(gaps):
            y += gaps[i] * fh
    out = _combined(items, runs, plates, block_width=width)
    return _placed(out, frame, anchor)


def grid(
    items: Sequence[Layout],
    *,
    frame: Frame | float,
    columns: int | None = None,
    gap: float | tuple[float, float] = DEFAULT_GRID_GAP,
    align: HAlign = "center",
    anchor: str | Sequence[str] | None = "center",
) -> Layout:
    """Blocks in uniform cells, row-major; one row when ``columns`` is None.

    Every cell is as wide as the widest item (so a row of glyphs keeps one
    pitch whatever each glyph's advance), each row as tall as its tallest
    item; items are aligned ``align`` within their cell and to its top.
    ``gap`` is a fraction of frame height, or ``(column_gap, row_gap)``.

    >>> from tituli.layout import block
    >>> from tituli.style import TextStyle
    >>> cells = [block(t, TextStyle(size=0.05), 1080) for t in "a b c d".split()]
    >>> g = grid(cells, frame=1080, columns=2)
    >>> tops = [round(r.bbox().y0) for r in g.runs]
    >>> tops[0] == tops[1] < tops[2] == tops[3]      # two rows of two
    True
    """
    fh = _height(frame)
    _measurable(items)
    n = len(items)
    if n == 0:
        return Layout()
    cols = n if columns is None else int(columns)
    if cols < 1:
        raise ValueError(f"columns must be >= 1, got {columns!r}")
    if isinstance(gap, (int, float)):
        col_gap = row_gap = float(gap)
    elif len(gap) == 2:
        col_gap, row_gap = (float(g) for g in gap)
    else:
        raise ValueError(
            f"grid gap is one number or (column_gap, row_gap), got {gap!r}"
        )
    boxes = [lay.bbox() if lay.runs else Box(0, 0, 0, 0) for lay in items]
    cell_w = max(b.width for b in boxes)
    rows = [list(range(r, min(r + cols, n))) for r in range(0, n, cols)]
    runs, plates = [], []
    y = 0.0
    for row in rows:
        row_h = max(boxes[i].height for i in row)
        for c, i in enumerate(row):
            if not items[i].runs:
                continue
            x = c * (cell_w + col_gap * fh) + _x_in(cell_w, boxes[i].width, align)
            moved = _at_origin(items[i]).translated(x, y)
            runs += moved.runs
            plates += moved.plates
        y += row_h + row_gap * fh
    out = _combined(
        items, runs, plates, cell_width=cell_w, columns=cols, rows=len(rows)
    )
    return _placed(out, frame, anchor)


def glossed(
    pairs: Sequence[tuple[str, str]],
    *,
    frame: Frame | float,
    glyph: TextStyle = GLOSS_GLYPH,
    gloss: TextStyle = GLOSS,
    gap: float = DEFAULT_GLOSS_GAP,
    column_gap: float = DEFAULT_GLOSS_COLUMN_GAP,
    columns: int | None = None,
    anchor: str | Sequence[str] | None = "center",
    engine: "Engine | None" = None,
) -> Layout:
    """A row of big glyphs, each with a small reading centred under it.

    ``pairs`` is ``[(glyph, gloss), ...]`` — ``[("カ", "ka"), ("ス", "su")]``.
    Columns share one pitch (the widest column), so readings line up under
    their glyphs and the row reads as a row. ``columns`` wraps a long row into
    several. Runs are tagged ``glyph:i`` / ``gloss:i`` (for staggered reveals).
    ``engine`` is the one that will draw it; it measures the columns.

    >>> lay = glossed([("カ", "ka"), ("ス", "su")], frame=1080)
    >>> [r.text for r in lay.runs]
    ['カ', 'ka', 'ス', 'su']
    >>> [r.tags for r in lay.runs][:2]
    [('glyph:0',), ('gloss:0',)]
    """
    fh = _height(frame)
    cells = [
        stack(
            [
                block(g, glyph, fh, tags=(f"glyph:{i}",), engine=engine),
                block(r, gloss, fh, tags=(f"gloss:{i}",), engine=engine),
            ],
            frame=fh,
            gap=gap,
            anchor=None,
        )
        for i, (g, r) in enumerate(pairs)
    ]
    return grid(
        cells,
        frame=frame,
        columns=columns,
        gap=(column_gap, DEFAULT_GRID_GAP),
        anchor=anchor,
    )


__all__ = ["stack", "grid", "glossed"]
