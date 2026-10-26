# tituli.video

Video output through ffmpeg: stills to clips, overlays onto footage, crawls.

Everything here composites **rendered PNGs**; ffmpeg never draws text. That is
deliberate twice over: the system ffmpeg on a developer Mac commonly lacks
`drawtext`/`libass` (this one does), and typographically `drawtext` is
crude. What ffmpeg is good at — `overlay`, `fade`, `crop`, encoding — is
all it is asked to do, and [`require_filters()`](#tituli.video.require_filters) fails loudly if even that
is missing rather than emitting a text-free video.

The overlay chain follows the shape verified in production on a found-image
film: each PNG is a looped input **with its own duration** (a shorter input
silently vanishes under `eof_action=pass`), faded on its own clock, shifted
with `setpts`, gated with `enable=between(t, …)`, and the audio is
stream-copied so the finished mix is never re-encoded.

Never burn text into stills that a camera move will pan and zoom — composite
onto the finished motion video, which is what [`overlay()`](#tituli.video.overlay) does.

### Functions

| [`materialize`](#tituli.video.materialize)(overlays, \*, frame[, engine])         | Give every overlay a layout, rendering payloads; raise naming any that can't be.              |
|-----------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------|
| [`ffmpeg_path`](#tituli.video.ffmpeg_path)()                                      | The ffmpeg binary: `$TITULI_FFMPEG` or the first on PATH.                                     |
| [`available_filters`](#tituli.video.available_filters)([binary])                        | Names of the filters this ffmpeg build has.                                                   |
| [`require_filters`](#tituli.video.require_filters)(\*names)                           | Raise [`FfmpegError`](#tituli.video.FfmpegError) naming any missing filter. |
| [`still`](#tituli.video.still)(image, dst, \*, duration[, fps, ...])        | A still held for `duration` seconds with fades — a title or credits card.                     |
| [`overlay`](#tituli.video.overlay)(video, overlays, dst, \*[, size, ...])     | Composite timed overlays onto `video` in one ffmpeg pass; audio copied.                       |
| [`crawl`](#tituli.video.crawl)(tall, dst, \*, size, speed_px_s[, fps, ...]) | Scroll a tall image up through a `size` window at `speed_px_s`.                               |
| [`frames_to_video`](#tituli.video.frames_to_video)(frames, dst, \*, size[, fps, ...]) | Encode a lazy stream of RGB frames (the kinetic path: per-glyph reveals).                     |
| [`probe_size`](#tituli.video.probe_size)(video)                                  | `(width, height)` of the first video stream, via ffprobe.                                     |
| [`has_audio`](#tituli.video.has_audio)(video)                                   | Whether `video` has an audio stream, via ffprobe.                                             |
| [`audio_streams`](#tituli.video.audio_streams)(video)                               | How many audio streams `video` has, via ffprobe.                                              |

### Exceptions

| [`FfmpegError`](#tituli.video.FfmpegError)   | ffmpeg is missing, or lacks a filter tituli needs.   |
|----------------------------------------------------------------|------------------------------------------------------|

### *exception* tituli.video.FfmpegError

Bases: [`RuntimeError`](https://docs.python.org/3/builtins/exceptions.html#RuntimeError)

ffmpeg is missing, or lacks a filter tituli needs.

### tituli.video.audio_streams(video)

How many audio streams `video` has, via ffprobe.

* **Return type:**
  [`int`](https://docs.python.org/3/builtins/functions.html#int)

### tituli.video.available_filters(binary=None)

Names of the filters this ffmpeg build has.

* **Return type:**
  [`frozenset`](https://docs.python.org/3/builtins/stdtypes.html#frozenset)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### tituli.video.crawl(tall, dst, , size, speed_px_s, fps=30, audio=None, crf=18)

Scroll a tall image up through a `size` window at `speed_px_s`.

The image should already carry its own lead-in and tail (as
[`tituli.credits.credits_crawl()`](tituli.credits.html.md#tituli.credits.credits_crawl) does), so the clip starts and ends on
an empty frame. Duration is `(image height - window height) / speed`.

* **Return type:**
  [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path)

### tituli.video.ffmpeg_path()

The ffmpeg binary: `$TITULI_FFMPEG` or the first on PATH.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### tituli.video.frames_to_video(frames, dst, , size, fps=30, audio=None, crf=18)

Encode a lazy stream of RGB frames (the kinetic path: per-glyph reveals).

* **Return type:**
  [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path)

### tituli.video.has_audio(video)

Whether `video` has an audio stream, via ffprobe.

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

### tituli.video.materialize(overlays, , frame, engine=None)

Give every overlay a layout, rendering payloads; raise naming any that can’t be.

`engine` is the one that will draw them: payloads are measured with it.

```pycon
>>> from tituli.frame import Frame
>>> from tituli.schedule import Label, TimedOverlay
>>> f = Frame.blank((640, 360))
>>> done = materialize([TimedOverlay(None, 0, 2, payload=Label("Eliza", "Earl, 1787"))], frame=f)
>>> done[0].layout is not None
True
```

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`TimedOverlay`](tituli.schedule.html.md#tituli.schedule.TimedOverlay)]

### tituli.video.overlay(video, overlays, dst, , size=None, frame=None, delivery='youtube', workdir=None, crf=18, preset='medium', engine=None, pad_start=0.0, pad_mode='clone')

Composite timed overlays onto `video` in one ffmpeg pass; audio copied.

Every overlay is rendered: one with a `layout` as it is; one with an
`image` (a frame-sized PIL image or path, e.g. a title page) as that
picture; one with only a `payload` (a [`Label`](tituli.schedule.html.md#tituli.schedule.Label)
from `schedule_labels`, or a dict with `text`/`attribution`/`kind`)
is laid out here against `frame` (default: a blank frame of the video’s
size with `delivery`’s reserved zones) at its `slot`. Anything that
cannot be rendered makes the call **raise, naming it** — nothing is ever
silently left off the film.

`pad_start` (seconds) lengthens the film at the head before compositing:
the first frame is held (`pad_mode="clone"`) or the head is black
(`"black"`), and the audio is delayed to match (and so re-encoded, AAC).
Overlay times are on the **padded** timeline — `TimedOverlay(None, 0, 3,
image="title.png", fade_in=0)` with `pad_start=0.8` is “the title over
the intro, the song starting under it 0.8 s in”.

* **Return type:**
  [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path)

### tituli.video.probe_size(video)

`(width, height)` of the first video stream, via ffprobe.

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`int`](https://docs.python.org/3/builtins/functions.html#int), [`int`](https://docs.python.org/3/builtins/functions.html#int)]

### tituli.video.require_filters(\*names)

Raise [`FfmpegError`](#tituli.video.FfmpegError) naming any missing filter.

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

### tituli.video.still(image, dst, , duration, fps=30, fade_in=0.4, fade_out=0.4, audio=None, crf=18)

A still held for `duration` seconds with fades — a title or credits card.

Transparent PNGs are flattened onto black.

* **Return type:**
  [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path)
