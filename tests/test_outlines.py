"""Glyph outlines (`tituli.outlines`) and the deterministic font request (`EMBEDDED`)."""

import hashlib
import re

import pytest
from PIL import Image, ImageDraw

from tituli import (
    EMBEDDED,
    Run,
    TextStyle,
    block,
    face_digest,
    resolve_face,
    run_outline,
)
from tituli.fonts import FALLBACK_FAMILY, face_bytes
from tituli.outlines import MissingGlyphError

INK = (0, 0, 0, 255)


def _run(text, *, size=80, x=20.0, y=100.0, **kw):
    return Run(text, x, y, resolve_face(EMBEDDED, size=size), INK, **kw)


# --- EMBEDDED ----------------------------------------------------------------------


def test_embedded_never_consults_the_system(monkeypatch):
    """`EMBEDDED` first means no scan at all — which is what makes it deterministic."""
    import tituli.fonts as fonts

    def boom():
        raise AssertionError("EMBEDDED must not scan the installed fonts")

    monkeypatch.setattr(fonts, "font_index", boom)
    face = resolve_face(EMBEDDED, size=30)
    assert (face.family, face.path, face.size) == (FALLBACK_FAMILY, None, 30)
    # ...and as the first entry of a preference list too
    assert resolve_face([EMBEDDED, "Helvetica"], size=30).path is None


def test_embedded_is_a_stop_in_a_preference_list():
    # names BEFORE it are still looked up; nothing after it is
    face = resolve_face(
        ["definitely-not-installed-xyz", EMBEDDED, "DejaVu Sans"], size=20
    )
    assert face.path is None


def test_face_identity_is_the_bytes():
    face = resolve_face(EMBEDDED, size=12)
    assert face_digest(face) == hashlib.sha256(face_bytes(face)).hexdigest()
    # size does not change the file
    assert face_digest(face) == face_digest(face.with_size(90))


# --- outlines ------------------------------------------------------------------------


def test_outline_lands_where_pillow_draws_the_run():
    """The contours and the rasteriser agree to a pixel: same face, same advances."""
    run = _run("Wave AVo")
    out = run_outline(run)
    im = Image.new("L", (800, 200), 0)
    ImageDraw.Draw(im).text(
        (run.x, run.y), run.text, font=run.face.pil, fill=255, anchor="ls"
    )
    x0, y0, x1, y1 = im.getbbox()
    b = out.bbox
    assert abs(b.x0 - x0) <= 1.5 and abs(b.x1 - x1) <= 1.5
    assert abs(b.y0 - y0) <= 1.5 and abs(b.y1 - y1) <= 1.5


def test_outline_is_translation_equivariant():
    a = run_outline(_run("Hi", x=0.0, y=0.0)).bbox
    b = run_outline(_run("Hi", x=100.0, y=40.0)).bbox
    assert (b.x0 - a.x0, b.y0 - a.y0) == pytest.approx((100.0, 40.0))


def test_rotation_turns_the_run_clockwise_about_its_origin():
    flat = run_outline(_run("Hi", x=0.0, y=0.0)).bbox
    down = run_outline(_run("Hi", x=0.0, y=0.0, angle=90.0)).bbox
    # the baseline now runs down the screen and the ink's tops point right
    assert down.y1 == pytest.approx(flat.x1, abs=0.02)
    assert down.x0 >= -0.01 and down.x1 == pytest.approx(-flat.y0, abs=0.02)


def test_tracking_widens_the_run_by_exactly_tracking_per_gap():
    base = run_outline(_run("AAA")).bbox
    tracked = run_outline(_run("AAA", tracking=10.0)).bbox
    assert tracked.width - base.width == pytest.approx(20.0, abs=0.02)


def test_a_space_has_no_ink():
    out = run_outline(_run(" "))
    assert out.d == "" and out.bbox is None


def test_missing_glyph_raises_naming_the_character():
    with pytest.raises(MissingGlyphError, match=r"U\+00E9"):
        run_outline(_run("café"))


def test_path_data_is_short_and_byte_stable():
    d = run_outline(_run("Stable")).d
    assert d == run_outline(_run("Stable")).d
    assert not re.search(r"\d\.\d{3}", d)  # two decimals at most
    assert "-0 " not in d and "e-" not in d


def test_word_runs_from_block_each_outline_inside_their_layout_box():
    lay = block(
        "one two three", TextStyle(family=(EMBEDDED,), size=0.06), 1080, unit="word"
    )
    assert [r.text for r in lay.runs] == ["one", "two", "three"]
    for r in lay.runs:
        ink, box = run_outline(r).bbox, r.bbox()
        assert box.x0 - 2 <= ink.x0 and ink.x1 <= box.x1 + 2
        assert box.y0 - 2 <= ink.y0 and ink.y1 <= box.y1 + 2
