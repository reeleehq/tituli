"""When overlays appear: timed overlays, and a scheduler that owns the rules.

Two ways in, both whole:

* **You schedule.** Build :class:`TimedOverlay` objects at the times you want
  and hand them to :func:`tituli.video.overlay`. tituli composites; it does
  not second-guess your times.
* **tituli schedules.** :func:`schedule_labels` derives one label per panel of
  a cut, with *first appearance*, *repeat gap* and *suppression by a heavier
  overlay* as first-class rules — and the suppression check lives **inside**
  the loop, so a label that loses its moment to a title card is not recorded
  as shown and gets its next chance. (That ordering bug once left the one
  portrait a cold viewer most needed named unlabelled for nine minutes.)

There is deliberately no middle: nothing here owns *some* of the timing and
leaves the caller to reconcile the rest.

A label is either a :class:`Label` or the explicit :data:`UNLABELLED` sentinel.
``None`` is refused: a still left uncaptioned next to a captioned one is an
implicit claim about what it is, so "no caption" must be said, never defaulted.

>>> spans = [Span(0, 5, "eliza"), Span(5, 10, "eliza"), Span(10, 15, "map")]
>>> labels = {"eliza": Label("Eliza Hamilton", "Ralph Earl, 1787"), "map": UNLABELLED}
>>> cards = [TimedOverlay(None, 0, 3, slot="top-left", weight=2)]
>>> out = schedule_labels(spans, lambda p: labels[p.key], suppressed_by=cards)
>>> [(round(o.start), round(o.end)) for o in out]   # first span lost to the card
[(5, 10)]
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Callable, Iterable, Sequence

from tituli.layout import Layout

DEFAULT_HOLD_S = 4.6  # long enough to read twice, short enough the picture breathes
DEFAULT_REPEAT_GAP_S = 150.0  # re-label a returning picture only after this long
MIN_READABLE_S = 1.5
DEFAULT_FADE_S = 0.45


class _Unlabelled:
    """Sentinel: this still is deliberately shown without a label."""

    def __repr__(self) -> str:
        return "UNLABELLED"


UNLABELLED = _Unlabelled()


@dataclass(frozen=True)
class Label:
    """What goes on a museum label: the thing, and where it came from."""

    text: str
    attribution: str = ""
    key: str | None = None  # identity for repeat suppression (defaults to text)

    @property
    def identity(self) -> str:
        """The overlay's key, or its text when it has none."""
        return self.key or self.text


@dataclass(frozen=True)
class Span:
    """A time range of the cut showing one picture. ``key`` identifies the picture.

    (Named ``Span`` rather than ``Panel`` so it never collides with
    ``braidio.video.Panel``, which callers of both will import alongside it.)
    """

    start: float
    end: float
    key: str
    data: Any = None


@dataclass(frozen=True)
class TimedOverlay:
    """A layout (or a thing to lay out) on screen from ``start`` to ``end``.

    ``slot`` names the region it occupies; ``weight`` orders overlays that
    contend for a slot — the heavier suppresses the lighter, never stacks.
    ``payload`` is whatever the caller wants to carry to rendering (a
    :class:`Label`, a dict, ...); ``layout`` is filled in once rendered.

    ``image`` is the other way in: an already-rendered frame-sized picture (a
    PIL image or a path) — a title page made elsewhere, a logo plate — timed
    like any layout. ``fade_in`` / ``fade_out`` override ``fade`` for one end
    (``fade_in=0`` for a title that must be up on the first frame).
    """

    layout: Layout | None
    start: float
    end: float
    slot: str = "top-left"
    weight: int = 1
    fade: float = DEFAULT_FADE_S
    payload: Any = None
    meta: dict = field(default_factory=dict, compare=False)
    image: Any = None
    fade_in: float | None = None
    fade_out: float | None = None

    @property
    def duration(self) -> float:
        """Length in seconds (``end - start``)."""
        return self.end - self.start

    def overlaps(self, other: "TimedOverlay") -> bool:
        """Whether the two overlays overlap in time."""
        return self.start < other.end and other.start < self.end

    def with_layout(self, layout: Layout) -> "TimedOverlay":
        """A copy of the overlay carrying ``layout``."""
        return replace(self, layout=layout, meta=dict(self.meta))


