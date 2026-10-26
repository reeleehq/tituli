# tituli.arrange

Layout combinators: several blocks composed into one `Layout`.

`title_card` and `note` each set one block. A page with a headline, a row of
glossed glyphs, a wrapped list and a footnote is several blocks — and composing
them by hand means measuring each `bbox()`, translating, and compositing one
rendered image per block. These combinators take `Layout`s and return
one `Layout`, so the page renders once and `tituli.video.overlay` can time
it like any other overlay.

* [`stack()`](#tituli.arrange.stack) — blocks top to bottom, aligned left/centre/right;
* [`grid()`](#tituli.arrange.grid) — blocks in uniform cells, row-major (one row by default);
* [`glossed()`](#tituli.arrange.glossed) — the glossed-glyph row: big glyph over a small reading,
  centred per column (a grid of two-block stacks).

Gaps are fractions of frame **height**, like every size in tituli. A combinator
given a [`Frame`](tituli.frame.html.md#tituli.frame.Frame) places its result with `frame.place` (so
the title-safe area and any delivery reservation bind); given a bare height, or
`anchor=None`, it leaves the result at the origin for an outer combinator to
place — nesting is the point.

```pycon
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
```

### Functions

| [`stack`](#tituli.arrange.stack)(items, \*, frame[, gap, align, anchor])      | Blocks top to bottom, `gap` apart, aligned within the widest.       |
|-----------------------------------------------------------------------------------------------------|---------------------------------------------------------------------|
| [`grid`](#tituli.arrange.grid)(items, \*, frame[, columns, gap, align, ...]) | Blocks in uniform cells, row-major; one row when `columns` is None. |
| [`glossed`](#tituli.arrange.glossed)(pairs, \*, frame[, glyph, gloss, ...])     | A row of big glyphs, each with a small reading centred under it.    |

### tituli.arrange.glossed(pairs, , frame, glyph=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.13, weight=700, italic=False, condensed=False, color=(255, 255, 255), tracking=0.0, leading=1.0, case='as-is', align='center', opacity=1.0, features=()), gloss=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.045, weight=600, italic=False, condensed=False, color=(255, 255, 255), tracking=0.0, leading=1.1, case='as-is', align='center', opacity=1.0, features=()), gap=0.012, column_gap=0.08, columns=None, anchor='center', engine=None)

A row of big glyphs, each with a small reading centred under it.

`pairs` is `[(glyph, gloss), ...]` — `[("カ", "ka"), ("ス", "su")]`.
Columns share one pitch (the widest column), so readings line up under
their glyphs and the row reads as a row. `columns` wraps a long row into
several. Runs are tagged `glyph:i` / `gloss:i` (for staggered reveals).
`engine` is the one that will draw it; it measures the columns.

```pycon
>>> lay = glossed([("カ", "ka"), ("ス", "su")], frame=1080)
>>> [r.text for r in lay.runs]
['カ', 'ka', 'ス', 'su']
>>> [r.tags for r in lay.runs][:2]
[('glyph:0',), ('gloss:0',)]
```

* **Return type:**
  [`Layout`](tituli.layout.html.md#tituli.layout.Layout)

### tituli.arrange.grid(items, , frame, columns=None, gap=0.03, align='center', anchor='center')

Blocks in uniform cells, row-major; one row when `columns` is None.

Every cell is as wide as the widest item (so a row of glyphs keeps one
pitch whatever each glyph’s advance), each row as tall as its tallest
item; items are aligned `align` within their cell and to its top.
`gap` is a fraction of frame height, or `(column_gap, row_gap)`.

```pycon
>>> from tituli.layout import block
>>> from tituli.style import TextStyle
>>> cells = [block(t, TextStyle(size=0.05), 1080) for t in "a b c d".split()]
>>> g = grid(cells, frame=1080, columns=2)
>>> tops = [round(r.bbox().y0) for r in g.runs]
>>> tops[0] == tops[1] < tops[2] == tops[3]      # two rows of two
True
```

* **Return type:**
  [`Layout`](tituli.layout.html.md#tituli.layout.Layout)

### tituli.arrange.stack(items, , frame, gap=0.02, align='center', anchor='center')

Blocks top to bottom, `gap` apart, aligned within the widest.

`gap` is a fraction of frame height: one number for every seam, or one
per seam (`len(items) - 1` values) when the page needs a rhythm. A block
with no runs is kept as a zero-height item, so per-seam gaps still line up.
Box plates travel with their block; a frame-anchored scrim raises (see
`_measurable`). A page larger than the title-safe area raises rather
than run off the frame. Parts’ loss reports (`overflow`/`unplaced`)
are summed into the result’s meta, and each part’s meta is kept under
`meta["parts"]`.

```pycon
>>> from tituli.layout import block
>>> from tituli.style import TextStyle
>>> a = block("wide line of text", TextStyle(size=0.05), 1080)
>>> b = block("x", TextStyle(size=0.05), 1080)
>>> s = stack([a, b], frame=1080, align="left")
>>> s.runs[0].bbox().x0 == s.runs[1].bbox().x0
True
```

* **Return type:**
  [`Layout`](tituli.layout.html.md#tituli.layout.Layout)
