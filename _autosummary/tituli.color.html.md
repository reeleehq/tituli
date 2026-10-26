# tituli.color

Colours, WCAG contrast, and the ink-for-this-background decision.

Everything here is pure arithmetic on `(r, g, b[, a])` tuples in 0–255, so it
costs nothing to import and is easy to test.

```pycon
>>> contrast_ratio((255, 255, 255), (0, 0, 0))
21.0
>>> ink_for(luminance=0.9)   # light background -> dark ink
(17, 17, 17)
>>> ink_for(luminance=0.1)   # dark background -> light ink
(255, 255, 255)
```

### Functions

| [`contrast_from_luminance`](#tituli.color.contrast_from_luminance)(ink, luminance)    | Contrast of `ink` over a background of known relative luminance.       |
|---------------------------------------------------------------------------------------------|------------------------------------------------------------------------|
| [`contrast_ratio`](#tituli.color.contrast_ratio)(a, b)                       | WCAG contrast ratio between two colours (1..21).                       |
| [`ink_for`](#tituli.color.ink_for)(\*, luminance[, light, dark])      | Pick the ink (light or dark) with more contrast against `luminance`.   |
| [`mean_luminance`](#tituli.color.mean_luminance)(pixels)                     | Mean relative luminance of a pixel sample.                             |
| [`mix`](#tituli.color.mix)(a, b, t)                               | Linear blend, `t=0` -> `a`, `t=1` -> `b`.                              |
| [`needs_scrim`](#tituli.color.needs_scrim)(ink, luminance, \*[, minimum]) | Whether `ink` over that background falls short of `minimum` contrast.  |
| [`parse_color`](#tituli.color.parse_color)(color)                         | Accept `"#rgb"`, `"#rrggbb"`, `"#rrggbbaa"`, a Pillow name or a tuple. |
| [`relative_luminance`](#tituli.color.relative_luminance)(color)                  | WCAG relative luminance in 0..1.                                       |
| [`with_alpha`](#tituli.color.with_alpha)(color, alpha)                   | Same colour with opacity `alpha` in 0..1.                              |

### tituli.color.contrast_from_luminance(ink, luminance)

Contrast of `ink` over a background of known relative luminance.

* **Return type:**
  [`float`](https://docs.python.org/3/builtins/functions.html#float)

### tituli.color.contrast_ratio(a, b)

WCAG contrast ratio between two colours (1..21).

```pycon
>>> round(contrast_ratio("#777", "#fff"), 2)
4.48
```

* **Return type:**
  [`float`](https://docs.python.org/3/builtins/functions.html#float)

### tituli.color.ink_for(, luminance, light=(255, 255, 255), dark=(17, 17, 17))

Pick the ink (light or dark) with more contrast against `luminance`.

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`int`](https://docs.python.org/3/builtins/functions.html#int), [`int`](https://docs.python.org/3/builtins/functions.html#int), [`int`](https://docs.python.org/3/builtins/functions.html#int)]

### tituli.color.mean_luminance(pixels)

Mean relative luminance of a pixel sample.

* **Return type:**
  [`float`](https://docs.python.org/3/builtins/functions.html#float)

### tituli.color.mix(a, b, t)

Linear blend, `t=0` -> `a`, `t=1` -> `b`.

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`int`](https://docs.python.org/3/builtins/functions.html#int), [`int`](https://docs.python.org/3/builtins/functions.html#int), [`int`](https://docs.python.org/3/builtins/functions.html#int), [`int`](https://docs.python.org/3/builtins/functions.html#int)]

### tituli.color.needs_scrim(ink, luminance, , minimum=4.5)

Whether `ink` over that background falls short of `minimum` contrast.

```pycon
>>> needs_scrim((255, 255, 255), luminance=0.5)
True
>>> needs_scrim((255, 255, 255), luminance=0.02)
False
```

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

### tituli.color.parse_color(color)

Accept `"#rgb"`, `"#rrggbb"`, `"#rrggbbaa"`, a Pillow name or a tuple.

```pycon
>>> parse_color("#fff")
(255, 255, 255, 255)
>>> parse_color((10, 20, 30))
(10, 20, 30, 255)
```

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`int`](https://docs.python.org/3/builtins/functions.html#int), [`int`](https://docs.python.org/3/builtins/functions.html#int), [`int`](https://docs.python.org/3/builtins/functions.html#int), [`int`](https://docs.python.org/3/builtins/functions.html#int)]

### tituli.color.relative_luminance(color)

WCAG relative luminance in 0..1.

```pycon
>>> round(relative_luminance((255, 255, 255)), 3)
1.0
>>> relative_luminance((0, 0, 0))
0.0
```

* **Return type:**
  [`float`](https://docs.python.org/3/builtins/functions.html#float)

### tituli.color.with_alpha(color, alpha)

Same colour with opacity `alpha` in 0..1.

```pycon
>>> with_alpha("#000", 0.5)
(0, 0, 0, 128)
```

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`int`](https://docs.python.org/3/builtins/functions.html#int), [`int`](https://docs.python.org/3/builtins/functions.html#int), [`int`](https://docs.python.org/3/builtins/functions.html#int), [`int`](https://docs.python.org/3/builtins/functions.html#int)]
