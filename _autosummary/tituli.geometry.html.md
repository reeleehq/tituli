# tituli.geometry

Boxes, anchors, safe areas and parametric paths — the coordinate vocabulary.

Two coordinate systems, deliberately:

* **normalised** `(x, y, w, h)` in `0..1` of the frame, top-left origin — the
  resolution-independent form used by specs, by `burns.salient_box` and by the
  lacing body. This is what a *request* is written in.
* **pixel** [`Box`](#tituli.geometry.Box) `(x0, y0, x1, y1)` floats — what layout and rendering
  compute in once a [`Frame`](tituli.frame.html.md#tituli.frame.Frame) size is known.

A [`Path`](#tituli.geometry.Path) is a curve you can lay glyphs along: `point(s)` and `angle(s)`
by arc length. Constructors cover lines, arcs, waves, Béziers, polylines and SVG
`d` strings, which is what lets a calligram be *any* shape rather than a
hard-coded sine.

```pycon
>>> b = Box(10, 20, 110, 70)
>>> b.width, b.height, b.center
(100, 50, (60.0, 45.0))
>>> Box.from_norm((0.25, 0.5, 0.5, 0.25), 1920, 1080)
Box(x0=480.0, y0=540.0, x1=1440.0, y1=810.0)
>>> p = Path.line((0, 0), (100, 0))
>>> p.length, p.point(50), p.angle(50)
(100.0, (50.0, 0.0), 0.0)
```

### Functions

| [`anchor_box`](#tituli.geometry.anchor_box)(region, size, anchor)         | Place a block of `size` inside `region` at a named anchor.   |
|-------------------------------------------------------------------------------------------|--------------------------------------------------------------|
| [`safe_area`](#tituli.geometry.safe_area)(width, height, \*[, fraction]) | The centred box holding `fraction` of each dimension.        |

### Classes

| [`Box`](#tituli.geometry.Box)(x0, y0, x1, y1)   | A pixel-space rectangle `(x0, y0, x1, y1)`; edges are floats.   |
|------------------------------------------------------------------------|-----------------------------------------------------------------|
| [`Path`](#tituli.geometry.Path)(points)          | A polyline with an arc-length parameterisation.                 |

### *class* tituli.geometry.Box(x0, y0, x1, y1)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A pixel-space rectangle `(x0, y0, x1, y1)`; edges are floats.

#### *classmethod* from_norm(nb, width, height)

Scale a normalised `(x, y, w, h)` into a frame of that size.

* **Return type:**
  [`Box`](#tituli.geometry.Box)

#### *classmethod* from_size(x, y, w, h)

Build from an origin and a size.

* **Return type:**
  [`Box`](#tituli.geometry.Box)

#### inset(dx, dy=None)

Shrink by `dx` horizontally and `dy` (default `dx`) vertically.

* **Return type:**
  [`Box`](#tituli.geometry.Box)

#### overlap_fraction(other)

Fraction of *this* box’s area covered by `other`.

```pycon
>>> Box(0, 0, 10, 10).overlap_fraction(Box(5, 0, 20, 10))
0.5
```

* **Return type:**
  [`float`](https://docs.python.org/3/builtins/functions.html#float)

#### to_norm(width, height)

The inverse of [`from_norm()`](#tituli.geometry.Box.from_norm).

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`float`](https://docs.python.org/3/builtins/functions.html#float), [`float`](https://docs.python.org/3/builtins/functions.html#float), [`float`](https://docs.python.org/3/builtins/functions.html#float), [`float`](https://docs.python.org/3/builtins/functions.html#float)]

### *class* tituli.geometry.Path(points)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A polyline with an arc-length parameterisation.

Build one with the constructors (`line()`, [`arc()`](#tituli.geometry.Path.arc), [`wave()`](#tituli.geometry.Path.wave),
[`bezier()`](#tituli.geometry.Path.bezier), `polyline()`, [`from_svg()`](#tituli.geometry.Path.from_svg), [`from_function()`](#tituli.geometry.Path.from_function)) and
query it by distance along the curve: `point(s)` and `angle(s)` (degrees,
clockwise-positive on screen because y points down).

#### angle(s)

Tangent direction at `s` in degrees (0 = rightwards, 90 = down).

* **Return type:**
  [`float`](https://docs.python.org/3/builtins/functions.html#float)

#### *classmethod* arc(center, radius, start_deg, end_deg, , samples=512)

Circular arc; angles in degrees, 0 = right, 90 = down (screen coords).

* **Return type:**
  [`Path`](#tituli.geometry.Path)

#### *classmethod* bezier(\*controls, samples=512)

A Bézier curve of any degree through `controls` (De Casteljau).

* **Return type:**
  [`Path`](#tituli.geometry.Path)

#### *classmethod* circle(center, radius, , start_deg=-90.0)

A full circle starting at the top by default, running clockwise.

* **Return type:**
  [`Path`](#tituli.geometry.Path)

#### *property* closed *: [bool](https://docs.python.org/3/builtins/functions.html#bool)*

Whether the path ends where it starts (a circle, a closed SVG path).

```pycon
>>> Path.circle((0, 0), 10).closed, Path.line((0, 0), (1, 1)).closed
(True, False)
```

#### fit(box, , keep_aspect=True)

Scale and translate so the path’s bounding box fills `box`.

Degenerate axes (a horizontal line has zero height) are centred rather
than scaled.

* **Return type:**
  [`Path`](#tituli.geometry.Path)

#### *classmethod* from_function(fn, , samples=512)

Sample `fn(t)` for `t` in `[0, 1]`.

* **Return type:**
  [`Path`](#tituli.geometry.Path)

#### *classmethod* from_svg(d)

Parse an SVG path `d` string (M L H V C S Q T Z, absolute or relative).

Arcs (`A`) are not supported — approximate them with a Bézier.

```pycon
>>> Path.from_svg("M 0 0 L 10 0 L 10 10").length
20.0
```

* **Return type:**
  [`Path`](#tituli.geometry.Path)

#### point(s)

Position at arc length `s` (clamped to the path).

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`float`](https://docs.python.org/3/builtins/functions.html#float), [`float`](https://docs.python.org/3/builtins/functions.html#float)]

#### *classmethod* wave(start, end, , amplitude, cycles=1.0, samples=512)

A sine wave along the segment `start -> end`.

* **Return type:**
  [`Path`](#tituli.geometry.Path)

### tituli.geometry.anchor_box(region, size, anchor)

Place a block of `size` inside `region` at a named anchor.

```pycon
>>> anchor_box(Box(0, 0, 100, 100), (20, 10), "bottom-right")
Box(x0=80.0, y0=90.0, x1=100.0, y1=100.0)
```

* **Return type:**
  [`Box`](#tituli.geometry.Box)

### tituli.geometry.safe_area(width, height, , fraction=0.9)

The centred box holding `fraction` of each dimension.

```pycon
>>> safe_area(1000, 500)
Box(x0=50.0, y0=25.0, x1=950.0, y1=475.0)
```

* **Return type:**
  [`Box`](#tituli.geometry.Box)
