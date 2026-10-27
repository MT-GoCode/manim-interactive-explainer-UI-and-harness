"""What each frame shows, known without drawing it. In pass 1 the camera runs its own drawing code, but every call it
would make to Cairo (paths, colours, gradients, line widths, joins, caps) and every point cloud and image it would
paint are recorded instead of rasterized. A frame is the digest of what its canvas started from (the background, or a
saved frame) and everything drawn on it since; equal digests draw equal pixels."""
import hashlib

import cairo
import numpy as np


def _sha(*parts: bytes) -> bytes:
    return hashlib.sha256(b"".join(parts)).digest()


class _Frame:
    """Stands in for a pixel array wherever the renderer passes frames around (the static frame, written frames)."""
    __slots__ = ("digest",)

    def __init__(self, digest: bytes):
        self.digest = digest


class _Context:
    """A cairo.Context that records each drawing call this Manim makes. Gradients are recorded by their geometry and
    colour stops. Any other attribute raises: a query (get_matrix, fill_extents) answered with None would draw wrong."""
    DRAWING = frozenset({"new_path", "new_sub_path", "move_to", "curve_to", "close_path", "set_source_rgba",
                         "set_source", "set_line_width", "set_line_join", "set_line_cap", "fill_preserve",
                         "stroke_preserve"})

    def __init__(self, ops: list):
        self._ops = ops

    def __getattr__(self, name):
        if name not in self.DRAWING:
            raise AttributeError(f"pass 1 does not record cairo.Context.{name}")

        def record(*args):
            self._ops.append((name, *(("gradient", a.get_linear_points(), a.get_color_stops_rgba())
                                      if isinstance(a, cairo.LinearGradient) else float(a) for a in args)))
        return record


class Recorder:
    """Installed on one scene's camera and renderer for pass 1. play_digest() closes one animation: the digests of
    the frames it wrote, each with its repeat count, in order."""

    def __init__(self, scene):
        cam, self._cam = scene.camera, scene.camera
        self._ops: list = []
        self._canvas = b""
        self._written: list[tuple[bytes, int]] = []
        self._backgrounds: dict[int, tuple[np.ndarray, bytes]] = {}
        background_colored = cam.display_multiple_background_colored_vmobjects

        def background_colored_vmobjects(vmobjects, pixel_array):
            vmobjects = list(vmobjects)
            displayer = cam.get_background_colored_vmobject_displayer()
            self._ops += [("background-image", self._array(displayer.get_background_array(v.get_background_image())))
                          for v in vmobjects]
            return background_colored(vmobjects, pixel_array)

        cam.get_cairo_context = self._context
        cam.display_point_cloud = self._points
        cam.display_image_mobject = self._image
        cam.display_multiple_background_colored_vmobjects = background_colored_vmobjects
        cam.reset = self._reset
        cam.set_frame_to_background = self._load
        scene.renderer.get_frame = self._snapshot
        scene.renderer.file_writer.write_frame = self._write

    def _array(self, a: np.ndarray) -> bytes:
        """Digest of an array that stays the same object while in use (the background, a background image); the
        array is kept alive with its digest, so its id is never reused for another."""
        hit = self._backgrounds.get(id(a))
        if hit is None:
            hit = self._backgrounds[id(a)] = (a, _sha(repr((a.shape, a.dtype.str)).encode(), a.tobytes()))
        return hit[1]

    def _context(self, pixel_array) -> _Context:
        """Paths are recorded in scene units: the world-to-pixel matrix Camera.get_cairo_context sets is part of what
        is drawn (the 3D camera's orientation is already in the projected points)."""
        c = self._cam
        sx, sy = c.pixel_width / c.frame_width, c.pixel_height / c.frame_height
        self._ops.append(("matrix", *map(float, (sx, -sy, c.pixel_width / 2 - c.frame_center[0] * sx,
                                                 c.pixel_height / 2 + c.frame_center[1] * sy))))
        return _Context(self._ops)

    def _points(self, pmobject, points, rgbas, thickness, pixel_array):
        coords = self._cam.points_to_pixel_coords(pmobject, points)
        self._ops.append(("points", _sha(coords.tobytes(), np.asarray(rgbas, float).tobytes()), float(thickness)))

    def _image(self, image_mobject, pixel_array):
        pixels = np.ascontiguousarray(image_mobject.get_pixel_array())
        corners = self._cam.points_to_subpixel_coords(image_mobject, image_mobject.points)
        self._ops.append(("image", _sha(repr(pixels.shape).encode(), pixels.tobytes(), corners.tobytes()),
                          int(image_mobject.resampling_algorithm)))

    def _reset(self):
        self._ops.clear()
        self._canvas = self._array(self._cam.background)
        return self._cam

    def _load(self, frame: _Frame):
        self._ops.clear()
        self._canvas = frame.digest

    def _snapshot(self) -> _Frame:
        self._canvas = _sha(self._canvas, repr(self._ops).encode())
        self._ops.clear()
        return _Frame(self._canvas)

    def _write(self, frame: _Frame, *, repeat: int = 1):
        self._written.append((frame.digest, repeat))

    def play_digest(self) -> str:
        d = _sha(repr(self._written).encode()).hex()
        self._written.clear()
        return d
