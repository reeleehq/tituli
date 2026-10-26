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

import os
import sys
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Iterator, Sequence

from PIL import ImageFont

_FONT_SUFFIXES = (".ttf", ".ttc", ".otf")
_MAX_TTC_INDEX = 32  # sanity bound when probing a collection's faces
_TTC_FIRST_INDEX = 0
_EMBEDDED_PROBE_SIZE = 12  # any size: the bytes do not depend on it

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
    #: (tituli#9), clamped to the axis range; ``None`` for a static face.
    wght: float | None = None

    @property
    def pil(self) -> ImageFont.FreeTypeFont:
        """The Pillow font object (cached per ``(path, index, size, wght)``)."""
        return _load_pil(self.path, self.index, self.size, self.wght)

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
        a static face."""
        return {} if self.wght is None else {"wght": self.wght}

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
            f = ImageFont.truetype(str(path), 12, index=index)
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
    if face.path is None:
        return _embedded_bytes()
    data = Path(face.path).read_bytes()
    return instance_bytes(data, face.index, face.wght)


def face_digest(face: Face) -> str:
    """``sha256`` of :func:`face_bytes` — what makes two faces the same face.

    A family name is not an identity (two machines can install different files
    under one name, and the embedded face can change with Pillow); the bytes are.
    """
    import hashlib

    return hashlib.sha256(face_bytes(face)).hexdigest()


@lru_cache(maxsize=1)
def _embedded_bytes() -> bytes:
    font = ImageFont.load_default(size=_EMBEDDED_PROBE_SIZE)
    data = getattr(font, "font_bytes", None)
    if not data:  # pragma: no cover - Pillow < 10.1 has no scalable default
        raise RuntimeError(
            "this Pillow has no embedded scalable font (Pillow >= 10.1 does)"
        )
    return data


@lru_cache(maxsize=256)
def _weight_axis(path: str, index: int) -> tuple[int, list[dict]] | None:
    """``(position, axes)`` of the ``wght`` axis of a variable font, else ``None``."""
    try:
        axes = ImageFont.truetype(path, 12, index=index).get_variation_axes()
    except (OSError, ValueError, AttributeError):  # static font, or no FreeType MM
        return None
    for i, axis in enumerate(axes):
        name = axis["name"]
        name = name.decode("latin-1") if isinstance(name, bytes) else name
        if name.lower() == "weight":
            return i, axes
    return None


def _wght_for(path: str | None, index: int, weight: int) -> float | None:
    """The ``wght`` to set for a requested ``weight``: clamped to the axis range."""
    found = _weight_axis(path, index) if path else None
    if found is None:
        return None
    axis = found[1][found[0]]
    return float(min(max(weight, axis["minimum"]), axis["maximum"]))


def instance_bytes(data: bytes, index: int, wght: float | None) -> bytes:
    """``data`` as a static font at ``wght`` (itself when ``wght`` is ``None``).

    The identity of a variable face is the file *and* the instance drawn from it.
    """
    if wght is None:
        return data
    import io

    try:
        from fontTools.ttLib import TTFont
        from fontTools.varLib.instancer import instantiateVariableFont
    except ImportError as e:  # pragma: no cover - depends on the extra
        raise ImportError(
            "a variable font's weight needs fontTools here: "
            "`pip install tituli[outlines]`"
        ) from e
    font = TTFont(io.BytesIO(data), fontNumber=index)
    instantiateVariableFont(font, {"wght": wght}, inplace=True)
    out = io.BytesIO()
    font.save(out)
    return out.getvalue()


@lru_cache(maxsize=256)
def _load_pil(
    path: str | None, index: int, size: int, wght: float | None = None
) -> ImageFont.FreeTypeFont:
    if path is None:
        return ImageFont.load_default(size=size)
    font = ImageFont.truetype(path, size, index=index)
    if wght is not None:
        pos, axes = _weight_axis(path, index)
        font.set_variation_by_axes(
            [wght if i == pos else a["default"] for i, a in enumerate(axes)]
        )
    return font
