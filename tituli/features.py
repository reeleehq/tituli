"""OpenType features a style asks for, applied without a shaper where they can be (tituli#4).

A style may ask for features by tag (``TextStyle(features=("tnum",))``: tabular
figures, so the digits of a changing number do not change width). Whether the
font HAS a feature is a property of its bytes, so a face records which of the
requested ones it applies (:attr:`tituli.fonts.Face.applied_features`); a
feature the font lacks is not applied, and the caller can say so.

Pillow applies features only through libraqm, which is often absent, and its
embedded face always lays out without it. So the features that are glyph
SUBSTITUTIONS one for one (GSUB lookup type 1, also inside an extension lookup:
``tnum``, ``lnum``, ``onum``, ``pnum``, ``zero``, ``smcp`` …) are applied here,
from the font's own tables: :func:`featured_glyphs` gives the substituted glyph
names and :func:`featured_length` their advances. Measurement
(:meth:`~tituli.fonts.Face.length`) and outlines (:func:`tituli.run_outline`)
read both, so they cannot disagree. A requested feature built from any other
kind of lookup needs a shaper and is refused (:class:`FeatureError`).

Needs fontTools (``tituli[outlines]``), like the outlines.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from tituli.fonts import glyph_set, ttfont

if TYPE_CHECKING:  # pragma: no cover
    from tituli.fonts import Face

__all__ = [
    "FeatureError",
    "font_features",
    "applied_features",
    "featured_glyphs",
    "featured_length",
]

#: GSUB lookup types applied here: single substitution, and the extension
#: lookup that wraps one.
_SINGLE_SUBSTITUTION: int = 1
_EXTENSION: int = 7


class FeatureError(ValueError):
    """A requested feature cannot be applied as asked; the message says what would."""


@lru_cache(maxsize=64)
def font_features(path: str | None, index: int = 0) -> frozenset[str]:
    """The GSUB feature tags a font declares.

    >>> from tituli import EMBEDDED, resolve_face
    >>> "tnum" in font_features(resolve_face(EMBEDDED, size=12).path)
    False
    """
    font = ttfont(path, index)
    if "GSUB" not in font:
        return frozenset()
    records = font["GSUB"].table.FeatureList.FeatureRecord
    return frozenset(r.FeatureTag for r in records)


def applied_features(face: "Face") -> tuple[str, ...]:
    """The face's requested features that its font has, in request order."""
    if not face.features:
        return ()
    have = font_features(face.path, face.index)
    return tuple(tag for tag in face.features if tag in have)


@lru_cache(maxsize=64)
def _substitutions(
    path: str | None, index: int, tags: tuple[str, ...]
) -> dict[str, str]:
    font = ttfont(path, index)
    table = font["GSUB"].table
    lookups = sorted(
        {
            i
            for record in table.FeatureList.FeatureRecord
            if record.FeatureTag in tags
            for i in record.Feature.LookupListIndex
        }
    )
    mapping: dict[str, str] = {}
    for i in lookups:
        lookup = table.LookupList.Lookup[i]
        for sub in lookup.SubTable:
            kind = lookup.LookupType
            if kind == _EXTENSION:
                kind, sub = sub.ExtensionLookupType, sub.ExtSubTable
            if kind != _SINGLE_SUBSTITUTION:
                raise FeatureError(
                    f"feature(s) {list(tags)} of this font use a GSUB lookup of type "
                    f"{kind}, which needs a shaper: draw with "
                    "`tituli.shaping.HarfBuzzEngine` (`pip install tituli[shaping]`), "
                    "or drop the feature"
                )
            for src, dst in sub.mapping.items():
                mapping[src] = mapping.get(dst, dst)
    return mapping


def featured_glyphs(face: "Face", text: str) -> list[str | None]:
    """The glyph name each character of ``text`` draws with the face's applied
    features (``None`` where the font has no glyph for it)."""
    cmap = ttfont(face.path, face.index).getBestCmap() or {}
    subs = _substitutions(face.path, face.index, applied_features(face))
    return [
        subs.get(name, name) if name else None
        for name in (cmap.get(ord(c)) for c in text)
    ]


def featured_length(face: "Face", text: str) -> float:
    """Advance width of ``text`` in pixels, from the substituted glyphs' own
    advances (the font's design metrics at the face's variation instance,
    scaled to the face's size)."""
    scale = face.size / ttfont(face.path, face.index)["head"].unitsPerEm
    glyphs = glyph_set(face)
    return sum(
        glyphs[name].width * scale
        for name in featured_glyphs(face, text)
        if name is not None
    )
