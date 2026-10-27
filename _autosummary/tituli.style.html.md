# tituli.style

Text styles and the tasteful presets.

A [`TextStyle`](#tituli.style.TextStyle) is resolution-independent: `size` is a \*\*fraction of the
frame height\*\* (`0.04` is 43 px at 1080p, 86 px at 4K) so the same style reads
identically at any resolution. It is resolved to pixels by [`TextStyle.face()`](#tituli.style.TextStyle.face)
once a frame is known.

The presets encode the style research (see `misc/docs/style.md`): sans-serif
working set, >= 36 px-equivalent at 1080p for anything meant to be read,
title-safe margins, tracked small caps for labels, generous leading.

```pycon
>>> s = TITLE.with_(size=0.1)
>>> s.size, s.weight
(0.1, 700)
>>> s.px(1080)
108
```

### Classes

| [`Halo`](#tituli.style.Halo)([color, spread, blur, gain, opacity])     | A soft glow under the glyphs: legibility over footage without a scrim (tituli#19).   |
|-------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------|
| [`TextStyle`](#tituli.style.TextStyle)([family, size, weight, italic, ...]) | How a run of text looks.                                                             |

### *class* tituli.style.Halo(color=None, spread=0.03, blur=0.1, gain=2.0, opacity=0.65)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A soft glow under the glyphs: legibility over footage without a scrim (tituli#19).

The glyphs’ own alpha, dilated by `spread`, blurred by `blur`, boosted by
`gain` and laid under the text at `opacity`. Sizes are in em (the
run’s type size: runs of different sizes get their own halo), so one halo
is right at any resolution. `color` `None` is the opposite of the ink:
dark under light text, light under dark.

The defaults give a soft glow that keeps letter shapes, for regular-weight
type. Thin type over very bright footage takes a heavier one, e.g.
`Halo(spread=0.08, blur=0.15, gain=3, opacity=0.8)` (a 12 %-of-height
EB Garamond italic over sand); on heavy type that one fills the counters.

### *class* tituli.style.TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.04, weight=400, italic=False, condensed=False, color=(255, 255, 255), tracking=0.0, leading=1.2, case='as-is', align='center', opacity=1.0, features=())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

How a run of text looks. All fields keyword-only; build variants with `with_`.

#### face(frame_height)

The resolved, sized font for this style.

* **Return type:**
  [`Face`](tituli.fonts.html.md#tituli.fonts.Face)

#### features *: [Union](https://docs.python.org/3/library/typing.html#typing.Union)[[Sequence](https://docs.python.org/3/library/typing.html#typing.Sequence)[[str](https://docs.python.org/3/builtins/stdtypes.html#str)], [Mapping](https://docs.python.org/3/library/typing.html#typing.Mapping)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [bool](https://docs.python.org/3/builtins/functions.html#bool)]]* *= ()*

`("tnum",)` or `{"tnum": True}`
(tituli#4). Kept as a tuple of tags; `fonts.Face.applied_features`
says which ones the resolved font has.

* **Type:**
  OpenType features to apply, by tag

#### px(frame_height)

Font size in pixels for a frame of that height.

* **Return type:**
  [`int`](https://docs.python.org/3/builtins/functions.html#int)

#### with_(\*\*changes)

A copy with some fields replaced.

```pycon
>>> TextStyle().with_(weight=700).weight
700
```

* **Return type:**
  [`TextStyle`](#tituli.style.TextStyle)
