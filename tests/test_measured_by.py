"""``Run.measured_by``: which engine measured a run, refused both ways (tituli#15)."""

import json
from dataclasses import replace

import pytest
from PIL import Image

from tituli import EMBEDDED, Frame, Layout, TextStyle, render_overlay
from tituli import tools
from tituli.compose import caption
from tituli.layout import Run, block, check_measured_by
from tituli.outlines import run_outline
from tituli.render import PillowEngine

STYLE = TextStyle(family=EMBEDDED, size=0.05)
FH = 1080


class Other:
    """A stand-in engine, named by its class."""

    def length(self, face, text):
        return face.length(text)

    def draw_run(self, canvas, run, opacity):
        pass


def _runs(engine):
    return block(["ab"], STYLE, Frame.blank((640, 360)), engine=engine).runs


def test_runs_record_the_engine_that_measured_them():
    assert {r.measured_by for r in _runs(PillowEngine())} == {"pillow"}
    assert {r.measured_by for r in _runs(Other())} == {"Other"}
    assert {r.measured_by for r in _runs(None)} == {None}


def test_a_matching_or_unrecorded_run_passes():
    pillow, other = _runs(PillowEngine())[0], _runs(Other())[0]
    check_measured_by(pillow, PillowEngine())
    check_measured_by(pillow, None)  # the face is what Pillow measures with
    check_measured_by(other, Other())
    check_measured_by(replace(other, measured_by=None), PillowEngine())


def test_a_mismatch_is_refused_in_both_directions():
    pillow, other = _runs(PillowEngine())[0], _runs(Other())[0]
    with pytest.raises(ValueError, match="'Other'"):
        check_measured_by(other, None)
    with pytest.raises(ValueError, match="'Other'"):
        check_measured_by(other, PillowEngine())
    with pytest.raises(ValueError, match="'pillow'"):
        check_measured_by(pillow, Other())


def test_run_outline_refuses_another_engines_run():
    pytest.importorskip("fontTools")
    run = _runs(Other())[0]
    with pytest.raises(ValueError, match="measured by"):
        run_outline(run, engine=PillowEngine())
    assert run_outline(run, engine=Other()).d


def test_render_overlay_refuses_a_layout_measured_by_another_engine():
    lay = caption("Hello", "x", frame=Frame.blank((640, 360)), engine=Other())
    with pytest.raises(ValueError, match="measured by"):
        render_overlay(lay, (640, 360), engine=PillowEngine())
    assert render_overlay(lay, (640, 360), engine=Other()).size == (640, 360)


def test_credits_and_calligram_take_an_engine(tmp_path, monkeypatch):
    seen = []
    real = tools._engine

    def spy(name):
        seen.append(name)
        return real(name)

    monkeypatch.setattr(tools, "_engine", spy)
    spec = json.dumps({"title": "T", "sections": [{"heading": "H", "entries": ["A"]}]})
    tools.credits(
        spec, out=str(tmp_path / "c.png"), mode="cards", size="320x180", engine="pillow"
    )
    tools.calligram(
        "hello world", out=str(tmp_path / "g.png"), size="320x180", engine="pillow"
    )
    assert seen == ["pillow", "pillow"]


def test_overlay_video_resolves_auto_anchors_to_the_corner_they_land_in(
    tmp_path, monkeypatch
):
    """An "auto" caption occupies a real corner, so it contends with a named one."""
    import tituli.video as video

    monkeypatch.setattr(video, "probe_size", lambda v: (640, 360))
    monkeypatch.setattr(video, "overlay", lambda *a, **k: None)
    items = [
        {"start": 0, "end": 2, "text": "Hello", "anchor": "auto"},
        {"start": 1, "end": 3, "text": "Again", "anchor": "top-left"},
    ]
    with pytest.raises(ValueError, match="collide"):
        tools.overlay_video("v.mp4", json.dumps(items), out="o.mp4")


def test_overlay_video_lays_out_with_the_engine(monkeypatch):
    import tituli.video as video

    got = {}
    monkeypatch.setattr(video, "probe_size", lambda v: (640, 360))
    monkeypatch.setattr(
        video, "overlay", lambda v, kept, out, **kw: got.update(kept=kept, **kw)
    )
    items = [
        {"start": 0, "end": 2, "text": "Hello", "attribution": "x"},
        {"start": 3, "end": 5, "text": "Name", "role": "Cook", "kind": "lower_third"},
    ]
    res = tools.overlay_video("v.mp4", json.dumps(items), out="o.mp4", engine="pillow")
    assert res["overlays"] == 2 and res["dropped"] == 0
    assert [o.slot for o in got["kept"]] == ["top-left", "bottom-left"]
    assert {r.measured_by for o in got["kept"] for r in o.layout.runs} == {"pillow"}


def test_dropping_the_advance_drops_the_engine_claim():
    run = _runs(Other())[0]
    assert run.measured_by == "Other"
    bare = replace(run, advance=None)
    assert bare.measured_by is None
    check_measured_by(bare, PillowEngine())


def test_harfbuzz_stamps_the_embedded_font_as_measured_by_pillow():
    """HarfBuzz hands the file-less embedded font to Pillow; the stamp says so (tituli#18)."""
    pytest.importorskip("uharfbuzz")
    pytest.importorskip("freetype")
    from tituli.fonts import resolve_face
    from tituli.shaping import HarfBuzzEngine

    hb = HarfBuzzEngine()
    runs = _runs(hb)
    assert {r.measured_by for r in runs} == {"pillow"}
    for run in runs:  # usable with either engine: the widths are Pillow's
        check_measured_by(run, PillowEngine())
        check_measured_by(run, hb)
    assert render_overlay(Layout(tuple(runs)), (640, 360)).size == (640, 360)

    face = resolve_face("DejaVu Sans", size=40)
    if face.path is None:
        pytest.skip("no installed font to shape with")
    shaped = block(
        ["ab"],
        TextStyle(family="DejaVu Sans", size=0.05),
        Frame.blank((640, 360)),
        engine=hb,
    ).runs
    assert {r.measured_by for r in shaped} == {"harfbuzz"}
    with pytest.raises(ValueError, match="'harfbuzz'"):
        check_measured_by(shaped[0], PillowEngine())


class Remeasuring(PillowEngine):
    """Inherits ``name = "pillow"`` but measures differently."""

    def length(self, face, text):
        return 2 * face.length(text)


class Renamed(PillowEngine):
    name = "renamed"

    def length(self, face, text):
        return 2 * face.length(text)


def test_a_subclass_that_remeasures_is_not_mistaken_for_its_base():
    assert {r.measured_by for r in _runs(Remeasuring())} == {"Remeasuring"}
    assert {r.measured_by for r in _runs(Renamed())} == {"renamed"}
    with pytest.raises(ValueError, match="'Remeasuring'"):
        check_measured_by(_runs(Remeasuring())[0], PillowEngine())


def test_an_instance_name_tells_two_configurations_apart():
    a, b = Other(), Other()
    a.name, b.name = "other:tight", "other:loose"
    assert {r.measured_by for r in _runs(a)} == {"other:tight"}
    with pytest.raises(ValueError, match="'other:tight'"):
        check_measured_by(_runs(a)[0], b)
