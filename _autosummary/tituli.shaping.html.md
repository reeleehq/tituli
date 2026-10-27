# tituli.shaping

Optional engine: HarfBuzz shaping + FreeType rendering (`pip install tituli[shaping]`).

The Pillow default handles Latin text well and rotates glyph *bitmaps*. This
engine shapes the run with HarfBuzz (kerning, ligatures, Arabic/Devanagari
joining) and asks FreeType to apply the rotation to the **outline** before
rasterising, which is the typographically correct order. Same `Run`
in, same canvas out — it is the `engine=` seam of `tituli.render.render()`.

Import cost is paid only when constructed; the module itself imports nothing
optional at top level.

### Functions

| [`shape`](#tituli.shaping.shape)(text, path, index, size, \*[, ...])   | `[(glyph_id, x_advance, y_advance, x_offset, y_offset), ...]` in pixels.   |
|----------------------------------------------------------------------------------------------|----------------------------------------------------------------------------|

### Classes

| [`HarfBuzzEngine`](#tituli.shaping.HarfBuzzEngine)()   | Draw runs through HarfBuzz + FreeType.   |
|---------------------------------------------------------------------|------------------------------------------|

### *class* tituli.shaping.HarfBuzzEngine

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Draw runs through HarfBuzz + FreeType. Falls back to Pillow for the embedded font.

#### length(face, text)

Advance of `text` as this engine shapes it (kerning, ligatures).

* **Return type:**
  [`float`](https://docs.python.org/3/builtins/functions.html#float)

#### measurer(face)

The engine that measures and draws `face`: Pillow for the embedded
font (it has no file to shape), this one otherwise.

### tituli.shaping.shape(text, path, index, size, , features=None, variations=None)

`[(glyph_id, x_advance, y_advance, x_offset, y_offset), ...]` in pixels.

`variations` are variable-font axis values by tag (`{"wght": 700}`).

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`int`](https://docs.python.org/3/builtins/functions.html#int), [`float`](https://docs.python.org/3/builtins/functions.html#float), [`float`](https://docs.python.org/3/builtins/functions.html#float), [`float`](https://docs.python.org/3/builtins/functions.html#float), [`float`](https://docs.python.org/3/builtins/functions.html#float)]]
