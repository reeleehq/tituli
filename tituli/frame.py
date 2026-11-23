"""The frame: what the layout engine is allowed to know about the picture.

This module is the answer to "is a text-only video a special case of text over
video?" — yes, and the axis that unifies them is **how much the layout engine
knows about the frame**, a ladder:

======  ===========================================  =================================
rung    the Frame knows                              so the engine can
======  ===========================================  =================================
(a)     only its size                                place by anchor; must assume the
                                                     worst and put a scrim under text
(b)     a solid background colour                    choose ink by contrast, no scrim
(c)     the actual pixels                            sample luminance under a candidate
                                                     box; choose ink; scrim only if the
                                                     patch is mid-toned or busy
(d)     (c) + regions to keep clear                  rank candidate positions by how
                                                     little they cover the subject
======  ===========================================  =================================

A single :class:`Frame` type carries all four rungs; every rung is optional and
the engine asks (``luminance_under``, ``overlap``) rather than branching on kind.
The regions-to-avoid input is one keyword, ``avoid=``, which takes boxes *or a
callable* ``image -> box(es)`` — the shape of ``burns.salient_box`` and of
``burns.FacesDetector`` — so subject detection plugs in without a dependency.

>>> f = Frame.blank((1920, 1080))
>>> f.luminance_under(f.safe) is None      # rung (a): unknown
True
>>> Frame.blank((1920, 1080), color="#fff").luminance_under(f.safe)
1.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence, Union

from PIL import Image, ImageStat

from tituli.color import RGBA, parse_color, relative_luminance
from tituli.geometry import ANCHORS, TITLE_SAFE, Box, NormBox, anchor_box, safe_area

Size = tuple[int, int]
Avoid = Union[None, Iterable[NormBox], Callable[[Any], Any]]

DEFAULT_SIZE: Size = (1920, 1080)
_SAMPLE_MAX = 128  # downscale a patch to at most this many px per side before stats
_LUMA_CHANNELS = 3

# Placement preference when the caller does not say: corners first (a portrait's
# face is rarely in a corner; the bottom-left corner is the broadcast lower-third
# convention, the top-left the museum-label one), then the edges, "center" last.
# With `delivery="youtube"` the bottom row is reserved and the top-left wins.
DEFAULT_ANCHOR_ORDER: tuple[str, ...] = (
    "bottom-left",
    "top-left",
    "bottom-right",
    "top-right",
    "bottom",
    "top",
    "left",
    "right",
    "center",
)


ImageLike = Union[Image.Image, str, Path]

# Parts of the picture a delivery target draws its own chrome over. YouTube puts
# subtitles and the control bar across the bottom ~22 % of the frame, so a
# lower-third caption there collides with the film's own SRT track. Normalised
# (x, y, w, h). Add targets here rather than remembering the rule per caller.
DELIVERY_RESERVED: dict[str, tuple[NormBox, ...]] = {
    "youtube": ((0.0, 0.78, 1.0, 0.22),),
    "broadcast": (),
    "none": (),
}
_MID_LUMINANCE = 0.18  # the luminance where white and black ink contrast equally


def reserved_zones(delivery: str | None) -> tuple[NormBox, ...]:
    """Normalised boxes a delivery target keeps for itself.

    >>> reserved_zones("youtube")
    ((0.0, 0.78, 1.0, 0.22),)
    >>> reserved_zones(None)
    ()
    """
    if delivery is None:
        return ()
    try:
        return DELIVERY_RESERVED[delivery]
    except KeyError:
        raise ValueError(
            f"unknown delivery target {delivery!r}; choose from {sorted(DELIVERY_RESERVED)}"
        ) from None


def _as_images(image: Any) -> list[Image.Image]:
    items = [image] if isinstance(image, (Image.Image, str, Path)) else list(image)
    if not items:
        raise ValueError("Frame.from_image needs at least one image")
    return [
        (i if isinstance(i, Image.Image) else Image.open(i)).convert("RGB")
        for i in items
    ]


def _patch_stats(img: Image.Image, box: Box) -> tuple[float, float] | None:
    crop = img.crop(box.rounded())
    if crop.width == 0 or crop.height == 0:
        return None
    crop.thumbnail((_SAMPLE_MAX, _SAMPLE_MAX))
    # relative luminance is non-linear; the per-channel means are close enough
    # to choose an ink and cheap enough to run per frame of a window.
    stat = ImageStat.Stat(crop)
    mean = relative_luminance(tuple(round(m) for m in stat.mean[:_LUMA_CHANNELS]))
    std = sum(stat.stddev[:_LUMA_CHANNELS]) / _LUMA_CHANNELS / 255.0
    return (mean, std)


def _as_boxes(result: Any) -> list[NormBox]:
    """Normalise ``avoid`` output: one ``(x, y, w, h)`` or a sequence of them."""
    if result is None:
        return []
    seq = list(result)
    if len(seq) == 4 and all(isinstance(v, (int, float)) for v in seq):
        return [tuple(float(v) for v in seq)]  # type: ignore[list-item]
    return [tuple(float(v) for v in b) for b in seq]  # type: ignore[misc]


@dataclass(frozen=True)
class Frame:
    """Size plus whatever else is known about the picture text will sit on."""

    width: int
    height: int
    color: RGBA | None = None
    image: Image.Image | None = field(default=None, repr=False, compare=False)
    avoid: tuple[Box, ...] = ()
    reserved: tuple[Box, ...] = ()
    samples: tuple[Image.Image, ...] = field(default=(), repr=False, compare=False)

    @classmethod
    def blank(cls, size: Size = DEFAULT_SIZE, *, color: Any = None) -> "Frame":
        """Rung (a) when ``color`` is None, rung (b) when it is given."""
        w, h = size
        return cls(int(w), int(h), None if color is None else parse_color(color))

    @classmethod
    def from_image(
        cls,
        image: ImageLike | Sequence[ImageLike],
        *,
        avoid: Avoid = None,
        size: Size | None = None,
        delivery: str | None = None,
    ) -> "Frame":
        """Rung (c), and rung (d) when ``avoid`` is given.

        ``image`` may also be a **sequence** of frames (the stills a camera move
        will pass through under the text): the first is what gets composited,
        all of them feed :meth:`luminance_stats`, which then reports the *worst*
        instant — so a scrim is as light as the whole window allows, not as
        heavy as one frame demands.

        ``avoid`` is normalised boxes, or a callable taking the PIL image and
        returning one box or several (``burns.salient_box`` fits directly). It
        runs on every sampled frame. ``size`` cover-fits the picture(s) to the
        frame first. ``delivery`` names a target whose reserved zones
        (``"youtube"``: subtitle band + control bar) placement must keep clear.
        """
        imgs = _as_images(image)
        if size is not None:
            imgs = [cover_fit(i, size) for i in imgs]
        first = imgs[0]
        boxes: list[NormBox] = []
        if callable(avoid):
            for i in imgs:
                boxes.extend(_as_boxes(avoid(i)))
        else:
            boxes = _as_boxes(avoid)
        px_boxes = tuple(Box.from_norm(b, first.width, first.height) for b in boxes)
        reserved = tuple(
            Box.from_norm(b, first.width, first.height)
            for b in reserved_zones(delivery)
        )
        return cls(
            first.width, first.height, None, first, px_boxes, reserved, tuple(imgs)
        )

    @classmethod
    def over(
        cls,
        stills: Sequence[ImageLike],
        *,
        avoid: Avoid = None,
        size: Size | None = None,
        delivery: str | None = None,
    ) -> "Frame":
        """The frame a caption will sit on *over a time window* of stills.

        The named entry point for the sequence case: the first still is what
        gets composited, all of them are sampled, and ``luminance_stats``
        reports the worst instant — so a scrim over a Ken Burns move is as
        light as the whole window allows. (``from_image`` accepts a sequence
        too; this name says what it is for.)
        """
        return cls.from_image(list(stills), avoid=avoid, size=size, delivery=delivery)

    def with_delivery(self, delivery: str | None) -> "Frame":
        """Same frame, placement keeping clear of that target's reserved zones."""
        reserved = tuple(
            Box.from_norm(b, self.width, self.height) for b in reserved_zones(delivery)
        )
        return Frame(
            self.width,
            self.height,
            self.color,
            self.image,
            self.avoid,
            reserved,
            self.samples,
        )

    # -- knowledge queries -------------------------------------------------------

    @property
    def size(self) -> Size:
        """The ``(width, height)`` of the frame."""
        return (self.width, self.height)

    @property
    def bounds(self) -> Box:
        """The frame as a :class:`Box` starting at the origin."""
        return Box(0, 0, self.width, self.height)

    @property
    def safe(self) -> Box:
        """The title-safe box (SMPTE ST 2046-1, 90 %)."""
        return safe_area(self.width, self.height, fraction=TITLE_SAFE)

    @property
    def knows_pixels(self) -> bool:
        """Whether the frame carries pixel data."""
        return self.image is not None

    def with_avoid(self, avoid: Avoid) -> "Frame":
        """Same frame with (additional) regions to keep clear."""
        img = self.image
        if callable(avoid) and img is None:
            raise ValueError("a callable avoid= needs a Frame with an image")
        boxes = _as_boxes(avoid(img) if callable(avoid) else avoid)
        extra = tuple(Box.from_norm(b, self.width, self.height) for b in boxes)
        return Frame(
            self.width,
            self.height,
            self.color,
            img,
            self.avoid + extra,
            self.reserved,
            self.samples,
        )

    def luminance_under(self, box: Box) -> float | None:
        """Mean relative luminance of the pixels under ``box``; None if unknown."""
        stats = self.luminance_stats(box)
        return None if stats is None else stats[0]

    def luminance_stats(self, box: Box) -> tuple[float, float] | None:
        """``(mean, stddev)`` of relative luminance under ``box``; None if unknown.

        A high stddev means a busy patch — even a well-contrasted mean will not
        keep every glyph readable, which is when a scrim earns its place.
        """
        imgs = self.samples or ((self.image,) if self.image is not None else ())
        if imgs:
            stats = [_patch_stats(i, box.intersection(self.bounds)) for i in imgs]
            stats = [st for st in stats if st is not None]
            if not stats:
                return None
            # Worst instant: the mean nearest mid-grey (least contrast headroom
            # for either ink) and the busiest patch.
            mean = min((m for m, _ in stats), key=lambda m: abs(m - _MID_LUMINANCE))
            std = max(sd for _, sd in stats)
            return (mean, std)
        if self.color is not None:
            return (relative_luminance(self.color), 0.0)
        return None

    def overlap(self, box: Box) -> float:
        """Fraction of ``box`` that covers something in ``avoid`` (0 when nothing)."""
        if not self.avoid:
            return 0.0
        return max(box.overlap_fraction(a) for a in self.avoid)

    def place(
        self,
        size: tuple[float, float],
        *,
        anchor: str | Sequence[str] = "auto",
        region: Box | None = None,
    ) -> tuple[str, Box]:
        """Where to put a block of ``size``: a named anchor and its pixel box.

        ``anchor`` may be one name, a preference list, or ``"auto"`` (the default
        order). With rung (d) knowledge the candidate that least covers the
        subject wins; ties fall to preference order.

        >>> f = Frame.blank((1000, 500))
        >>> f.place((200, 50), anchor="bottom")[0]
        'bottom'
        """
        region = self.safe if region is None else region
        if isinstance(anchor, str):
            order = DEFAULT_ANCHOR_ORDER if anchor == "auto" else (anchor,)
        else:
            order = tuple(anchor)
        unknown = [a for a in order if a not in ANCHORS]
        if unknown:
            raise ValueError(
                f"unknown anchor(s) {unknown}; choose from {sorted(ANCHORS)}"
            )
        candidates = [(a, anchor_box(region, size, a)) for a in order]
        clear = [c for c in candidates if not self._reserved_overlap(c[1])]
        if clear:
            candidates = clear
        else:
            # Every candidate lands in a reserved zone — which happens whenever
            # the caller named a single anchor, since there is then nothing to
            # choose between. Move each one out instead of placing it inside: a
            # reserved zone that only binds on ``anchor="auto"`` does not bind.
            candidates = [(a, self._clear_of_reserved(b)) for a, b in candidates]
        best = min(
            enumerate(candidates),
            key=lambda ic: (
                round(self.overlap(ic[1][1]), 2),
                -self._distance_from_subject(ic[1][1]),
                ic[0],
            ),
        )
        return best[1]

    def _reserved_overlap(self, box: Box) -> bool:
        return any(box.overlap_fraction(r) > 0 for r in self.reserved)

    def _clear_of_reserved(self, box: Box) -> Box:
        """``box`` slid the shortest way out of every reserved zone.

        Reserved zones are the platform's furniture — YouTube's subtitle track
        and control bar along the bottom, a Short's title and action rail. They
        are edge bands, so the way out is a translation along one axis, and the
        cheapest one wins. If the block is too big to clear (a band taller than
        the frame's free height), it is left where it was: shrinking or dropping
        it is the caller's call, not a silent decision made here.
        """
        for _ in range(len(self.reserved) + 1):
            hit = next((r for r in self.reserved if box.overlap_fraction(r) > 0), None)
            if hit is None:
                return box
            moves = [
                (hit.y0 - box.y1, 0.0, -1.0),  # up, above the band
                (box.y0 - hit.y1, 0.0, 1.0),  # down, below it
                (hit.x0 - box.x1, -1.0, 0.0),  # left
                (box.x0 - hit.x1, 1.0, 0.0),  # right
            ]
            # `gap` is negative while they overlap; the smallest push is the
            # least negative, and a move that would leave the frame is no move.
            options = []
            for gap, dx, dy in moves:
                shift = -gap
                moved = box.translate(dx * shift, dy * shift)
                if (
                    moved.x0 >= -0.5
                    and moved.y0 >= -0.5
                    and moved.x1 <= self.width + 0.5
                    and moved.y1 <= self.height + 0.5
                ):
                    options.append((shift, moved))
            if not options:
                return box
            box = min(options, key=lambda sm: sm[0])[1]
        return box

    def _distance_from_subject(self, box: Box) -> float:
        """Tie-break for coarse avoid boxes: prefer the candidate farthest from their centres."""
        if not self.avoid:
            return 0.0
        cx, cy = box.center
        diag = (self.width**2 + self.height**2) ** 0.5
        return round(
            min(
                ((cx - a.center[0]) ** 2 + (cy - a.center[1]) ** 2) ** 0.5
                for a in self.avoid
            )
            / diag,
            2,
        )


def cover_fit(img: Image.Image, size: Size) -> Image.Image:
    """Scale ``img`` to fill ``size`` and crop the overflow, centred.

    >>> cover_fit(Image.new("RGB", (100, 50)), (50, 50)).size
    (50, 50)
    """
    w, h = size
    scale = max(w / img.width, h / img.height)
    resized = img.resize(
        (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
    )
    x0 = (resized.width - w) // 2
    y0 = (resized.height - h) // 2
    return resized.crop((x0, y0, x0 + w, y0 + h))
