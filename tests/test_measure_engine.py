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


def test_harfbuzz_length_is_the_sum_of_what_it_draws():
    pytest.importorskip("uharfbuzz")
    pytest.importorskip("freetype")
    from tituli.fonts import resolve_face
    from tituli.shaping import HarfBuzzEngine, shape

    face = resolve_face("Helvetica", size=100)
    if face.path is None:
        pytest.skip("no installed font to shape with")
    eng = HarfBuzzEngine()
    want = sum(
        a[1]
        for a in shape(
            "AVA fi", face.path, face.index, face.size, features=eng._features(face)
        )
    )
    assert eng.length(face, "AVA fi") == pytest.approx(want)
    assert eng.length(resolve_face(EMBEDDED, size=40), "abc") == pytest.approx(
        resolve_face(EMBEDDED, size=40).length("abc")
    )
