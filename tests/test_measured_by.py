"""``Run.measured_by``: which engine measured a run, refused both ways (tituli#15)."""

import json
from dataclasses import replace

import pytest
from PIL import Image

from tituli import EMBEDDED, Frame, TextStyle, render_overlay
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


def test_overlay_video_goes_through_materialize(tmp_path, monkeypatch):
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
    assert all(o.layout is not None for o in got["kept"])
    assert got["engine"].name == "pillow"
    assert {r.measured_by for o in got["kept"] for r in o.layout.runs} == {"pillow"}
