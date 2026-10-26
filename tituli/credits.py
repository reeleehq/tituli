"""Credits: structured data in, designed cards or a crawl out.

The data model is the point. A credits roll is not a list of filenames; it is
*sections* of *entries*, each entry a role and a name (or just a name, or a
line of licence prose). Given that structure the layout can do what a title
designer does: tracked small-caps section headings, role/name pairs on a
shared gutter, a single column that reads top to bottom, generous leading, and
a **never-truncate** rule — attributions are a licence surface, so content that
does not fit paginates onto more cards or raises when the caller capped the
count; it is never silently dropped.

>>> c = Credits.from_dict({
...     "title": "The Apple",
...     "sections": [{"heading": "Voices", "entries": [["Narrator", "A. Reader"]]},
...                  {"heading": "Images", "entries": ["Still Life — Cézanne — public domain"]}],
... })
>>> len(c.sections), c.sections[0].entries[0].role
(2, 'Narrator')
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterable, Sequence

from tituli.color import CREDITS_BLACK, WHITE, parse_color
from tituli.frame import Frame
from tituli.layout import Layout, block
from tituli.style import (
    CREDITS_HEADING,
    CREDITS_LINE,
    CREDITS_NAME,
    CREDITS_ROLE,
    CREDITS_TITLE,
    TextStyle,
)

if TYPE_CHECKING:  # pragma: no cover
    from tituli.render import Engine

# Typographic rhythm, in em of the name face.
_HEADING_GAP_ABOVE = 2.2
_HEADING_GAP_BELOW = 0.9
_ROW_GAP = 0.35  # space between rows beyond the measured text height, in em
_BALANCE_ROUNDS = 12  # attempts at an even fill before falling back to greedy
_BALANCE_STEP = 1.08  # target growth per attempt
_GUTTER_EM = 1.0  # space between the role column and the name column
_ROLE_COLUMN = 0.42  # fraction of the column width given to roles
_TITLE_GAP_BELOW = 2.0
_CLOSING_GAP_ABOVE = 2.5
_COLUMN_WIDTH = 0.7  # fraction of the safe width the credits occupy
_CARD_FILL = 0.86  # fraction of the safe height a card may fill
_CRAWL_LEAD_FRAMES = 1.0  # blank frame-heights before the first line
_CRAWL_TAIL_FRAMES = 1.0
DEFAULT_CRAWL_SPEED = 0.09  # frame heights per second (≈ 97 px/s at 1080p)
DEFAULT_CARD_HOLD_S = 3.5


@dataclass(frozen=True)
class Entry:
    """One credit line: ``role`` + ``name``, a bare ``name``, or prose."""

    name: str
    role: str = ""

    @classmethod
    def of(cls, item: Any) -> "Entry":
        if isinstance(item, Entry):
            return item
        if isinstance(item, str):
            return cls(item)
        if isinstance(item, dict):
            return cls(str(item.get("name", "")), str(item.get("role", "")))
        role, name = item
        return cls(str(name), str(role))


@dataclass(frozen=True)
class Section:
    """A heading over a run of entries. ``kind`` picks the treatment:

    ``"pairs"`` role/name on a gutter (cast, crew); ``"list"`` centred names;
    ``"prose"`` wrapped small text (licences, thanks).
    """

    heading: str = ""
    entries: tuple[Entry, ...] = ()
    kind: str = "auto"

    @property
    def resolved_kind(self) -> str:
        if self.kind != "auto":
            return self.kind
        if any(e.role for e in self.entries):
            return "pairs"
        longest = max((len(e.name) for e in self.entries), default=0)
        return "prose" if longest > 48 else "list"


@dataclass(frozen=True)
class Credits:
    """The whole roll."""

    sections: tuple[Section, ...] = ()
    title: str = ""
    closing: tuple[str, ...] = ()
    meta: dict = field(default_factory=dict, compare=False)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Credits":
        """Build from ``{"title", "sections": [{"heading", "entries", "kind"}], "closing"}``.

        The caller owns making the text presentable: tituli sets whatever it is
        given, so a raw manifest — camera filenames as roles, ``"Unknown
        authorUnknown author"`` from a concatenated field — comes out as a
        designed card of raw manifest strings. Map titles, artists and
        licences into readable roles and names first.
        """
        sections = tuple(
            Section(
                heading=str(s.get("heading", "")),
                entries=tuple(Entry.of(e) for e in s.get("entries", ())),
                kind=str(s.get("kind", "auto")),
            )
            for s in d.get("sections", ())
        )
        closing = d.get("closing", ())
        closing = (
            (closing,) if isinstance(closing, str) else tuple(str(c) for c in closing)
        )
        return cls(sections, str(d.get("title", "")), closing)

    @classmethod
    def from_lines(
        cls, lines: Iterable[str], *, heading: str = "Credits", title: str = ""
    ) -> "Credits":
        """The plain-list case (what ``braidio.video.credits_card`` takes).

        Each line is set as prose, verbatim. Lines built from a fetch manifest
        (``"<file> — <author> — <licence>"``) read as a terminal dump however
        well they are typeset; prefer :meth:`from_dict` with ``{"role", "name"}``
        entries ("Portrait of Eliza Hamilton", "Ralph Earl, 1787 · public domain").
        """
        return cls((Section(heading, tuple(Entry(l) for l in lines)),), title)

    @property
    def line_count(self) -> int:
        return sum(len(s.entries) for s in self.sections) + len(self.closing)


@dataclass(frozen=True)
class CreditsStyle:
    """The type ramp for a roll. One object so a film is one design."""

    title: TextStyle = CREDITS_TITLE
    heading: TextStyle = CREDITS_HEADING
    role: TextStyle = CREDITS_ROLE
    name: TextStyle = CREDITS_NAME
    line: TextStyle = CREDITS_LINE
    ink: Any = WHITE
    background: Any = CREDITS_BLACK

    def inked(self) -> "CreditsStyle":
        c = parse_color(self.ink)
        return CreditsStyle(
            *(
                s.with_(color=c)
                for s in (self.title, self.heading, self.role, self.name, self.line)
            ),
            self.ink,
            self.background,
        )


# ----------------------------------------------------------------------------
# Flow layout: a sequence of "items" with heights, then pagination
# ----------------------------------------------------------------------------


def _flow(
    credits: Credits,
    style: CreditsStyle,
    frame: Frame,
    engine: "Engine | None" = None,
) -> list[tuple[str, float, Layout]]:
    """Each item as ``(kind, height, layout-at-origin)``, in reading order."""
    st = style.inked()
    fh = frame.height
    col_w = frame.safe.width * _COLUMN_WIDTH
    name_em = st.name.face(fh).size
    items: list[tuple[str, float, Layout]] = []

    def add(kind: str, lay: Layout, height: float) -> None:
        items.append((kind, height, lay))

    def rows_height(lay: Layout) -> float:
        """Measured height of a possibly wrapped row: lines x line height + gap.

        Advancing by one line height regardless of wrapping is how a long role
        once ran into the row beneath it — measure first, then advance.
        """
        return _text_height(lay) + name_em * _ROW_GAP

    if credits.title:
        lay = block(
            credits.title,
            st.title.with_(align="center"),
            frame,
            max_width=col_w,
            engine=engine,
        )
        add("title", lay, lay.bbox().height + name_em * _TITLE_GAP_BELOW)
    for si, sec in enumerate(credits.sections):
        if sec.heading:
            gap_above = name_em * (_HEADING_GAP_ABOVE if items else 0.0)
            lay = block(
                sec.heading,
                st.heading.with_(align="center"),
                frame,
                max_width=col_w,
                y=gap_above,
                engine=engine,
            )
            add(
                "heading",
                lay,
                gap_above + lay.bbox().height + name_em * _HEADING_GAP_BELOW,
            )
        kind = sec.resolved_kind
        for e in sec.entries:
            if kind == "pairs":
                lay = _pair(e, st, frame, col_w, engine)
                add("pair", lay, rows_height(lay))
            elif kind == "prose":
                lay = block(
                    e.name,
                    st.line.with_(align="center"),
                    frame,
                    max_width=col_w,
                    engine=engine,
                )
                add("prose", lay, rows_height(lay))
            else:
                lay = block(
                    e.name,
                    st.name.with_(align="center"),
                    frame,
                    max_width=col_w,
                    engine=engine,
                )
                add("line", lay, rows_height(lay))
    for i, line in enumerate(credits.closing):
        gap = name_em * (_CLOSING_GAP_ABOVE if i == 0 else 0.0)
        lay = block(
            line,
            st.line.with_(align="center"),
            frame,
            max_width=col_w,
            y=gap,
            engine=engine,
        )
        add("closing", lay, gap + lay.bbox().height + name_em * 0.4)
    return items


def _text_height(lay: Layout) -> float:
    """Height of a block's lines as laid out: distinct baselines x line height."""
    if not lay.runs:
        return 0.0
    baselines = sorted({round(r.y, 3) for r in lay.runs})
    line_h = lay.meta.get("line_height") or lay.runs[0].face.line_height
    return (baselines[-1] - baselines[0]) + line_h


