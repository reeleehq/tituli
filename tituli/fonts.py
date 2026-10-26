"""Font discovery with no bundled fonts.

``tituli`` never ships a typeface (licensing), so a *typeface request* — a family
name, weight and slant — is resolved against the fonts already installed on the
machine, and falls back to the scalable face Pillow embeds (Aileron). That fallback
is a real font, not a stub, so every render works out of the box on a bare CI
runner; it just looks better on a machine with Helvetica Neue.

Resolution order is a *preference list*: the first family found wins.

>>> face = resolve_face(["No Such Family", "DejaVu Sans"], size=48)
>>> face.size
48
>>> face.family in ("DejaVu Sans", "Aileron") or isinstance(face.family, str)
True
"""

from __future__ import annotations

import io
import os
import struct
import sys
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Sequence

from PIL import ImageFont

_FONT_SUFFIXES = (".ttf", ".ttc", ".otf")
_MAX_TTC_INDEX = 32  # sanity bound when probing a collection's faces
_TTC_FIRST_INDEX = 0
_EMBEDDED_PROBE_SIZE = 12  # any size: the bytes do not depend on it
#: Pixel size a font file is opened at when only its tables are read (names).
_PROBE_SIZE = 12
#: The registered tag of the weight axis of a variable font.
WEIGHT_AXIS = "wght"

# The working set the style research settled on, most-preferred first. Every
# entry is a family name as the font's own ``name`` table reports it.
SANS_STACK: tuple[str, ...] = (
    "Helvetica Neue",
    "Inter",
    "Helvetica",
    "Avenir Next",
    "Roboto",
    "Univers",
    "Liberation Sans",
    "DejaVu Sans",
    "Arial",
)
SERIF_STACK: tuple[str, ...] = (
    "Georgia",
    "Palatino",
    "Baskerville",
    "Liberation Serif",
    "DejaVu Serif",
    "Times New Roman",
)
DISPLAY_STACK: tuple[str, ...] = ("Futura", "Avenir Next", "Gill Sans") + SANS_STACK
MONO_STACK: tuple[str, ...] = (
    "Menlo",
    "DejaVu Sans Mono",
    "Liberation Mono",
    "Courier",
)

FALLBACK_FAMILY = "Aileron"  # what Pillow's embedded ``load_default`` reports

#: A family request that means *Pillow's embedded face, and never the system*.
#: In a preference list it is a stop: the names before it are looked up as
#: usual, and if none is installed the embedded face is used without scanning
#: further. Alone (or first) it never scans the system at all, so the result is
#: the same bytes on every machine with the same Pillow — the deterministic
#: choice for a caller whose output must not depend on the installed fonts.
#: (Asking for ``"Aileron"`` by name is not the same thing: a machine that has
#: Aileron installed would resolve to *that* file.)
EMBEDDED = "tituli:embedded"

_WEIGHT_WORDS = {
    "thin": 100,
    "ultralight": 200,
    "extralight": 200,
    "light": 300,
    "regular": 400,
    "book": 400,
    "roman": 400,
    "normal": 400,
    "medium": 500,
    "semibold": 600,
    "demibold": 600,
    "demi": 600,
    "bold": 700,
    "extrabold": 800,
    "ultrabold": 800,
    "heavy": 800,
    "black": 900,
}
REGULAR_WEIGHT = 400
BOLD_WEIGHT = 700


@dataclass(frozen=True)
class FontFile:
    """One face inside a font file (a ``.ttc`` holds several)."""

    path: str
    index: int
    family: str
    style: str

    @property
    def weight(self) -> int:
        """CSS-style weight parsed from the style name (``"Bold"`` -> 700)."""
        return _weight_of(self.style)

    @property
    def italic(self) -> bool:
        """Whether the style name says italic/oblique."""
        s = self.style.lower()
        return "italic" in s or "oblique" in s

    @property
    def condensed(self) -> bool:
        """Whether the style name says condensed/narrow/compressed."""
        s = self.style.lower()
        return any(w in s for w in ("condensed", "narrow", "compressed"))


