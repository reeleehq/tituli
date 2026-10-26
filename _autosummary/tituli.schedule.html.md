# tituli.schedule

When overlays appear: timed overlays, and a scheduler that owns the rules.

Two ways in, both whole:

* **You schedule.** Build [`TimedOverlay`](#tituli.schedule.TimedOverlay) objects at the times you want
  and hand them to [`tituli.video.overlay()`](tituli.video.html.md#tituli.video.overlay). tituli composites; it does
  not second-guess your times.
* **tituli schedules.** [`schedule_labels()`](#tituli.schedule.schedule_labels) derives one label per panel of
  a cut, with *first appearance*, *repeat gap* and \*suppression by a heavier
  overlay\* as first-class rules — and the suppression check lives **inside**
  the loop, so a label that loses its moment to a title card is not recorded
  as shown and gets its next chance. (That ordering bug once left the one
  portrait a cold viewer most needed named unlabelled for nine minutes.)

There is deliberately no middle: nothing here owns *some* of the timing and
leaves the caller to reconcile the rest.

A label is either a [`Label`](#tituli.schedule.Label) or the explicit `UNLABELLED` sentinel.
`None` is refused: a still left uncaptioned next to a captioned one is an
implicit claim about what it is, so “no caption” must be said, never defaulted.

```pycon
>>> spans = [Span(0, 5, "eliza"), Span(5, 10, "eliza"), Span(10, 15, "map")]
>>> labels = {"eliza": Label("Eliza Hamilton", "Ralph Earl, 1787"), "map": UNLABELLED}
>>> cards = [TimedOverlay(None, 0, 3, slot="top-left", weight=2)]
>>> out = schedule_labels(spans, lambda p: labels[p.key], suppressed_by=cards)
>>> [(round(o.start), round(o.end)) for o in out]   # first span lost to the card
[(5, 10)]
```

### Functions

| [`schedule_labels`](#tituli.schedule.schedule_labels)(spans, label_for, \*[, ...])   | One label per span, held `hold_s`, with the three rules built in.             |
|-------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------|
| [`resolve`](#tituli.schedule.resolve)(overlays, \*[, min_readable_s])        | Enforce one overlay per slot at a time: the heavier wins, the lighter yields. |

### Classes

| [`Label`](#tituli.schedule.Label)(text[, attribution, key])               | What goes on a museum label: the thing, and where it came from.   |
|------------------------------------------------------------------------------------------------|-------------------------------------------------------------------|
| [`Span`](#tituli.schedule.Span)(start, end, key[, data])                 | A time range of the cut showing one picture.                      |
| [`TimedOverlay`](#tituli.schedule.TimedOverlay)(layout, start, end[, slot, ...]) | A layout (or a thing to lay out) on screen from `start` to `end`. |

### *class* tituli.schedule.Label(text, attribution='', key=None)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

What goes on a museum label: the thing, and where it came from.

### *class* tituli.schedule.Span(start, end, key, data=None)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A time range of the cut showing one picture. `key` identifies the picture.

(Named `Span` rather than `Panel` so it never collides with
`braidio.video.Panel`, which callers of both will import alongside it.)

### *class* tituli.schedule.TimedOverlay(layout, start, end, slot='top-left', weight=1, fade=0.45, payload=None, meta=dict(), image=None, fade_in=None, fade_out=None)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A layout (or a thing to lay out) on screen from `start` to `end`.

`slot` names the region it occupies; `weight` orders overlays that
contend for a slot — the heavier suppresses the lighter, never stacks.
`payload` is whatever the caller wants to carry to rendering (a
[`Label`](#tituli.schedule.Label), a dict, …); `layout` is filled in once rendered.

`image` is the other way in: an already-rendered frame-sized picture (a
PIL image or a path) — a title page made elsewhere, a logo plate — timed
like any layout. `fade_in` / `fade_out` override `fade` for one end
(`fade_in=0` for a title that must be up on the first frame).

### tituli.schedule.resolve(overlays, , min_readable_s=1.5)

Enforce one overlay per slot at a time: the heavier wins, the lighter yields.

A lighter overlay is truncated to the time before the heavier one starts
and dropped only if what remains is under `min_readable_s` (see
`_yield_to`). Equal weights that collide raise — that is an authoring
error, not a rule. Use this on a hand-built list to guarantee two weights
never stack.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`TimedOverlay`](#tituli.schedule.TimedOverlay)]

### tituli.schedule.schedule_labels(spans, label_for, , suppressed_by=(), hold_s=4.6, repeat_gap_s=150.0, min_readable_s=1.5, slot='top-left', weight=1)

One label per span, held `hold_s`, with the three rules built in.

* **first appearance**: a picture is labelled the first time it is shown;
* **repeat gap**: and again only if `repeat_gap_s` has passed since;
* **suppression**: a heavier overlay in the same slot owns that moment. The
  label is *truncated* to the time before the heavier one starts, and
  skipped only if what remains is shorter than `min_readable_s` — and a
  skipped label is *not recorded as shown*, so it gets its next chance.

`label_for` returns a [`Label`](#tituli.schedule.Label) or `UNLABELLED`; `None` raises.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`TimedOverlay`](#tituli.schedule.TimedOverlay)]
