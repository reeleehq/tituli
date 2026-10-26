# tituli.features

OpenType features a style asks for, applied without a shaper where they can be (tituli#4).

A style may ask for features by tag (`TextStyle(features=("tnum",))`: tabular
figures, so the digits of a changing number do not change width). Whether the
font HAS a feature is a property of its bytes, so a face records which of the
requested ones it applies ([`tituli.fonts.Face.applied_features`](tituli.fonts.html.md#tituli.fonts.Face.applied_features)); a
feature the font lacks is not applied, and the caller can say so.

Pillow applies features only through libraqm, which is often absent, and its
embedded face always lays out without it. So the features that are glyph
SUBSTITUTIONS one for one (GSUB lookup type 1, also inside an extension lookup:
`tnum`, `lnum`, `onum`, `pnum`, `zero`, `smcp` …) are applied here,
from the font’s own tables: [`featured_glyphs()`](#tituli.features.featured_glyphs) gives the substituted glyph
names and [`featured_length()`](#tituli.features.featured_length) their advances. Measurement
([`length()`](tituli.fonts.html.md#tituli.fonts.Face.length)) and outlines ([`tituli.run_outline()`](tituli.html.md#tituli.run_outline))
read both, so they cannot disagree. A requested feature built from any other
kind of lookup needs a shaper and is refused ([`FeatureError`](#tituli.features.FeatureError)).

Needs fontTools (`tituli[outlines]`), like the outlines.

### Functions

| [`font_features`](#tituli.features.font_features)(path[, index])   | The GSUB feature tags a font declares.                                                                                                                                |
|---------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`applied_features`](#tituli.features.applied_features)(face)         | The face's requested features that its font has, in request order.                                                                                                    |
| [`featured_glyphs`](#tituli.features.featured_glyphs)(face, text)    | The glyph name each character of `text` draws with the face's applied features (`None` where the font has no glyph for it).                                           |
| [`featured_length`](#tituli.features.featured_length)(face, text)    | Advance width of `text` in pixels, from the substituted glyphs' own advances (the font's design metrics at the face's variation instance, scaled to the face's size). |

### Exceptions

| [`FeatureError`](#tituli.features.FeatureError)   | A requested feature cannot be applied as asked; the message says what would.   |
|-----------------------------------------------------------------|--------------------------------------------------------------------------------|

### *exception* tituli.features.FeatureError

Bases: [`ValueError`](https://docs.python.org/3/builtins/exceptions.html#ValueError)

A requested feature cannot be applied as asked; the message says what would.

### tituli.features.applied_features(face)

The face’s requested features that its font has, in request order.

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`...`](https://docs.python.org/3/builtins/constants.html#Ellipsis)]

### tituli.features.featured_glyphs(face, text)

The glyph name each character of `text` draws with the face’s applied
features (`None` where the font has no glyph for it).

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)]

### tituli.features.featured_length(face, text)

Advance width of `text` in pixels, from the substituted glyphs’ own
advances (the font’s design metrics at the face’s variation instance,
scaled to the face’s size).

* **Return type:**
  [`float`](https://docs.python.org/3/builtins/functions.html#float)

### tituli.features.font_features(path, index=0)

The GSUB feature tags a font declares.

```pycon
>>> from tituli import EMBEDDED, resolve_face
>>> "tnum" in font_features(resolve_face(EMBEDDED, size=12).path)
False
```

* **Return type:**
  [`frozenset`](https://docs.python.org/3/builtins/stdtypes.html#frozenset)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]