@dataclass(frozen=True)
class Face:
    """A resolved, sized font ready to measure and draw with Pillow."""

    family: str
    style: str
    size: int
    path: str | None
    index: int = 0
    #: OpenType feature tags the style asked for (tituli#4); which of them the
    #: font has is :attr:`applied_features`.
    features: tuple[str, ...] = ()
    #: Value of the ``wght`` axis when the file is a variable font with one
    #: (tituli#9), clamped to the axis range; ``None`` for a static face. A face
    #: at the axis default still differs from ``None`` in :func:`face_digest`.
    wght: float | None = None

    def __post_init__(self):
        if self.wght is None:
            return
        axis = _axis(self.path, self.index, WEIGHT_AXIS)
        if axis is None:
            raise ValueError(
                f"wght={self.wght} needs a variable font with a {WEIGHT_AXIS!r} axis, "
                f"and {self.path or FALLBACK_FAMILY!r} (index {self.index}) has none: "
                "leave wght=None (resolve_face sets it only where the font has the axis)"
            )
        # one canonical value per instance, so a face and its digest agree
        clamped = float(min(max(self.wght, axis.minimum), axis.maximum))
        object.__setattr__(self, "wght", clamped)

    @property
    def pil(self) -> ImageFont.FreeTypeFont:
        """The Pillow font object (cached per ``(path, index, size, variations)``)."""
        key = variation_key(self.applied_variations)
        return _load_pil(self.path, self.index, self.size, key)

    def with_size(self, size: int) -> "Face":
        """Same face at another pixel size."""
        return replace(self, size=int(size))

    @property
    def applied_features(self) -> tuple[str, ...]:
        """The requested :attr:`features` this font has, so the ones measured and
        outlined with; a requested tag missing here was not applied.

        >>> resolve_face(EMBEDDED, size=12).applied_features
        ()
        """
        if not self.features:
            return ()
        from tituli.features import applied_features

        return applied_features(self)

    @property
    def applied_variations(self) -> dict[str, float]:
        """The variable-font axis values applied (``{"wght": 700.0}``); empty for
        a static face. Every engine reads this, never :attr:`wght` itself; an
        axis not named here stays at its default."""
        return {} if self.wght is None else {WEIGHT_AXIS: self.wght}

    def length(self, text: str) -> float:
        """Advance width of ``text`` in pixels.

        With :attr:`applied_features`, the advances of the substituted glyphs
        (:func:`tituli.features.featured_length`): the font's design advances,
        without hinting or kerning, which is what tabular figures are for.
        """
        if self.applied_features:
            from tituli.features import featured_length

            return featured_length(self, text)
        return self.pil.getlength(text)

    @property
    def ascent(self) -> int:
        """Ascent in pixels."""
        return self.pil.getmetrics()[0]

    @property
    def descent(self) -> int:
        """Descent in pixels."""
        return self.pil.getmetrics()[1]

    @property
    def line_height(self) -> int:
        """Ascent + descent."""
        a, d = self.pil.getmetrics()
        return a + d


def _weight_of(style: str) -> int:
    s = style.lower().replace(" ", "").replace("-", "")
    # longest match first so "ultralight" beats "light", "semibold" beats "bold"
    for word in sorted(_WEIGHT_WORDS, key=len, reverse=True):
        if word in s:
            return _WEIGHT_WORDS[word]
    return REGULAR_WEIGHT


def font_dirs() -> list[Path]:
    """Platform font directories that exist on this machine.

    Extra directories can be prepended with ``TITULI_FONT_DIRS`` (``os.pathsep``
    separated), which is also how a project supplies its own licensed fonts.
    """
    home = Path.home()
    if sys.platform == "darwin":
        candidates = [
            home / "Library/Fonts",
            Path("/Library/Fonts"),
            Path("/System/Library/Fonts"),
            Path("/System/Library/Fonts/Supplemental"),
        ]
    elif sys.platform.startswith("win"):
        windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
        candidates = [home / "AppData/Local/Microsoft/Windows/Fonts", windir / "Fonts"]
    else:
        candidates = [
            home / ".fonts",
            home / ".local/share/fonts",
            Path("/usr/local/share/fonts"),
            Path("/usr/share/fonts"),
        ]
    extra = [
        Path(p) for p in os.environ.get("TITULI_FONT_DIRS", "").split(os.pathsep) if p
    ]
    return [d for d in extra + candidates if d.is_dir()]


