"""Video output through ffmpeg: stills to clips, overlays onto footage, crawls.

Everything here composites **rendered PNGs**; ffmpeg never draws text. That is
deliberate twice over: the system ffmpeg on a developer Mac commonly lacks
``drawtext``/``libass`` (this one does), and typographically ``drawtext`` is
crude. What ffmpeg is good at — ``overlay``, ``fade``, ``crop``, encoding — is
all it is asked to do, and :func:`require_filters` fails loudly if even that
is missing rather than emitting a text-free video.

The overlay chain follows the shape verified in production on a found-image
film: each PNG is a looped input **with its own duration** (a shorter input
silently vanishes under ``eof_action=pass``), faded on its own clock, shifted
with ``setpts``, gated with ``enable=between(t, …)``, and the audio is
stream-copied so the finished mix is never re-encoded.

Never burn text into stills that a camera move will pan and zoom — composite
onto the finished motion video, which is what :func:`overlay` does.
"""

from __future__ import annotations

import os
from dataclasses import replace
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, Literal, Sequence

from PIL import Image

if TYPE_CHECKING:  # pragma: no cover
    from tituli.render import Engine

from tituli.schedule import TimedOverlay

FFMPEG_ENV_VAR = "TITULI_FFMPEG"
DEFAULT_FPS = 30
DEFAULT_CRF = 18
DEFAULT_PRESET = "medium"
DEFAULT_FADE_S = 0.4
_MIN_HOLD_S = 0.1
_FADE_SHARE = 2.5  # a fade never exceeds hold / this
_REQUIRED_FILTERS = ("overlay", "fade", "crop", "format", "setpts")
_PAD_FILTERS = ("tpad", "adelay")
PadMode = Literal["clone", "black"]
_PAD_MODES: dict[str, str] = {"clone": "clone", "black": "add"}  # name -> tpad mode
_AUDIO_BITRATE = "192k"  # only when padding forces an audio re-encode
# YouTube rejects an `elst` edit list that `+faststart` alone leaves behind.
_MOV_FLAGS = "+faststart+negative_cts_offsets"
_ENCODE = [
    "-c:v",
    "libx264",
    "-pix_fmt",
    "yuv420p",
    "-movflags",
    _MOV_FLAGS,
    "-use_editlist",
    "0",
]


class FfmpegError(RuntimeError):
    """ffmpeg is missing, or lacks a filter tituli needs."""


def ffmpeg_path() -> str:
    """The ffmpeg binary: ``$TITULI_FFMPEG`` or the first on PATH."""
    cand = os.environ.get(FFMPEG_ENV_VAR) or shutil.which("ffmpeg")
    if not cand:
        raise FfmpegError(
            "ffmpeg not found. Install it (https://ffmpeg.org, `brew install ffmpeg`, "
            f"`apt install ffmpeg`) or set ${FFMPEG_ENV_VAR} to the binary."
        )
    return cand


