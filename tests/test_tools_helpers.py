"""The ``tituli.tools`` helpers and operations not exercised by test_surfaces (pure Pillow, no ffmpeg)."""

import json

import pytest
from PIL import Image

from tituli import tools


# --- _size / _avoid / _engine / _save -----------------------------------------


@pytest.mark.parametrize(
    "arg, expected",
    [
        (None, tools.DEFAULT_SIZE),
        ("1280x720", (1280, 720)),
        ("1080×1920", (1080, 1920)),
        ("640X360", (640, 360)),
        ([800, 600], (800, 600)),
        ((10.0, 20.0), (10, 20)),
    ],
)
def test_size_forms(arg, expected):
    assert tools._size(arg) == expected


def test_avoid_forms():
    assert tools._avoid(None) is None and tools._avoid("") is None
    assert tools._avoid("0.1,0.2,0.3,0.4") == [(0.1, 0.2, 0.3, 0.4)]
    with pytest.raises(ValueError, match="saliency"):
        tools._avoid("1,2,3")


def test_avoid_saliency_without_burns_names_the_extra(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "burns", None)
    with pytest.raises(ImportError, match="tituli\\[saliency\\]"):
        tools._avoid("saliency")


def test_engine_default_and_named():
    assert tools._engine(None) is None
    assert tools._engine("pillow") is not None


def test_save_creates_parent_and_flattens_rgba_for_jpeg(tmp_path):
    img = Image.new("RGBA", (4, 4), (255, 0, 0, 128))
    p = tools._save(img, tmp_path / "a" / "b" / "x.jpg")
    assert p.is_file() and Image.open(p).mode == "RGB"
    p2 = tools._save(img, tmp_path / "y.png")
    assert Image.open(p2).mode == "RGBA"


def test_opt_float():
    assert tools._opt_float(None) is None and tools._opt_float("1.5") == 1.5


# --- _frame --------------------------------------------------------------------


def test_frame_from_colour_and_from_image(tmp_path):
    f = tools._frame("#101014", (64, 36), avoid=None, delivery=None)
    assert f.size == (64, 36)
    p = tmp_path / "bg.png"
    Image.new("RGB", (64, 36), (1, 2, 3)).save(p)
    g = tools._frame(str(p), (64, 36), avoid="0,0,0.5,0.5", delivery=None)
    assert g.size == (64, 36) and len(g.avoid) == 1


# --- operations ---------------------------------------------------------------


def test_title_card_on_a_colour_reports_bbox_and_file(tmp_path):
    out = tmp_path / "t.png"
    r = tools.title_card("Hello", "World", out=str(out), background="#202020", size="320x180")
    assert out.is_file() and r["out"] == str(out) and len(r["bbox"]) == 4


def test_lower_third_over_a_picture(tmp_path):
    bg = tmp_path / "bg.png"
    Image.new("RGB", (320, 180), (10, 10, 10)).save(bg)
    out = tmp_path / "lt.png"
    r = tools.lower_third("Ada", "Engineer", out=str(out), background=str(bg), size="320x180")
    assert out.is_file() and "bbox" in r


def test_caption_overlay_only_is_transparent(tmp_path):
    src = tmp_path / "src.png"
    Image.new("RGB", (320, 180), (200, 200, 200)).save(src)
    out = tmp_path / "cap.png"
    r = tools.caption(str(src), "A label", "credit", out=str(out), avoid=None, overlay_only=True)
    assert Image.open(out).mode == "RGBA" and r["avoided"] == 0


def test_credits_cards_from_json_string_and_bad_mode(tmp_path):
    spec = json.dumps({"title": "T", "sections": [{"heading": "Cast", "entries": [["Lead", "Ada"], "Bob"]}]})
    out = tmp_path / "c.png"
    r = tools.credits(spec, out=str(out), mode="cards", size="320x180")
    assert r["cards"] >= 1 and all(p.endswith(".png") for p in r["out"])
    with pytest.raises(ValueError, match="mode must be"):
        tools.credits(spec, out=str(out), mode="nope", size="320x180")


def test_credits_from_plain_list_and_crawl_png(tmp_path):
    out = tmp_path / "crawl.png"
    r = tools.credits(json.dumps(["A", "B", "C"]), out=str(out), mode="crawl", size="320x180")
    assert out.is_file() and r["height"] >= 1


def test_fonts_filter_is_case_insensitive():
    everything = tools.fonts()
    assert everything["count"] == len(everything["families"])
    assert tools.fonts("zzzz-no-such-family")["count"] == 0