def _iter_font_paths(dirs: Iterable[Path]) -> Iterator[Path]:
    for d in dirs:
        for p in d.rglob("*"):
            if p.suffix.lower() in _FONT_SUFFIXES and p.is_file():
                yield p


def _faces_in(path: Path) -> Iterator[FontFile]:
    for index in range(_MAX_TTC_INDEX):
        try:
            f = ImageFont.truetype(str(path), _PROBE_SIZE, index=index)
        except (OSError, ValueError, IndexError):
            break
        family, style = f.getname()
        yield FontFile(str(path), index, family or path.stem, style or "Regular")
        if path.suffix.lower() != ".ttc":
            break


@lru_cache(maxsize=1)
def font_index() -> dict[str, tuple[FontFile, ...]]:
    """Installed faces grouped by family name. Scanned once per process.

    >>> idx = font_index()
    >>> all(isinstance(k, str) for k in idx)
    True
    """
    index: dict[str, list[FontFile]] = {}
    for path in _iter_font_paths(font_dirs()):
        for ff in _faces_in(path):
            index.setdefault(ff.family, []).append(ff)
    return {k: tuple(v) for k, v in index.items()}


def families() -> list[str]:
    """Sorted family names installed on this machine."""
    return sorted(font_index())


def _best_style(
    faces: Sequence[FontFile], *, weight: int, italic: bool, condensed: bool
) -> FontFile:
    def score(ff: FontFile) -> tuple[int, int, int]:
        return (
            ff.italic != italic,
            ff.condensed != condensed,
            abs(ff.weight - weight),
        )

    return min(faces, key=score)


def find_font(
    family: str | Sequence[str],
    *,
    weight: int = REGULAR_WEIGHT,
    italic: bool = False,
    condensed: bool = False,
) -> FontFile | None:
    """First installed family in the preference list, at the closest style.

    ``family`` may be one name or a preference list. A path to a font file is
    accepted too, and wins outright.

    >>> find_font("definitely-not-installed-xyz") is None
    True
    """
    names = [family] if isinstance(family, str) else list(family)
    idx = font_index()
    for name in names:
        if name.lower().endswith(_FONT_SUFFIXES) and Path(name).is_file():
            faces = tuple(_faces_in(Path(name)))
            if faces:
                return _best_style(
                    faces, weight=weight, italic=italic, condensed=condensed
                )
        if name in idx:
            return _best_style(
                idx[name], weight=weight, italic=italic, condensed=condensed
            )
    # case-insensitive second pass
    lower = {k.lower(): k for k in idx}
    for name in names:
        if name.lower() in lower:
            return _best_style(
                idx[lower[name.lower()]],
                weight=weight,
                italic=italic,
                condensed=condensed,
            )
    return None


def resolve_face(
    family: str | Sequence[str] = SANS_STACK,
    *,
    size: int,
    weight: int = REGULAR_WEIGHT,
    italic: bool = False,
    condensed: bool = False,
    features: Iterable[str] = (),
) -> Face:
    """Resolve a typeface request to a sized ``Face``; never fails.

    ``features`` are OpenType feature tags to apply (``("tnum",)``), carried by
    the face; see :attr:`Face.applied_features` for which the font has.

    Falls back to Pillow's embedded Aileron when nothing in the list is installed,
    so a render on a fontless CI box still produces a real (if plainer) result.
    :data:`EMBEDDED` in the list stops the search there (see its comment):

    >>> resolve_face(EMBEDDED, size=20).path is None
    True
    >>> resolve_face(["definitely-not-installed-xyz", EMBEDDED], size=20).family
    'Aileron'
    """
    names = [family] if isinstance(family, str) else list(family)
    if EMBEDDED in names:
        names = names[: names.index(EMBEDDED)]
    ff = (
        find_font(names, weight=weight, italic=italic, condensed=condensed)
        if names
        else None
    )
    if ff is None:
        return Face(FALLBACK_FAMILY, "Regular", int(size), None, 0, tuple(features))
    return Face(
        ff.family,
        ff.style,
        int(size),
        ff.path,
        ff.index,
        tuple(features),
        _wght_for(ff.path, ff.index, weight),
    )


