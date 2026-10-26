# tituli.tools

The SSOT of dispatchable operations: flat, JSON-able in, JSON-able out.

These are the functions every surface projects: the CLI (`python -m tituli`)
today, an MCP server or HTTP route tomorrow, an agent skill in prose. Nothing
here imports a surface library; each function takes paths and strings, writes
a file, and returns a dict describing what it wrote.

```pycon
>>> sorted(f.__name__ for f in _dispatch_funcs)
['calligram', 'caption', 'credits', 'fonts', 'lower_third', 'overlay_video', 'title_card']
```

### Functions

| [`calligram`](#tituli.tools.calligram)(text, \*[, out, shape, size, ...])     | Lay `text` along a shape (`circle`, `wave`, `arc`, an SVG path, `rain`).         |
|---------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------|
| [`caption`](#tituli.tools.caption)(image, text[, attribution, out, ...])    | Put a museum-label caption and a tiny attribution on `image`.                    |
| [`credits`](#tituli.tools.credits)(spec, \*[, out, mode, size, speed, ...]) | Render credits from a JSON spec file (or JSON string) to `out`.                  |
| [`fonts`](#tituli.tools.fonts)([query])                                   | List installed font families (optionally filtered by substring).                 |
| [`lower_third`](#tituli.tools.lower_third)(name[, role, out, background, ...])  | A name + role block, bottom-left, as a transparent overlay (or on a picture).    |
| [`overlay_video`](#tituli.tools.overlay_video)(video, overlays, \*[, out, ...])   | Composite captions/lower thirds/images onto a finished video in one ffmpeg pass. |
| [`title_card`](#tituli.tools.title_card)(title[, subtitle, out, ...])          | Render a title card to `out` (PNG, or MP4 when `duration` is given).             |

### tituli.tools.calligram(text, , out='calligram.png', shape='wave', size=None, background='#f4f1e8', upright=False, mask=None, reveal=None)

Lay `text` along a shape (`circle`, `wave`, `arc`, an SVG path, `rain`).

`shape="rain"` is Apollinaire’s *Il pleut* (lines become streaks; give
it a portrait `size`). `mask` (an image path, light = inside) pours the
text into a silhouette instead. `reveal` (seconds) writes an MP4 with a
glyph-by-glyph reveal rather than a PNG.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### tituli.tools.caption(image, text, attribution='', , out='captioned.png', anchor='auto', avoid='saliency', delivery='youtube', size=None, overlay_only=False, engine=None)

Put a museum-label caption and a tiny attribution on `image`.

Placement avoids the subject (`avoid="saliency"` uses `burns` when
installed, otherwise nothing is avoided) and the delivery target’s
reserved zones. `overlay_only` writes a transparent PNG to composite
onto motion video instead of the flattened picture. `engine` is
`"pillow"` (default) or `"harfbuzz"`.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### tituli.tools.credits(spec, , out='credits.mp4', mode='crawl', size=None, speed=None, hold=None, background=None, audio=None)

Render credits from a JSON spec file (or JSON string) to `out`.

Spec: `{"title": ..., "sections": [{"heading": ..., "entries":
[["Role", "Name"], "Name", ...]}], "closing": [...]}` — or a plain JSON
list of lines. `mode` is `"crawl"` (one MP4) or `"cards"` (PNG per
card, or one MP4 when `out` ends in .mp4). Never truncates.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### tituli.tools.fonts(query='')

List installed font families (optionally filtered by substring).

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### tituli.tools.lower_third(name, role='', , out='lower_third.png', background=None, size=None, delivery='youtube', engine=None)

A name + role block, bottom-left, as a transparent overlay (or on a picture).

`engine` is `"pillow"` (default) or `"harfbuzz"`.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### tituli.tools.overlay_video(video, overlays, , out='overlaid.mp4', delivery='youtube', pad_start=0.0, engine=None)

Composite captions/lower thirds/images onto a finished video in one ffmpeg pass.

`overlays` is a JSON file/string: a list of `{"start", "end", "text",
"attribution"?, "kind"?: "caption"|"lower_third", "role"?, "anchor"?}`
or `{"start", "end", "image", "fade_in"?, "fade_out"?}` (a frame-sized
PNG, e.g. a title page; it occupies its own slot and suppresses no
caption — time captions after it). Text is laid out against the video’s frame size;
the picture under each overlay is not sampled (pass a still through
`caption` for that). `pad_start` seconds are added at the head (first
frame held, audio delayed); overlay times are on the padded timeline.
`engine` is `"pillow"` (default) or `"harfbuzz"`: it measures and draws.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### tituli.tools.title_card(title, subtitle='', , out='title.png', background=None, size=None, kicker='', anchor='center', avoid=None, duration=None, engine=None)

Render a title card to `out` (PNG, or MP4 when `duration` is given).

`background` is a colour (`#101014`), an image path, or nothing (a
transparent overlay). `anchor` is a grid position; `avoid` is
`"saliency"` or `"x,y,w,h"` to keep the title off the subject.
`engine` is `"pillow"` (default) or `"harfbuzz"` (`tituli[shaping]`).

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)
