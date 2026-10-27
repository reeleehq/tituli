"""A text halo: a soft glow under the glyphs instead of a scrim (tituli#19)."""

import pytest
from PIL import Image

from tituli import EMBEDDED, Frame, Halo, TextStyle, caption, render, render_overlay
from tituli.layout import Layout, block

SIZE = (640, 320)
BIG = TextStyle(family=EMBEDDED, size=0.12, italic=True)


def _centred(**kw):
    return caption(
        "AI imagining", frame=Frame.blank(SIZE), anchor="center", style=BIG, **kw
    )


def _core(lay):
    """A pixel the glyphs cover fully (where only the text can decide the colour)."""
    alpha = render_overlay(lay.with_halo(None), SIZE).getchannel("A")
    return next(
        (x, y)
        for y in range(SIZE[1])
        for x in range(SIZE[0])
        if alpha.getpixel((x, y)) == 255
    )


def _ring_alpha(img, lay):
    """Alpha just outside the text block's bbox (where only a halo can be)."""
    bb = lay.bbox()
    y = int(bb.y0 + bb.height / 2)
    x = int(bb.x0) - 3
    return img.getchannel("A").getpixel((x, y))


def test_a_halo_glows_around_the_text_and_nothing_else():
    plain = _centred(scrim=False, accent=False)
    glowing = _centred(scrim=False, accent=False, halo=True)
    assert all(r.halo == Halo() for r in glowing.runs)
    a, b = render_overlay(plain, SIZE), render_overlay(glowing, SIZE)
    assert _ring_alpha(a, plain) == 0
    assert _ring_alpha(b, glowing) > 0
    # the glow stays near the glyphs: the frame's corners are untouched
    assert b.getpixel((0, 0))[3] == 0 and b.getpixel((SIZE[0] - 1, SIZE[1] - 1))[3] == 0
    # and the text is still drawn on top, in its own ink
    assert b.getchannel("A").getbbox() is not None


def test_the_halo_replaces_the_automatic_scrim_and_says_so():
    auto = _centred(accent=False)
    assert auto.plates  # unknown background: a scrim by default
    haloed = _centred(accent=False, halo=True)
    assert not haloed.plates
    assert "halo instead of scrim" in haloed.meta["ink"]
    forced = _centred(accent=False, halo=True, scrim=True)
    assert forced.plates and "halo" not in forced.meta["ink"]


def test_the_text_is_drawn_on_top_of_its_halo():
    ink = (255, 255, 255)
    lay = _centred(scrim=False, accent=False, halo=Halo(opacity=1), ink=ink)
    assert render_overlay(lay, SIZE).getpixel(_core(lay)) == (*ink, 255)


def test_halo_colour_opposes_the_ink_unless_given():
    # orange is a mid-tone: light enough that dark gives it more contrast
    for ink, dark in (
        ((255, 255, 255), True),
        ((17, 17, 17), False),
        ((230, 120, 40), True),
    ):
        lay = _centred(scrim=False, accent=False, halo=True, ink=ink)
        img = render_overlay(lay, SIZE)
        r, g, b, a = img.getpixel(
            (int(lay.bbox().x0) - 3, int(lay.bbox().y0 + lay.bbox().height / 2))
        )
        assert a > 0 and ((r < 128) if dark else (r > 128))
    red = _centred(scrim=False, accent=False, halo=Halo(color="#ff0000"))
    r, g, b, _ = render_overlay(red, SIZE).getpixel(
        (int(red.bbox().x0) - 3, int(red.bbox().y0 + red.bbox().height / 2))
    )
    assert r > 200 and g < 50


def test_the_halo_fades_with_the_reveal():
    lay = _centred(scrim=False, accent=False, halo=True).with_timing(1.0, 2.0)
    before = render_overlay(lay, SIZE, t=0.5)
    half = render_overlay(lay, SIZE, t=1.5)
    full = render_overlay(lay, SIZE, t=2.5)
    assert before.getchannel("A").getbbox() is None
    assert 0 < _ring_alpha(half, lay) < _ring_alpha(full, lay)


def test_a_fading_halo_fades_with_its_text_not_ahead_of_it():
    """Glyph and glow fade as one: no dark silhouette before the letters show."""
    lay = _centred(scrim=False, accent=False, halo=True).with_timing(1.0, 2.0)
    core = _core(lay)
    full = render_overlay(lay, SIZE, t=2.5).getpixel(core)
    for t, f in ((1.25, 0.25), (1.5, 0.5)):
        faded = render_overlay(lay, SIZE, t=t).getpixel(core)
        assert faded[3] == pytest.approx(f * full[3], abs=2)
        assert faded[:3] == full[:3]  # still the ink's colour, not the halo's