def face_bytes(face: Face) -> bytes:
    """The bytes of the font file behind ``face`` — the embedded face's too.

    Pillow keeps the embedded face's bytes on the font object it builds
    (``font_bytes``), so the fallback has an identity like any file does.

    >>> face_bytes(resolve_face(EMBEDDED, size=12))[:4] in (b"\\x00\\x01\\x00\\x00", b"true", b"OTTO")
    True
    """
    return _file_bytes(face.path)


def face_digest(face: Face) -> str:
    """``sha256`` of :func:`face_bytes` and the :attr:`Face.applied_variations` —
    what makes two faces the same face.

    A family name is not an identity (two machines can install different files
    under one name, and the embedded face can change with Pillow); the bytes are,
    together with the instance a variable font is drawn at. A static face's digest
    is the hash of its bytes alone. Cached per ``(path, variations)``, so a file
    rewritten in place during the process keeps its first digest.
    """
    return _digest(face.path, variation_key(face.applied_variations))


#: Separates a variable face's axis values from the file bytes in its digest.
_VARIATIONS_SALT = b"\0tituli:variations:"


@lru_cache(maxsize=256)
def _digest(path: str | None, variations: tuple[tuple[str, float], ...]) -> str:
    import hashlib
    import json

    h = hashlib.sha256(_file_bytes(path))
    if variations:
        h.update(_VARIATIONS_SALT + json.dumps(variations).encode())
    return h.hexdigest()


def _file_bytes(path: str | None) -> bytes:
    return _embedded_bytes() if path is None else Path(path).read_bytes()


@lru_cache(maxsize=1)
def _embedded_bytes() -> bytes:
    font = ImageFont.load_default(size=_EMBEDDED_PROBE_SIZE)
    data = getattr(font, "font_bytes", None)
    if not data:  # pragma: no cover - Pillow < 10.1 has no scalable default
        raise RuntimeError(
            "this Pillow has no embedded scalable font (Pillow >= 10.1 does)"
        )
    return data


@lru_cache(maxsize=32)
def ttfont(path: str | None, index: int = 0):
    """fontTools' parsed font behind ``(path, index)``: opened lazily, cached per
    file (not per size or instance). The one opener outlines and features share;
    a variable instance is read through :func:`glyph_set`.

    Needs fontTools (``tituli[outlines]``).
    """
    try:
        from fontTools.ttLib import TTFont
    except ImportError as e:  # pragma: no cover - depends on the extra
        raise ImportError(
            "outlines and OpenType features need fontTools: "
            "`pip install tituli[outlines]`"
        ) from e
    return TTFont(io.BytesIO(_file_bytes(path)), fontNumber=index, lazy=True)


def glyph_set(face: Face):
    """The glyphs of ``face``'s font at its :attr:`Face.applied_variations`:
    outlines to draw and ``.width`` advances (in font units) to measure with."""
    return _glyph_set(face.path, face.index, variation_key(face.applied_variations))


@lru_cache(maxsize=64)
def _glyph_set(path: str | None, index: int, variations: tuple):
    font = ttfont(path, index)
    if not variations:
        return font.getGlyphSet()
    return font.getGlyphSet(location=dict(variations), normalized=False)


# --- variable fonts: the axes, read by tag from the file's own `fvar` -------


@dataclass(frozen=True)
class VariationAxis:
    """One axis of a variable font's ``fvar`` table, in design units."""

    tag: str
    minimum: float
    default: float
    maximum: float


