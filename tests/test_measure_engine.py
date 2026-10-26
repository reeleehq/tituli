"""The engine that draws a text measures it (tituli#7)."""

import pytest

from tituli import TextStyle, block, glossed, measure, wrap, fit_size, stack, EMBEDDED
from tituli.render import PillowEngine

FH = 1080
STYLE = TextStyle(family=EMBEDDED, size=0.05)


class Doubling:
    """A stand-in engine whose text is twice as wide as Pillow's."""

    def length(self, face, text):
        return 2 * face.length(text)

    def draw_run(self, canvas, run, opacity):  # pragma: no cover - never drawn
        raise AssertionError


def test_pillow_engine_is_the_default_measure():
    assert measure("hello", STYLE, FH, engine=PillowEngine()) == measure(
        "hello", STYLE, FH
    )


def test_measure_follows_the_engine():
    assert measure("hello", STYLE, FH, engine=Doubling()) == pytest.approx(
        2 * measure("hello", STYLE, FH)
    )


def test_wrap_breaks_where_the_engine_says():
    text = "one two three four"
    width = measure(text, STYLE, FH) * 1.1  # fits on one line for Pillow
    assert len(wrap(text, STYLE, FH, max_width=width)) == 1
    assert len(wrap(text, STYLE, FH, max_width=width, engine=Doubling())) >= 2


def test_fit_size_shrinks_for_a_wider_engine():
    text = "Supercalifragilisticexpialidocious"  # one unbreakable word
    width = measure(text, STYLE, FH) * 1.1
    assert fit_size(text, STYLE, FH, max_width=width).size == STYLE.size
    assert (
        fit_size(text, STYLE, FH, max_width=width, engine=Doubling()).size < STYLE.size
    )


@pytest.mark.parametrize("unit", ["line", "word", "glyph"])
def test_block_runs_keep_the_engine_width(unit):
    plain = block("ab cd", STYLE, FH, unit=unit)
    wide = block("ab cd", STYLE, FH, unit=unit, engine=Doubling())
    assert wide.bbox().width == pytest.approx(2 * plain.bbox().width, rel=0.02)
    assert all(r.advance is not None for r in wide.runs)
    assert all(r.advance is None for r in plain.runs)


def test_block_without_engine_is_unchanged():
    assert block("ab", STYLE, FH) == block("ab", STYLE, FH, engine=None)


def test_a_stack_places_by_the_engine_width():
    a = block("wide line", STYLE, FH, engine=Doubling())
    b = block("x", STYLE, FH, engine=Doubling())
    s = stack([a, b], frame=FH, align="right", anchor=None)
    right = {round(r.bbox().x1, 3) for r in s.runs}
    assert len(right) == 1  # both lines end on the engine-measured right edge


def test_glossed_pitch_follows_the_engine():
    pairs = [("ab", "x"), ("cd", "y")]
    plain = glossed(pairs, frame=FH, anchor=None)
    wide = glossed(pairs, frame=FH, anchor=None, engine=Doubling())
    assert wide.bbox().width > plain.bbox().width


class Kerning:
    """An engine that kerns "AV" pairs tighter across characters, as a shaper does."""

    def length(self, face, text):
        return face.length(text) - 0.1 * face.size * text.count("AV")

    def draw_run(self, canvas, run, opacity):  # pragma: no cover
        raise AssertionError


@pytest.mark.parametrize("align", ["left", "center", "right"])
def test_glyph_layout_measures_what_its_glyphs_occupy(align):
    """Glyph runs advance by single characters, so the line's width (alignment,
    block_width) is the sum of those, not a kerned whole-line measure."""
    style = STYLE.with_(align=align)
    lay = block("AVAV", style, FH, unit="glyph", max_width=800, engine=Kerning())
    face = style.face(FH)
    occupied = sum(face.length(c) for c in "AVAV")
    x0 = min(r.bbox().x0 for r in lay.runs)
    x1 = max(r.bbox().x1 for r in lay.runs)
    assert x1 - x0 == pytest.approx(occupied, abs=1.0)
    if align == "right":
        assert x1 == pytest.approx(800, abs=1.0)


def test_an_engine_that_cannot_measure_says_so():
    class DrawOnly:
        def draw_run(self, canvas, run, opacity):  # pragma: no cover
            ...

    with pytest.raises(TypeError, match="length"):
        measure("abc", STYLE, FH, engine=DrawOnly())


def test_harfbuzz_length_is_the_pen_advance_it_draws():
    pytest.importorskip("uharfbuzz")
    pytest.importorskip("freetype")
    from PIL import Image

    from tituli import Run
    from tituli.fonts import resolve_face
    from tituli.shaping import HarfBuzzEngine

    face = resolve_face("Helvetica", size=100)
    if face.path is None:
        pytest.skip("no installed font to shape with")
    eng = HarfBuzzEngine()
    ink = []
    for text in ("AV", "A"):
        canvas = Image.new("RGBA", (400, 200))
        eng.draw_run(canvas, Run(text, 10, 120, face, (0, 0, 0, 255)), 1.0)
        ink.append(canvas.getchannel("A").getbbox())
    # drawn right edge of "AV" = pen advance of "A" (shaped, kerned) + V's own ink
    assert eng.length(face, "AV") <= eng.length(face, "A") + eng.length(face, "V")
    assert eng.length(face, "AV") == pytest.approx(
        sum(eng.length(face, c) for c in "AV"), abs=face.size * 0.2
    )
    assert ink[0][2] > ink[1][2]  # the second glyph is drawn after the first
    emb = resolve_face(EMBEDDED, size=40)
    assert eng.length(emb, "abc") == pytest.approx(emb.length("abc"))
