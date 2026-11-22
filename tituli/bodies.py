"""A lacing body schema for a rendered caption (``pip install tituli[lacing]``).

URI: ``annot://schema/text-overlay/v1``. A caption is an annotation **on the
image** (``MediaRef(asset_id=<image hash>)``), and when that image sits under an
audio segment the pair is expressed the way ``artful.PanelBody`` does it: the
annotation's ``reference`` is the interval on the segment and
``provenance.was_derived_from`` lists both the image ``asset_id`` and the
caption annotation id. No N-ary reference type is invented; the timing lives
on the reference, not in this body.

Registration is lazy and idempotent (:func:`register`), so ``import tituli``
never touches lacing.
"""

from __future__ import annotations

from typing import Any

TEXT_OVERLAY_V1 = "annot://schema/text-overlay/v1"
_REGISTERED = False


def _model():
    from pydantic import BaseModel, Field

    class TextOverlayBodyV1(BaseModel):
        """What was written over the picture, and how. Placement is normalised."""

        model_config = {"frozen": True, "extra": "forbid"}

        text: str = Field(
            ..., description="The caption as displayed (after wrapping/truncation)."
        )
        attribution: str = Field(
            "", description="The small credit line under the caption, if any."
        )
        kind: str = Field(
            "caption",
            description="Free string: 'caption', 'lower_third', 'title', 'intertitle', ...",
        )
        anchor: str = Field(
            "", description="Grid position the block was placed at ('top-left', ...)."
        )
        box: tuple[float, float, float, float] | None = Field(
            None, description="Normalised (x, y, w, h) of the text block in the frame."
        )
        ink: str | None = Field(None, description="Ink colour as #rrggbb, if recorded.")
        scrim: bool | None = Field(
            None, description="Whether a scrim was drawn under the text."
        )
        halo: dict[str, Any] | None = Field(
            None,
            description="The Halo fields (spread, blur, gain, opacity in em; color, null for the ink's opposite) the text was drawn with, if any.",
        )
        reason: str | None = Field(
            None, description="The ink/scrim decision the frame's knowledge led to."
        )
        style: dict[str, Any] | None = Field(
            None, description="The TextStyle fields used, for re-rendering."
        )
        unlabelled: bool = Field(
            False,
            description="True when the still was deliberately shown without a label (an explicit choice, not an omission).",
        )
        overlay_asset_id: str | None = Field(
            None, description="asset_id of the rendered transparent PNG, if stored."
        )

    return TextOverlayBodyV1


def register() -> str:
    """Register the schema with lacing (once). Returns the URI."""
    global _REGISTERED
    if _REGISTERED:
        return TEXT_OVERLAY_V1
    from lacing import register_body_schema

    register_body_schema(TEXT_OVERLAY_V1, _model())
    _REGISTERED = True
    return TEXT_OVERLAY_V1


def _halo_of(layout) -> dict | None:
    """The first run's halo as plain data (a colour tuple becomes a list), or None."""
    from dataclasses import asdict

    for run in layout.runs:
        if run.halo is not None:
            d = asdict(run.halo)
            if isinstance(d["color"], tuple):
                d["color"] = list(d["color"])
            return d
    return None


def body_for(
    layout,
    frame,
    *,
    text: str,
    attribution: str = "",
    kind: str = "caption",
    unlabelled: bool = False,
) -> dict:
    """The body dict for a rendered layout — plain data, no lacing needed.

    >>> from tituli.frame import Frame
    >>> from tituli.compose import caption
    >>> f = Frame.blank((1920, 1080))
    >>> b = body_for(caption("A still", "PD", frame=f), f, text="A still", attribution="PD")
    >>> b["kind"], b["anchor"], len(b["box"])
    ('caption', 'bottom-left', 4)
    """
    bb = layout.bbox()
    ink = None
    if layout.runs:
        r, g, b, _ = layout.runs[0].color
        ink = f"#{r:02x}{g:02x}{b:02x}"
    return {
        "text": text,
        "attribution": attribution,
        "kind": kind,
        "anchor": str(layout.meta.get("anchor", "")),
        "box": tuple(round(v, 4) for v in bb.to_norm(frame.width, frame.height)),
        "ink": ink,
        "scrim": any(p.kind != "box" or p.color[3] < 255 for p in layout.plates)
        or None,
        "halo": _halo_of(layout),
        "reason": layout.meta.get("ink"),
        "style": None,
        "unlabelled": unlabelled,
        "overlay_asset_id": None,
    }


__all__ = ["TEXT_OVERLAY_V1", "register", "body_for"]