def schedule_labels(
    spans: Sequence[Span],
    label_for: Callable[[Span], Label | _Unlabelled],
    *,
    suppressed_by: Iterable[TimedOverlay] = (),
    hold_s: float = DEFAULT_HOLD_S,
    repeat_gap_s: float = DEFAULT_REPEAT_GAP_S,
    min_readable_s: float = MIN_READABLE_S,
    slot: str = "top-left",
    weight: int = 1,
) -> list[TimedOverlay]:
    """One label per span, held ``hold_s``, with the three rules built in.

    * **first appearance**: a picture is labelled the first time it is shown;
    * **repeat gap**: and again only if ``repeat_gap_s`` has passed since;
    * **suppression**: a heavier overlay in the same slot owns that moment. The
      label is *truncated* to the time before the heavier one starts, and
      skipped only if what remains is shorter than ``min_readable_s`` — and a
      skipped label is *not recorded as shown*, so it gets its next chance.

    ``label_for`` returns a :class:`Label` or :data:`UNLABELLED`; ``None`` raises.
    """
    heavier = [o for o in suppressed_by if o.slot == slot and o.weight > weight]
    out: list[TimedOverlay] = []
    last_shown: dict[str, float] = {}
    for span in spans:
        label = label_for(span)
        if label is None:
            raise ValueError(
                f"label_for returned None for span {span.key!r}. Return a Label, or "
                f"tituli.schedule.UNLABELLED to state that the still is deliberately unlabelled."
            )
        if label is UNLABELLED:
            continue
        assert isinstance(label, Label)
        previous = last_shown.get(label.identity)
        if previous is not None and span.start - previous < repeat_gap_s:
            continue
        end = min(span.start + hold_s, span.end)
        candidate = TimedOverlay(
            None, span.start, end, slot=slot, weight=weight, payload=label
        )
        candidate = _yield_to(candidate, heavier)
        if candidate is None or candidate.duration < min_readable_s:
            continue  # the heavier overlay owns this moment; try again next appearance
        last_shown[label.identity] = span.start
        out.append(candidate)
    return out


def _yield_to(o: TimedOverlay, heavier: Iterable[TimedOverlay]) -> TimedOverlay | None:
    """Cut ``o`` down to the time before the first heavier overlap; None if none is left.

    Truncate-then-check rather than drop-whole: a label that starts three
    seconds before a card keeps those three seconds. The two policies agree
    until cards get dense, then this one loses fewer labels.
    """
    end = o.end
    for h in heavier:
        if o.overlaps(h):
            if h.start <= o.start:
                return None  # the heavier one already holds the slot when we begin
            end = min(end, h.start)
    if end == o.end:
        return o
    return replace(o, end=end, meta=dict(o.meta))


def resolve(
    overlays: Iterable[TimedOverlay], *, min_readable_s: float = MIN_READABLE_S
) -> list[TimedOverlay]:
    """Enforce one overlay per slot at a time: the heavier wins, the lighter yields.

    A lighter overlay is truncated to the time before the heavier one starts
    and dropped only if what remains is under ``min_readable_s`` (see
    ``_yield_to``). Equal weights that collide raise — that is an authoring
    error, not a rule. Use this on a hand-built list to guarantee two weights
    never stack.
    """
    items = sorted(overlays, key=lambda o: (-o.weight, o.start))
    kept: list[TimedOverlay] = []
    for o in items:
        rivals = [k for k in kept if k.slot == o.slot and k.overlaps(o)]
        same = [r for r in rivals if r.weight == o.weight]
        if same:
            r = same[0]
            raise ValueError(
                f"two overlays of weight {o.weight} collide in slot {o.slot!r}: "
                f"[{r.start:.2f}, {r.end:.2f}] and [{o.start:.2f}, {o.end:.2f}]"
            )
        cut = _yield_to(o, [r for r in rivals if r.weight > o.weight])
        if cut is None or cut.duration < min_readable_s:
            continue
        kept.append(cut)
    return sorted(kept, key=lambda o: o.start)


__all__ = [
    "Label",
    "Span",
    "TimedOverlay",
    "UNLABELLED",
    "schedule_labels",
    "resolve",
    "DEFAULT_HOLD_S",
    "DEFAULT_REPEAT_GAP_S",
]
