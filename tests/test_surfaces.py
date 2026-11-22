"""Surface guardrails: the core stays surface-agnostic; the tools and video paths run."""

import json
import shutil
import subprocess
import sys

import pytest
from PIL import Image

from tituli import Frame, TimedOverlay, caption, render_overlay
from tituli.tools import _dispatch_funcs

SURFACE_LIBS = {
    "argh",
    "cw",
    "click",
    "typer",
    "fastapi",
    "starlette",
    "uvicorn",
    "flask",
    "mcp",
    "fastmcp",
    "qh",
    "uf",
}


def test_core_import_pulls_no_surface_library():
    code = (
        "import sys, importlib; importlib.import_module('tituli');"
        f"bad = {{m.split('.')[0] for m in sys.modules}} & {SURFACE_LIBS!r}; print(sorted(bad))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout
    assert out.strip() == "[]"


def test_core_import_pulls_no_optional_dependency():
    code = (
        "import sys, importlib; importlib.import_module('tituli');"
        "print(sorted({m.split('.')[0] for m in sys.modules} & {'burns', 'lacing', 'uharfbuzz', 'freetype', 'numpy'}))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout
    assert out.strip() == "[]"


def test_dispatch_funcs_are_json_shaped(tmp_path):
    names = sorted(f.__name__ for f in _dispatch_funcs)
    assert names == [
        "calligram",
        "caption",
        "credits",
        "fonts",
        "lower_third",
        "overlay_video",
        "title_card",
    ]


def test_tools_title_card_and_caption(tmp_path):
    from tituli.tools import caption as caption_tool
    from tituli.tools import title_card

    r = title_card(
        "Hello", "world", out=str(tmp_path / "t.png"), background="#000", size="640x360"
    )
    assert (tmp_path / "t.png").exists() and r["bbox"][2] > r["bbox"][0]
    still = tmp_path / "still.jpg"
    Image.new("RGB", (640, 360), (40, 40, 40)).save(still)
    r = caption_tool(
        str(still), "A thing", "a source", out=str(tmp_path / "c.png"), avoid=None
    )
    assert (tmp_path / "c.png").exists() and r["anchor"]


def test_tools_credits_cards_png(tmp_path):
    from tituli.tools import credits

    spec = json.dumps(
        {"title": "T", "sections": [{"heading": "Cast", "entries": [["Role", "Name"]]}]}
    )
    r = credits(spec, out=str(tmp_path / "cred.png"), mode="cards", size="640x360")
    assert r["cards"] == 1 and (tmp_path / "cred_01.png").exists()


def test_tools_calligram_png(tmp_path):
    from tituli.tools import calligram

    r = calligram(
        "round and round", out=str(tmp_path / "c.png"), shape="circle", size="400x400"
    )
    assert r["glyphs"] == len("roundandround")


def test_cli_dispatch_lists_commands():
    pytest.importorskip("cw")
    out = subprocess.run(
        [sys.executable, "-m", "tituli", "--help"], capture_output=True, text=True
    )
    assert out.returncode == 0 and "title_card" in out.stdout.replace("-", "_")


# --- video (needs ffmpeg) ----------------------------------------------------------

ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")


@ffmpeg
def test_video_still_overlay_crawl_frames(tmp_path):
    from tituli import video
    from tituli.credits import Credits, credits_crawl, credits_frame
    from tituli.render import frames, render

    video.require_filters("overlay", "fade", "crop")
    size = (320, 180)
    base = Image.new("RGB", size, (30, 60, 90))
    clip = video.still(base, tmp_path / "still.mp4", duration=1.0, fps=10)
    assert clip.exists() and video.probe_size(clip) == size

    frame = Frame.blank(size)
    lay = caption("Hello", "src", frame=frame)
    out = video.overlay(
        clip,
        [TimedOverlay(lay, 0.2, 0.8)],
        tmp_path / "over.mp4",
        size=size,
        workdir=tmp_path / "w",
    )
    assert out.exists() and out.stat().st_size > 0

    cf = credits_frame(size)
    tall_lay, total = credits_crawl(Credits.from_lines(["a", "b", "c"]), frame=cf)
    tall = render(tall_lay, Frame.blank((size[0], total), color=cf.color))
    crawl = video.crawl(tall, tmp_path / "crawl.mp4", size=size, speed_px_s=400, fps=10)
    assert crawl.exists()

    fr = frames(
        lay.staggered(step=0.1, ramp=0.1),
        Frame.blank(size, color="#000"),
        duration=0.5,
        fps=10,
    )
    fv = video.frames_to_video(fr, tmp_path / "frames.mp4", size=size, fps=10)
    assert fv.exists()


@ffmpeg
def test_overlay_requires_a_layout(tmp_path):
    from tituli import video

    with pytest.raises(ValueError):
        video.overlay(
            "x.mp4", [TimedOverlay(None, 0, 1)], tmp_path / "o.mp4", size=(10, 10)
        )


def test_render_overlay_is_transparent_outside_text():
    lay = caption("Hi", frame=Frame.blank((300, 200)))
    img = render_overlay(lay, (300, 200))
    assert img.getpixel((299, 0))[3] == 0


def test_lacing_body_shape():
    from tituli.bodies import body_for

    f = Frame.blank((1920, 1080))
    b = body_for(caption("A", "B", frame=f), f, text="A", attribution="B")
    assert set(b) >= {
        "text",
        "attribution",
        "kind",
        "anchor",
        "box",
        "ink",
        "unlabelled",
    }
    pytest.importorskip("lacing")
    from lacing.schema import get_body_schema

    from tituli.bodies import TEXT_OVERLAY_V1, register

    assert register() == TEXT_OVERLAY_V1
    model = get_body_schema(TEXT_OVERLAY_V1)
    model(**b)
    with pytest.raises(Exception):
        model(**{**b, "extra": 1})


def test_body_records_the_halo():
    from tituli import Halo
    from tituli.bodies import body_for

    f = Frame.blank((1920, 1080))
    lay = caption("A", "B", frame=f)
    assert body_for(lay, f, text="A")["halo"] is None
    b = body_for(lay.with_halo(Halo(spread=0.05, color="#000000")), f, text="A")
    assert b["halo"]["spread"] == 0.05 and b["halo"]["color"] == "#000000"
    pytest.importorskip("lacing")
    from tituli.bodies import register
    from lacing.schema import get_body_schema

    from tituli.bodies import TEXT_OVERLAY_V1

    register()
    get_body_schema(TEXT_OVERLAY_V1).model_validate(b)
