"""TextStyle.weight on a variable-font file sets its ``wght`` axis (tituli#9)."""

import pytest
from PIL import Image

pytest.importorskip("fontTools")

from tituli import Run, TextStyle, block, resolve_face, run_outline
from tituli.fonts import Face, face_bytes, face_digest, variation_axes
from tituli.render import PillowEngine

LIGHT, HEAVY = 100, 900  # the axis range of the synthetic font
STEM = {LIGHT: 200, HEAVY: 800}  # width of the glyph's box at each end


WIDE_AT = 200  # the `wdth` value at which the multi-axis font's box doubles
ALT_EXTRA = 400  # how much wider the `ss01` alternate's advance is


def _build_vfont(path, axes, masters):
    """A one-glyph variable font: ``axes`` is ``{tag: (min, default, max)}``,
    ``masters`` is ``[(location, box width)]``. Its ``ss01`` swaps ``A`` for a
    wider-advancing ``A.alt``."""
    from fontTools.designspaceLib import (
        AxisDescriptor,
        DesignSpaceDocument,
        SourceDescriptor,
    )
    from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.varLib import build

    def master(w):
        fb = FontBuilder(1000, isTTF=True)
        names = [".notdef", "A", "A.alt"]
        fb.setupGlyphOrder(names)
        fb.setupCharacterMap({65: "A"})
        glyphs = {}
        for name in names:
            pen = TTGlyphPen(None)
            pen.moveTo((100, 0))
            pen.lineTo((100, 700))
            pen.lineTo((100 + w, 700))
            pen.lineTo((100 + w, 0))
            pen.closePath()
            glyphs[name] = pen.glyph()
        fb.setupGlyf(glyphs)
        extra = {"A.alt": ALT_EXTRA}
        fb.setupHorizontalMetrics({n: (w + 200 + extra.get(n, 0), 100) for n in glyphs})
        fb.setupHorizontalHeader(ascent=800, descent=-200)
        fb.setupNameTable({"familyName": "Vtest", "styleName": "Regular"})
        fb.setupOS2()
        fb.setupPost()
        addOpenTypeFeaturesFromString(fb.font, "feature ss01 { sub A by A.alt; } ss01;")
        return fb.font

    ds = DesignSpaceDocument()
    for tag, (lo, default, hi) in axes.items():
        axis = AxisDescriptor()
        axis.tag, axis.name = tag, tag
        axis.minimum, axis.default, axis.maximum = lo, default, hi
        ds.addAxis(axis)
    for i, (loc, w) in enumerate(masters):
        src = SourceDescriptor()
        src.font, src.location, src.name = master(w), loc, f"m{i}"
        ds.addSource(src)
    build(ds)[0].save(path)
    return str(path)


@pytest.fixture(scope="module")
def vfont(tmp_path_factory):
    """A one-glyph variable font whose box widens with ``wght``."""
    path = tmp_path_factory.mktemp("vf") / "Vtest[wght].ttf"
    masters = [({"wght": loc}, w) for loc, w in STEM.items()]
    return _build_vfont(path, {"wght": (LIGHT, LIGHT, HEAVY)}, masters)


@pytest.fixture(scope="module")
def vfont2(tmp_path_factory):
    """``wdth`` before ``wght`` (as in SFNS): only ``wght`` may move with weight."""
    path = tmp_path_factory.mktemp("vf2") / "Vtest[wdth,wght].ttf"
    masters = [
        ({"wdth": 100, "wght": LIGHT}, STEM[LIGHT]),
        ({"wdth": 100, "wght": HEAVY}, STEM[HEAVY]),
        ({"wdth": WIDE_AT, "wght": LIGHT}, 2 * STEM[LIGHT]),
    ]
    axes = {"wdth": (100, 100, WIDE_AT), "wght": (LIGHT, LIGHT, HEAVY)}
    return _build_vfont(path, axes, masters)


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


def test_features_measure_at_the_weight(vfont):
    def featured(w):
        face = resolve_face(vfont, size=100, weight=w, features=("ss01",))
        assert face.applied_features == ("ss01",)
        return face.length("A")

    extra = ALT_EXTRA / 10  # font units -> px at size 100, upm 1000
    assert featured(LIGHT) == pytest.approx(40 + extra)
    assert featured(HEAVY) == pytest.approx(100 + extra)


def test_other_axes_stay_at_their_default(vfont2):
    assert [a.tag for a in variation_axes(vfont2)] == ["wdth", "wght"]
    heavy = _face(vfont2, HEAVY)
    assert heavy.applied_variations == {"wght": HEAVY}
    assert heavy.length("A") == pytest.approx(100)  # wdth left at 100, not moved
    run = Run("A", 0, 100, heavy, (0, 0, 0, 255))
    bbox = run_outline(run).bbox
    assert bbox.x1 - bbox.x0 == pytest.approx(STEM[HEAVY] / 10, rel=0.05)


def test_harfbuzz_keeps_other_axes_at_default(vfont2):
    pytest.importorskip("uharfbuzz")
    from tituli.shaping import shape

    face = _face(vfont2, HEAVY)
    (glyph,) = shape("A", vfont2, 0, 100, variations=face.applied_variations)
    assert glyph[1] == pytest.approx(100, abs=1)


def test_static_face_digest_is_the_hash_of_its_bytes():
    import hashlib

    from tituli import EMBEDDED

    face = resolve_face(EMBEDDED, size=20, weight=700)
    assert face_digest(face) == hashlib.sha256(face_bytes(face)).hexdigest()


def test_digest_needs_no_fonttools(vfont, monkeypatch):
    import sys

    from tituli import fonts

    face = _face(vfont, 500)
    expected = face_digest(face)
    fonts._digest.cache_clear()
    for name in [m for m in sys.modules if m.split(".")[0] == "fontTools"]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setitem(sys.modules, "fontTools", None)  # import now fails
    assert face_digest(face) == expected
    assert face_digest(_face(vfont, 600)) != expected


def test_a_hand_built_weight_on_the_embedded_face_is_refused():
    with pytest.raises(ValueError, match="variable font"):
        Face("Aileron", "Regular", 20, None, 0, wght=700)


def test_a_hand_built_weight_on_a_static_file_is_refused(tmp_path):
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder([".notdef"])
    fb.setupCharacterMap({})
    fb.setupGlyf({".notdef": TTGlyphPen(None).glyph()})
    fb.setupHorizontalMetrics({".notdef": (500, 0)})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "Static", "styleName": "Regular"})
    fb.setupOS2()
    fb.setupPost()
    path = str(tmp_path / "static.ttf")
    fb.save(path)
    assert variation_axes(path) == ()
    assert resolve_face(path, size=20, weight=700).wght is None
    with pytest.raises(ValueError, match="'wght' axis"):
        Face("Static", "Regular", 20, path, 0, wght=700)


def test_hand_built_face_is_canonical(vfont):
    from dataclasses import replace

    base = _face(vfont, HEAVY)
    assert replace(base, wght=HEAVY).applied_variations == {"wght": 900.0}
    assert replace(base, wght=5000).wght == HEAVY  # clamped like resolve_face
    assert face_digest(replace(base, wght=5000)) == face_digest(
        replace(base, wght=HEAVY)
    )
