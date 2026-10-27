---
name: tituli
description: Put tasteful text on video or stills with the `tituli` Python package — title cards, end credits from structured data, captions with a tiny source attribution that stay off the subject, lower thirds, editorial context notes, and calligrams / concrete poems (text along a circle, wave, SVG path, or falling like Apollinaire's "Il pleut"). Use when asked to "add credits", "add a title card", "caption this image", "label these stills", "put a name and role on screen", "add context cards", "overlay text on this video", "make a calligram", "text on a path", or when a film needs on-screen text that looks designed rather than debug-dumped. Owns placement (title-safe, subject-avoiding, YouTube subtitle band reserved), ink/scrim by contrast, wrapping and shrink-to-fit, scheduling of captions against heavier cards, and ffmpeg compositing. Not for SRT subtitles (use `mixing`).
license: MIT
metadata:
  audience: users
---

# tituli — text in video

`pip install tituli` (Pillow only). Video output needs `ffmpeg` on PATH (only `overlay`/`fade`/`crop`; never `drawtext`). Extras: `[saliency]` (burns, subject avoidance), `[shaping]` (HarfBuzz), `[lacing]`, `[cli]`.

## The one model

Every call returns a `Layout`; `render(layout, frame)` gives an image; `tituli.video.*` puts images on footage. A `Frame` says how much is known about the picture:

```python
from tituli import Frame

Frame.blank((1920, 1080))  # knows only its size -> white on a dark scrim
Frame.blank((1920, 1080), color="#101014")  # solid colour -> ink by contrast, no scrim
Frame.from_image(
    "still.jpg", delivery="youtube"
)  # samples pixels; keeps the subtitle band clear
Frame.from_image("still.jpg", avoid=burns.salient_box)  # ...and keeps off the subject
Frame.over(
    ["f01.jpg", "f02.jpg", "f03.jpg"], avoid=burns.salient_box
)  # the frames under a camera move; worst instant wins
```

## Recipes

**Centred text over footage without darkening it**: a halo instead of a scrim.
```python
# or halo=Halo(spread=0.08, blur=0.15, gain=3, opacity=0.8) for thin type
caption("AI imagining…", frame=f, anchor="center", halo=True)
```

**Text as geometry** (no font engine downstream — e.g. an animation runtime that draws SVG): lay out with a deterministic face, then take each run's contours.
```python
from tituli import EMBEDDED, TextStyle, block, face_digest, run_outline

lay = block(
    "Words on screen", TextStyle(family=(EMBEDDED,), size=0.08), 1080, unit="word"
)
paths = [
    run_outline(r).d for r in lay.runs
]  # SVG `d`, frame pixels; needs tituli[outlines]
font_id = face_digest(lay.runs[0].face)  # sha256 of the font bytes: record it
```
`EMBEDDED` never scans installed fonts (same bytes on every machine with the same Pillow); a font-file path in `family` works too. A character the face lacks raises `MissingGlyphError`.

**Title card** (PNG, or MP4 with a duration):
```python
from tituli import Frame, title_card, render

f = Frame.blank((1920, 1080), color="#101014")
render(title_card("The Apple", "a concrete poem", kicker="Episode 3", frame=f), f).save(
    "title.png"
)
# video: tituli.video.still(image, "title.mp4", duration=4)
```

**Caption + tiny attribution on a still** — text is wrapped and *shrunk to fit* for you (never cut); attribution is small on purpose:
```python
from tituli import Frame, caption, render

f = Frame.from_image(
    "still.jpg", delivery="youtube"
)  # add avoid=burns.salient_box if burns is installed
lay = caption(
    "Angelica Schuyler Church", "John Trumbull, 1785 · public domain", frame=f
)
render(lay, f).save(
    "captioned.png"
)  # or render_overlay(lay, f.size) for a transparent PNG
```

**Lower third / context note**: `lower_third("Eliza Hamilton", "née Schuyler", frame=f)`; `note(["What Hamilton is", "Who Chernow is"], headline="Before we go on", frame=f)`.

**Credits** — structured, never a wall of filenames, never truncated:
```python
from tituli import Credits, credits_cards, credits_crawl, credits_frame, render, Frame

cr = Credits.from_dict(
    {
        "title": "The Apple",
        "sections": [
            {"heading": "Voices", "entries": [["Narrator", "T. Whalen"]]},
            {"heading": "Images", "entries": ["Still Life — Cézanne — public domain"]},
        ],
        "closing": ["Made with tituli"],
    }
)
f = credits_frame((1920, 1080))
for i, card in enumerate(credits_cards(cr, frame=f)):
    render(card, f).save(f"credits_{i}.png")
lay, total = credits_crawl(
    cr, frame=f
)  # then tituli.video.crawl(render(lay, Frame.blank((1920, total), color=f.color)), "credits.mp4", size=(1920,1080), speed_px_s=97)
```
`Credits.from_lines(lines)` takes a plain list (braidio's `credits_card` shape).

**Captions on a finished film** (composite onto the motion video, never into the stills):
```python
from tituli import Span, Label, UNLABELLED, schedule_labels, TimedOverlay, resolve, note
from tituli.video import overlay
f = Frame.blank((1920, 1080)).with_delivery("youtube")
cards = [TimedOverlay(note([...], headline="...", frame=f), 12.0, 18.0, slot="top-left", weight=2)]
spans = [Span(start, end, key=still_id) for ...]                  # your cut
labels = schedule_labels(spans, lambda s: Label(text, attribution) if known else UNLABELLED, suppressed_by=cards)
overlay("film.mp4", resolve([*cards, *labels]), "film_captioned.mp4")   # renders Label payloads itself; raises naming anything it can't
```
Rules built in: label on first appearance, again only after 150 s, truncated (not dropped) against a heavier card, and a suppressed label is not counted as shown. Returning `None` from `label_for` raises — say `UNLABELLED` when a still is deliberately unlabelled.

**A page of several blocks** (headline, glossed glyph row, a wrapped `a · b` list, a footnote) is one `Layout` — never measure-and-translate by hand, never composite one PNG per block:
```python
from tituli import Frame, TextStyle, block, glossed, render, stack

f = Frame.blank((1920, 1080), color="#14161f")
page = stack(
    [
        block("Sing along to learn 7 katakana", TextStyle(size=0.05, weight=700), f),
        glossed(
            [("カ", "ka"), ("ス", "su"), ("ン", "n")], frame=f, anchor=None
        ),  # glyph over reading, one pitch
        block(
            "バス bus · スープ soup · …",
            TextStyle(size=0.027),
            f,
            max_width=0.86 * f.width,
            break_at=" · ",
        ),
    ],
    frame=f,
    gap=[0.06, 0.05],
)  # fractions of frame height, one per seam; placed centred in title-safe
render(page, f).save("title.png")
```
`grid(blocks, columns=3, frame=f)` for cells on one pitch. Nested combinators take `anchor=None`. `break_at` wraps a list only between items; U+00A0 keeps two words together anywhere.

**Title over the intro** (no hand ffmpeg): `overlay("film.mp4", [TimedOverlay(None, 0, 3, image="title.png", fade_in=0, fade_out=0.25)], "out.mp4", pad_start=0.8)` — the head is padded (first frame held; `pad_mode="black"` for black), audio delayed to match, and overlay times are on the padded timeline. An image must be the video's size (it raises otherwise).

**Calligram**: `on_path(text, shape="circle"|"wave"|"arc"|"M 0 0 C ..."|Path, frame=f, upright=False)`; `rain(lines, frame=Frame.blank((1080, 1920), color="#f4f1e8"))` (portrait); `in_shape(text, mask_image, frame=f)`. A glyph-by-glyph reveal: `lay.staggered(step=0.05, ramp=0.2)` → `tituli.video.frames_to_video(frames(lay, f, duration=6), "out.mp4", size=f.size)`.

## CLI

`python -m tituli title_card "Title" "sub" --background "#101014" --out t.png` · `python -m tituli caption still.jpg "text" "source" --out c.png` · `python -m tituli credits spec.json --mode crawl --out credits.mp4` · `python -m tituli calligram "text" --shape circle --out c.png` · `python -m tituli overlay_video film.mp4 overlays.json --out out.mp4` · `python -m tituli fonts Helvetica`.

**A number that changes (a counter, a clock) asks for tabular figures:** `TextStyle(features=("tnum",))`, so "11" is as wide as "88" and the text does not jitter. Check `style.face(h).applied_features`: a font without `tnum` measures as before (the embedded face's digits are already one width). Measure and outline with it (`run_outline`), or draw with `HarfBuzzEngine`; the Pillow engine refuses a run whose glyphs a feature changes.

## Your words are set complete, or not at all

`caption`, `lower_third` and `note` never truncate text you wrote. They shrink the
type until it fits, and if that would take it below legibility
(`MIN_LEGIBLE_SIZE`, 2.2 % of frame height) they raise `TextDoesNotFit` instead.
**The raise is the feature** — it is handing you a decision only you can make.

The trap it closes: type is sized as a fraction of frame **height** but has to fit
the frame's **width**. On 1920×1080 a lower third at 0.042 em is 45 px tall against
1920 px of width and fits easily; on **1080×1920 the same call is 81 px tall against
1080 px of width** and overflows. A short that shipped with `1981 · Centr…` burnt in
had been checked on landscape. Test portrait, or trust the raise.

When you catch `TextDoesNotFit`, pick one — in this order:

```python
try:
    lay = lower_third("1981 · Central Park, live", frame=f)
except TextDoesNotFit:
    lay = lower_third("1981 · Central Park", frame=f)  # 1. shorter wording
    # 2. more lines:  caption(text, frame=f, max_lines=4)
    # 3. wider box:   caption(text, frame=f, max_width=0.9)
    # 4. don't show it — an absent label beats a false one
```

Shortening is a judgement call about meaning, which is why the package will not
make it for you: `1981 · Centr…` tells the viewer the recording is from somewhere
called Centr. `1981` tells them less and lies about nothing.

The one exception is text whose length you genuinely do **not** control — a licence
template that some upstream pasted into an artist field. Ask for the old behaviour
by name: `caption(blob, frame=f, on_overflow="truncate")`. Never for words you wrote.

## The bottom of the frame is not yours

`Frame.with_delivery("youtube")` reserves the bottom ~22% — the subtitle track,
the control bar, and on a vertical Short the title, channel line and action rail.
That reservation now binds **whatever anchor you named**: a block that would land
in the band is slid the shortest way out of it, keeping the anchor you asked for.
Before this it only bound on `anchor="auto"`, so every `lower_third` (which names
`"bottom-left"`) sat at 95% of frame height, under YouTube's own furniture.

So `anchor="bottom-left"` means "as low as the platform allows", not "at the
bottom edge". If you genuinely want the last pixel row, build the frame without a
delivery target.

## Taste rules the defaults already follow

Title-safe 90 %; WCAG 4.5:1 target; sans working set (Helvetica Neue → Inter → … → DejaVu Sans) with Pillow's Aileron as the last fallback; ≥ 36 px-equivalent at 1080p for anything meant to be read; attribution ~22 px and 85 % opacity; credits hold ≥ 3 s / crawl ≈ 97 px/s; reveals 0.4 s; corner-falloff scrim cut to the text block, only when contrast or busyness demands it. Sizes are fractions of frame height, so the same call is right at 720p and 4K. Don't override these unless asked.
