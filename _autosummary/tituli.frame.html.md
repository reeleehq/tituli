# tituli.frame

The frame: what the layout engine is allowed to know about the picture.

This module is the answer to “is a text-only video a special case of text over
video?” — yes, and the axis that unifies them is \*\*how much the layout engine
knows about the frame\*\*, a ladder:

| rung   | the Frame knows            | so the engine can                                                                                        |
|--------|----------------------------|----------------------------------------------------------------------------------------------------------|
|        | only its size              | place by anchor; must assume the<br/>worst and put a scrim under text                                    |
|        | a solid background colour  | choose ink by contrast, no scrim                                                                         |
|        | the actual pixels          | sample luminance under a candidate<br/>box; choose ink; scrim only if the<br/>patch is mid-toned or busy |
|        | 1. + regions to keep clear | rank candidate positions by how<br/>little they cover the subject                                        |

A single [`Frame`](#tituli.frame.Frame) type carries all four rungs; every rung is optional and
the engine asks (`luminance_under`, `overlap`) rather than branching on kind.
The regions-to-avoid input is one keyword, `avoid=`, which takes boxes \*or a
callable\* `image -> box(es)` — the shape of `burns.salient_box` and of
`burns.FacesDetector` — so subject detection plugs in without a dependency.

```pycon
>>> f = Frame.blank((1920, 1080))
>>> f.luminance_under(f.safe) is None      # rung (a): unknown
True
>>> Frame.blank((1920, 1080), color="#fff").luminance_under(f.safe)
1.0
```

### Functions

| [`cover_fit`](#tituli.frame.cover_fit)(img, size)     | Scale `img` to fill `size` and crop the overflow, centred.   |
|---------------------------------------------------------------------------|--------------------------------------------------------------|
| [`reserved_zones`](#tituli.frame.reserved_zones)(delivery) | Normalised boxes a delivery target keeps for itself.         |

### Classes

| [`Frame`](#tituli.frame.Frame)(width, height[, color, image, avoid, ...])   | Size plus whatever else is known about the picture text will sit on.   |
|-----------------------------------------------------------------------------------------------------|------------------------------------------------------------------------|

### *class* tituli.frame.Frame(width, height, color=None, image=None, avoid=(), reserved=(), samples=())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Size plus whatever else is known about the picture text will sit on.

#### *classmethod* blank(size=(1920, 1080), , color=None)

Rung (a) when `color` is None, rung (b) when it is given.

* **Return type:**
  [`Frame`](#tituli.frame.Frame)

#### *classmethod* from_image(image, , avoid=None, size=None, delivery=None)

Rung (c), and rung (d) when `avoid` is given.

`image` may also be a **sequence** of frames (the stills a camera move
will pass through under the text): the first is what gets composited,
all of them feed [`luminance_stats()`](#tituli.frame.Frame.luminance_stats), which then reports the *worst*
instant — so a scrim is as light as the whole window allows, not as
heavy as one frame demands.

`avoid` is normalised boxes, or a callable taking the PIL image and
returning one box or several (`burns.salient_box` fits directly). It
runs on every sampled frame. `size` cover-fits the picture(s) to the
frame first. `delivery` names a target whose reserved zones
(`"youtube"`: subtitle band + control bar) placement must keep clear.

* **Return type:**
  [`Frame`](#tituli.frame.Frame)

#### luminance_stats(box)

`(mean, stddev)` of relative luminance under `box`; None if unknown.

A high stddev means a busy patch — even a well-contrasted mean will not
keep every glyph readable, which is when a scrim earns its place.

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`float`](https://docs.python.org/3/builtins/functions.html#float), [`float`](https://docs.python.org/3/builtins/functions.html#float)] | [`None`](https://docs.python.org/3/builtins/constants.html#None)

#### luminance_under(box)

Mean relative luminance of the pixels under `box`; None if unknown.

* **Return type:**
  [`float`](https://docs.python.org/3/builtins/functions.html#float) | [`None`](https://docs.python.org/3/builtins/constants.html#None)

#### *classmethod* over(stills, , avoid=None, size=None, delivery=None)

The frame a caption will sit on *over a time window* of stills.

The named entry point for the sequence case: the first still is what
gets composited, all of them are sampled, and `luminance_stats`
reports the worst instant — so a scrim over a Ken Burns move is as
light as the whole window allows. (`from_image` accepts a sequence
too; this name says what it is for.)

* **Return type:**
  [`Frame`](#tituli.frame.Frame)

#### overlap(box)

Fraction of `box` that covers something in `avoid` (0 when nothing).

* **Return type:**
  [`float`](https://docs.python.org/3/builtins/functions.html#float)

#### place(size, , anchor='auto', region=None)

Where to put a block of `size`: a named anchor and its pixel box.

`anchor` may be one name, a preference list, or `"auto"` (the default
order). With rung (d) knowledge the candidate that least covers the
subject wins; ties fall to preference order.

```pycon
>>> f = Frame.blank((1000, 500))
>>> f.place((200, 50), anchor="bottom")[0]
'bottom'
```

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Box`](tituli.geometry.html.md#tituli.geometry.Box)]

#### *property* safe *: [Box](tituli.geometry.html.md#tituli.geometry.Box)*

The title-safe box (SMPTE ST 2046-1, 90 %).

#### with_avoid(avoid)

Same frame with (additional) regions to keep clear.

* **Return type:**
  [`Frame`](#tituli.frame.Frame)

#### with_delivery(delivery)

Same frame, placement keeping clear of that target’s reserved zones.

* **Return type:**
  [`Frame`](#tituli.frame.Frame)

### tituli.frame.cover_fit(img, size)

Scale `img` to fill `size` and crop the overflow, centred.

```pycon
>>> cover_fit(Image.new("RGB", (100, 50)), (50, 50)).size
(50, 50)
```

* **Return type:**
  `Image`

### tituli.frame.reserved_zones(delivery)

Normalised boxes a delivery target keeps for itself.

```pycon
>>> reserved_zones("youtube")
((0.0, 0.78, 1.0, 0.22),)
>>> reserved_zones(None)
()
```

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`float`](https://docs.python.org/3/builtins/functions.html#float), [`float`](https://docs.python.org/3/builtins/functions.html#float), [`float`](https://docs.python.org/3/builtins/functions.html#float), [`float`](https://docs.python.org/3/builtins/functions.html#float)], [`...`](https://docs.python.org/3/builtins/constants.html#Ellipsis)]
