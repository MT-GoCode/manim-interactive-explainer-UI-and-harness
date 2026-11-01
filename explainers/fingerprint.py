"""What each frame shows, known without drawing it. In pass 1 the camera runs its own drawing code, but every call it
would make to Cairo (paths, colours, gradients, line widths, joins, caps) and every point cloud and image it would
paint are recorded instead of rasterized. A worker's tee records the same calls and forwards them, so its frames carry
real pixels and a digest the build compares with pass 1's. A frame is the digest of what its canvas started from (the
background, or a saved frame) and everything drawn on it since; equal digests draw equal pixels. Vendored from
presenters' clip.py, which vendored this file first."""
import hashlib
import importlib.metadata
import subprocess
import sys
from pathlib import Path
from typing import Any

import cairo
import numpy as np

from explainers.config import FPS, HEIGHT, OUTPUT, WIDTH

ENGINE = Path(__file__).parent  # where identity() reads the engine's code


def _sha(*parts: bytes) -> bytes:
    return hashlib.sha256(b"".join(parts)).digest()


class Frame:
    """Stands in for a pixel array wherever the renderer passes frames around (the static frame, written frames)."""

    __slots__ = ("digest",)

    def __init__(self, digest: bytes):
        self.digest = digest


DRAWING = frozenset(
    {
        "new_path",
        "new_sub_path",
        "move_to",
        "curve_to",
        "close_path",
        "set_source_rgba",
        "set_source",
        "set_line_width",
        "set_line_join",
        "set_line_cap",
        "fill_preserve",
        "stroke_preserve",
    }
)


def _op(name: str, args: tuple[Any, ...]) -> tuple[Any, ...]:
    return (
        name,
        *(
            ("gradient", a.get_linear_points(), a.get_color_stops_rgba())
            if isinstance(a, cairo.LinearGradient)
            else float(a)
            for a in args
        ),
    )


class _Context:
    """A cairo.Context that records each drawing call this Manim makes. Any other attribute raises: a query
    (get_matrix, fill_extents) answered with None would draw wrong."""

    def __init__(self, ops: list[tuple[Any, ...]]):
        self._ops = ops

    def __getattr__(self, name: str) -> Any:
        if name not in DRAWING:
            raise AttributeError(f"the recorder does not record cairo.Context.{name}")

        def record(*args: Any) -> None:
            self._ops.append(_op(name, args))

        return record


class Recorder:
    """Installed on one scene's camera and renderer for pass 1: digest-only frames. `play_digest()` closes one
    animation: the digests of the frames it wrote, each with its repeat count, in order."""

    def __init__(self, scene: Any):
        cam = self._cam = scene.camera
        self._ops: list[tuple[Any, ...]] = []
        self._canvas = b""
        self._written: list[tuple[bytes, int]] = []
        self._arrays: dict[int, tuple[np.ndarray, bytes]] = {}
        names = (
            "get_cairo_context",
            "display_point_cloud",
            "display_image_mobject",
            "display_multiple_background_colored_vmobjects",
            "reset",
            "set_frame_to_background",
        )
        self._orig: dict[str, Any] = {n: getattr(cam, n) for n in names}
        self._orig_get_frame = scene.renderer.get_frame
        self._orig_write = scene.renderer.file_writer.write_frame
        cam.get_cairo_context = self._context
        cam.display_point_cloud = self._points
        cam.display_image_mobject = self._image
        cam.display_multiple_background_colored_vmobjects = self._backgrounds
        cam.reset = self._reset
        cam.set_frame_to_background = self._load
        scene.renderer.get_frame = self._snapshot
        scene.renderer.file_writer.write_frame = self._write

    def _array(self, a: np.ndarray) -> bytes:
        """Digest of an array that stays the same object while in use (the background, a background image). The
        entry holds the array, so its id is never reused while the entry exists."""
        hit = self._arrays.get(id(a))
        if hit is None:
            hit = self._arrays[id(a)] = (a, _sha(repr((a.shape, a.dtype.str)).encode(), a.tobytes()))
        return hit[1]

    def _matrix(self) -> None:
        """Paths are recorded in scene units: the world-to-pixel matrix Camera.get_cairo_context sets is part of what
        is drawn."""
        c = self._cam
        sx, sy = c.pixel_width / c.frame_width, c.pixel_height / c.frame_height
        tx, ty = c.pixel_width / 2 - c.frame_center[0] * sx, c.pixel_height / 2 + c.frame_center[1] * sy
        self._ops.append(("matrix", float(sx), float(-sy), float(tx), float(ty)))

    def _context(self, pixel_array: np.ndarray) -> Any:
        self._matrix()
        return _Context(self._ops)

    def _backgrounds(self, vmobjects: Any, pixel_array: np.ndarray) -> Any:
        vmobjects = list(vmobjects)
        displayer = self._cam.get_background_colored_vmobject_displayer()
        self._ops += [
            ("background-image", self._array(displayer.get_background_array(v.get_background_image())))
            for v in vmobjects
        ]
        return self._orig["display_multiple_background_colored_vmobjects"](vmobjects, pixel_array)

    def _points(self, pmobject: Any, points: np.ndarray, rgbas: np.ndarray, thickness: float, pixel_array: Any) -> Any:
        coords = self._cam.points_to_pixel_coords(pmobject, points)
        self._ops.append(("points", _sha(coords.tobytes(), np.asarray(rgbas, float).tobytes()), float(thickness)))

    def _image(self, image_mobject: Any, pixel_array: np.ndarray) -> Any:
        pixels = np.ascontiguousarray(image_mobject.get_pixel_array())
        corners = self._cam.points_to_subpixel_coords(image_mobject, image_mobject.points)
        self._ops.append(
            (
                "image",
                _sha(repr(pixels.shape).encode(), pixels.tobytes(), corners.tobytes()),
                int(image_mobject.resampling_algorithm),
            )
        )

    def _reset(self) -> Any:
        self._ops.clear()
        self._canvas = self._array(self._cam.background)
        return self._cam

    def _load(self, frame: Frame) -> None:
        self._ops.clear()
        self._canvas = frame.digest

    def _snapshot(self) -> Frame:
        self._canvas = _sha(self._canvas, repr(self._ops).encode())
        self._ops.clear()
        return Frame(self._canvas)

    def _write(self, frame: Frame, *, repeat: int = 1) -> None:
        self._written.append((frame.digest, repeat))

    def play_digest(self) -> tuple[str, int]:
        """(digest of the frames the play wrote, how many frames it wrote)."""
        d = _sha(repr(self._written).encode()).hex()
        n = sum(r for _, r in self._written)
        self._written.clear()
        return d, n