def _pair(
    e: Entry,
    st: CreditsStyle,
    frame: Frame,
    col_w: float,
    engine: "Engine | None" = None,
) -> Layout:
    """Role right-aligned into the left column, name left-aligned after the gutter."""
    fh = frame.height
    gutter = st.name.face(fh).size * _GUTTER_EM
    role_w = col_w * _ROLE_COLUMN
    name_w = col_w - role_w - gutter
    role = block(
        e.role, st.role.with_(align="right"), frame, max_width=role_w, engine=engine
    )
    name = block(
        e.name,
        st.name.with_(align="left"),
        frame,
        max_width=name_w,
        x=role_w + gutter,
        engine=engine,
    )
    # align baselines: block() puts the first baseline at ascent + leading slack
    if role.runs and name.runs:
        dy = name.runs[0].y - role.runs[0].y
        role = role.translated(0, dy)
    out = role + name
    out.meta["line_height"] = max(
        role.meta.get("line_height", 0), name.meta.get("line_height", 0)
    )
    return out


def _stack_items(
    items: Sequence[tuple[str, float, Layout]], x: float, y: float
) -> Layout:
    out = Layout()
    for _, h, lay in items:
        out = out + lay.translated(x, y)
        y += h
    return out


def credits_crawl(
    credits: Credits,
    *,
    frame: Frame,
    style: CreditsStyle = CreditsStyle(),
    engine: "Engine | None" = None,
) -> tuple[Layout, int]:
    """One tall layout and its total height in pixels (for :func:`tituli.video.crawl`).
    ``engine`` is the one that will draw it; it measures the rows.

    The layout starts one frame-height down and ends one frame-height before
    its bottom, so the crawl enters from an empty frame and leaves to one.
    """
    items = _flow(credits, style, frame, engine)
    x = frame.safe.x0 + (frame.safe.width - frame.safe.width * _COLUMN_WIDTH) / 2
    lead = frame.height * _CRAWL_LEAD_FRAMES
    lay = _stack_items(items, x, lead)
    total = lead + sum(h for _, h, _ in items) + frame.height * _CRAWL_TAIL_FRAMES
    return lay, int(round(total))


