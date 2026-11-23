"""Boxes, anchors, safe areas and parametric paths — the coordinate vocabulary.

Two coordinate systems, deliberately:

* **normalised** ``(x, y, w, h)`` in ``0..1`` of the frame, top-left origin — the
  resolution-independent form used by specs, by ``burns.salient_box`` and by the
  lacing body. This is what a *request* is written in.
* **pixel** :class:`Box` ``(x0, y0, x1, y1)`` floats — what layout and rendering
  compute in once a :class:`~tituli.frame.Frame` size is known.

A :class:`Path` is a curve you can lay glyphs along: ``point(s)`` and ``angle(s)``
by arc length. Constructors cover lines, arcs, waves, Béziers, polylines and SVG
``d`` strings, which is what lets a calligram be *any* shape rather than a
hard-coded sine.

>>> b = Box(10, 20, 110, 70)
>>> b.width, b.height, b.center
(100, 50, (60.0, 45.0))
>>> Box.from_norm((0.25, 0.5, 0.5, 0.25), 1920, 1080)
Box(x0=480.0, y0=540.0, x1=1440.0, y1=810.0)
>>> p = Path.line((0, 0), (100, 0))
>>> p.length, p.point(50), p.angle(50)
(100.0, (50.0, 0.0), 0.0)
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

Point = tuple[float, float]
NormBox = tuple[float, float, float, float]  # x, y, w, h in 0..1

# SMPTE ST 2046-1: action-safe 93 %, title-safe 90 % of the picture.
ACTION_SAFE = 0.93
TITLE_SAFE = 0.90

_PATH_SAMPLES = 512  # arc-length table resolution for curved paths
_BEZIER_SAMPLES = 48
_DEG = 180.0 / math.pi


@dataclass(frozen=True)
class Box:
    """A pixel-space rectangle ``(x0, y0, x1, y1)``; edges are floats."""

    x0: float
    y0: float
    x1: float
    y1: float

    @classmethod
    def from_size(cls, x: float, y: float, w: float, h: float) -> "Box":
        """Build from an origin and a size."""
        return cls(x, y, x + w, y + h)

    @classmethod
    def from_norm(cls, nb: NormBox, width: float, height: float) -> "Box":
        """Scale a normalised ``(x, y, w, h)`` into a frame of that size."""
        x, y, w, h = nb
        return cls(x * width, y * height, (x + w) * width, (y + h) * height)

    def to_norm(self, width: float, height: float) -> NormBox:
        """The inverse of :meth:`from_norm`."""
        return (
            self.x0 / width,
            self.y0 / height,
            self.width / width,
            self.height / height,
        )

    @property
    def width(self) -> float:
        """The width (``x1 - x0``)."""
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        """The height (``y1 - y0``)."""
        return self.y1 - self.y0

    @property
    def center(self) -> Point:
        """The centre point of the box."""
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)

    @property
    def area(self) -> float:
        """The area, zero for an empty or inverted box."""
        return max(0.0, self.width) * max(0.0, self.height)

    def inset(self, dx: float, dy: float | None = None) -> "Box":
        """Shrink by ``dx`` horizontally and ``dy`` (default ``dx``) vertically."""
        dy = dx if dy is None else dy
        return Box(self.x0 + dx, self.y0 + dy, self.x1 - dx, self.y1 - dy)

    def translate(self, dx: float, dy: float) -> "Box":
        """A copy of the box moved by ``(dx, dy)``."""
        return Box(self.x0 + dx, self.y0 + dy, self.x1 + dx, self.y1 + dy)

    def intersection(self, other: "Box") -> "Box":
        """The overlapping box (zero-area or inverted when the boxes are disjoint)."""
        return Box(
            max(self.x0, other.x0),
            max(self.y0, other.y0),
            min(self.x1, other.x1),
            min(self.y1, other.y1),
        )

    def overlap_fraction(self, other: "Box") -> float:
        """Fraction of *this* box's area covered by ``other``.

        >>> Box(0, 0, 10, 10).overlap_fraction(Box(5, 0, 20, 10))
        0.5
        """
        if self.area == 0:
            return 0.0
        return self.intersection(other).area / self.area

    def union(self, other: "Box") -> "Box":
        """The smallest box containing both boxes."""
        return Box(
            min(self.x0, other.x0),
            min(self.y0, other.y0),
            max(self.x1, other.x1),
            max(self.y1, other.y1),
        )

    def rounded(self) -> tuple[int, int, int, int]:
        """Integer bounds ``(x0, y0, x1, y1)``, rounded outwards."""
        return (
            int(math.floor(self.x0)),
            int(math.floor(self.y0)),
            int(math.ceil(self.x1)),
            int(math.ceil(self.y1)),
        )


def safe_area(width: float, height: float, *, fraction: float = TITLE_SAFE) -> Box:
    """The centred box holding ``fraction`` of each dimension.

    >>> safe_area(1000, 500)
    Box(x0=50.0, y0=25.0, x1=950.0, y1=475.0)
    """
    mx = (width - width * fraction) / 2
    my = (height - height * fraction) / 2
    return Box(mx, my, width - mx, height - my)


# Anchor names -> (fx, fy): where the block's own reference point sits within the
# region, in 0..1. The nine-position grid every overlay is placed on.
ANCHORS: dict[str, tuple[float, float]] = {
    "top-left": (0.0, 0.0),
    "top": (0.5, 0.0),
    "top-right": (1.0, 0.0),
    "left": (0.0, 0.5),
    "center": (0.5, 0.5),
    "right": (1.0, 0.5),
    "bottom-left": (0.0, 1.0),
    "bottom": (0.5, 1.0),
    "bottom-right": (1.0, 1.0),
}


def anchor_box(region: Box, size: tuple[float, float], anchor: str) -> Box:
    """Place a block of ``size`` inside ``region`` at a named anchor.

    >>> anchor_box(Box(0, 0, 100, 100), (20, 10), "bottom-right")
    Box(x0=80.0, y0=90.0, x1=100.0, y1=100.0)
    """
    if anchor not in ANCHORS:
        raise ValueError(f"unknown anchor {anchor!r}; choose from {sorted(ANCHORS)}")
    fx, fy = ANCHORS[anchor]
    w, h = size
    x = region.x0 + (region.width - w) * fx
    y = region.y0 + (region.height - h) * fy
    return Box.from_size(x, y, w, h)


# ----------------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------------


def _dist(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


@dataclass(frozen=True)
class Path:
    """A polyline with an arc-length parameterisation.

    Build one with the constructors (:meth:`line`, :meth:`arc`, :meth:`wave`,
    :meth:`bezier`, :meth:`polyline`, :meth:`from_svg`, :meth:`from_function`) and
    query it by distance along the curve: ``point(s)`` and ``angle(s)`` (degrees,
    clockwise-positive on screen because y points down).
    """

    points: tuple[Point, ...]

    def __post_init__(self) -> None:
        if len(self.points) < 2:
            raise ValueError("a Path needs at least two points")

    @property
    def _cumulative(self) -> tuple[float, ...]:
        acc = [0.0]
        for a, b in zip(self.points, self.points[1:]):
            acc.append(acc[-1] + _dist(a, b))
        return tuple(acc)

    @property
    def length(self) -> float:
        """The total length of the path."""
        return self._cumulative[-1]

    @property
    def closed(self) -> bool:
        """Whether the path ends where it starts (a circle, a closed SVG path).

        >>> Path.circle((0, 0), 10).closed, Path.line((0, 0), (1, 1)).closed
        (True, False)
        """
        (x0, y0), (x1, y1) = self.points[0], self.points[-1]
        return math.hypot(x1 - x0, y1 - y0) <= 1e-6 * max(1.0, self.length)

    def _segment_at(self, s: float) -> tuple[int, float]:
        cum = self._cumulative
        s = min(max(s, 0.0), cum[-1])
        # binary search for the segment containing s
        lo, hi = 0, len(cum) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if cum[mid] <= s:
                lo = mid
            else:
                hi = mid
        seg_len = cum[hi] - cum[lo]
        t = 0.0 if seg_len == 0 else (s - cum[lo]) / seg_len
        return lo, t

    def point(self, s: float) -> Point:
        """Position at arc length ``s`` (clamped to the path)."""
        i, t = self._segment_at(s)
        (x0, y0), (x1, y1) = self.points[i], self.points[i + 1]
        return (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)

    def angle(self, s: float) -> float:
        """Tangent direction at ``s`` in degrees (0 = rightwards, 90 = down)."""
        i, _ = self._segment_at(s)
        (x0, y0), (x1, y1) = self.points[i], self.points[i + 1]
        return math.atan2(y1 - y0, x1 - x0) * _DEG

    def transformed(self, fn: Callable[[Point], Point]) -> "Path":
        """A path with ``fn`` applied to every point."""
        return Path(tuple(fn(p) for p in self.points))

    def scaled(self, sx: float, sy: float | None = None) -> "Path":
        """A path scaled by ``sx`` horizontally and ``sy`` vertically (default ``sx``)."""
        sy = sx if sy is None else sy
        return self.transformed(lambda p: (p[0] * sx, p[1] * sy))

    def translated(self, dx: float, dy: float) -> "Path":
        """A copy moved by ``(dx, dy)``."""
        return self.transformed(lambda p: (p[0] + dx, p[1] + dy))

    def bbox(self) -> Box:
        """The bounding :class:`Box` of the points."""
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return Box(min(xs), min(ys), max(xs), max(ys))

    def fit(self, box: Box, *, keep_aspect: bool = True) -> "Path":
        """Scale and translate so the path's bounding box fills ``box``.

        Degenerate axes (a horizontal line has zero height) are centred rather
        than scaled.
        """
        bb = self.bbox()
        sx = box.width / bb.width if bb.width > 0 else 1.0
        sy = box.height / bb.height if bb.height > 0 else 1.0
        if keep_aspect:
            s = min(sx, sy)
            sx = sy = s
        scaled = self.scaled(sx, sy)
        sb = scaled.bbox()
        dx = box.x0 + (box.width - sb.width) / 2 - sb.x0
        dy = box.y0 + (box.height - sb.height) / 2 - sb.y0
        return scaled.translated(dx, dy)

    # -- constructors ---------------------------------------------------------

    @classmethod
    def line(cls, start: Point, end: Point) -> "Path":
        """A straight path from ``start`` to ``end``."""
        return cls((tuple(start), tuple(end)))  # type: ignore[arg-type]

    @classmethod
    def polyline(cls, points: Iterable[Point]) -> "Path":
        """A path through ``points``."""
        return cls(tuple((float(x), float(y)) for x, y in points))

    @classmethod
    def from_function(
        cls, fn: Callable[[float], Point], *, samples: int = _PATH_SAMPLES
    ) -> "Path":
        """Sample ``fn(t)`` for ``t`` in ``[0, 1]``."""
        return cls(tuple(fn(i / (samples - 1)) for i in range(samples)))

    @classmethod
    def arc(
        cls,
        center: Point,
        radius: float,
        start_deg: float,
        end_deg: float,
        *,
        samples: int = _PATH_SAMPLES,
    ) -> "Path":
        """Circular arc; angles in degrees, 0 = right, 90 = down (screen coords)."""
        cx, cy = center
        a0, a1 = math.radians(start_deg), math.radians(end_deg)

        def fn(t: float) -> Point:
            a = a0 + (a1 - a0) * t
            return (cx + radius * math.cos(a), cy + radius * math.sin(a))

        return cls.from_function(fn, samples=samples)

    @classmethod
    def circle(
        cls, center: Point, radius: float, *, start_deg: float = -90.0
    ) -> "Path":
        """A full circle starting at the top by default, running clockwise."""
        return cls.arc(center, radius, start_deg, start_deg + 360.0)

    @classmethod
    def wave(
        cls,
        start: Point,
        end: Point,
        *,
        amplitude: float,
        cycles: float = 1.0,
        samples: int = _PATH_SAMPLES,
    ) -> "Path":
        """A sine wave along the segment ``start -> end``."""
        (x0, y0), (x1, y1) = start, end
        dx, dy = x1 - x0, y1 - y0
        n = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / n, dx / n  # unit normal

        def fn(t: float) -> Point:
            off = amplitude * math.sin(2 * math.pi * cycles * t)
            return (x0 + dx * t + nx * off, y0 + dy * t + ny * off)

        return cls.from_function(fn, samples=samples)

    @classmethod
    def bezier(cls, *controls: Point, samples: int = _PATH_SAMPLES) -> "Path":
        """A Bézier curve of any degree through ``controls`` (De Casteljau)."""
        if len(controls) < 2:
            raise ValueError("a Bézier needs at least two control points")

        def fn(t: float) -> Point:
            pts = [tuple(p) for p in controls]
            while len(pts) > 1:
                pts = [
                    (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                    for a, b in zip(pts, pts[1:])
                ]
            return pts[0]  # type: ignore[return-value]

        return cls.from_function(fn, samples=samples)

    @classmethod
    def from_svg(cls, d: str) -> "Path":
        """Parse an SVG path ``d`` string (M L H V C S Q T Z, absolute or relative).

        Arcs (``A``) are not supported — approximate them with a Bézier.

        >>> Path.from_svg("M 0 0 L 10 0 L 10 10").length
        20.0
        """
        return cls(tuple(_svg_points(d)))


_SVG_TOKEN = re.compile(r"[MmLlHhVvCcSsQqTtZzAa]|-?\d*\.?\d+(?:[eE][-+]?\d+)?")


def _svg_points(d: str) -> list[Point]:
    tokens = _SVG_TOKEN.findall(d)
    pts: list[Point] = []
    cur: Point = (0.0, 0.0)
    start: Point = (0.0, 0.0)
    last_ctrl: Point | None = None
    cmd = ""
    i = 0

    def nums(n: int) -> list[float]:
        nonlocal i
        vals = [float(t) for t in tokens[i : i + n]]
        if len(vals) < n:
            raise ValueError(f"truncated SVG path near token {i}")
        i += n
        return vals

    def rel(p: Point) -> Point:
        return (cur[0] + p[0], cur[1] + p[1]) if cmd.islower() else p

    def add_curve(ctrl: Sequence[Point]) -> None:
        curve = Path.bezier(cur, *ctrl, samples=_BEZIER_SAMPLES)
        pts.extend(curve.points[1:])

    while i < len(tokens):
        tok = tokens[i]
        if tok.isalpha():
            cmd = tok
            i += 1
            if cmd in "Zz":
                if pts and pts[-1] != start:
                    pts.append(start)
                cur = start
                last_ctrl = None
                continue
        c = cmd.upper()
        if c == "M":
            x, y = nums(2)
            cur = rel((x, y))
            start = cur
            if pts:
                pts.append(cur)  # a subpath break is drawn as a jump (single polyline)
            else:
                pts.append(cur)
            cmd = "l" if cmd == "m" else "L"
            last_ctrl = None
        elif c == "L":
            x, y = nums(2)
            cur = rel((x, y))
            pts.append(cur)
            last_ctrl = None
        elif c == "H":
            (x,) = nums(1)
            cur = (cur[0] + x, cur[1]) if cmd.islower() else (x, cur[1])
            pts.append(cur)
            last_ctrl = None
        elif c == "V":
            (y,) = nums(1)
            cur = (cur[0], cur[1] + y) if cmd.islower() else (cur[0], y)
            pts.append(cur)
            last_ctrl = None
        elif c == "C":
            x1, y1, x2, y2, x, y = nums(6)
            c1, c2, end = rel((x1, y1)), rel((x2, y2)), rel((x, y))
            add_curve([c1, c2, end])
            last_ctrl, cur = c2, end
        elif c == "S":
            x2, y2, x, y = nums(4)
            c2, end = rel((x2, y2)), rel((x, y))
            c1 = (
                (2 * cur[0] - last_ctrl[0], 2 * cur[1] - last_ctrl[1])
                if last_ctrl
                else cur
            )
            add_curve([c1, c2, end])
            last_ctrl, cur = c2, end
        elif c == "Q":
            x1, y1, x, y = nums(4)
            c1, end = rel((x1, y1)), rel((x, y))
            add_curve([c1, end])
            last_ctrl, cur = c1, end
        elif c == "T":
            x, y = nums(2)
            end = rel((x, y))
            c1 = (
                (2 * cur[0] - last_ctrl[0], 2 * cur[1] - last_ctrl[1])
                if last_ctrl
                else cur
            )
            add_curve([c1, end])
            last_ctrl, cur = c1, end
        elif c == "A":
            raise ValueError("SVG arc commands are not supported; use a Bézier")
        else:
            raise ValueError(f"unexpected token {tok!r} in SVG path")
    if len(pts) < 2:
        raise ValueError("SVG path has fewer than two points")
    return pts
