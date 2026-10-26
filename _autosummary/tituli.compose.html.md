# tituli.compose

The composed pieces: title cards, captions with attribution, lower thirds.

Each function turns a few strings into a [`Layout`](tituli.layout.html.md#tituli.layout.Layout) placed
on a [`Frame`](tituli.frame.html.md#tituli.frame.Frame), applying the ink-and-scrim decision the frame’s
knowledge allows. The pipeline order is fixed and matters: \*\*shape/wrap →
measure → decide ink → cut the scrim to the measured block → compose\*\*. A scrim
sized before the text is measured is how a three-line caption ends up hanging
off its own backdrop.

```pycon
>>> from tituli.frame import Frame
>>> lay = title_card("The Apple", "a concrete poem", frame=Frame.blank((1920, 1080)))
>>> "".join(r.text for r in lay.runs)      # tracked styles set one run per glyph
'The Applea concrete poem'
>>> lay.meta["anchor"], lay.meta["ink"]
('center', 'background unknown: white on dark scrim')
```

### Functions

| [`decide_ink`](#tituli.compose.decide_ink)(frame, box, \*[, preferred])          | Choose ink and whether a scrim is needed under `box`.                      |
|---------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------|
| [`truncate`](#tituli.compose.truncate)(text, style, frame_height, \*, ...)     | Wrap and hard-truncate with an ellipsis at `max_lines` lines.              |
| [`title_card`](#tituli.compose.title_card)(title[, subtitle, kicker, ...])       | An opening card: optional kicker, title, optional subtitle.                |
| [`caption`](#tituli.compose.caption)(text[, attribution, anchor, style, ...]) | A museum label over a picture: what is on screen, plus a tiny credit line. |
| [`lower_third`](#tituli.compose.lower_third)(name[, role, anchor, ...])           | Who is speaking: a name and a role, left-anchored, scrimmed if needed.     |
| [`note`](#tituli.compose.note)(lines, \*, frame[, headline, anchor, ...])  | An editorial context card: an optional headline over equal-weight lines.   |
| [`intertitle`](#tituli.compose.intertitle)(text, \*, frame[, style, engine])     | A silent-film style card: serif italic prose, centred on the frame.        |

### Classes

| [`InkDecision`](#tituli.compose.InkDecision)(ink, scrim, luminance, reason)   | What the frame told us to do about legibility.   |
|-----------------------------------------------------------------------------------------------|--------------------------------------------------|

### *class* tituli.compose.InkDecision(ink, scrim, luminance, reason)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

What the frame told us to do about legibility.

### tituli.compose.caption(text, attribution='', , frame, anchor='auto', style=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.04, weight=600, italic=False, condensed=False, color=(255, 255, 255), tracking=0.0, leading=1.25, case='as-is', align='left', opacity=1.0, features=()), attribution_style=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.02, weight=400, italic=False, condensed=False, color=(255, 255, 255), tracking=0.03, leading=1.2, case='as-is', align='left', opacity=0.85, features=()), max_lines=3, max_width=0.55, ink=None, scrim=None, accent=True, on_overflow='fit', engine=None)

A museum label over a picture: what is on screen, plus a tiny credit line.

`text` is wrapped to `max_width` of the safe box and **shrunk to fit**
within `max_lines` rather than cut; `attribution` is set small and
slightly transparent — present enough to credit, small enough not to
compete. If the words cannot be set legibly this raises
[`TextDoesNotFit`](tituli.html.md#tituli.TextDoesNotFit); pass `on_overflow="truncate"` for text whose
length you do not control (see `OVERFLOW_POLICIES`). Placement avoids the
frame’s `avoid` boxes and its delivery target’s reserved zones; the
scrim is a 2-D corner falloff cut to the measured block.

* **Return type:**
  [`Layout`](tituli.layout.html.md#tituli.layout.Layout)

### tituli.compose.decide_ink(frame, box, , preferred=None)

Choose ink and whether a scrim is needed under `box`.

Rung (a) (nothing known): white on a dark scrim, the universal default.
Rung (b)/(c): the ink with more contrast; a scrim only when contrast is still
short of WCAG 4.5:1 or the patch is busy. `preferred` is honoured when it
already has enough contrast.

* **Return type:**
  [`InkDecision`](#tituli.compose.InkDecision)

### tituli.compose.intertitle(text, , frame, style=None, engine=None)

A silent-film style card: serif italic prose, centred on the frame.

* **Return type:**
  [`Layout`](tituli.layout.html.md#tituli.layout.Layout)

### tituli.compose.lower_third(name, role='', , frame, anchor='bottom-left', name_style=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.042, weight=700, italic=False, condensed=False, color=(255, 255, 255), tracking=0.0, leading=1.2, case='as-is', align='left', opacity=1.0, features=()), role_style=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.026, weight=400, italic=False, condensed=False, color=(255, 255, 255), tracking=0.04, leading=1.2, case='as-is', align='left', opacity=0.9, features=()), ink=None, scrim=None, on_overflow='fit', engine=None)

Who is speaking: a name and a role, left-anchored, scrimmed if needed.

Respects the frame’s delivery zones — with `delivery="youtube"` the block
moves above the subtitle band rather than into it.

The name and role are **shrunk to fit** rather than cut, and
[`TextDoesNotFit`](tituli.html.md#tituli.TextDoesNotFit) is raised if they cannot be set legibly. A lower
third reading `1981 · Centr…` once shipped in a finished film; that is not
a shortened label but a false one.

* **Return type:**
  [`Layout`](tituli.layout.html.md#tituli.layout.Layout)

### tituli.compose.note(lines, , frame, headline='', anchor='top-left', headline_style=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.055, weight=700, italic=False, condensed=False, color=(255, 255, 255), tracking=0.0, leading=1.15, case='as-is', align='left', opacity=1.0, features=()), line_style=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.03, weight=400, italic=False, condensed=False, color=(255, 255, 255), tracking=0.0, leading=1.4, case='as-is', align='left', opacity=0.92, features=()), max_width=0.62, ink=None, scrim=None, accent=True, on_overflow='fit', engine=None)

An editorial context card: an optional headline over equal-weight lines.

The block for what the audio assumes and a cold viewer does not have
(“what *Hamilton* is”, “Philip died at 19”). Heavier than a caption —
schedule it with a higher `weight` so the two never share a corner. Each
line wraps to `max_width` of the safe box, shrinking to fit within
`_NOTE_MAX_LINES` rows rather than being cut; every line shares the
smallest size any of them needed, so the block reads as one block.
Raises [`TextDoesNotFit`](tituli.html.md#tituli.TextDoesNotFit) if a line cannot be set legibly.

* **Return type:**
  [`Layout`](tituli.layout.html.md#tituli.layout.Layout)

### tituli.compose.title_card(title, subtitle='', , frame, kicker='', anchor='center', title_style=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.075, weight=700, italic=False, condensed=False, color=(255, 255, 255), tracking=-0.01, leading=1.1, case='as-is', align='center', opacity=1.0, features=()), subtitle_style=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.032, weight=400, italic=False, condensed=False, color=(255, 255, 255), tracking=0.02, leading=1.3, case='as-is', align='center', opacity=1.0, features=()), kicker_style=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.022, weight=500, italic=False, condensed=False, color=(255, 255, 255), tracking=0.18, leading=1.2, case='upper', align='center', opacity=1.0, features=()), ink=None, scrim=None, engine=None)

An opening card: optional kicker, title, optional subtitle.

Fits the title to 80 % of the safe width (shrinking, never clipping), stacks
the parts with a gap proportional to the type, places the block at
`anchor` (subject-avoiding when the frame knows the picture), and picks
ink by the frame’s contrast. `scrim` forces a scrim on/off; None decides.

* **Return type:**
  [`Layout`](tituli.layout.html.md#tituli.layout.Layout)

### tituli.compose.truncate(text, style, frame_height, , max_width, max_lines, engine=None)

Wrap and hard-truncate with an ellipsis at `max_lines` lines.

For text whose length you do not control (a licence template blob pasted
into an artist field). The result always fits.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)
