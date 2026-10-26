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


# --- the remaining measurers (tituli#12) -----------------------------------

from tituli import Credits, Frame, Run, along_path, calligram, credits_cards
from tituli.geometry import Box, Path
from tituli.layout import fill_shape, glyph_columns
from tituli.outlines import run_outline


def _frame():
    return Frame.blank((1920, 1080))


def test_along_path_follows_the_engine():
    path = Path.line((0, 500), (1800, 500))
    plain = along_path("hello", path, STYLE, FH)
    wide = along_path("hello", path, STYLE, FH, engine=Doubling())
    span = lambda lay: lay.runs[-1].x - lay.runs[0].x
    assert span(wide) > 1.5 * span(plain)
    assert all(r.advance is not None for r in wide.runs)
    assert all(r.advance is None for r in plain.runs)


def test_glyph_columns_centres_by_the_engine():
    kw = dict(box=Box(0, 0, 600, 600), slants=[0.0], head_offsets=[0.0])
    plain = glyph_columns(["ab"], STYLE, FH, **kw)
    wide = glyph_columns(["ab"], STYLE, FH, engine=Doubling(), **kw)
    assert wide.runs[0].x < plain.runs[0].x  # wider glyph, smaller left margin
    assert all(r.advance is not None for r in wide.runs)


def test_fill_shape_packs_fewer_words_for_a_wider_engine():
    from PIL import Image

    mask = Image.new("L", (400, 200), 255)
    text = "aa bb cc dd ee ff gg hh"
    plain = fill_shape(text, mask, STYLE, FH, box=Box(0, 0, 400, 200), repeat=False)
    wide = fill_shape(
        text, mask, STYLE, FH, box=Box(0, 0, 400, 200), repeat=False, engine=Doubling()
    )
    assert len(wide.meta["unplaced"]) > len(plain.meta["unplaced"])
    assert all(r.advance is not None for r in wide.runs)


def _mask():
    from PIL import Image

    return Image.new("L", (400, 200), 255)


def test_calligram_wrappers_pass_the_engine():
    frame = _frame()
    kw = dict(frame=frame, style=STYLE.with_(size=0.12), fit_text=False)
    plain = calligram.on_path("hello world", **kw)
    wide = calligram.on_path("hello world", engine=Doubling(), **kw)
    assert all(r.advance is not None for r in wide.runs)
    assert all(r.advance is None for r in plain.runs)
    assert (
        calligram.rain("ab", frame=frame, style=STYLE, engine=Doubling())
        .runs[0]
        .advance
    )
    assert (
        calligram.in_shape("ab", _mask(), frame=frame, style=STYLE, engine=Doubling())
        .runs[0]
        .advance
    )


def test_credits_follow_the_engine():
    frame = _frame()
    cr = Credits.from_lines(["Director: A. Person", "Editor: B. Person"])
    plain = credits_cards(cr, frame=frame)
    wide = credits_cards(cr, frame=frame, engine=Doubling())
    assert all(r.advance is None for lay in plain for r in lay.runs)
    assert all(r.advance is not None for lay in wide for r in lay.runs)


def test_run_outline_advances_with_the_engine():
    pytest.importorskip("fontTools")
    face = STYLE.face(FH)
    run = Run("ab", 0, 100, face, (0, 0, 0, 255))
    plain, wide = run_outline(run), run_outline(run, engine=Doubling())
    assert wide.bbox.x1 > plain.bbox.x1
