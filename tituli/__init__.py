"""tituli — text in video: title cards, credits, captions and calligrams.

One model underneath: a :class:`Layout` of placed :class:`Run`s on a
:class:`Frame` that knows as much (or as little) about the picture as you tell
it. Everything else is a convenience over that.

Quick start::

    from tituli import Frame, title_card, caption, credits_crawl, on_path, render

    frame = Frame.blank((1920, 1080), color="#101014")
    render(title_card("Il pleut", "Apollinaire, 1918", frame=frame), frame).save("title.png")

    frame = Frame.from_image("still.jpg", delivery="youtube")   # add avoid=burns.salient_box
    render(caption("Eliza Hamilton", "Ralph Earl, 1787 · public domain", frame=frame), frame).save("cap.png")

Optional layers, none imported here: ``tituli[outlines]`` (fontTools, for
:func:`run_outline` — glyph contours as SVG path data), ``tituli[shaping]`` (HarfBuzz engine),
``tituli[saliency]`` (``burns`` subject avoidance), ``tituli[lacing]`` (the
text-overlay body schema), ``tituli[cli]`` (``python -m tituli``).
"""

from tituli.arrange import glossed, grid, stack
from tituli.calligram import in_shape, on_path, rain, resolve_shape
from tituli.color import contrast_ratio, ink_for, parse_color
from tituli.compose import (
    caption,
    decide_ink,
    intertitle,
    lower_third,
    note,
    title_card,
    MIN_LEGIBLE_SIZE,
    TextDoesNotFit,
    fit,
    truncate,
)
from tituli.credits import (
    Credits,
    CreditsStyle,
    Entry,
    Section,
    credits_cards,
    credits_crawl,
    credits_frame,
)
from tituli.fonts import EMBEDDED, Face, face_digest, families, find_font, resolve_face
from tituli.frame import DELIVERY_RESERVED, Frame, cover_fit, reserved_zones
from tituli.geometry import ANCHORS, TITLE_SAFE, Box, Path, safe_area
from tituli.layout import Layout, Plate, Run, along_path, block, fit_size, measure, wrap
from tituli.outlines import MissingGlyphError, Outline, run_outline
from tituli.render import frames, make_engine, render, render_overlay
from tituli.schedule import (
    UNLABELLED,
    Label,
    Span,
    TimedOverlay,
    resolve,
    schedule_labels,
)
from tituli.style import (
    ATTRIBUTION,
    CALLIGRAM,
    CAPTION,
    CREDITS_NAME,
    GLOSS,
    GLOSS_GLYPH,
    KICKER,
    SUBTITLE,
    TITLE,
    Halo,
    TextStyle,
)

__all__ = [
    "Frame",
    "Layout",
    "Run",
    "Plate",
    "Box",
    "Path",
    "TextStyle",
    "Halo",
    "Face",
    "title_card",
    "caption",
    "lower_third",
    "note",
    "intertitle",
    "MIN_LEGIBLE_SIZE",
    "TextDoesNotFit",
    "fit",
    "truncate",
    "decide_ink",
    "Credits",
    "CreditsStyle",
    "Entry",
    "Section",
    "credits_cards",
    "credits_crawl",
    "credits_frame",
    "on_path",
    "rain",
    "in_shape",
    "resolve_shape",
    "block",
    "stack",
    "grid",
    "glossed",
    "along_path",
    "wrap",
    "measure",
    "fit_size",
    "render",
    "render_overlay",
    "frames",
    "make_engine",
    "Label",
    "Span",
    "TimedOverlay",
    "UNLABELLED",
    "schedule_labels",
    "resolve",
    "families",
    "find_font",
    "resolve_face",
    "EMBEDDED",
    "face_digest",
    "run_outline",
    "Outline",
    "MissingGlyphError",
    "contrast_ratio",
    "ink_for",
    "parse_color",
    "safe_area",
    "ANCHORS",
    "TITLE_SAFE",
    "DELIVERY_RESERVED",
    "reserved_zones",
    "cover_fit",
    "TITLE",
    "SUBTITLE",
    "KICKER",
    "CAPTION",
    "ATTRIBUTION",
    "CREDITS_NAME",
    "CALLIGRAM",
    "GLOSS",
    "GLOSS_GLYPH",
]
