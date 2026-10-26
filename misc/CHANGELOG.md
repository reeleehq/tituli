# Changelog

## 2026-09-14 — 0.0.1

First release. Frame-knowledge ladder (`Frame`), `Layout`/`Run`/`Plate` model, Pillow renderer with rotated glyph tiles, optional HarfBuzz+FreeType engine, title card / caption / lower third / note / intertitle, structured credits (cards + crawl, never truncating), calligrams (`on_path`, `rain`, `in_shape`), scheduler with first-appearance / repeat-gap / suppression inside the loop, ffmpeg output (`still`, `overlay`, `crawl`, `frames_to_video`), CLI via `cw`, lacing body `annot://schema/text-overlay/v1`, shipped `tituli` skill.

## 2026-09-14 — 0.0.3

Credits: a wrapped role/name row now advances by its measured height (was one line height — wrapped roles collided with the row beneath); cards are balanced to an even fill instead of greedy-then-nearly-empty; `from_lines`/`from_dict` document that the caller owns presentable text. Review fixes before this: `video.overlay` renders payload-only overlays or raises naming them; `Panel` → `Span`; `note()`; truncate-then-check suppression shared by `schedule_labels` and `resolve`.

## 2026-09-14 — 0.0.4

Packaging: the shipped skill now actually ships. hatchling's followlinks walk marked the real `tituli/data/skills/tituli` as already seen via the `.claude/skills` symlink, so the published 0.0.2/0.0.3 wheels had no `tituli/data/` at all. `skip-excluded-dirs` + excluding `.claude` from the sdist fixes it; `tests/test_packaging.py` builds sdist → wheel to keep it fixed.

## 2026-10-06

OpenType features on a style (tituli#4): `TextStyle(features=("tnum",))` (or `{"tnum": True}`) reaches the `Face`, which records the ones its font has (`applied_features`). Single-substitution features are applied by `Face.length` and `run_outline` from the font's GSUB and hmtx (`tituli.features`, needs `tituli[outlines]`), `HarfBuzzEngine` passes them to HarfBuzz, and `PillowEngine` raises `FeatureError` for a run they change instead of drawing other glyphs than were measured.

## 2026-10-26

Variable fonts (tituli#9): `TextStyle.weight` sets the `wght` axis of a variable-font file (`Face.wght`, clamped to the axis; other axes stay at their defaults), read by tag from the file's own `fvar` (`tituli.fonts.variation_axes`, no fontTools). Every engine reads `Face.applied_variations`: Pillow and FreeType through one ordered coordinate list, HarfBuzz and fontTools glyph sets (outlines, `featured_length` advances) as is. **`face_digest` of a variable face changes**: it is now the sha256 of the file bytes plus the applied axis values, so two instances of one file are two faces; a static face's digest is unchanged (the hash of its bytes alone). A hand-built `Face(wght=...)` on a font without a `wght` axis raises `ValueError`.