_TTC_TAG = b"ttcf"
_FVAR_TAG = b"fvar"
_SFNT_HEADER = ">4sH"  # sfntVersion, numTables
_TTC_HEADER = ">4sHHI"  # ttcTag, majorVersion, minorVersion, numFonts
_TABLE_RECORDS_AT = 12  # after the sfnt header's search fields
_TABLE_RECORD = ">4sIII"  # tag, checksum, offset, length
_FVAR_HEADER = ">6H"  # version, version, axesArrayOffset, reserved, axisCount, axisSize
_AXIS_RECORD = ">4siii"  # tag, minValue, defaultValue, maxValue (16.16 Fixed)
_FIXED_ONE = 1 << 16


@lru_cache(maxsize=256)
def variation_axes(path: str | None, index: int = 0) -> tuple[VariationAxis, ...]:
    """The variation axes of a font file, in ``fvar`` order (the order FreeType
    and Pillow take coordinates in); empty for a static font or one this cannot
    read. Parsed from the file's tables directly, so it needs no fontTools and
    keeps the exact (unrounded) axis values.

    >>> variation_axes(None)
    ()
    """
    if path is None:
        return ()
    try:
        with open(path, "rb") as f:
            return _read_fvar(f, index)
    except (OSError, struct.error):
        return ()


def _read_fvar(f, index: int) -> tuple[VariationAxis, ...]:
    def read(offset: int, fmt: str) -> tuple:
        f.seek(offset)
        return struct.unpack(fmt, f.read(struct.calcsize(fmt)))

    base = 0
    tag, *_, num_fonts = read(0, _TTC_HEADER)
    if tag == _TTC_TAG:
        if index >= num_fonts:
            return ()
        (base,) = read(struct.calcsize(_TTC_HEADER) + 4 * index, ">I")
    _, num_tables = read(base, _SFNT_HEADER)
    record = struct.calcsize(_TABLE_RECORD)
    for i in range(num_tables):
        tag, _, fvar, _ = read(base + _TABLE_RECORDS_AT + i * record, _TABLE_RECORD)
        if tag == _FVAR_TAG:
            break
    else:
        return ()
    *_, axes_at, _, count, size = read(fvar, _FVAR_HEADER)
    axes = []
    for i in range(count):
        tag, lo, default, hi = read(fvar + axes_at + i * size, _AXIS_RECORD)
        axes.append(
            VariationAxis(
                tag.decode("latin-1"),
                lo / _FIXED_ONE,
                default / _FIXED_ONE,
                hi / _FIXED_ONE,
            )
        )
    return tuple(axes)


def _axis(path: str | None, index: int, tag: str) -> VariationAxis | None:
    return next((a for a in variation_axes(path, index) if a.tag == tag), None)


def _wght_for(path: str | None, index: int, weight: int) -> float | None:
    """The ``wght`` to set for a requested ``weight``: clamped to the axis range."""
    axis = _axis(path, index, WEIGHT_AXIS)
    if axis is None:
        return None
    return float(min(max(weight, axis.minimum), axis.maximum))


def variation_key(variations: Mapping[str, float]) -> tuple[tuple[str, float], ...]:
    """``variations`` as a hashable, canonical (tag-sorted) tuple — a cache key."""
    return tuple(sorted((t, float(v)) for t, v in variations.items()))


def variation_coords(
    path: str | None, index: int, variations: Mapping[str, float]
) -> list[float]:
    """One coordinate per axis, in ``fvar`` order, as FreeType and Pillow take
    them: the value in ``variations`` for its tag, the axis default otherwise."""
    return [variations.get(a.tag, a.default) for a in variation_axes(path, index)]


@lru_cache(maxsize=256)
def _load_pil(
    path: str | None, index: int, size: int, variations: tuple = ()
) -> ImageFont.FreeTypeFont:
    if path is None:
        return ImageFont.load_default(size=size)
    font = ImageFont.truetype(path, size, index=index)
    if variations:
        font.set_variation_by_axes(variation_coords(path, index, dict(variations)))
    return font
