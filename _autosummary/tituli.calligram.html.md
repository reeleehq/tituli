# tituli.calligram

Calligrams and concrete poems: text whose shape is part of the meaning.

Three treatments, all producing an ordinary [`Layout`](tituli.layout.html.md#tituli.layout.Layout):

* [`on_path()`](#tituli.calligram.on_path) — glyphs ride a [`Path`](tituli.geometry.html.md#tituli.geometry.Path) (any shape:
  circle, wave, Bézier, SVG `d`), rotated to the tangent or kept upright;
* [`rain()`](#tituli.calligram.rain) — Apollinaire’s *Il pleut*: upright letters stepping down
  fanning streaks (a preset of the same machinery, with the 1918 measurements
  as defaults);
* [`in_shape()`](#tituli.calligram.in_shape) — prose poured into a silhouette, the concrete-page case.

`shape=` accepts a named preset, an SVG path string, or a
[`Path`](tituli.geometry.html.md#tituli.geometry.Path), so a caller can say `"circle"` and a
designer can hand over a traced outline — the same seam.

```pycon
>>> from tituli.frame import Frame
>>> lay = on_path("round and round", shape="circle", frame=Frame.blank((800, 800)))
>>> len(lay.runs) == len("round and round".replace(" ", ""))
True
```

### Functions

| [`on_path`](#tituli.calligram.on_path)(text, \*[, shape, style, box, ...])        | Set `text` along a shape inside `box` (default: the safe area, inset).      |
|-----------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| [`rain`](#tituli.calligram.rain)(lines, \*, frame[, style, box, slants, ...])  | *Il pleut*: each line a streak of upright letters falling across the frame. |
| [`in_shape`](#tituli.calligram.in_shape)(text, mask, \*, frame[, style, box, ...]) | Pour prose into a silhouette (light = inside).                              |
| [`resolve_shape`](#tituli.calligram.resolve_shape)(shape, box)                          | Turn a name, an SVG `d` string or a Path into a Path fitted to `box`.       |

### tituli.calligram.in_shape(text, mask, , frame, style=TextStyle(family=('Georgia', 'Palatino', 'Baskerville', 'Liberation Serif', 'DejaVu Serif', 'Times New Roman'), size=0.035, weight=400, italic=False, condensed=False, color=(17, 17, 17), tracking=0.0, leading=1.2, case='as-is', align='left', opacity=1.0, features=()), box=None, repeat=True, engine=None)

Pour prose into a silhouette (light = inside). See [`tituli.layout.fill_shape()`](tituli.layout.html.md#tituli.layout.fill_shape).

* **Return type:**
  [`Layout`](tituli.layout.html.md#tituli.layout.Layout)

### tituli.calligram.on_path(text, , shape='wave', frame, style=TextStyle(family=('Georgia', 'Palatino', 'Baskerville', 'Liberation Serif', 'DejaVu Serif', 'Times New Roman'), size=0.035, weight=400, italic=False, condensed=False, color=(17, 17, 17), tracking=0.0, leading=1.2, case='as-is', align='left', opacity=1.0, features=()), box=None, upright=False, align='center', fit_text=True, engine=None)

Set `text` along a shape inside `box` (default: the safe area, inset).

With `fit_text` the type is shrunk until the whole string fits the path
length (never clipped); the resulting size is in `meta["size"]`.

* **Return type:**
  [`Layout`](tituli.layout.html.md#tituli.layout.Layout)

### tituli.calligram.rain(lines, , frame, style=TextStyle(family=('Georgia', 'Palatino', 'Baskerville', 'Liberation Serif', 'DejaVu Serif', 'Times New Roman'), size=0.035, weight=400, italic=False, condensed=False, color=(17, 17, 17), tracking=0.0, leading=1.2, case='as-is', align='left', opacity=1.0, features=()), box=None, slants=(0.186, 0.22, 0.257, 0.298, 0.353), head_offsets=(0.0, 7.0, 11.7, 16.4, 19.3), size_ratio=0.86, engine=None)

*Il pleut*: each line a streak of upright letters falling across the frame.

Wants a portrait frame. `slants` (dx per step down) and `head_offsets`
(where each streak starts, in slot units) are shape parameters, not
coordinates — the defaults are Apollinaire’s.

* **Return type:**
  [`Layout`](tituli.layout.html.md#tituli.layout.Layout)

### tituli.calligram.resolve_shape(shape, box)

Turn a name, an SVG `d` string or a Path into a Path fitted to `box`.

Names: `"line"`, `"circle"`, `"arc"`, `"wave"`, `"diagonal"`,
`"s-curve"`. Anything starting with `M`/`m` is parsed as SVG.

* **Return type:**
  [`Path`](tituli.geometry.html.md#tituli.geometry.Path)