def _paginate(
    items: Sequence[tuple[str, float, Layout]],
    limit: float,
    *,
    target: float | None = None,
) -> list[list[tuple[str, float, Layout]]]:
    """Greedy fill to ``target`` (default: the limit); never past ``limit``.

    A heading is never orphaned at the bottom of a card.
    """
    fill = limit if target is None else min(limit, target)
    pages: list[list[tuple[str, float, Layout]]] = [[]]
    used = 0.0
    for i, item in enumerate(items):
        kind, h, _ = item
        nxt_h = items[i + 1][1] if kind == "heading" and i + 1 < len(items) else 0.0
        if pages[-1] and used + h + nxt_h > fill:
            pages.append([])
            used = 0.0
        pages[-1].append(item)
        used += h
    return pages


def credits_cards(
    credits: Credits,
    *,
    frame: Frame,
    style: CreditsStyle = CreditsStyle(),
    max_cards: int | None = None,
    engine: "Engine | None" = None,
) -> list[Layout]:
    """Paginate the roll into cards that each fit the safe area, centred.

    A heading is never orphaned at the bottom of a card. Raises when
    ``max_cards`` would force truncation — losing an attribution silently is a
    licence failure invisible to the person responsible for it.
    """
    items = _flow(credits, style, frame, engine)
    limit = frame.safe.height * _CARD_FILL
    pages = _paginate(items, limit)
    # Balance: a greedy fill leaves the last card nearly empty. Re-page to the
    # smallest even share per card that still fits the same number of cards.
    if len(pages) > 1:
        n = len(pages)
        target = sum(h for _, h, _ in items) / n
        for _ in range(_BALANCE_ROUNDS):
            balanced = _paginate(items, limit, target=target)
            if len(balanced) <= n:
                pages = balanced
                break
            target *= _BALANCE_STEP
    if max_cards is not None and len(pages) > max_cards:
        raise ValueError(
            f"credits: {credits.line_count} lines need {len(pages)} cards at this size but "
            f"max_cards={max_cards}. Use more cards, a crawl, or a smaller CreditsStyle — "
            f"tituli never truncates a credit."
        )
    out: list[Layout] = []
    x = frame.safe.x0 + (frame.safe.width - frame.safe.width * _COLUMN_WIDTH) / 2
    for page in pages:
        height = sum(h for _, h, _ in page)
        y = frame.safe.y0 + (frame.safe.height - height) / 2
        # strip the leading gap on a page's first heading so pages sit centred
        first_kind, first_h, first_lay = page[0]
        if first_kind == "heading":
            bb = first_lay.bbox()
            page = [
                ("heading", first_h - (bb.y0), first_lay.translated(0, -bb.y0))
            ] + list(page[1:])
            height = sum(h for _, h, _ in page)
            y = frame.safe.y0 + (frame.safe.height - height) / 2
        out.append(_stack_items(page, x, y))
    return out


def credits_frame(size: tuple[int, int], style: CreditsStyle = CreditsStyle()) -> Frame:
    """The canonical credits frame: near-black, so ink defaults to white."""
    return Frame.blank(size, color=style.background)


__all__ = [
    "Entry",
    "Section",
    "Credits",
    "CreditsStyle",
    "credits_crawl",
    "credits_cards",
    "credits_frame",
    "DEFAULT_CRAWL_SPEED",
    "DEFAULT_CARD_HOLD_S",
]