class _TeeCtx:
    """Records exactly the op pass 1 records, then forwards it to the real Cairo context."""

    def __init__(self, ops: list[tuple[Any, ...]], real: Any):
        self._ops, self._real = ops, real

    def __getattr__(self, name: str) -> Any:
        if name not in DRAWING:
            raise AttributeError(f"the tee does not forward cairo.Context.{name}")
        forward = getattr(self._real, name)

        def tee(*args: Any) -> Any:
            self._ops.append(_op(name, args))
            return forward(*args)

        return tee


class Tee(Recorder):
    """A worker's recorder: every call pass 1 records is both digested (with the same op encoder) and forwarded, so
    its frames carry real pixels and a digest the parent compares with pass 1's. It demands nothing more of the camera
    than pass 1 does and guarantees more (Liskov)."""

    def __init__(self, scene: Any):
        super().__init__(scene)
        self._static: tuple[np.ndarray, bytes] | None = None  # the current static_image and its digest
        self._last: tuple[np.ndarray, bytes] | None = None
        renderer = scene.renderer
        save = renderer.save_static_frame_data

        def save_static(sc: Any, static_mobjects: Any) -> Any:
            out = save(sc, static_mobjects)
            self._static = self._last if renderer.static_image is not None else None
            return out

        renderer.save_static_frame_data = save_static

    def _context(self, pixel_array: np.ndarray) -> Any:
        self._matrix()
        return _TeeCtx(self._ops, self._orig["get_cairo_context"](pixel_array))

    def _points(self, pmobject: Any, points: np.ndarray, rgbas: np.ndarray, thickness: float, pixel_array: Any) -> Any:
        super()._points(pmobject, points, rgbas, thickness, pixel_array)
        return self._orig["display_point_cloud"](pmobject, points, rgbas, thickness, pixel_array)

    def _image(self, image_mobject: Any, pixel_array: np.ndarray) -> Any:
        super()._image(image_mobject, pixel_array)
        return self._orig["display_image_mobject"](image_mobject, pixel_array)

    def _reset(self) -> Any:
        super()._reset()
        return self._orig["reset"]()

    def _load(self, frame: Any) -> None:
        assert self._static is not None and self._static[0] is frame, "a background frame the tee did not snapshot"
        self._ops.clear()
        self._canvas = self._static[1]
        self._orig["set_frame_to_background"](frame)

    def _snapshot(self) -> Any:
        super()._snapshot()
        real = self._orig_get_frame()
        self._last = (real, self._canvas)
        return real

    def _write(self, frame: Any, *, repeat: int = 1) -> None:
        self._written.append((self._canvas, repeat))
        self._orig_write(frame, repeat=repeat)


def stream_check(path: Path) -> list[str]:
    """What the clip's stream declares against what config.py requires: codec, pixel format, size and frame rate. Drawing
    is covered by the digests; encoding is covered here. The rate is FFmpeg's base rate: the average rate is frames over
    duration, and a join's small shift at a partial's start makes it inexact on sound clips."""
    import av

    with av.open(str(path)) as f:
        v = f.streams.video[0]
        got = {
            "codec": v.codec_context.name,
            "pix_fmt": v.codec_context.pix_fmt,
            "size": (v.width, v.height),
            "fps": v.base_rate,
        }
    want = {
        "codec": "h264",
        "pix_fmt": OUTPUT["pixel_format"],
        "size": (WIDTH, HEIGHT),
        "fps": FPS,
    }
    return [f"{k} {got[k]} ≠ {want[k]}" for k in want if got[k] != want[k]]


def _pixman() -> str:
    """Read from its pkg-config record: pixman can change antialiased pixels for identical draw calls."""
    return subprocess.run(["pkg-config", "--modversion", "pixman-1"], check=True, capture_output=True, text=True).stdout.strip()


def identity() -> dict:
    """Everything after the frames that shapes a clip's bytes: the three files that hold the recorder, every render setting
    and join, and the drawing and encoding libraries."""
    return {"code": {n: hashlib.sha256((ENGINE / n).read_bytes()).hexdigest() for n in ("fingerprint.py", "config.py", "render.py")},
            "python": sys.version,
            "versions": {d: importlib.metadata.version(d) for d in ("manim", "pycairo", "av", "numpy", "pillow")},
            "cairo": cairo.cairo_version_string(), "pixman": _pixman()}