@lru_cache(maxsize=4)
def available_filters(binary: str | None = None) -> frozenset[str]:
    """Names of the filters this ffmpeg build has."""
    binary = binary or ffmpeg_path()
    out = subprocess.run(
        [binary, "-hide_banner", "-filters"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    names = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] and all(c in "TSC." for c in parts[0]):
            names.add(parts[1])
    return frozenset(names)


def require_filters(*names: str) -> None:
    """Raise :class:`FfmpegError` naming any missing filter."""
    have = available_filters()
    missing = [n for n in names if n not in have]
    if missing:
        raise FfmpegError(
            f"this ffmpeg build lacks filter(s) {missing}; tituli needs {list(names)}"
        )


def _run(args: Sequence[str]) -> None:
    proc = subprocess.run(list(args), capture_output=True, text=True)
    if proc.returncode != 0:
        raise FfmpegError(f"ffmpeg failed ({proc.returncode}):\n{proc.stderr[-2000:]}")


def _even(n: int) -> int:
    return n if n % 2 == 0 else n - 1


def _size_args(size: tuple[int, int]) -> list[str]:
    w, h = _even(size[0]), _even(size[1])
    return ["-vf", f"scale={w}:{h}"]


def still(
    image: str | Path | Image.Image,
    dst: str | Path,
    *,
    duration: float,
    fps: float = DEFAULT_FPS,
    fade_in: float = DEFAULT_FADE_S,
    fade_out: float = DEFAULT_FADE_S,
    audio: str | Path | None = None,
    crf: int = DEFAULT_CRF,
) -> Path:
    """A still held for ``duration`` seconds with fades — a title or credits card.

    Transparent PNGs are flattened onto black.
    """
    require_filters("fade", "format")
    src, tmp = _as_png(image, dst)
    fade_in = min(fade_in, duration / _FADE_SHARE)
    fade_out = min(fade_out, duration / _FADE_SHARE)
    vf = (
        f"format=rgba,fade=t=in:st=0:d={fade_in:.3f},"
        f"fade=t=out:st={max(0.0, duration - fade_out):.3f}:d={fade_out:.3f},format=yuv420p"
    )
    args = [
        ffmpeg_path(),
        "-y",
        "-loglevel",
        "error",
        "-loop",
        "1",
        "-framerate",
        str(fps),
        "-i",
        str(src),
    ]
    if audio:
        args += ["-i", str(audio)]
    args += [
        "-t",
        f"{duration:.3f}",
        "-vf",
        vf,
        *_ENCODE,
        "-crf",
        str(crf),
        "-preset",
        DEFAULT_PRESET,
    ]
    if audio:
        args += ["-c:a", "aac", "-shortest"]
    args += [str(dst)]
    try:
        _run(args)
    finally:
        if tmp:
            tmp.unlink(missing_ok=True)
    return Path(dst)


def _as_png(
    image: str | Path | Image.Image, near: str | Path
) -> tuple[Path, Path | None]:
    if isinstance(image, Image.Image):
        tmp = Path(near).with_suffix(".tituli-tmp.png")
        img = image
        if img.mode == "RGBA":
            flat = Image.new("RGB", img.size, (0, 0, 0))
            flat.paste(img, mask=img.split()[3])
            img = flat
        img.save(tmp)
        return tmp, tmp
    return Path(image), None


def overlay(
    video: str | Path,
    overlays: Sequence[TimedOverlay],
    dst: str | Path,
    *,
    size: tuple[int, int] | None = None,
    frame: "Frame | None" = None,
    delivery: str | None = "youtube",
    workdir: str | Path | None = None,
    crf: int = DEFAULT_CRF,
    preset: str = DEFAULT_PRESET,
    engine: "Engine | None" = None,
    pad_start: float = 0.0,
    pad_mode: PadMode = "clone",
) -> Path:
    """Composite timed overlays onto ``video`` in one ffmpeg pass; audio copied.

    Every overlay is rendered: one with a ``layout`` as it is; one with an
    ``image`` (a frame-sized PIL image or path, e.g. a title page) as that
    picture; one with only a ``payload`` (a :class:`~tituli.schedule.Label`
    from ``schedule_labels``, or a dict with ``text``/``attribution``/``kind``)
    is laid out here against ``frame`` (default: a blank frame of the video's
    size with ``delivery``'s reserved zones) at its ``slot``. Anything that
    cannot be rendered makes the call **raise, naming it** — nothing is ever
    silently left off the film.

    ``pad_start`` (seconds) lengthens the film at the head before compositing:
    the first frame is held (``pad_mode="clone"``) or the head is black
    (``"black"``), and the audio is delayed to match (and so re-encoded, AAC).
    Overlay times are on the **padded** timeline — ``TimedOverlay(None, 0, 3,
    image="title.png", fade_in=0)`` with ``pad_start=0.8`` is "the title over
    the intro, the song starting under it 0.8 s in".
    """
    from tituli.render import render_overlay

    if pad_start < 0:
        raise ValueError(f"pad_start must be >= 0 seconds, got {pad_start}")
    if pad_mode not in _PAD_MODES:
        raise ValueError(
            f"pad_mode must be one of {sorted(_PAD_MODES)}, got {pad_mode!r}"
        )
    require_filters(*_REQUIRED_FILTERS, *(_PAD_FILTERS if pad_start else ()))
    video, dst = Path(video), Path(dst)
    if not overlays:
        raise ValueError("overlay() needs at least one TimedOverlay")
    size = size or probe_size(video)
    items = materialize(
        overlays, frame=frame or _blank_frame(size, delivery), engine=engine
    )
    _check_image_sizes(items, size)
    workdir = Path(workdir) if workdir else dst.parent / f"_{dst.stem}_overlays"
    workdir.mkdir(parents=True, exist_ok=True)
    pngs: list[Path] = []
    for i, o in enumerate(items):
        p = workdir / f"ov{i:03d}.png"
        if o.layout is not None:
            render_overlay(o.layout, size, engine=engine).save(p)
        else:
            _open_image(o.image).convert("RGBA").save(p)
        pngs.append(p)

    args = [ffmpeg_path(), "-y", "-loglevel", "error", "-i", str(video)]
    for p, o in zip(pngs, items):
        args += [
            "-loop",
            "1",
            "-t",
            f"{max(_MIN_HOLD_S, o.duration):.3f}",
            "-i",
            str(p),
        ]
    steps: list[str] = []
    current = "0:v"
    if pad_start:
        steps.append(
            f"[0:v]tpad=start_duration={pad_start:.3f}:"
            f"start_mode={_PAD_MODES[pad_mode]}[padded]"
        )
        current = "padded"
    for i, o in enumerate(items):
        hold = max(_MIN_HOLD_S, o.duration)
        cap = hold / _FADE_SHARE
        fade_in = min(o.fade if o.fade_in is None else o.fade_in, cap)
        fade_out = min(o.fade if o.fade_out is None else o.fade_out, cap)
        fades = ""
        if fade_in > 0:
            fades += f"fade=t=in:st=0:d={fade_in:.3f}:alpha=1,"
        if fade_out > 0:
            fades += f"fade=t=out:st={hold - fade_out:.3f}:d={fade_out:.3f}:alpha=1,"
        steps.append(
            f"[{i + 1}:v]format=rgba,{fades}setpts=PTS+{o.start:.3f}/TB[ov{i}]"
        )
        nxt = f"v{i}"
        steps.append(
            f"[{current}][ov{i}]overlay=0:0:eof_action=pass:"
            f"enable='between(t,{o.start:.3f},{o.end:.3f})'[{nxt}]"
        )
        current = nxt
    audio: list[str] = ["-map", "0:a?", "-c:a", "copy"]
    n_audio = audio_streams(video) if pad_start else 0
    if n_audio:
        delay_ms = round(pad_start * 1000)
        audio = []
        for k in range(n_audio):  # every track, not only the first
            steps.append(f"[0:a:{k}]adelay=delays={delay_ms}:all=1[a{k}]")
            audio += ["-map", f"[a{k}]"]
        audio += ["-c:a", "aac", "-b:a", _AUDIO_BITRATE]
    args += [
        "-filter_complex",
        ";".join(steps),
        "-map",
        f"[{current}]",
        *_ENCODE,
        "-crf",
        str(crf),
        "-preset",
        preset,
        *audio,
        str(dst),
    ]
    _run(args)
    return dst


def _open_image(image: Image.Image | str | Path) -> Image.Image:
    return image if isinstance(image, Image.Image) else Image.open(image)


def _check_image_sizes(items: Sequence[TimedOverlay], size: tuple[int, int]) -> None:
    """Raise naming every image overlay that is not the video's size.

    An image is composited at ``(0, 0)`` unscaled, so a wrong-sized one would
    land partly off the film — refused rather than silently cropped.
    """
    wrong = []
    for i, o in enumerate(items):
        if o.layout is None and o.image is not None:
            got = _open_image(o.image).size
            if tuple(got) != tuple(size):
                wrong.append(f"#{i} [{o.start:.2f}, {o.end:.2f}] image is {got}")
    if wrong:
        raise ValueError(
            f"overlay(): image overlays must match the video size {tuple(size)} "
            "(render them on a Frame of that size):\n  " + "\n  ".join(wrong)
        )


def has_audio(video: str | Path) -> bool:
    """Whether ``video`` has an audio stream, via ffprobe."""
    return audio_streams(video) > 0


def audio_streams(video: str | Path) -> int:
    """How many audio streams ``video`` has, via ffprobe."""
    out = subprocess.run(
        [
            _ffprobe_path(),
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            str(video),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return len(out.splitlines())


def _ffprobe_path() -> str:
    return shutil.which("ffprobe") or str(Path(ffmpeg_path()).with_name("ffprobe"))


def _blank_frame(size: tuple[int, int], delivery: str | None):
    from tituli.frame import Frame

    return Frame.blank(size).with_delivery(delivery)


def materialize(
    overlays: Sequence[TimedOverlay], *, frame, engine: "Engine | None" = None
) -> list[TimedOverlay]:
    """Give every overlay a layout, rendering payloads; raise naming any that can't be.

    ``engine`` is the one that will draw them: payloads are measured with it.

    >>> from tituli.frame import Frame
    >>> from tituli.schedule import Label, TimedOverlay
    >>> f = Frame.blank((640, 360))
    >>> done = materialize([TimedOverlay(None, 0, 2, payload=Label("Eliza", "Earl, 1787"))], frame=f)
    >>> done[0].layout is not None
    True
    """
    from tituli.compose import caption, lower_third, note, title_card
    from tituli.schedule import Label

    out: list[TimedOverlay] = []
    unrenderable: list[str] = []
    for i, o in enumerate(overlays):
        if o.layout is not None and o.image is not None:
            unrenderable.append(
                f"#{i} [{o.start:.2f}, {o.end:.2f}] has both a layout and an image; "
                "give one (render the layout onto the image to have both)"
            )
            continue
        bad_fades = [
            f"{k}={v}"
            for k, v in (
                ("fade", o.fade),
                ("fade_in", o.fade_in),
                ("fade_out", o.fade_out),
            )
            if v is not None and v < 0
        ]
        if bad_fades:
            unrenderable.append(
                f"#{i} [{o.start:.2f}, {o.end:.2f}] negative {bad_fades}"
            )
            continue
        if o.layout is not None or o.image is not None:
            out.append(o)
            continue
        p = o.payload
        lay = None
        if isinstance(p, Label):
            lay = caption(
                p.text, p.attribution, frame=frame, anchor=o.slot, engine=engine
            )
        elif isinstance(p, dict) and "text" in p:
            kind = p.get("kind", "caption")
            halo = bool(p.get("halo", False))
            if kind == "lower_third":
                lay = lower_third(
                    p["text"],
                    p.get("role", ""),
                    frame=frame,
                    anchor=o.slot,
                    engine=engine,
                    halo=halo,
                )
            elif kind == "note":
                lay = note(
                    p.get("lines", ()),
                    headline=p["text"],
                    frame=frame,
                    anchor=o.slot,
                    engine=engine,
                    halo=halo,
                )
            elif kind == "title":
                lay = title_card(
                    p["text"],
                    p.get("subtitle", ""),
                    frame=frame,
                    anchor=o.slot,
                    engine=engine,
                    halo=halo,
                )
            else:
                lay = caption(
                    p["text"],
                    p.get("attribution", ""),
                    frame=frame,
                    anchor=o.slot,
                    engine=engine,
                    halo=halo,
                )
        if lay is None:
            unrenderable.append(
                f"#{i} [{o.start:.2f}, {o.end:.2f}] slot={o.slot!r} payload={p!r}"
            )
        else:
            # The slot it occupies is where it was placed ("auto" resolves to a corner).
            out.append(replace(o.with_layout(lay), slot=lay.meta.get("anchor", o.slot)))
    if unrenderable:
        raise ValueError(
            "overlay(): these overlays cannot be rendered as given (each needs exactly "
            "one of a layout, an image, or a renderable payload — a Label, or a dict "
            "with 'text' — and no negative fade); fix them or they would be silently "
            "missing from the film:\n  " + "\n  ".join(unrenderable)
        )
    return out


def crawl(
    tall: Image.Image | str | Path,
    dst: str | Path,
    *,
    size: tuple[int, int],
    speed_px_s: float,
    fps: float = DEFAULT_FPS,
    audio: str | Path | None = None,
    crf: int = DEFAULT_CRF,
) -> Path:
    """Scroll a tall image up through a ``size`` window at ``speed_px_s``.

    The image should already carry its own lead-in and tail (as
    :func:`tituli.credits.credits_crawl` does), so the clip starts and ends on
    an empty frame. Duration is ``(image height - window height) / speed``.
    """
    require_filters("crop")
    w, h = _even(size[0]), _even(size[1])
    src, tmp = _as_png(tall, dst)
    with Image.open(src) as im:
        ih = im.height
    travel = max(1, ih - h)
    duration = travel / speed_px_s
    vf = f"crop={w}:{h}:0:'min(t*{speed_px_s:.4f},{travel})',format=yuv420p"
    args = [
        ffmpeg_path(),
        "-y",
        "-loglevel",
        "error",
        "-loop",
        "1",
        "-framerate",
        str(fps),
        "-i",
        str(src),
    ]
    if audio:
        args += ["-i", str(audio)]
    args += [
        "-t",
        f"{duration:.3f}",
        "-vf",
        vf,
        *_ENCODE,
        "-crf",
        str(crf),
        "-preset",
        DEFAULT_PRESET,
    ]
    if audio:
        args += ["-c:a", "aac", "-shortest"]
    args += [str(dst)]
    try:
        _run(args)
    finally:
        if tmp:
            tmp.unlink(missing_ok=True)
    return Path(dst)


def frames_to_video(
    frames: Iterable[Image.Image],
    dst: str | Path,
    *,
    size: tuple[int, int],
    fps: float = DEFAULT_FPS,
    audio: str | Path | None = None,
    crf: int = DEFAULT_CRF,
) -> Path:
    """Encode a lazy stream of RGB frames (the kinetic path: per-glyph reveals)."""
    w, h = _even(size[0]), _even(size[1])
    args = [
        ffmpeg_path(),
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{w}x{h}",
        "-r",
        str(fps),
        "-i",
        "-",
    ]
    if audio:
        args += ["-i", str(audio)]
    args += [*_ENCODE, "-crf", str(crf), "-preset", DEFAULT_PRESET]
    if audio:
        args += ["-c:a", "aac", "-shortest"]
    args += [str(dst)]
    proc = subprocess.Popen(args, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for f in frames:
            if f.size != (w, h):
                f = f.resize((w, h))
            proc.stdin.write(f.convert("RGB").tobytes())
    finally:
        proc.stdin.close()
        err = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
        proc.wait()
    if proc.returncode != 0:
        raise FfmpegError(f"ffmpeg failed ({proc.returncode}):\n{err[-2000:]}")
    return Path(dst)


def probe_size(video: str | Path) -> tuple[int, int]:
    """``(width, height)`` of the first video stream, via ffprobe."""
    out = subprocess.run(
        [
            _ffprobe_path(),
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0",
            str(video),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    w, h = out.split(",")[:2]
    return int(w), int(h)


__all__ = [
    "FfmpegError",
    "materialize",
    "ffmpeg_path",
    "available_filters",
    "require_filters",
    "still",
    "overlay",
    "crawl",
    "frames_to_video",
    "probe_size",
    "has_audio",
    "audio_streams",
]
