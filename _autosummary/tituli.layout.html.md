# tituli.layout

The layout model: placed runs of text, and the engines that place them.

A [`Layout`](#tituli.layout.Layout) is the single intermediate every use case produces and the
renderer consumes — a title card, a credits crawl and a calligram are all just
different ways of filling one. A [`Run`](#tituli.layout.Run) is the unit: a string, a baseline
origin in frame pixels, an angle, a resolved face and a colour. A block of prose
is a few runs (one per line); a calligram is one run per glyph. That is the whole
unification — the humble cases are the degenerate calligram, exactly as hoped.

Real font metrics throughout (`Face.length`), never an average-character
estimate.

```pycon
>>> from tituli.frame import Frame
>>> from tituli.style import TextStyle
>>> lay = block("Hello\nWorld", TextStyle(size=0.05), Frame.blank((1920, 1080)))
>>> len(lay.runs)                      # one run per line (a tracked style would give one per glyph)
2
>>> lay.bbox().width > 0
True
```

### Functions

| [`along_path`](#tituli.layout.along_path)(text, path, style, frame, \*[, ...])    | Set `text` glyph by glyph along `path` (the path is the baseline).                                                                |
|-----------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------|
| [`block`](#tituli.layout.block)(text, style, frame, \*[, max_width, x, ...]) | Lay out prose as lines from the top-left corner `(x, y)`.                                                                         |
| [`fill_shape`](#tituli.layout.fill_shape)(text, mask, style, frame, \*, box)      | Pour prose into a silhouette, row by row — the concrete-poem 'shape' case.                                                        |
| [`fit_size`](#tituli.layout.fit_size)(text, style, frame_height, \*, max_width) | Shrink `style.size` until `text` wraps within the given bounds.                                                                   |
| [`glyph_columns`](#tituli.layout.glyph_columns)(lines, style, frame, \*, box, ...)   | Upright glyphs stepping down slanted streaks — Apollinaire's *Il pleut*.                                                          |
| [`measure`](#tituli.layout.measure)(text, style, frame_height, \*[, engine])   | Width in pixels of `text` set in `style` on a frame of that height.                                                               |
| [`merge`](#tituli.layout.merge)(layouts)                                     | Concatenate layouts.                                                                                                              |
| [`text_advance`](#tituli.layout.text_advance)(engine, face, text, \*[, per_glyph])  | Advance of `text`: the engine that will draw it measures it (tituli#7); with no engine, the face does (what `PillowEngine` does). |
| [`wrap`](#tituli.layout.wrap)(text, style, frame_height, \*, max_width)     | Greedy word wrap on measured widths.                                                                                              |

### Classes

| [`Layout`](#tituli.layout.Layout)([runs, plates, meta])               | Everything the renderer needs: runs on top of plates, in frame pixels.   |
|---------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|
| [`Plate`](#tituli.layout.Plate)(box, color[, kind, radius, solid])   | A backdrop drawn under the runs: a scrim, a box, a rule.                 |
| [`Run`](#tituli.layout.Run)(text, x, y, face, color[, angle, ...]) | A string drawn from a baseline origin, possibly rotated.                 |

### *class* tituli.layout.Layout(runs=(), plates=(), meta=dict())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Everything the renderer needs: runs on top of plates, in frame pixels.

#### bbox()

Bounds of the runs (plates excluded).

* **Return type:**
  [`Box`](tituli.geometry.html.md#tituli.geometry.Box)

#### *property* duration_hint *: [float](https://docs.python.org/3/builtins/functions.html#float)*

Latest `t_full` among the runs (0 when untimed).

#### moved_to(box)

Translate so the runs’ bbox top-left lands on `box`’s top-left.

* **Return type:**
  [`Layout`](#tituli.layout.Layout)

#### staggered(, start=0.0, step, ramp)

Reveal runs one after another: run `i` starts at `start + i*step`.

* **Return type:**
  [`Layout`](#tituli.layout.Layout)

#### with_timing(t_in, t_full)

Give every run the same reveal envelope.

* **Return type:**
  [`Layout`](#tituli.layout.Layout)

### *class* tituli.layout.Plate(box, color, kind='box', radius=0.0, solid=(0.5, 0.5))

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A backdrop drawn under the runs: a scrim, a box, a rule.

### *class* tituli.layout.Run(text, x, y, face, color, angle=0.0, opacity=1.0, tracking=0.0, unit='line', index=0, t_in=None, t_full=None, tags=(), advance=None)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A string drawn from a baseline origin, possibly rotated.

#### advance *: [float](https://docs.python.org/3/builtins/functions.html#float) | [None](https://docs.python.org/3/builtins/constants.html#None)* *= None*

Width the drawing engine measured for this run (tituli#7); `None` means
measure with the face (Pillow), which is what a hand-built run does.
Valid only for the `text` and `face` it was measured with: build a
run by hand, or drop it (`replace(run, advance=None)`) after changing either.

#### bbox()

Axis-aligned bounds (ignores rotation — fine for placement).

* **Return type:**
  [`Box`](tituli.geometry.html.md#tituli.geometry.Box)

### tituli.layout.along_path(text, path, style, frame, , start=0.0, align='start', offset=0.0, upright=False, color=None, tags=(), engine=None)

Set `text` glyph by glyph along `path` (the path is the baseline).

Each glyph’s origin is the point at its arc length and it is rotated to the
tangent there — unless `upright` (a calligram convention: letters stay
vertical while their *positions* follow the shape). `offset` shifts the
baseline perpendicular to the path (negative = above, in screen terms).
`align` positions the whole string on the path from `start`.

Text longer than the path keeps its spacing and runs off the end — that is
reported in `meta["overflow"]` rather than silently squeezed. `engine` is
the one that will draw it; it measures the glyph advances.

* **Return type:**
  [`Layout`](#tituli.layout.Layout)

### tituli.layout.block(text, style, frame, , max_width=None, x=0.0, y=0.0, color=None, unit='line', tags=(), break_at=None, engine=None)

Lay out prose as lines from the top-left corner `(x, y)`.

`text` is a string (wrapped to `max_width` when given) or pre-broken
lines. Alignment follows `style.align` within `max_width` (or the widest
line when no width is given). `unit="glyph"` emits one run per character
(needed for tracking and for per-glyph reveals). `break_at` (e.g.
`" · "`) wraps a list only between its items — see [`wrap()`](#tituli.layout.wrap). `engine`
is the one that will draw the layout: it measures the lines, and the runs
keep that width, so a page composed from this block (`stack`, `grid`)
is placed by the engine’s measure too.

* **Return type:**
  [`Layout`](#tituli.layout.Layout)

### tituli.layout.fill_shape(text, mask, style, frame, , box, threshold=128, min_span=0.5, color=None, tags=(), repeat=True, engine=None)

Pour prose into a silhouette, row by row — the concrete-poem ‘shape’ case.

`mask` is any Pillow image (or path): dark pixels are *outside*, light
pixels are the shape (invert your mask if it is the other way round). It is
fitted into `box`; for each line of text height the horizontal spans of
the shape are found and filled with as many words as fit, in reading order.
With `repeat` the text cycles until the shape is full; otherwise leftover
spans stay empty and leftover words are reported in `meta["unplaced"]`. `engine` is the one
that will draw it; it measures the words.

* **Return type:**
  [`Layout`](#tituli.layout.Layout)

### tituli.layout.fit_size(text, style, frame_height, , max_width, max_height=None, min_size=0.012, step=0.9, break_at=None, engine=None)

Shrink `style.size` until `text` wraps within the given bounds.

Shrinks geometrically by `step` and never below `min_size` (a fraction
of frame height, like `size` itself).

* **Return type:**
  [`TextStyle`](tituli.style.html.md#tituli.style.TextStyle)

### tituli.layout.glyph_columns(lines, style, frame, , box, slants, head_offsets, word_gap_slots=1, size_ratio=0.86, color=None, tags=(), engine=None)

Upright glyphs stepping down slanted streaks — Apollinaire’s *Il pleut*.

Line `k` becomes a streak: glyph `i` sits at 

```
``
```

(u, v) = (head_offsets[k]

+ i \* slants[k], i)\`\` on an abstract slot grid, fitted to `box` in one
  step, so the shape is aspect-independent. Letters stay upright. This is the
  solver muvid’s `calligram` archetype introduced, generalised over real
  glyph metrics and any frame — the streaks are `Path` lines, which is
  how it stays one preset of [`along_path()`](#tituli.layout.along_path) rather than a second family.

`slants` and `head_offsets` are cycled if shorter than `lines`.
`engine` is the one that will draw it; it centres each glyph in its slot.

* **Return type:**
  [`Layout`](#tituli.layout.Layout)

### tituli.layout.measure(text, style, frame_height, , engine=None)

Width in pixels of `text` set in `style` on a frame of that height.

`engine` is the one that will draw it (default: measure with the face, as
Pillow draws); a page measured by one engine and drawn by another can have
wrong wrap points and column pitch.

* **Return type:**
  [`float`](https://docs.python.org/3/builtins/functions.html#float)

### tituli.layout.merge(layouts)

Concatenate layouts.

* **Return type:**
  [`Layout`](#tituli.layout.Layout)

### tituli.layout.text_advance(engine, face, text, , per_glyph=False)

Advance of `text`: the engine that will draw it measures it (tituli#7);
with no engine, the face does (what `PillowEngine` does).

`per_glyph` sums the characters one by one — how a glyph-by-glyph layout
(`unit="glyph"`, a tracked style) places them, so the line measures what
its glyphs occupy even for an engine that kerns across characters.

* **Return type:**
  [`float`](https://docs.python.org/3/builtins/functions.html#float)

### tituli.layout.wrap(text, style, frame_height, , max_width, break_at=None, engine=None)

Greedy word wrap on measured widths. Explicit newlines are honoured.

`break_at` makes a list wrap only *between* its items: with `" · "`,
`"バス bus · スープ soup"` never ends a line on `バス`. An item wider
than the whole line falls back to word wrapping inside that item (it is
never cut). A no-break space (U+00A0) binds two words in any mode.

```pycon
>>> from tituli.style import CAPTION
>>> lines = wrap("one two three four five six", CAPTION, 1080, max_width=300)
>>> len(lines) >= 2 and all(measure(l, CAPTION, 1080) <= 300 for l in lines)
True
```

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]
