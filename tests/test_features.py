"""OpenType features on a style (tituli#4): requested, recorded, measured and outlined."""

import pytest
from PIL import Image

pytest.importorskip("fontTools")

from tituli import EMBEDDED, Run, TextStyle, resolve_face, run_outline
from tituli.features import FeatureError, featured_glyphs, font_features
from tituli.fonts import Face
from tituli.render import PillowEngine

INK = (0, 0, 0, 255)
UPM = 1000
NARROW, WIDE = 300, 600  # "1" and "8" advances: proportional by default


def _box(width):
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    pen = TTGlyphPen(None)
    pen.moveTo((50, 0))
    pen.lineTo((50, 700))
    pen.lineTo((width - 50, 700))
    pen.lineTo((width - 50, 0))
    pen.closePath()
    return pen.glyph()


@pytest.fixture(scope="module")
def digits_font(tmp_path_factory):
    """A font whose default digits are proportional and whose `tnum` makes them
    one width — the font a counter jitters in."""
    from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
    from fontTools.fontBuilder import FontBuilder

    widths = {
        ".notdef": WIDE,
        "one": NARROW,
        "eight": WIDE,
        "one.tnum": WIDE,
        "eight.tnum": WIDE,
    }
    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(list(widths))
    fb.setupCharacterMap({ord("1"): "one", ord("8"): "eight"})
    fb.setupGlyf({name: _box(w) for name, w in widths.items()})
    fb.setupHorizontalMetrics({name: (w, 50) for name, w in widths.items()})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "Digits Test", "styleName": "Regular"})
    fb.setupOS2(
        sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200
    )
    fb.setupPost()
    addOpenTypeFeaturesFromString(
        fb.font, "feature tnum { sub one by one.tnum; sub eight by eight.tnum; } tnum;"
    )
    path = tmp_path_factory.mktemp("fonts") / "digits.ttf"
    fb.save(str(path))
    return str(path)


def _face(path, *features, size=UPM):
    return Face("Digits Test", "Regular", size, path, 0, tuple(features))


def test_a_style_carries_its_features_to_the_face():
    assert TextStyle(features={"tnum": True}).features == ("tnum",)
    assert TextStyle(features=("tnum", "zero")).face(1080).features == ("tnum", "zero")
    assert resolve_face(EMBEDDED, size=20, features=("tnum",)).with_size(
        40
    ).features == ("tnum",)
    with pytest.raises(ValueError, match="turned off"):
        TextStyle(features={"liga": False})


def test_a_feature_the_font_lacks_is_requested_but_not_applied():
    face = resolve_face(EMBEDDED, size=40, features=("tnum",))
    assert "tnum" not in font_features(face.path)
    assert face.applied_features == ()
    # ...so it measures exactly as without the request
    assert face.length("1188") == resolve_face(EMBEDDED, size=40).length("1188")


def test_tabular_figures_make_every_number_one_width(digits_font):
    plain, tnum = _face(digits_font), _face(digits_font, "tnum")
    assert tnum.applied_features == ("tnum",)
    assert plain.length("11") == pytest.approx(2 * NARROW)
    assert plain.length("11") != plain.length("88")  # the jitter
    assert tnum.length("11") == tnum.length("88") == pytest.approx(2 * WIDE)
    assert featured_glyphs(tnum, "18") == ["one.tnum", "eight.tnum"]


def test_the_outline_draws_the_glyphs_the_length_measured(digits_font):
    face = _face(digits_font, "tnum", size=100)
    out = run_outline(Run("11", 0.0, 100.0, face, INK))
    # two WIDE boxes, side-inset by 50 units each: 5 .. 115 px at size 100
    assert out.bbox.x0 == pytest.approx(5)
    assert out.bbox.x1 == pytest.approx(2 * WIDE / 10 - 5)


def test_pillow_refuses_to_draw_glyphs_it_cannot_substitute(digits_font):
    canvas = Image.new("RGBA", (300, 200))
    PillowEngine().draw_run(canvas, Run("11", 0.0, 100.0, _face(digits_font), INK), 1.0)
    with pytest.raises(FeatureError, match="HarfBuzzEngine"):
        PillowEngine().draw_run(
            canvas,
            Run("11", 0.0, 100.0, _face(digits_font, "tnum", size=100), INK),
            1.0,
        )


def test_harfbuzz_draws_the_substituted_glyphs(digits_font):
    pytest.importorskip("uharfbuzz")
    pytest.importorskip("freetype")
    from tituli.shaping import HarfBuzzEngine

    def ink_width(face):
        canvas = Image.new("RGBA", (400, 200))
        HarfBuzzEngine().draw_run(canvas, Run("11", 10.0, 120.0, face, INK), 1.0)
        x0, _, x1, _ = canvas.getbbox()
        return x1 - x0

    assert ink_width(_face(digits_font, "tnum", size=100)) > ink_width(
        _face(digits_font, size=100)
    )
