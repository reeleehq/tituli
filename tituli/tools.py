"""The SSOT of dispatchable operations: flat, JSON-able in, JSON-able out.

These are the functions every surface projects: the CLI (``python -m tituli``)
today, an MCP server or HTTP route tomorrow, an agent skill in prose. Nothing
here imports a surface library; each function takes paths and strings, writes
a file, and returns a dict describing what it wrote.

>>> sorted(f.__name__ for f in _dispatch_funcs)
['calligram', 'caption', 'credits', 'fonts', 'lower_third', 'overlay_video', 'title_card']
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from tituli.frame import DEFAULT_SIZE, Frame

_PORTRAIT = (1080, 1920)


def _size(size: str | Sequence[int] | None) -> tuple[int, int]:
    if size is None:
        return DEFAULT_SIZE
    if isinstance(size, str):
        w, h = size.lower().replace("×", "x").split("x")
        return int(w), int(h)
    w, h = size
    return int(w), int(h)


def _frame(
    background: str | None,
    size: tuple[int, int],
    *,
    avoid: str | None,
    delivery: str | None,
) -> Frame:
    """Build a frame from a colour, an image path, or nothing."""
    if background and Path(background).is_file():
        avoid_fn = _avoid(avoid)
        return Frame.from_image(
            background, size=size, avoid=avoid_fn, delivery=delivery
        )
    frame = Frame.blank(size, color=background or None)
    return frame.with_delivery(delivery)


def _avoid(spec: str | None):
    """``avoid="saliency"`` -> burns.salient_box; ``"x,y,w,h"`` -> a box; None -> nothing."""
    if not spec:
        return None
    if spec == "saliency":
        try:
            from burns import salient_box
        except ImportError as e:
            raise ImportError(
                "avoid='saliency' needs `pip install tituli[saliency]`"
            ) from e
        return salient_box
    parts = [float(p) for p in spec.split(",")]
    if len(parts) != 4:
        raise ValueError("avoid must be 'saliency' or 'x,y,w,h' in 0..1")
    return [tuple(parts)]


def _engine(name: str | None):
    """An engine by name (``"pillow"``/``"harfbuzz"``); None keeps the default."""
    from tituli.render import make_engine

    return make_engine(name) if name else None


def _save(img, out: str | Path) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() in (".jpg", ".jpeg") and img.mode == "RGBA":
        img = img.convert("RGB")
    img.save(out)
    return out


def _emit(out: Path, layout, **extra: Any) -> dict:
    bb = layout.bbox()
    return {
        "out": str(out),
        "bbox": [round(bb.x0), round(bb.y0), round(bb.x1), round(bb.y1)],
        **layout.meta,
        **extra,
    }


def title_card(
    title: str,
    subtitle: str = "",
    *,
    out: str = "title.png",
    background: str | None = None,
    size: str | None = None,
    kicker: str = "",
    anchor: str = "center",
    avoid: str | None = None,
    duration: float | None = None,
    engine: str | None = None,
    halo: bool = False,
) -> dict:
    """Render a title card to ``out`` (PNG, or MP4 when ``duration`` is given).

    ``background`` is a colour (``#101014``), an image path, or nothing (a
    transparent overlay). ``anchor`` is a grid position; ``avoid`` is
    ``"saliency"`` or ``"x,y,w,h"`` to keep the title off the subject.
    ``engine`` is ``"pillow"`` (default) or ``"harfbuzz"`` (``tituli[shaping]``).
    ``halo`` glows under the text instead of a scrim (over footage).
    """
    from tituli.compose import title_card as _title
    from tituli.render import render

    sz = _size(size)
    frame = _frame(background, sz, avoid=avoid, delivery=None)
    eng = _engine(engine)
    lay = _title(
        title,
        subtitle,
        kicker=kicker,
        frame=frame,
        anchor=anchor,
        engine=eng,
        halo=halo,
    )
    img = render(lay, frame, engine=eng)
    if duration:
        from tituli.video import still

        still(img, out, duration=duration)
        return _emit(Path(out), lay, duration=duration)
    return _emit(_save(img, out), lay)


def caption(
    image: str,
    text: str,
    attribution: str = "",
    *,
    out: str = "captioned.png",
    anchor: str = "auto",
    avoid: str | None = "saliency",
    delivery: str | None = "youtube",
    size: str | None = None,
    overlay_only: bool = False,
    engine: str | None = None,
    halo: bool = False,
) -> dict:
    """Put a museum-label caption and a tiny attribution on ``image``.

    Placement avoids the subject (``avoid="saliency"`` uses ``burns`` when
    installed, otherwise nothing is avoided) and the delivery target's
    reserved zones. ``overlay_only`` writes a transparent PNG to composite
    onto motion video instead of the flattened picture. ``engine`` is
    ``"pillow"`` (default) or ``"harfbuzz"``. ``halo`` glows under the text
    instead of a scrim (a centred caption over footage).
    """
    from tituli.compose import caption as _caption
    from tituli.render import render, render_overlay

    sz = _size(size) if size else None
    try:
        avoid_fn = _avoid(avoid)
    except ImportError:
        avoid_fn = None
    frame = Frame.from_image(image, size=sz, avoid=avoid_fn, delivery=delivery)
    eng = _engine(engine)
    lay = _caption(text, attribution, frame=frame, anchor=anchor, engine=eng, halo=halo)
    img = (
        render_overlay(lay, frame.size, engine=eng)
        if overlay_only
        else render(lay, frame, engine=eng)
    )
    return _emit(_save(img, out), lay, avoided=len(frame.avoid))


def lower_third(
    name: str,
    role: str = "",
    *,
    out: str = "lower_third.png",
    background: str | None = None,
    size: str | None = None,
    delivery: str | None = "youtube",
    engine: str | None = None,
    halo: bool = False,
) -> dict:
    """A name + role block, bottom-left, as a transparent overlay (or on a picture).

    ``engine`` is ``"pillow"`` (default) or ``"harfbuzz"``. ``halo`` glows under
    the text instead of a scrim.
    """
    from tituli.compose import lower_third as _lt
    from tituli.render import render

    sz = _size(size)
    frame = _frame(background, sz, avoid=None, delivery=delivery)
    eng = _engine(engine)
    lay = _lt(name, role, frame=frame, engine=eng, halo=halo)
    return _emit(_save(render(lay, frame, engine=eng), out), lay)


def credits(
    spec: str,
    *,
    out: str = "credits.mp4",
    mode: str = "crawl",
    size: str | None = None,
    speed: float | None = None,
    hold: float | None = None,
    background: str | None = None,
    audio: str | None = None,
    engine: str | None = None,
) -> dict:
    """Render credits from a JSON spec file (or JSON string) to ``out``.

    Spec: ``{"title": ..., "sections": [{"heading": ..., "entries":
    [["Role", "Name"], "Name", ...]}], "closing": [...]}`` — or a plain JSON
    list of lines. ``mode`` is ``"crawl"`` (one MP4) or ``"cards"`` (PNG per
    card, or one MP4 when ``out`` ends in .mp4). Never truncates. ``engine`` is
    ``"pillow"`` (default) or ``"harfbuzz"``: it measures and draws.
    """
    from tituli.credits import (
        DEFAULT_CARD_HOLD_S,
        DEFAULT_CRAWL_SPEED,
        Credits,
        CreditsStyle,
        credits_cards,
        credits_crawl,
        credits_frame,
    )
    from tituli.render import render

    raw = Path(spec).read_text() if Path(spec).is_file() else spec
    data = json.loads(raw)
    cr = Credits.from_lines(data) if isinstance(data, list) else Credits.from_dict(data)
    sz = _size(size)
    style = CreditsStyle(background=background) if background else CreditsStyle()
    frame = credits_frame(sz, style)
    eng = _engine(engine)
    out_p = Path(out)
    if mode == "crawl":
        from tituli.video import crawl as _crawl

        lay, total = credits_crawl(cr, frame=frame, style=style, engine=eng)
        tall = Frame.blank((sz[0], total), color=style.background)
        img = render(lay, tall, engine=eng)
        px_s = (speed or DEFAULT_CRAWL_SPEED) * sz[1]
        if out_p.suffix.lower() == ".png":
            return _emit(_save(img, out_p), lay, height=total)
        _crawl(img, out_p, size=sz, speed_px_s=px_s, audio=audio)
        return _emit(
            out_p,
            lay,
            height=total,
            duration=round((total - sz[1]) / px_s, 2),
            lines=cr.line_count,
        )
    if mode == "cards":
        cards = credits_cards(cr, frame=frame, style=style, engine=eng)
        imgs = [render(c, frame, engine=eng) for c in cards]
        if out_p.suffix.lower() == ".mp4":
            from tituli.render import frames as _frames
            from tituli.video import DEFAULT_FPS, frames_to_video

            hold_s = hold or DEFAULT_CARD_HOLD_S

            def gen():
                for c in cards:
                    for f in _frames(
                        c.with_timing(0.0, 0.4),
                        frame,
                        duration=hold_s,
                        fps=DEFAULT_FPS,
                        engine=eng,
                    ):
                        yield f

            frames_to_video(gen(), out_p, size=sz, audio=audio)
            return {
                "out": str(out_p),
                "cards": len(cards),
                "duration": round(hold_s * len(cards), 2),
                "lines": cr.line_count,
            }
        outs = [
            str(
                _save(
                    im,
                    out_p.with_name(
                        f"{out_p.stem}_{i + 1:02d}{out_p.suffix or '.png'}"
                    ),
                )
            )
            for i, im in enumerate(imgs)
        ]
        return {"out": outs, "cards": len(cards), "lines": cr.line_count}
    raise ValueError("mode must be 'crawl' or 'cards'")


def calligram(
    text: str,
    *,
    out: str = "calligram.png",
    shape: str = "wave",
    size: str | None = None,
    background: str | None = "#f4f1e8",
    upright: bool = False,
    mask: str | None = None,
    reveal: float | None = None,
    engine: str | None = None,
) -> dict:
    """Lay ``text`` along a shape (``circle``, ``wave``, ``arc``, an SVG path, ``rain``).

    ``shape="rain"`` is Apollinaire's *Il pleut* (lines become streaks; give
    it a portrait ``size``). ``mask`` (an image path, light = inside) pours the
    text into a silhouette instead. ``reveal`` (seconds) writes an MP4 with a
    glyph-by-glyph reveal rather than a PNG. ``engine`` is ``"pillow"``
    (default) or ``"harfbuzz"``.
    """
    from tituli import calligram as cg
    from tituli.render import render

    sz = _size(size) if size else (_PORTRAIT if shape == "rain" else DEFAULT_SIZE)
    frame = Frame.blank(sz, color=background)
    eng = _engine(engine)
    if mask:
        lay = cg.in_shape(text, mask, frame=frame, engine=eng)
    elif shape == "rain":
        lay = cg.rain(text, frame=frame, engine=eng)
    else:
        lay = cg.on_path(text, shape=shape, frame=frame, upright=upright, engine=eng)
    if reveal:
        from tituli.render import frames as _frames
        from tituli.video import DEFAULT_FPS, frames_to_video

        n = max(1, len(lay.runs))
        step = reveal * 0.8 / n
        timed = lay.staggered(step=step, ramp=max(0.15, step * 3))
        frames_to_video(
            _frames(timed, frame, duration=reveal, fps=DEFAULT_FPS, engine=eng),
            out,
            size=sz,
        )
        return _emit(Path(out), lay, glyphs=len(lay.runs), duration=reveal)
    return _emit(_save(render(lay, frame, engine=eng), out), lay, glyphs=len(lay.runs))


def overlay_video(
    video: str,
    overlays: str,
    *,
    out: str = "overlaid.mp4",
    delivery: str | None = "youtube",
    pad_start: float = 0.0,
    engine: str | None = None,
) -> dict:
    """Composite captions/lower thirds/images onto a finished video in one ffmpeg pass.

    ``overlays`` is a JSON file/string: a list of ``{"start", "end", "text",
    "attribution"?, "kind"?: "caption"|"lower_third", "role"?, "anchor"?,
    "halo"?: true}``
    or ``{"start", "end", "image", "fade_in"?, "fade_out"?}`` (a frame-sized
    PNG, e.g. a title page; it occupies its own slot and suppresses no
    caption — time captions after it). Text is laid out against the video's frame size;
    the picture under each overlay is not sampled (pass a still through
    ``caption`` for that). ``pad_start`` seconds are added at the head (first
    frame held, audio delayed); overlay times are on the padded timeline.
    ``engine`` is ``"pillow"`` (default) or ``"harfbuzz"``: it measures and draws.
    """
    from tituli.schedule import TimedOverlay, resolve
    from tituli.video import materialize
    from tituli.video import overlay as _overlay
    from tituli.video import probe_size

    raw = Path(overlays).read_text() if Path(overlays).is_file() else overlays
    items = json.loads(raw)
    size = probe_size(video)
    frame = Frame.blank(size).with_delivery(delivery)
    eng = _engine(engine)
    timed = []
    for it in items:
        start, end = float(it["start"]), float(it["end"])
        if "image" in it:
            timed.append(
                TimedOverlay(
                    None,
                    start,
                    end,
                    slot=it.get("slot", "full"),
                    weight=int(it.get("weight", 3)),
                    image=it["image"],
                    fade_in=_opt_float(it.get("fade_in")),
                    fade_out=_opt_float(it.get("fade_out")),
                )
            )
            continue
        lower_third = it.get("kind", "caption") == "lower_third"
        timed.append(
            TimedOverlay(
                None,
                start,
                end,
                slot=it.get("anchor", "bottom-left" if lower_third else "top-left"),
                weight=2 if lower_third else 1,
                payload=it,
            )
        )
    # Laid out here, with the engine that will draw them, to resolve slot
    # contention on real layouts; ``overlay`` then renders what is passed.
    kept = resolve(materialize(timed, frame=frame, engine=eng))
    _overlay(video, kept, out, size=size, pad_start=pad_start, engine=eng)
    return {"out": out, "overlays": len(kept), "dropped": len(timed) - len(kept)}


def _opt_float(v) -> float | None:
    return None if v is None else float(v)


def fonts(query: str = "") -> dict:
    """List installed font families (optionally filtered by substring)."""
    from tituli.fonts import families

    fams = [f for f in families() if query.lower() in f.lower()]
    return {"count": len(fams), "families": fams}


_dispatch_funcs = [
    title_card,
    caption,
    lower_third,
    credits,
    calligram,
    overlay_video,
    fonts,
]
