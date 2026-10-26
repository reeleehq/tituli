# tituli.credits

Credits: structured data in, designed cards or a crawl out.

The data model is the point. A credits roll is not a list of filenames; it is
*sections* of *entries*, each entry a role and a name (or just a name, or a
line of licence prose). Given that structure the layout can do what a title
designer does: tracked small-caps section headings, role/name pairs on a
shared gutter, a single column that reads top to bottom, generous leading, and
a **never-truncate** rule — attributions are a licence surface, so content that
does not fit paginates onto more cards or raises when the caller capped the
count; it is never silently dropped.

```pycon
>>> c = Credits.from_dict({
...     "title": "The Apple",
...     "sections": [{"heading": "Voices", "entries": [["Narrator", "A. Reader"]]},
...                  {"heading": "Images", "entries": ["Still Life — Cézanne — public domain"]}],
... })
>>> len(c.sections), c.sections[0].entries[0].role
(2, 'Narrator')
```

### Functions

| [`credits_crawl`](#tituli.credits.credits_crawl)(credits, \*, frame[, style, engine])   | One tall layout and its total height in pixels (for [`tituli.video.crawl()`](tituli.video.html.md#tituli.video.crawl)).   |
|-------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------|
| [`credits_cards`](#tituli.credits.credits_cards)(credits, \*, frame[, style, ...])      | Paginate the roll into cards that each fit the safe area, centred.                                                                               |
| [`credits_frame`](#tituli.credits.credits_frame)(size[, style])                         | The canonical credits frame: near-black, so ink defaults to white.                                                                               |

### Classes

| [`Entry`](#tituli.credits.Entry)(name[, role])                             | One credit line: `role` + `name`, a bare `name`, or prose.   |
|--------------------------------------------------------------------------------------------------|--------------------------------------------------------------|
| [`Section`](#tituli.credits.Section)([heading, entries, kind])               | A heading over a run of entries.                             |
| [`Credits`](#tituli.credits.Credits)([sections, title, closing, meta])       | The whole roll.                                              |
| [`CreditsStyle`](#tituli.credits.CreditsStyle)([title, heading, role, name, ...]) | The type ramp for a roll.                                    |

### *class* tituli.credits.Credits(sections=(), title='', closing=(), meta=dict())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

The whole roll.

#### *classmethod* from_dict(d)

Build from `{"title", "sections": [{"heading", "entries", "kind"}], "closing"}`.

The caller owns making the text presentable: tituli sets whatever it is
given, so a raw manifest — camera filenames as roles, `"Unknown
authorUnknown author"` from a concatenated field — comes out as a
designed card of raw manifest strings. Map titles, artists and
licences into readable roles and names first.

* **Return type:**
  [`Credits`](#tituli.credits.Credits)

#### *classmethod* from_lines(lines, , heading='Credits', title='')

The plain-list case (what `braidio.video.credits_card` takes).

Each line is set as prose, verbatim. Lines built from a fetch manifest
(`"<file> — <author> — <licence>"`) read as a terminal dump however
well they are typeset; prefer [`from_dict()`](#tituli.credits.Credits.from_dict) with `{"role", "name"}`
entries (“Portrait of Eliza Hamilton”, “Ralph Earl, 1787 · public domain”).

* **Return type:**
  [`Credits`](#tituli.credits.Credits)

### *class* tituli.credits.CreditsStyle(title=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.06, weight=700, italic=False, condensed=False, color=(255, 255, 255), tracking=-0.005, leading=1.2, case='as-is', align='center', opacity=1.0, features=()), heading=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.024, weight=500, italic=False, condensed=False, color=(255, 255, 255), tracking=0.22, leading=1.2, case='upper', align='center', opacity=0.75, features=()), role=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.026, weight=400, italic=False, condensed=False, color=(255, 255, 255), tracking=0.03, leading=1.2, case='as-is', align='right', opacity=0.8, features=()), name=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.032, weight=600, italic=False, condensed=False, color=(255, 255, 255), tracking=0.0, leading=1.2, case='as-is', align='left', opacity=1.0, features=()), line=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.03, weight=400, italic=False, condensed=False, color=(255, 255, 255), tracking=0.0, leading=1.4, case='as-is', align='center', opacity=1.0, features=()), ink=(255, 255, 255), background=(8, 8, 10))

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

The type ramp for a roll. One object so a film is one design.

### *class* tituli.credits.Entry(name, role='')

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

One credit line: `role` + `name`, a bare `name`, or prose.

### *class* tituli.credits.Section(heading='', entries=(), kind='auto')

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A heading over a run of entries. `kind` picks the treatment:

`"pairs"` role/name on a gutter (cast, crew); `"list"` centred names;
`"prose"` wrapped small text (licences, thanks).

### tituli.credits.credits_cards(credits, , frame, style=CreditsStyle(title=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.06, weight=700, italic=False, condensed=False, color=(255, 255, 255), tracking=-0.005, leading=1.2, case='as-is', align='center', opacity=1.0, features=()), heading=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.024, weight=500, italic=False, condensed=False, color=(255, 255, 255), tracking=0.22, leading=1.2, case='upper', align='center', opacity=0.75, features=()), role=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.026, weight=400, italic=False, condensed=False, color=(255, 255, 255), tracking=0.03, leading=1.2, case='as-is', align='right', opacity=0.8, features=()), name=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.032, weight=600, italic=False, condensed=False, color=(255, 255, 255), tracking=0.0, leading=1.2, case='as-is', align='left', opacity=1.0, features=()), line=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.03, weight=400, italic=False, condensed=False, color=(255, 255, 255), tracking=0.0, leading=1.4, case='as-is', align='center', opacity=1.0, features=()), ink=(255, 255, 255), background=(8, 8, 10)), max_cards=None, engine=None)

Paginate the roll into cards that each fit the safe area, centred.

A heading is never orphaned at the bottom of a card. Raises when
`max_cards` would force truncation — losing an attribution silently is a
licence failure invisible to the person responsible for it.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Layout`](tituli.layout.html.md#tituli.layout.Layout)]

### tituli.credits.credits_crawl(credits, , frame, style=CreditsStyle(title=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.06, weight=700, italic=False, condensed=False, color=(255, 255, 255), tracking=-0.005, leading=1.2, case='as-is', align='center', opacity=1.0, features=()), heading=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.024, weight=500, italic=False, condensed=False, color=(255, 255, 255), tracking=0.22, leading=1.2, case='upper', align='center', opacity=0.75, features=()), role=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.026, weight=400, italic=False, condensed=False, color=(255, 255, 255), tracking=0.03, leading=1.2, case='as-is', align='right', opacity=0.8, features=()), name=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.032, weight=600, italic=False, condensed=False, color=(255, 255, 255), tracking=0.0, leading=1.2, case='as-is', align='left', opacity=1.0, features=()), line=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.03, weight=400, italic=False, condensed=False, color=(255, 255, 255), tracking=0.0, leading=1.4, case='as-is', align='center', opacity=1.0, features=()), ink=(255, 255, 255), background=(8, 8, 10)), engine=None)

One tall layout and its total height in pixels (for [`tituli.video.crawl()`](tituli.video.html.md#tituli.video.crawl)).
`engine` is the one that will draw it; it measures the rows.

The layout starts one frame-height down and ends one frame-height before
its bottom, so the crawl enters from an empty frame and leaves to one.

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`Layout`](tituli.layout.html.md#tituli.layout.Layout), [`int`](https://docs.python.org/3/builtins/functions.html#int)]

### tituli.credits.credits_frame(size, style=CreditsStyle(title=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.06, weight=700, italic=False, condensed=False, color=(255, 255, 255), tracking=-0.005, leading=1.2, case='as-is', align='center', opacity=1.0, features=()), heading=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.024, weight=500, italic=False, condensed=False, color=(255, 255, 255), tracking=0.22, leading=1.2, case='upper', align='center', opacity=0.75, features=()), role=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.026, weight=400, italic=False, condensed=False, color=(255, 255, 255), tracking=0.03, leading=1.2, case='as-is', align='right', opacity=0.8, features=()), name=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.032, weight=600, italic=False, condensed=False, color=(255, 255, 255), tracking=0.0, leading=1.2, case='as-is', align='left', opacity=1.0, features=()), line=TextStyle(family=('Helvetica Neue', 'Inter', 'Helvetica', 'Avenir Next', 'Roboto', 'Univers', 'Liberation Sans', 'DejaVu Sans', 'Arial'), size=0.03, weight=400, italic=False, condensed=False, color=(255, 255, 255), tracking=0.0, leading=1.4, case='as-is', align='center', opacity=1.0, features=()), ink=(255, 255, 255), background=(8, 8, 10)))

The canonical credits frame: near-black, so ink defaults to white.

* **Return type:**
  [`Frame`](tituli.frame.html.md#tituli.frame.Frame)
