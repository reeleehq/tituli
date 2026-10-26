"""Optional engine: HarfBuzz shaping + FreeType rendering (``pip install tituli[shaping]``).

The Pillow default handles Latin text well and rotates glyph *bitmaps*. This
engine shapes the run with HarfBuzz (kerning, ligatures, Arabic/Devanagari
joining) and asks FreeType to apply the rotation to the **outline** before
rasterising, which is the typographically correct order. Same :class:`Run`
in, same canvas out — it is the ``engine=`` seam of :func:`tituli.render.render`.

Import cost is paid only when constructed; the module itself imports nothing
optional at top level.
"""

from __future__ import annotations

import math
from functools import lru_cache

from PIL import Image

from tituli.fonts import variation_coords, variation_key
from tituli.layout import Run

_HB_SCALE = 64  # 26.6 fixed point
_FT_MATRIX_ONE = 0x10000  # 16.16 fixed point
#: What HarfBuzz is asked for when nothing else is; a style's own features
#: (``TextStyle.features``) are added to these.
_DEFAULT_FEATURES: dict = {"kern": True, "liga": True}


def _require():
    try:
        import freetype  # noqa: F401
        import uharfbuzz  # noqa: F401
    except ImportError as e:  # pragma: no cover - depends on the extra
        raise ImportError(
            "the HarfBuzz engine needs `pip install tituli[shaping]`"
        ) from e


@lru_cache(maxsize=64)
def _hb_font(path: str, index: int, size: int, variations: tuple = ()):
    import uharfbuzz as hb

    blob = hb.Blob.from_file_path(path)
    face = hb.Face(blob, index)
    font = hb.Font(face)
    font.scale = (size * _HB_SCALE, size * _HB_SCALE)
    if variations:
        font.set_variations(dict(variations))
    return font


@lru_cache(maxsize=64)
def _ft_face(path: str, index: int, size: int, variations: tuple = ()):
    import freetype

    face = freetype.Face(path, index)
    face.set_char_size(size * _HB_SCALE)
    if variations:
        face.set_var_design_coords(variation_coords(path, index, dict(variations)))
    return face


def shape(
    text: str,
    path: str,
    index: int,
    size: int,
    *,
    features: dict | None = None,
    variations: dict | None = None,
) -> list[tuple[int, float, float, float, float]]:
    """``[(glyph_id, x_advance, y_advance, x_offset, y_offset), ...]`` in pixels.

    ``variations`` are variable-font axis values by tag (``{"wght": 700}``).
    """
    import uharfbuzz as hb

    font = _hb_font(path, index, size, variation_key(variations or {}))
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, features or _DEFAULT_FEATURES)
    out = []
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        out.append(
            (
                info.codepoint,
                pos.x_advance / _HB_SCALE,
                pos.y_advance / _HB_SCALE,
                pos.x_offset / _HB_SCALE,
                pos.y_offset / _HB_SCALE,
            )
        )
    return out


class HarfBuzzEngine:
    """Draw runs through HarfBuzz + FreeType. Falls back to Pillow for the embedded font."""

    def __init__(self) -> None:
        _require()
        from tituli.render import PillowEngine

        self._fallback = PillowEngine()

    def draw_run(self, canvas: Image.Image, run: Run, opacity: float) -> None:
        import freetype

        face = run.face
        if face.path is None:  # Pillow's embedded fallback font has no file
            self._fallback.draw_run(canvas, run, opacity)
            return
        r, g, b, a = run.color
        alpha = max(0.0, min(1.0, (a / 255) * run.opacity * opacity))
        if alpha == 0 or not run.text:
            return
        variations = face.applied_variations
        ft = _ft_face(face.path, face.index, face.size, variation_key(variations))
        ang = math.radians(-run.angle)  # FreeType's y points up
        cos, sin = math.cos(ang), math.sin(ang)
        matrix = freetype.Matrix(
            int(cos * _FT_MATRIX_ONE),
            int(-sin * _FT_MATRIX_ONE),
            int(sin * _FT_MATRIX_ONE),
            int(cos * _FT_MATRIX_ONE),
        )
        pen_x, pen_y = 0.0, 0.0  # along the (rotated) baseline, in unrotated px
        features = {**_DEFAULT_FEATURES, **{tag: True for tag in face.features}}
        for gid, xa, ya, xo, yo in shape(
            run.text,
            face.path,
            face.index,
            face.size,
            features=features,
            variations=variations,
        ):
            ft.set_transform(matrix, freetype.Vector(0, 0))
            ft.load_glyph(gid, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_NORMAL)
            bmp = ft.glyph.bitmap
            if bmp.width and bmp.rows:
                # rotate the pen position into screen space (y down, angle clockwise)
                sa = math.radians(run.angle)
                sx = run.x + (pen_x + xo) * math.cos(sa) - (pen_y + yo) * math.sin(sa)
                sy = run.y + (pen_x + xo) * math.sin(sa) + (pen_y + yo) * math.cos(sa)
                tile = Image.frombytes(
                    "L", (bmp.width, bmp.rows), bytes(bmp.buffer), "raw", "L", bmp.pitch
                )
                if alpha < 1:
                    tile = tile.point(lambda v: round(v * alpha))
                layer = Image.new("RGBA", tile.size, (r, g, b, 0))
                layer.putalpha(tile)
                x0 = int(round(sx + ft.glyph.bitmap_left))
                y0 = int(round(sy - ft.glyph.bitmap_top))
                canvas.alpha_composite(layer, (x0, y0))
            pen_x += xa + run.tracking
            pen_y += ya


__all__ = ["HarfBuzzEngine", "shape"]
