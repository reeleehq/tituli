# tituli.fonts

Font discovery with no bundled fonts.

`tituli` never ships a typeface (licensing), so a *typeface request* — a family
name, weight and slant — is resolved against the fonts already installed on the
machine, and falls back to the scalable face Pillow embeds (Aileron). That fallback
is a real font, not a stub, so every render works out of the box on a bare CI
runner; it just looks better on a machine with Helvetica Neue.

Resolution order is a *preference list*: the first family found wins.

```pycon
>>> face = resolve_face(["No Such Family", "DejaVu Sans"], size=48)
>>> face.size
48
>>> face.family in ("DejaVu Sans", "Aileron") or isinstance(face.family, str)
True
```

### Module Attributes

| [`WEIGHT_AXIS`](#tituli.fonts.WEIGHT_AXIS)   | The registered tag of the weight axis of a variable font.                   |
|----------------------------------------------------------------|-----------------------------------------------------------------------------|
| [`EMBEDDED`](#tituli.fonts.EMBEDDED)      | A family request that means *Pillow's embedded face, and never the system*. |

### Functions

| [`face_bytes`](#tituli.fonts.face_bytes)(face)                                   | The bytes of the font file behind `face` — the embedded face's too.                                                                                                                              |
|-----------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`face_digest`](#tituli.fonts.face_digest)(face)                                  | `sha256` of [`face_bytes()`](#tituli.fonts.face_bytes) and the [`Face.applied_variations`](#tituli.fonts.Face.applied_variations) — what makes two faces the same face. |
| [`families`](#tituli.fonts.families)()                                         | Sorted family names installed on this machine.                                                                                                                                                   |
| [`find_font`](#tituli.fonts.find_font)(family, \*[, weight, italic, condensed]) | First installed family in the preference list, at the closest style.                                                                                                                             |
| [`font_dirs`](#tituli.fonts.font_dirs)()                                        | Platform font directories that exist on this machine.                                                                                                                                            |
| [`font_index`](#tituli.fonts.font_index)()                                       | Installed faces grouped by family name.                                                                                                                                                          |
| [`glyph_set`](#tituli.fonts.glyph_set)(face)                                    | The glyphs of `face`'s font at its [`Face.applied_variations`](#tituli.fonts.Face.applied_variations): outlines to draw and `.width` advances (in font units) to measure with.             |
| [`resolve_face`](#tituli.fonts.resolve_face)([family, weight, italic, ...])        | Resolve a typeface request to a sized `Face`; never fails.                                                                                                                                       |
| [`ttfont`](#tituli.fonts.ttfont)(path[, index])                              | fontTools' parsed font behind `(path, index)`: opened lazily, cached per file (not per size or instance).                                                                                        |
| [`variation_axes`](#tituli.fonts.variation_axes)(path[, index])                      | The variation axes of a font file, in `fvar` order (the order FreeType and Pillow take coordinates in); empty for a static font or one this cannot read.                                         |
| [`variation_coords`](#tituli.fonts.variation_coords)(path, index, variations)          | One coordinate per axis, in `fvar` order, as FreeType and Pillow take them: the value in `variations` for its tag, the axis default otherwise.                                                   |
| [`variation_key`](#tituli.fonts.variation_key)(variations)                          | `variations` as a hashable, canonical (tag-sorted) tuple — a cache key.                                                                                                                          |

### Classes

| [`Face`](#tituli.fonts.Face)(family, style, size, path[, index, ...])   | A resolved, sized font ready to measure and draw with Pillow.   |
|--------------------------------------------------------------------------------------------------|-----------------------------------------------------------------|
| [`FontFile`](#tituli.fonts.FontFile)(path, index, family, style)            | One face inside a font file (a `.ttc` holds several).           |
| [`VariationAxis`](#tituli.fonts.VariationAxis)(tag, minimum, default, maximum)   | One axis of a variable font's `fvar` table, in design units.    |

### tituli.fonts.EMBEDDED *= 'tituli:embedded'*

A family request that means *Pillow’s embedded face, and never the system*.
In a preference list it is a stop: the names before it are looked up as
usual, and if none is installed the embedded face is used without scanning
further. Alone (or first) it never scans the system at all, so the result is
the same bytes on every machine with the same Pillow — the deterministic
choice for a caller whose output must not depend on the installed fonts.
(Asking for `"Aileron"` by name is not the same thing: a machine that has
Aileron installed would resolve to *that* file.)

### *class* tituli.fonts.Face(family, style, size, path, index=0, features=(), wght=None)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A resolved, sized font ready to measure and draw with Pillow.

#### *property* applied_features *: [tuple](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), ...]*

The requested [`features`](#tituli.fonts.Face.features) this font has, so the ones measured and
outlined with; a requested tag missing here was not applied.

```pycon
>>> resolve_face(EMBEDDED, size=12).applied_features
()
```

#### *property* applied_variations *: [dict](https://docs.python.org/3/builtins/stdtypes.html#dict)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [float](https://docs.python.org/3/builtins/functions.html#float)]*

The variable-font axis values applied (`{"wght": 700.0}`); empty for
a static face. Every engine reads this, never [`wght`](#tituli.fonts.Face.wght) itself; an
axis not named here stays at its default.

#### *property* ascent *: [int](https://docs.python.org/3/builtins/functions.html#int)*

Ascent in pixels.

#### *property* descent *: [int](https://docs.python.org/3/builtins/functions.html#int)*

Descent in pixels.

#### features *: [tuple](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), ...]* *= ()*

OpenType feature tags the style asked for (tituli#4); which of them the
font has is [`applied_features`](#tituli.fonts.Face.applied_features).

#### length(text)

Advance width of `text` in pixels.

With [`applied_features`](#tituli.fonts.Face.applied_features), the advances of the substituted glyphs
([`tituli.features.featured_length()`](tituli.features.html.md#tituli.features.featured_length)): the font’s design advances,
without hinting or kerning, which is what tabular figures are for.

* **Return type:**
  [`float`](https://docs.python.org/3/builtins/functions.html#float)

#### *property* line_height *: [int](https://docs.python.org/3/builtins/functions.html#int)*

Ascent + descent.

#### *property* pil *: FreeTypeFont*

The Pillow font object (cached per `(path, index, size, variations)`).

#### wght *: [float](https://docs.python.org/3/builtins/functions.html#float) | [None](https://docs.python.org/3/builtins/constants.html#None)* *= None*

Value of the `wght` axis when the file is a variable font with one
(tituli#9), clamped to the axis range; `None` for a static face. A face
at the axis default still differs from `None` in [`face_digest()`](#tituli.fonts.face_digest).

#### with_size(size)

Same face at another pixel size.

* **Return type:**
  [`Face`](#tituli.fonts.Face)

### *class* tituli.fonts.FontFile(path, index, family, style)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

One face inside a font file (a `.ttc` holds several).

#### *property* condensed *: [bool](https://docs.python.org/3/builtins/functions.html#bool)*

Whether the style name says condensed/narrow/compressed.

#### *property* italic *: [bool](https://docs.python.org/3/builtins/functions.html#bool)*

Whether the style name says italic/oblique.

#### *property* weight *: [int](https://docs.python.org/3/builtins/functions.html#int)*

CSS-style weight parsed from the style name (`"Bold"` -> 700).

### *class* tituli.fonts.VariationAxis(tag, minimum, default, maximum)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

One axis of a variable font’s `fvar` table, in design units.

### tituli.fonts.WEIGHT_AXIS *= 'wght'*

The registered tag of the weight axis of a variable font.

### tituli.fonts.face_bytes(face)

The bytes of the font file behind `face` — the embedded face’s too.

Pillow keeps the embedded face’s bytes on the font object it builds
(`font_bytes`), so the fallback has an identity like any file does.

```pycon
>>> face_bytes(resolve_face(EMBEDDED, size=12))[:4] in (b"\x00\x01\x00\x00", b"true", b"OTTO")
True
```

* **Return type:**
  [`bytes`](https://docs.python.org/3/builtins/stdtypes.html#bytes)

### tituli.fonts.face_digest(face)

`sha256` of [`face_bytes()`](#tituli.fonts.face_bytes) and the [`Face.applied_variations`](#tituli.fonts.Face.applied_variations) —
what makes two faces the same face.

A family name is not an identity (two machines can install different files
under one name, and the embedded face can change with Pillow); the bytes are,
together with the instance a variable font is drawn at. A static face’s digest
is the hash of its bytes alone. Cached per `(path, variations)`, so a file
rewritten in place during the process keeps its first digest.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### tituli.fonts.families()

Sorted family names installed on this machine.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### tituli.fonts.find_font(family, , weight=400, italic=False, condensed=False)

First installed family in the preference list, at the closest style.

`family` may be one name or a preference list. A path to a font file is
accepted too, and wins outright.

```pycon
>>> find_font("definitely-not-installed-xyz") is None
True
```

* **Return type:**
  [`FontFile`](#tituli.fonts.FontFile) | [`None`](https://docs.python.org/3/builtins/constants.html#None)

### tituli.fonts.font_dirs()

Platform font directories that exist on this machine.

Extra directories can be prepended with `TITULI_FONT_DIRS` (`os.pathsep`
separated), which is also how a project supplies its own licensed fonts.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path)]

### tituli.fonts.font_index()

Installed faces grouped by family name. Scanned once per process.

```pycon
>>> idx = font_index()
>>> all(isinstance(k, str) for k in idx)
True
```

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`FontFile`](#tituli.fonts.FontFile), [`...`](https://docs.python.org/3/builtins/constants.html#Ellipsis)]]

### tituli.fonts.glyph_set(face)

The glyphs of `face`’s font at its [`Face.applied_variations`](#tituli.fonts.Face.applied_variations):
outlines to draw and `.width` advances (in font units) to measure with.

### tituli.fonts.resolve_face(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), , size, weight=400, italic=False, condensed=False, features=())

Resolve a typeface request to a sized `Face`; never fails.

`features` are OpenType feature tags to apply (`("tnum",)`), carried by
the face; see [`Face.applied_features`](#tituli.fonts.Face.applied_features) for which the font has.

Falls back to Pillow’s embedded Aileron when nothing in the list is installed,
so a render on a fontless CI box still produces a real (if plainer) result.
[`EMBEDDED`](#tituli.fonts.EMBEDDED) in the list stops the search there (see its comment):

```pycon
>>> resolve_face(EMBEDDED, size=20).path is None
True
>>> resolve_face(["definitely-not-installed-xyz", EMBEDDED], size=20).family
'Aileron'
```

* **Return type:**
  [`Face`](#tituli.fonts.Face)

### tituli.fonts.ttfont(path, index=0)

fontTools’ parsed font behind `(path, index)`: opened lazily, cached per
file (not per size or instance). The one opener outlines and features share;
a variable instance is read through [`glyph_set()`](#tituli.fonts.glyph_set).

Needs fontTools (`tituli[outlines]`).

### tituli.fonts.variation_axes(path, index=0)

The variation axes of a font file, in `fvar` order (the order FreeType
and Pillow take coordinates in); empty for a static font or one this cannot
read. Parsed from the file’s tables directly, so it needs no fontTools and
keeps the exact (unrounded) axis values.

```pycon
>>> variation_axes(None)
()
```

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`VariationAxis`](#tituli.fonts.VariationAxis), [`...`](https://docs.python.org/3/builtins/constants.html#Ellipsis)]

### tituli.fonts.variation_coords(path, index, variations)

One coordinate per axis, in `fvar` order, as FreeType and Pillow take
them: the value in `variations` for its tag, the axis default otherwise.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`float`](https://docs.python.org/3/builtins/functions.html#float)]

### tituli.fonts.variation_key(variations)

`variations` as a hashable, canonical (tag-sorted) tuple — a cache key.

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`float`](https://docs.python.org/3/builtins/functions.html#float)], [`...`](https://docs.python.org/3/builtins/constants.html#Ellipsis)]