def test_halo_is_sized_in_em():
    def reach(frame_h):
        f = Frame.blank((frame_h * 2, frame_h))
        lay = block("I", BIG, f).with_halo()
        lay = lay.translated(frame_h, frame_h / 3)
        ink = render_overlay(lay.with_halo(None), f.size).getchannel("A").getbbox()
        glow = render_overlay(lay, f.size).getchannel("A").getbbox()
        return (ink[0] - glow[0]) / lay.runs[0].face.size

    small, large = reach(400), reach(800)
    assert small > Halo().spread  # the glow reaches past its dilation...
    assert small == pytest.approx(large, rel=0.1)  # ...by the same number of em


def test_each_type_size_gets_its_own_halo():
    """A small line beside a big one glows as if it were alone: halos group by size."""
    f = Frame.blank(SIZE)
    big = block("I", BIG, f).translated(100, 80).with_halo()
    small = block("i", BIG.with_(size=0.04), f).translated(400, 140).with_halo()
    both = render_overlay(Layout(big.runs + small.runs), SIZE)
    alone = render_overlay(small, SIZE)
    region = (300, 0, SIZE[0], SIZE[1])
    assert both.crop(region).tobytes() == alone.crop(region).tobytes()


def test_a_halo_at_the_frame_edge_is_clipped_not_an_error():
    gap = 2  # px between the frame's left edge and the ink: within the glow's reach
    lay = block("Edge", BIG, Frame.blank(SIZE)).with_halo()
    x0 = render_overlay(lay.with_halo(None), SIZE).getchannel("A").getbbox()[0]
    lay = lay.translated(gap - x0, 0)
    plain = render_overlay(lay.with_halo(None), SIZE).getchannel("A")
    img = render_overlay(lay, SIZE)
    _, y0, _, y1 = plain.getbbox()
    edge = [(0, y) for y in range(y0, y1)]
    assert img.size == SIZE
    assert max(plain.getpixel(p) for p in edge) == 0  # no ink at the edge...
    assert max(img.getchannel("A").getpixel(p) for p in edge) > 0  # ...but glow, cut


def test_a_halo_refuses_impossible_settings():
    for bad in ({"spread": -0.1}, {"blur": -1}, {"gain": -2}, {"opacity": 1.5}):
        with pytest.raises(ValueError, match=next(iter(bad))):
            Halo(**bad)
    with pytest.raises(ValueError, match="opacity"):
        Halo(opacity=-0.1)
    assert Halo(spread=0, blur=0, gain=0, opacity=0)  # zero is allowed


def test_render_composites_a_halo_onto_a_picture():
    """The issue's case: white type over bright sand, darkened only around the letters."""
    from PIL import ImageStat

    sand = (240, 220, 170)
    bright = Frame.from_image(Image.new("RGB", SIZE, sand))

    def shot(halo):
        lay = caption(
            "Sand",
            frame=bright,
            anchor="center",
            style=BIG,
            ink=(255, 255, 255),
            scrim=False,
            halo=halo,
            accent=False,
        )
        bb = lay.bbox()
        around = (int(bb.x0) - 8, int(bb.y0) - 8, int(bb.x1) + 8, int(bb.y1) + 8)
        out = render(lay, bright)
        return out, sum(ImageStat.Stat(out.crop(around)).mean)

    plain, plain_mean = shot(False)
    glowing, glow_mean = shot(True)
    assert glow_mean < plain_mean - 60  # the block reads darker...
    assert glowing.getpixel((0, 0)) == sand  # ...but the picture is not dimmed


def test_overlay_items_and_cli_take_a_halo(tmp_path, monkeypatch):
    import tituli.compose as compose
    from tituli import tools
    from tituli.schedule import TimedOverlay
    from tituli.video import materialize

    f = Frame.blank(SIZE)
    done = materialize(
        [TimedOverlay(None, 0, 2, payload={"text": "Hi", "halo": True})], frame=f
    )
    assert all(r.halo == Halo() for r in done[0].layout.runs)
    tuned = materialize(
        [TimedOverlay(None, 0, 2, payload={"text": "Hi", "halo": {"spread": 0.05}})],
        frame=f,
    )
    assert all(r.halo == Halo(spread=0.05) for r in tuned[0].layout.runs)
    for bad in ("false", 1, {"radius": 2}):
        item = TimedOverlay(None, 0, 2, payload={"text": "Hi", "halo": bad})
        with pytest.raises(ValueError, match=r"#0 \[0.00, 2.00\] halo="):
            materialize([item], frame=f)

    seen = []
    real = compose.caption
    monkeypatch.setattr(
        compose, "caption", lambda *a, **k: seen.append(k["halo"]) or real(*a, **k)
    )
    img = tmp_path / "in.png"
    Image.new("RGB", SIZE, (200, 200, 200)).save(img)
    tools.caption(str(img), "Hi", out=str(tmp_path / "o.png"), avoid=None, halo=True)
    assert seen == [True] and (tmp_path / "o.png").exists()
