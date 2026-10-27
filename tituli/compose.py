"""The composed pieces: title cards, captions with attribution, lower thirds.

Each function turns a few strings into a :class:`~tituli.layout.Layout` placed
on a :class:`~tituli.frame.Frame`, applying the ink-and-scrim decision the frame's
knowledge allows. The pipeline order is fixed and matters: **shape/wrap →
measure → decide ink → cut the scrim to the measured block → compose**. A scrim
sized before the text is measured is how a three-line caption ends up hanging
off its own backdrop.

>>> from tituli.frame import Frame
>>> lay = title_card("The Apple", "a concrete poem", frame=Frame.blank((1920, 1080)))
>>> "".join(r.text for r in lay.runs)      # tracked styles set one run per glyph
'The Applea concrete poem'
>>> lay.meta["anchor"], lay.meta["ink"]
('center', 'background unknown: white on dark scrim')
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

from tituli.color import (
    WCAG_NORMAL_MIN,
    WHITE,
    RGBA,
    contrast_from_luminance,
    ink_for,
    parse_color,
    with_alpha,
)
from tituli.frame import Frame
from tituli.geometry import Box
from tituli.layout import Layout, Plate, Run, block, fit_size, measure, wrap
from tituli.style import (
    ATTRIBUTION,
    CAPTION,
    KICKER,
    LOWER_THIRD_NAME,
    LOWER_THIRD_ROLE,
    NOTE_HEADLINE,
    NOTE_LINE,
    SUBTITLE,
    TITLE,
    Halo,
    TextStyle,
)

if TYPE_CHECKING:  # pragma: no cover
    from tituli.render import Engine

# Scrim tuning. Opacity is what a dark scrim needs to carry white text over
# white paper (the worst case a found-image film throws at it) — the corner
# falloff keeps it from dimming the whole frame on everything else.
SCRIM_DARK: RGBA = (6, 7, 10, 210)
SCRIM_LIGHT: RGBA = (250, 249, 246, 210)
_BUSY_STD = 0.12  # luminance stddev above which a patch is "busy"
_SCRIM_PAD_EM = 1.0  # full-strength margin around a block, in em of its largest face
_SCRIM_BLEED_EM = 9.0  # the falloff beyond that margin, in em
_GAP_EM = 0.55  # vertical gap between the parts of a card, in em
_TITLE_MAX_WIDTH = 0.8  # fraction of the safe box a title may span
_CAPTION_MAX_WIDTH = 0.55
_LOWER_THIRD_MAX_WIDTH = 0.6
_NOTE_MAX_WIDTH = 0.62
_NOTE_MAX_LINES = 4  # per line of the note, after wrapping
_ELLIPSIS = "…"
_ACCENT: RGBA = (214, 170, 94, 255)  # a warm gold, used only for the accent rule
_RULE_EM = (1.6, 0.09)  # accent rule length and thickness, in em of the title face


@dataclass(frozen=True)
class InkDecision:
    """What the frame told us to do about legibility."""

    ink: RGBA
    scrim: RGBA | None  # None = no scrim needed
    luminance: float | None
    reason: str


def decide_ink(frame: Frame, box: Box, *, preferred: RGBA | None = None) -> InkDecision:
    """Choose ink and whether a scrim is needed under ``box``.

    Rung (a) (nothing known): white on a dark scrim, the universal default.
    Rung (b)/(c): the ink with more contrast; a scrim only when contrast is still
    short of WCAG 4.5:1 or the patch is busy. ``preferred`` is honoured when it
    already has enough contrast.
    """
    stats = frame.luminance_stats(box)
    if stats is None:
        return InkDecision(
            WHITE, SCRIM_DARK, None, "background unknown: white on dark scrim"
        )
    lum, std = stats
    if (
        preferred is not None
        and contrast_from_luminance(preferred, lum) >= WCAG_NORMAL_MIN
        and std < _BUSY_STD
    ):
        return InkDecision(preferred, None, lum, "preferred ink has enough contrast")
    ink = ink_for(luminance=lum)
    ok = contrast_from_luminance(ink, lum) >= WCAG_NORMAL_MIN
    if ok and std < _BUSY_STD:
        return InkDecision(ink, None, lum, "background contrast sufficient")
    scrim = SCRIM_DARK if ink == WHITE else SCRIM_LIGHT
    why = "busy background" if ok else "insufficient contrast"
    return InkDecision(ink, scrim, lum, f"{why}: scrim added")


def _scrim_plate(
    block_box: Box, frame: Frame, scrim: RGBA, *, em: float, anchor: str
) -> Plate:
    """A 2-D corner (or edge) falloff cut to the block, bleeding away from it."""
    pad = em * _SCRIM_PAD_EM
    bleed = em * _SCRIM_BLEED_EM
    core = Box(
        block_box.x0 - pad, block_box.y0 - pad, block_box.x1 + pad, block_box.y1 + pad
    )
    horizontal = "left" in anchor or "right" in anchor
    vertical = "top" in anchor or "bottom" in anchor
    # The plate runs from the frame edge the block hugs, through the core, and
    # `bleed` further; `solid` is the core's share of that extent per axis.
    x0 = 0.0 if "left" in anchor else core.x0 - bleed
    x1 = float(frame.width) if "right" in anchor else core.x1 + bleed
    y0 = 0.0 if "top" in anchor else core.y0 - bleed
    y1 = float(frame.height) if "bottom" in anchor else core.y1 + bleed
    if not horizontal:
        x0, x1 = 0.0, float(frame.width)
    if not vertical:
        y0, y1 = core.y0 - bleed, core.y1 + bleed
    b = Box(x0, y0, x1, y1).intersection(frame.bounds)
    solid_x = (core.x1 if "left" in anchor else b.x1 - core.x0) / max(1.0, b.width)
    solid_y = (core.y1 if "top" in anchor else b.y1 - core.y0) / max(1.0, b.height)
    solid = (min(1.0, solid_x), min(1.0, solid_y))
    if horizontal and vertical:
        return Plate(b, scrim, f"corner-{anchor}", solid=solid)  # type: ignore[arg-type]
    if "bottom" in anchor:
        return Plate(b, scrim, "gradient-bottom", solid=solid)
    if "top" in anchor:
        return Plate(b, scrim, "gradient-top", solid=solid)
    return Plate(b, scrim, "box", radius=em * 0.3)


def truncate(
    text: str,
    style: TextStyle,
    frame_height: float,
    *,
    max_width: float,
    max_lines: int,
    engine: "Engine | None" = None,
) -> str:
    """Wrap and hard-truncate with an ellipsis at ``max_lines`` lines.

    For text whose length you do not control (a licence template blob pasted
    into an artist field). The result always fits.
    """
    lines = wrap(text, style, frame_height, max_width=max_width, engine=engine)
    if len(lines) <= max_lines:
        return "\n".join(lines)
    kept = lines[:max_lines]
    last = kept[-1]
    while (
        last
        and measure(last + _ELLIPSIS, style, frame_height, engine=engine) > max_width
    ):
        last = last[:-1].rstrip()
    kept[-1] = last + _ELLIPSIS
    return "\n".join(kept)


#: Below this the type is present but not readable at viewing distance — a
#: caption at 2% of frame height on a phone is a grey smudge. Expressed, like
#: every other size here, as a fraction of frame height.
MIN_LEGIBLE_SIZE = 0.022


#: What to do when text will not fit the box it was given.
#:
#: ``"fit"`` shrinks the type until the words fit and raises
#: :class:`TextDoesNotFit` if that would make them unreadable — the right
#: default, because the caller is the only one who can choose between shorter
#: wording, more lines and no overlay at all.
#:
#: ``"truncate"`` cuts with an ellipsis. Opt into it only for text whose length
#: you genuinely do not control — a licence template pasted into an artist
#: field — and never for words you wrote, where a cut label is a *wrong* label
#: rather than a short one.
OVERFLOW_POLICIES = ("fit", "truncate")


def _set_within(
    text: str,
    style: TextStyle,
    frame_height: float,
    *,
    max_width: float,
    max_lines: int,
    on_overflow: str,
    engine: "Engine | None" = None,
) -> tuple[str, TextStyle]:
    """Apply an :data:`OVERFLOW_POLICIES` policy, returning (text, style)."""
    if on_overflow not in OVERFLOW_POLICIES:
        raise ValueError(
            f"on_overflow must be one of {OVERFLOW_POLICIES}, got {on_overflow!r}"
        )
    if on_overflow == "truncate":
        return (
            truncate(
                text,
                style,
                frame_height,
                max_width=max_width,
                max_lines=max_lines,
                engine=engine,
            ),
            style,
        )
    return fit(
        text,
        style,
        frame_height,
        max_width=max_width,
        max_lines=max_lines,
        engine=engine,
    )


class TextDoesNotFit(ValueError):
    """The text cannot be set completely without going below legibility.

    Raised rather than truncating, because the caller is the only one who can
    decide what to do: shorten the wording ("1981 · Central Park, live" ->
    "1981 · Central Park", or "1981"), give it more lines, widen the box, or
    drop the overlay. Silently ellipsising picks the one option nobody wants —
    a label that is *wrong* rather than absent.

    Attributes:
        text: what could not be set.
        tried_size: the smallest size attempted, as a fraction of frame height.
        lines_at_min: how many lines it still needed there.
        max_lines: how many were allowed.
    """

    def __init__(self, text, tried_size, lines_at_min, max_lines):
        self.text = text
        self.tried_size = tried_size
        self.lines_at_min = lines_at_min
        self.max_lines = max_lines
        shown = text if len(text) <= 60 else text[:57] + "..."
        super().__init__(
            f"cannot set {shown!r} in {max_lines} line(s) without going below "
            f"the legible minimum ({MIN_LEGIBLE_SIZE:g} of frame height): at "
            f"{tried_size:g} it still needs {lines_at_min}. Shorten the text, "
            f"allow more lines, widen max_width, or do not show it."
        )


def fit(
    text: str,
    style: TextStyle,
    frame_height: float,
    *,
    max_width: float,
    max_lines: int,
    min_size: float = MIN_LEGIBLE_SIZE,
    engine: "Engine | None" = None,
) -> tuple[str, TextStyle]:
    """Wrap ``text`` complete, shrinking the type until it fits — never cutting it.

    Returns the wrapped text and the (possibly smaller) style to set it in.

    **Why this exists rather than :func:`truncate`.** Type here is sized as a
    fraction of frame *height* but has to fit the frame's *width*. On a portrait
    frame those pull apart hard: a lower third at 0.042 of height is 81px tall on
    a 1080x1920 frame and has to fit inside ~1080px of width, so a perfectly
    ordinary line overflows. Truncating then produced a shipped caption reading
    ``1981 · Centr…`` — which is not a shortened label, it is a wrong one.

    Shrinking is tried first because it is invisible to the viewer and costs
    nothing. Only when shrinking would make the text unreadable does this raise
    :class:`TextDoesNotFit`, handing the decision back to whoever wrote the words.

    Args:
        text: the words, set in full or not at all.
        style: the style to start from; its ``size`` is the ceiling.
        frame_height: pixels, for resolving em sizes.
        max_width: pixels available.
        max_lines: how many lines the design allows.
        min_size: legibility floor, as a fraction of frame height.
        engine: the engine that will draw the text (default: measure with the face).

    Raises:
        TextDoesNotFit: when even ``min_size`` needs more than ``max_lines``.

    Examples:
        >>> from tituli.style import TextStyle
        >>> st = TextStyle(size=0.05)
        >>> body, used = fit("short", st, 1000.0, max_width=900, max_lines=1)
        >>> body, used.size == st.size
        ('short', True)
    """
    size = style.size
    last_lines = 1
    while True:
        st = style.with_(size=size)
        lines = wrap(text, st, frame_height, max_width=max_width, engine=engine)
        last_lines = len(lines)
        if last_lines <= max_lines:
            return "\n".join(lines), st
        if size <= min_size:
            raise TextDoesNotFit(text, size, last_lines, max_lines)
        # 6% steps: fine enough that the shrink is imperceptible, coarse enough
        # to terminate quickly.
        size = max(min_size, size * 0.94)


def _stack(
    parts: Sequence[tuple[str, TextStyle]],
    frame: Frame,
    *,
    max_width: float,
    align: str | None = None,
    engine: "Engine | None" = None,
) -> Layout:
    """Lay out several (text, style) blocks top-to-bottom with style-sized gaps."""
    y = 0.0
    out = Layout()
    for i, (text, style) in enumerate(parts):
        if not text:
            continue
        st = style.with_(align=align) if align else style
        lay = block(text, st, frame, max_width=max_width, y=y, engine=engine)
        out = out + lay
        y += (
            len(text.split("\n")) * lay.meta["line_height"]
            + st.face(frame.height).size * _GAP_EM
        )
    return out


def title_card(
    title: str,
    subtitle: str = "",
    *,
    frame: Frame,
    kicker: str = "",
    anchor: str = "center",
    title_style: TextStyle = TITLE,
    subtitle_style: TextStyle = SUBTITLE,
    kicker_style: TextStyle = KICKER,
    ink: RGBA | None = None,
    scrim: bool | None = None,
    halo: bool | Halo = False,
    engine: "Engine | None" = None,
) -> Layout:
    """An opening card: optional kicker, title, optional subtitle.

    Fits the title to 80 % of the safe width (shrinking, never clipping), stacks
    the parts with a gap proportional to the type, places the block at
    ``anchor`` (subject-avoiding when the frame knows the picture), and picks
    ink by the frame's contrast. ``scrim`` forces a scrim on/off; None decides.
    ``halo`` (``True`` or a :class:`~tituli.style.Halo`) glows under the glyphs
    in place of an automatic scrim: legible over footage without darkening it.
    """
    safe = frame.safe
    max_w = safe.width * _TITLE_MAX_WIDTH
    tstyle = fit_size(
        title,
        title_style,
        frame.height,
        max_width=max_w,
        max_height=safe.height * 0.6,
        engine=engine,
    )
    parts = [(kicker, kicker_style), (title, tstyle), (subtitle, subtitle_style)]
    align = (
        "center"
        if anchor in ("top", "center", "bottom")
        else ("left" if "left" in anchor else "right")
    )
    lay = _stack(parts, frame, max_width=max_w, align=align, engine=engine)
    bb = lay.bbox()
    where, box = frame.place((bb.width, bb.height), anchor=anchor)
    lay = lay.moved_to(box)
    return _finish(
        lay,
        frame,
        where,
        ink=ink,
        scrim=scrim,
        halo=halo,
        em=tstyle.face(frame.height).size,
        preferred=parse_color(title_style.color),
    )


def caption(
    text: str,
    attribution: str = "",
    *,
    frame: Frame,
    anchor: str | Sequence[str] = "auto",
    style: TextStyle = CAPTION,
    attribution_style: TextStyle = ATTRIBUTION,
    max_lines: int = 3,
    max_width: float = _CAPTION_MAX_WIDTH,
    ink: RGBA | None = None,
    scrim: bool | None = None,
    halo: bool | Halo = False,
    accent: bool = True,
    on_overflow: str = "fit",
    engine: "Engine | None" = None,
) -> Layout:
    """A museum label over a picture: what is on screen, plus a tiny credit line.

    ``text`` is wrapped to ``max_width`` of the safe box and **shrunk to fit**
    within ``max_lines`` rather than cut; ``attribution`` is set small and
    slightly transparent — present enough to credit, small enough not to
    compete. If the words cannot be set legibly this raises
    :class:`TextDoesNotFit`; pass ``on_overflow="truncate"`` for text whose
    length you do not control (see :data:`OVERFLOW_POLICIES`). Placement avoids the
    frame's ``avoid`` boxes and its delivery target's reserved zones; the
    scrim is a 2-D corner falloff cut to the measured block. ``halo`` (``True``
    or a :class:`~tituli.style.Halo`) glows under the glyphs in place of an
    automatic scrim — for a centred caption over footage, where a scrim would
    dim the frame.
    """
    safe = frame.safe
    max_w = safe.width * max_width
    body, style = _set_within(
        text,
        style,
        frame.height,
        max_width=max_w,
        max_lines=max_lines,
        on_overflow=on_overflow,
        engine=engine,
    )
    credit, attribution_style = (
        _set_within(
            attribution,
            attribution_style,
            frame.height,
            max_width=max_w,
            max_lines=2,
            on_overflow=on_overflow,
            engine=engine,
        )
        if attribution
        else ("", attribution_style)
    )
    # Try the layout at each candidate anchor's alignment; alignment follows the side.
    lay = _stack(
        [(body, style), (credit, attribution_style)],
        frame,
        max_width=max_w,
        align="left",
        engine=engine,
    )
    bb = lay.bbox()
    where, box = frame.place((bb.width, bb.height), anchor=anchor)
    if "right" in where:
        lay = _stack(
            [(body, style), (credit, attribution_style)],
            frame,
            max_width=max_w,
            align="right",
            engine=engine,
        )
    elif where in ("top", "center", "bottom"):
        lay = _stack(
            [(body, style), (credit, attribution_style)],
            frame,
            max_width=max_w,
            align="center",
            engine=engine,
        )
    bb = lay.bbox()
    lay = lay.moved_to(box)
    em = style.face(frame.height).size
    out = _finish(
        lay,
        frame,
        where,
        ink=ink,
        scrim=scrim,
        halo=halo,
        em=em,
        preferred=parse_color(style.color),
    )
    if accent:
        out = _with_accent_rule(out, em, where)
    return out


def lower_third(
    name: str,
    role: str = "",
    *,
    frame: Frame,
    anchor: str = "bottom-left",
    name_style: TextStyle = LOWER_THIRD_NAME,
    role_style: TextStyle = LOWER_THIRD_ROLE,
    ink: RGBA | None = None,
    scrim: bool | None = None,
    halo: bool | Halo = False,
    on_overflow: str = "fit",
    engine: "Engine | None" = None,
) -> Layout:
    """Who is speaking: a name and a role, left-anchored, scrimmed if needed.

    Respects the frame's delivery zones — with ``delivery="youtube"`` the block
    moves above the subtitle band rather than into it.

    The name and role are **shrunk to fit** rather than cut, and
    :class:`TextDoesNotFit` is raised if they cannot be set legibly. A lower
    third reading ``1981 · Centr…`` once shipped in a finished film; that is not
    a shortened label but a false one.
    """
    max_w = frame.safe.width * _LOWER_THIRD_MAX_WIDTH
    name_t, name_style = _set_within(
        name,
        name_style,
        frame.height,
        max_width=max_w,
        max_lines=1,
        on_overflow=on_overflow,
        engine=engine,
    )
    role_t, role_style = (
        _set_within(
            role,
            role_style,
            frame.height,
            max_width=max_w,
            max_lines=1,
            on_overflow=on_overflow,
            engine=engine,
        )
        if role
        else ("", role_style)
    )
    lay = _stack(
        [(name_t, name_style), (role_t, role_style)],
        frame,
        max_width=max_w,
        align="left",
        engine=engine,
    )
    bb = lay.bbox()
    where, box = frame.place((bb.width, bb.height), anchor=anchor)
    lay = lay.moved_to(box)
    em = name_style.face(frame.height).size
    out = _finish(
        lay,
        frame,
        where,
        ink=ink,
        scrim=scrim,
        halo=halo,
        em=em,
        preferred=parse_color(name_style.color),
    )
    return _with_accent_rule(out, em, where)


def note(
    lines: Sequence[str] | str,
    *,
    frame: Frame,
    headline: str = "",
    anchor: str | Sequence[str] = "top-left",
    headline_style: TextStyle = NOTE_HEADLINE,
    line_style: TextStyle = NOTE_LINE,
    max_width: float = _NOTE_MAX_WIDTH,
    ink: RGBA | None = None,
    scrim: bool | None = None,
    halo: bool | Halo = False,
    accent: bool = True,
    on_overflow: str = "fit",
    engine: "Engine | None" = None,
) -> Layout:
    """An editorial context card: an optional headline over equal-weight lines.

    The block for what the audio assumes and a cold viewer does not have
    ("what *Hamilton* is", "Philip died at 19"). Heavier than a caption —
    schedule it with a higher ``weight`` so the two never share a corner. Each
    line wraps to ``max_width`` of the safe box, shrinking to fit within
    ``_NOTE_MAX_LINES`` rows rather than being cut; every line shares the
    smallest size any of them needed, so the block reads as one block.
    Raises :class:`TextDoesNotFit` if a line cannot be set legibly.
    """
    if isinstance(lines, str):
        lines = [l for l in lines.split("\n") if l.strip()]
    max_w = frame.safe.width * max_width

    # One shared size for every line, so a long line does not end up set smaller
    # than its neighbours — the block has to read as one block.
    def _set(text, style, max_lines):
        return _set_within(
            text,
            style,
            frame.height,
            max_width=max_w,
            max_lines=max_lines,
            on_overflow=on_overflow,
            engine=engine,
        )

    fitted = [_set(l, line_style, _NOTE_MAX_LINES) for l in lines]
    if fitted:
        line_style = min((st for _, st in fitted), key=lambda st: st.size)
        fitted = [_set(l, line_style, _NOTE_MAX_LINES) for l in lines]
    body = [t for t, _ in fitted]
    head, headline_style = (
        _set(headline, headline_style, 2) if headline else ("", headline_style)
    )
    parts = [(head, headline_style)] + [(b, line_style) for b in body]
    align = "left"
    lay = _stack(parts, frame, max_width=max_w, align=align, engine=engine)
    bb = lay.bbox()
    where, box = frame.place((bb.width, bb.height), anchor=anchor)
    if "right" in where or where in ("top", "center", "bottom"):
        align = "right" if "right" in where else "center"
        lay = _stack(parts, frame, max_width=max_w, align=align, engine=engine)
    lay = lay.moved_to(box)
    em = (headline_style if head else line_style).face(frame.height).size
    out = _finish(
        lay,
        frame,
        where,
        ink=ink,
        scrim=scrim,
        halo=halo,
        em=em,
        preferred=parse_color(line_style.color),
    )
    return _with_accent_rule(out, em, where) if accent else out


def _with_accent_rule(lay: Layout, em: float, anchor: str) -> Layout:
    bb = lay.bbox()
    length, thick = em * _RULE_EM[0], max(2.0, em * _RULE_EM[1])
    gap = em * 0.45
    if "right" in anchor:
        x0 = bb.x1 - length
    elif "left" in anchor:
        x0 = bb.x0
    else:
        x0 = (bb.x0 + bb.x1 - length) / 2
    rule = Plate(Box(x0, bb.y0 - gap - thick, x0 + length, bb.y0 - gap), _ACCENT, "box")
    return lay.with_plates(rule)


def _finish(
    lay: Layout,
    frame: Frame,
    anchor: str,
    *,
    ink: RGBA | None,
    scrim: bool | None,
    em: float,
    preferred: RGBA,
    halo: bool | Halo = False,
) -> Layout:
    """Apply the ink decision and, if needed, the scrim — after measuring.

    ``halo`` (``True`` for the default :class:`~tituli.style.Halo`, or one)
    glows under the glyphs: legibility over footage without darkening the
    picture. It stands in for the scrim the decision would add; ``scrim=True``
    still forces one, and ``meta["ink"]`` says when the halo replaced it.
    """
    bb = lay.bbox()
    decision = decide_ink(frame, bb, preferred=preferred)
    chosen = ink if ink is not None else decision.ink
    glow = Halo() if halo is True else (halo or None)
    runs = tuple(
        Run(
            **{
                **r.__dict__,
                "color": with_alpha(chosen, r.color[3] / 255),
                "halo": glow or r.halo,
            }
        )
        for r in lay.runs
    )
    reason = decision.reason
    if glow is not None and scrim is None and decision.scrim is not None:
        scrim, reason = False, f"{reason}; halo instead of scrim"
    lay = Layout(runs, lay.plates, {**lay.meta, "ink": reason, "anchor": anchor})
    want_scrim = decision.scrim is not None if scrim is None else scrim
    if want_scrim:
        color = decision.scrim or (SCRIM_DARK if chosen == WHITE else SCRIM_LIGHT)
        plate = _scrim_plate(bb, frame, color, em=em, anchor=anchor)
        lay = Layout(lay.runs, (plate,) + lay.plates, lay.meta)
    return lay


def intertitle(
    text: str,
    *,
    frame: Frame,
    style: TextStyle | None = None,
    engine: "Engine | None" = None,
) -> Layout:
    """A silent-film style card: serif italic prose, centred on the frame."""
    from tituli.style import INTERTITLE

    st = style or INTERTITLE
    safe = frame.safe
    st = fit_size(
        text,
        st,
        frame.height,
        max_width=safe.width * 0.7,
        max_height=safe.height * 0.7,
        engine=engine,
    )
    lay = block(text, st, frame, max_width=safe.width * 0.7, engine=engine)
    bb = lay.bbox()
    _, box = frame.place((bb.width, bb.height), anchor="center")
    lay = lay.moved_to(box)
    return _finish(
        lay,
        frame,
        "center",
        ink=None,
        scrim=None,
        em=st.face(frame.height).size,
        preferred=parse_color(st.color),
    )


__all__ = [
    "InkDecision",
    "decide_ink",
    "truncate",
    "title_card",
    "caption",
    "lower_third",
    "note",
    "intertitle",
    "SCRIM_DARK",
    "SCRIM_LIGHT",
]
