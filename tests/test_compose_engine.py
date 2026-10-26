"""The engine that draws a text measures it, through the compose builders (tituli#13)."""

import pytest

from tituli import EMBEDDED, TextStyle, measure
from tituli.compose import (
    caption,
    fit,
    intertitle,
    lower_third,
    note,
    title_card,
    truncate,
)
from tituli.frame import Frame
from tituli.layout import fill_shape
from tituli.schedule import Label, TimedOverlay
from tituli.video import materialize

FH = 1080
STYLE = TextStyle(family=EMBEDDED, size=0.05)
FRAME = Frame.blank((1920, 1080))


class Doubling:
    """A stand-in engine whose text is twice as wide as Pillow's."""

    def length(self, face, text):
        return 2 * face.length(text)

    def draw_run(self, canvas, run, opacity):  # pragma: no cover - never drawn
        raise AssertionError


def _width(lay):
    return lay.bbox().width


@pytest.mark.parametrize(
    "build",
    [
        lambda **kw: caption("Eliza at the harp", "Earl, 1787", frame=FRAME, **kw),
        lambda **kw: lower_third("Eliza Hamilton", "Founder", frame=FRAME, **kw),
        lambda **kw: title_card("The Apple", "a poem", frame=FRAME, **kw),
        lambda **kw: note(["Philip died at 19"], headline="Context", frame=FRAME, **kw),
        lambda **kw: intertitle("It was a dark night", frame=FRAME, **kw),
    ],
    ids=["caption", "lower_third", "title_card", "note", "intertitle"],
)
def test_builders_measure_with_the_engine(build):
    plain, wide = build(), build(engine=Doubling())
    assert all(r.advance is not None for r in wide.runs)
    assert all(r.advance is None for r in plain.runs)
    assert _width(wide) > 1.2 * _width(plain)


def test_fit_shrinks_for_a_wider_engine():
    text = "one two three four"
    width = measure(text, STYLE, FH) * 1.1  # one line for Pillow, two for Doubling
    _, plain = fit(text, STYLE, FH, max_width=width, max_lines=1)
    _, wide = fit(text, STYLE, FH, max_width=width, max_lines=1, engine=Doubling())
    assert wide.size < plain.size


def test_truncate_cuts_where_the_engine_says():
    text = "one two three four five six"
    kept = truncate(text, STYLE, FH, max_width=900, max_lines=1)
    cut = truncate(text, STYLE, FH, max_width=900, max_lines=1, engine=Doubling())
    assert len(cut) < len(kept)


def test_materialize_threads_the_engine_to_payloads():
    done = materialize(
        [TimedOverlay(None, 0, 2, payload=Label("Eliza", "Earl, 1787"))],
        frame=FRAME,
        engine=Doubling(),
    )
    assert all(r.advance is not None for r in done[0].layout.runs)


def test_fill_shape_measures_each_word_once():
    from PIL import Image

    from tituli.geometry import Box

    calls = []

    class Counting(Doubling):
        def length(self, face, text):
            calls.append(text)
            return super().length(face, text)

    mask = Image.new("L", (400, 300), 255)
    fill_shape(
        "alpha beta gamma",
        mask,
        STYLE,
        FH,
        box=Box(0, 0, 400, 300),
        engine=Counting(),
    )
    for w in ("alpha", "beta", "gamma"):
        assert calls.count(w) == 1


def test_run_outline_refuses_an_engine_measured_run_without_the_engine():
    pytest.importorskip("fontTools")
    from tituli import block, run_outline

    wide = block("ab", STYLE, FH, engine=Doubling())
    run = wide.runs[0]
    with pytest.raises(ValueError, match="engine"):
        run_outline(run)
    run_outline(run, engine=Doubling())  # the engine that measured it: fine
