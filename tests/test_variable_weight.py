"""TextStyle.weight on a variable-font file sets its ``wght`` axis (tituli#9)."""

import pytest
from PIL import Image

pytest.importorskip("fontTools")

from tituli import Run, TextStyle, block, resolve_face, run_outline
from tituli.fonts import face_digest
from tituli.render import PillowEngine

LIGHT, HEAVY = 100, 900  # the axis range of the synthetic font
STEM = {LIGHT: 200, HEAVY: 800}  # width of the glyph's box at each end


@pytest.fixture(scope="module")
def vfont(tmp_path_factory):
    """A one-glyph variable font whose box widens with ``wght``."""
    from fontTools.designspaceLib import (
        AxisDescriptor,
        DesignSpaceDocument,
        SourceDescriptor,
    )
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.varLib import build

    def master(w):
        fb = FontBuilder(1000, isTTF=True)
        fb.setupGlyphOrder([".notdef", "A"])
        fb.setupCharacterMap({65: "A"})
        glyphs = {}
        for name in (".notdef", "A"):
            pen = TTGlyphPen(None)
            pen.moveTo((100, 0))
            pen.lineTo((100, 700))
            pen.lineTo((100 + w, 700))
            pen.lineTo((100 + w, 0))
            pen.closePath()
            glyphs[name] = pen.glyph()
        fb.setupGlyf(glyphs)
        fb.setupHorizontalMetrics({n: (w + 200, 100) for n in glyphs})
        fb.setupHorizontalHeader(ascent=800, descent=-200)
        fb.setupNameTable({"familyName": "Vtest", "styleName": "Regular"})
        fb.setupOS2()
        fb.setupPost()
        return fb.font

    ds = DesignSpaceDocument()
    axis = AxisDescriptor()
    axis.tag, axis.name = "wght", "Weight"
    axis.minimum, axis.default, axis.maximum = LIGHT, LIGHT, HEAVY
    ds.addAxis(axis)
    for loc, w in STEM.items():
        src = SourceDescriptor()
        src.font, src.location, src.name = master(w), {"Weight": loc}, f"m{loc}"
        ds.addSource(src)
    path = tmp_path_factory.mktemp("vf") / "Vtest[wght].ttf"
    build(ds)[0].save(path)
    return str(path)


def _face(path, weight):
    return resolve_face(path, size=100, weight=weight)


def test_weight_sets_the_axis_and_changes_measure(vfont):
    light, heavy = _face(vfont, LIGHT), _face(vfont, HEAVY)
    assert (light.wght, heavy.wght) == (LIGHT, HEAVY)
    assert light.applied_variations == {"wght": LIGHT}
    assert light.length("A") == pytest.approx(40)
    assert heavy.length("A") == pytest.approx(100)


def test_weight_is_clamped_to_the_axis(vfont):
    assert _face(vfont, 1200).wght == HEAVY
    assert _face(vfont, 1).wght == LIGHT


def test_static_face_has_no_variation():
    from tituli import EMBEDDED

    face = resolve_face(EMBEDDED, size=20, weight=700)
    assert face.wght is None and face.applied_variations == {}


def test_with_size_keeps_the_weight(vfont):
    assert _face(vfont, 500).with_size(10).wght == 500


def test_pillow_ink_follows_weight(vfont):
    ink = {}
    for w in (LIGHT, HEAVY):
        lay = block(
            "A", TextStyle(family=(vfont,), size=0.2, weight=w), 500, x=10, y=10
        )
        canvas = Image.new("RGBA", (300, 300))
        PillowEngine().draw_run(canvas, lay.runs[0], 1.0)
        ink[w] = sum(1 for a in canvas.getchannel("A").tobytes() if a > 128)
    assert ink[HEAVY] > 2 * ink[LIGHT]


def test_outline_follows_weight(vfont):
    def width(w):
        run = Run("A", 0, 100, _face(vfont, w), (0, 0, 0, 255))
        return (lambda b: b.x1 - b.x0)(run_outline(run).bbox)

    assert width(HEAVY) == pytest.approx(
        width(LIGHT) * STEM[HEAVY] / STEM[LIGHT], rel=0.05
    )


def test_digest_tells_instances_apart(vfont):
    assert face_digest(_face(vfont, LIGHT)) != face_digest(_face(vfont, HEAVY))


def test_harfbuzz_follows_weight(vfont):
    pytest.importorskip("uharfbuzz")
    pytest.importorskip("freetype")
    from tituli.shaping import HarfBuzzEngine

    ink = {}
    for w in (LIGHT, HEAVY):
        run = Run("A", 50, 150, _face(vfont, w), (0, 0, 0, 255))
        canvas = Image.new("RGBA", (300, 300))
        HarfBuzzEngine().draw_run(canvas, run, 1.0)
        ink[w] = sum(1 for a in canvas.getchannel("A").tobytes() if a > 128)
    assert ink[HEAVY] > 2 * ink[LIGHT]
