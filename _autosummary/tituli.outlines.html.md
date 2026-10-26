# tituli.outlines

Glyph outlines as SVG path data — the vector form of a placed `Run`.

A [`Layout`](tituli.layout.html.md#tituli.layout.Layout) says *where* each run goes; this module says
*what it looks like as geometry*: the font’s own contours, scaled to the run’s
face size, advanced along the run exactly as `Face.length()` measures it,
rotated by the run’s angle and translated to its baseline origin. The result is
an SVG `d` string in frame pixels (y down), so a caller can draw text with no
font engine at all — an animation runtime that only knows how to draw SVG, for
instance (thorwhalen/an#155: \*glyphs as SVG sprites, converted at compile
time\*).

```pycon
>>> from tituli.fonts import EMBEDDED, resolve_face
>>> from tituli.layout import Run
>>> run = Run("Hi", 10.0, 50.0, resolve_face(EMBEDDED, size=40), (0, 0, 0, 255))
>>> out = run_outline(run)
>>> out.d.startswith("M")
True
>>> out.bbox.y1 <= 50.0 + 1 and out.bbox.y0 < 50.0   # ink sits on the baseline
True
```

Missing glyphs **raise** rather than drawing a box or nothing: a string the
face cannot set is the caller’s decision (another face, other words), never a
silent substitution.

```pycon
>>> run_outline(Run("é", 0, 0, resolve_face(EMBEDDED, size=40), (0, 0, 0, 255)))
Traceback (most recent call last):
...
tituli.outlines.MissingGlyphError: 'Aileron' Regular has no glyph for 'é' (U+00E9)
```

Needs `fontTools` (`pip install tituli[outlines]`); imported lazily, so the
rest of the package never pays for it.

### Module Attributes

| [`DFLT_PRECISION`](#tituli.outlines.DFLT_PRECISION)   | Decimal places kept in the path data.   |
|-------------------------------------------------------------------|-----------------------------------------|

### Functions

| [`run_outline`](#tituli.outlines.run_outline)(run, \*[, precision, engine])   | The contours of `run` as one SVG path, placed where the run is drawn.   |
|----------------------------------------------------------------------------------------------|-------------------------------------------------------------------------|

### Classes

| [`Outline`](#tituli.outlines.Outline)(d, bbox)   | A run's contours as SVG path data, in frame pixels.   |
|---------------------------------------------------------------------|-------------------------------------------------------|

### Exceptions

| [`MissingGlyphError`](#tituli.outlines.MissingGlyphError)   | The run's face has no glyph for one of its characters.   |
|----------------------------------------------------------------------|----------------------------------------------------------|

### tituli.outlines.DFLT_PRECISION *= 2*

Decimal places kept in the path data. Two is a hundredth of a pixel —
invisible, and it keeps the string short and byte-stable.

### *exception* tituli.outlines.MissingGlyphError

Bases: [`ValueError`](https://docs.python.org/3/builtins/exceptions.html#ValueError)

The run’s face has no glyph for one of its characters.

### *class* tituli.outlines.Outline(d, bbox)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A run’s contours as SVG path data, in frame pixels.

`bbox` is the ink’s bounds (`None` when nothing is inked, e.g. a space).

### tituli.outlines.run_outline(run, , precision=2, engine=None)

The contours of `run` as one SVG path, placed where the run is drawn.

Glyph `i` starts at `face.length(text[:i]) + i * tracking` along the
baseline — the same advances the layout measured with, kerning included,
so the outline and the layout cannot disagree about where a glyph is.
`engine` is the one the layout was measured with (default: the face). A
run that carries an `advance` from another engine’s measure is refused
when `engine` is not given, rather than outlined with the face’s advances.

* **Return type:**
  [`Outline`](#tituli.outlines.Outline)
