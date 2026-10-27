"""The base classes every lesson's scene subclasses (Lesson, Lesson3D). One continuous Manim scene; self.cell(slug)
marks where each cell starts. In a dry run (pass 1) it records what the build needs: cell boundaries, run times, a
digest of every frame each animation writes, and exactly what is drawn at each cell's end, where the camera draws it,
with the lesson.py line that created each thing."""
import sys
from dataclasses import dataclass, field

import numpy as np
from manim import (Axes, DecimalNumber, Dot, Group, ImageMobject, MarkupText, Mobject, NumberPlane, Paragraph, Scene,
                   SingleStringMathTex, Text, ThreeDScene, VGroup, VMobject)

from explainers.fingerprint import Recorder

TEXT = (Text, MarkupText)                     # plain text units (minimum font size 32)
LATEX = (SingleStringMathTex, DecimalNumber)  # TeX-set units: MathTex, Tex, numbers (minimum 40)
GLYPHS = TEXT + LATEX + (Paragraph,)          # every leaf under these is a glyph (Paragraph: Code, Table entries)
BACKGROUND = (NumberPlane, Axes)              # their lines never count for overlap
SAMPLES_PER_CURVE = 8  # chords per cubic: a 45° arc (Manim's circle segment) in 8 chords strays 0.0012·r from the
#                        curve, under half a pixel (0.0037) up to r = 3
_T = np.linspace(0, 1, SAMPLES_PER_CURVE + 1)
_BERNSTEIN = np.stack([(1 - _T) ** 3, 3 * (1 - _T) ** 2 * _T, 3 * (1 - _T) * _T ** 2, _T ** 3], axis=1)


class LessonError(Exception):
    pass


@dataclass
class Unit:
    """One thing drawn at a cell's end, as the geometry check sees it; coordinates are where the camera draws them."""
    kind: str
    line: int                      # lesson.py line that created it (a helper's import-time objects: the import line)
    owners: list[int]              # ids of its whole family and of the plain groups it was opened from
    attached_to: int | None        # id of the object it was attached to (self.attach)
    transient_cell: int | None     # index of the cell it was made transient in (self.transient)
    text_size: float | None        # smallest plain-text font size in it, if any
    latex_size: float | None       # smallest TeX font size in it (MathTex, numbers, a Matrix's entries), if any
    glyphs: list[list[float]]      # boxes [x0, y0, x1, y1] of letters and symbols
    markers: list[list[float]]     # boxes of dots: placed on paths by intent, so they meet glyphs and dots only
    strokes: list[list[list[float]]]  # polylines [[x, y], ...], one per subpath
    fills: list[list[float]]       # boxes of fill-only shapes and images (off frame only)


@dataclass
class CellRec:
    slug: str
    line: int | None
    first_anim: int
    cuttable: bool = True  # nothing on screen at this cell's start has a time-based updater, so a render chunk may
    #                        start here (fast-forwarding runs such updaters once with dt = run_time, not per frame)
    run_times: list[float] = field(default_factory=list)
    drawn: list[str] = field(default_factory=list)  # per animation: the digest of the frames it writes (fingerprint.py)
    end: list[Unit] | None = None


def _lesson_line(source: str) -> int | None:
    """The innermost lesson.py line on the current stack (a helper called from lesson.py resolves to the call)."""
    f = sys._getframe(1)
    while f is not None and f.f_code.co_filename != source:
        f = f.f_back
    return f.f_lineno if f is not None else None


def record_creation_lines(source: str) -> None:
    """Every mobject made while a lesson runs remembers the lesson line that made it; a copy, the line that copied."""
    init, copy = Mobject.__init__, Mobject.copy

    def recording_init(m, *a, **k):
        init(m, *a, **k)
        m._born = _lesson_line(source)

    def recording_copy(m, *a, **k):
        c = copy(m, *a, **k)
        line = _lesson_line(source)
        for x in c.get_family():
            x._born = line
        return c

    Mobject.__init__, Mobject.copy = recording_init, recording_copy


def _box(p: np.ndarray) -> list[float]:
    return [float(p[:, 0].min()), float(p[:, 1].min()), float(p[:, 0].max()), float(p[:, 1].max())]


def _polylines(m: VMobject):
    """Each subpath's cubic curves sampled at SAMPLES_PER_CURVE chords (subpaths are never joined)."""
    for sub in m.get_subpaths():
        pts = np.einsum("sk,ckd->csd", _BERNSTEIN, sub.reshape(-1, 4, 3))
        yield np.concatenate([pts[:, :-1].reshape(-1, 3), pts[-1, -1:]])


def _leaves(m, screen, glyph=False, background=False, out=None):
    """Children first, then the mobject's own path (an Arrow's shaft is the parent; its tip is a child).
    screen(mobject, points) maps points to where the camera draws them."""
    out = out if out is not None else ([], [], [], [])
    glyph = glyph or isinstance(m, GLYPHS)
    background = background or isinstance(m, BACKGROUND)
    for s in m.submobjects:
        _leaves(s, screen, glyph, background, out)
    if isinstance(m, ImageMobject):
        out[3].append(_box(screen(m, m.points)))
    elif isinstance(m, VMobject) and len(m.points):
        if glyph:
            out[0].append(_box(screen(m, m.points)))
        elif isinstance(m, Dot):
            out[1].append(_box(screen(m, m.points)))
        elif m.get_stroke_width() > 0 and m.get_stroke_opacity() > 0:
            if not background:
                out[2].extend(screen(m, p).tolist() for p in _polylines(m))
        elif m.get_fill_opacity() > 0:
            out[3].append(_box(screen(m, m.points)))
    return out


def _sizes(m) -> tuple[float | None, float | None]:
    """(smallest plain-text size, smallest TeX size) in m: its own if it is text, else over the text inside it."""
    if isinstance(m, TEXT):
        return float(m.font_size), None
    if isinstance(m, LATEX):
        return None, float(m.font_size)
    found = [_sizes(c) for c in m.submobjects]
    pick = lambda vals: min(vals) if vals else None
    return pick([t for t, _ in found if t is not None]), pick([l for _, l in found if l is not None])


class Lesson(Scene):
    SOURCE: str = ""     # the path lesson.py is compiled under; set by explain-build
    RECORDING = False    # pass 1 (the check) records each cell's end state; render workers do not

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cells: list[CellRec] = []
        self._anchors: list[Mobject] = []  # everything attached to stays alive, so its id is never reused
        if self.RECORDING:
            self._recorder = Recorder(self)

    def play(self, *args, **kwargs):
        if not self._cells:
            raise LessonError(f"animation before the first self.cell() (lesson.py:{_lesson_line(self.SOURCE)})")
        super().play(*args, **kwargs)
        self._cells[-1].run_times.append(self.duration)  # the play's exact run time (the clock accumulates float error)
        if self.RECORDING:
            self._cells[-1].drawn.append(self._recorder.play_digest())

    def cell(self, slug: str):
        if self._cells:
            self._close()
        else:
            self._camera = self._camera_state()
        live = any(x.has_time_based_updater() for m in self.mobjects for x in m.get_family())
        self._cells.append(CellRec(slug, _lesson_line(self.SOURCE), self.renderer.num_plays, cuttable=not live))

    def tear_down(self):
        if not self._cells:
            raise LessonError("no self.cell() in the lesson")
        self._close()
        super().tear_down()

    def _close(self):
        """End the current cell: in pass 1, record what is on screen; the camera must not have moved (checked at
        cell ends: a move that returns within one cell is not seen)."""
        if not self.RECORDING:
            return
        c = self._cells[-1]
        if self._camera_state() != self._camera:
            raise LessonError(f'the camera moved in cell "{c.slug}" (lesson.py:{c.line}); the camera is static: '
                              "set it before the first self.cell()")
        c.end = self._end_state()

    def attach(self, child, to):
        """Mark child as meant to sit on `to` or any part of it (a label on its arrow, a number in its cell): they
        may overlap. Copies of child stay attached to the same `to`."""
        self._anchors.append(to)
        child._attached_to = id(to)
        return child

    def transient(self, *mobs):
        """Mark mobjects (cursors, highlights) that must be gone by the end of the cell they were made in."""
        if not self._cells:
            raise LessonError(f"transient() before the first self.cell() (lesson.py:{_lesson_line(self.SOURCE)})")
        for m in mobs:
            m._transient_cell = len(self._cells) - 1
        return mobs[0] if len(mobs) == 1 else mobs

    def _camera_state(self) -> list[float] | None:
        return None  # a 2D Scene's camera cannot move

    def _end_state(self) -> list[Unit]:
        units: list[Unit] = []
        # The display's own mapping: the camera's transform, then its frame centre (Camera.points_to_subpixel_coords).
        screen = lambda m, p: (self.camera.transform_points_pre_display(m, p) - self.camera.frame_center)[:, :2]

        def visit(m, born, groups, attached, transient):
            born = getattr(m, "_born", None) or born
            a = getattr(m, "_attached_to", None)
            attached = a if a is not None else attached
            t = getattr(m, "_transient_cell", None)
            transient = t if t is not None else transient
            if type(m) in (VGroup, Group):  # plain groups are opened: grouping never hides anything
                for s in m.submobjects:
                    visit(s, born, groups + [id(m)], attached, transient)
                return
            g, d, s, f = _leaves(m, screen)
            if not (g or d or s or f):  # draws nothing (wait() adds such a placeholder): not on screen
                return
            assert born is not None, f"{type(m).__name__} has no creation line"  # all lesson code runs from lesson.py
            units.append(Unit(type(m).__name__, born, groups + [id(x) for x in m.get_family()], attached, transient,
                              *_sizes(m), g, d, s, f))

        for m in self.mobjects:
            visit(m, None, [], None, None)
        return units


class Lesson3D(Lesson, ThreeDScene):
    """A 3D lesson. Set the camera once, before the first self.cell(); it never moves after that (static camera)."""

    def _camera_state(self) -> list[float]:
        c = self.camera
        return [float(c.get_phi()), float(c.get_theta()), float(c.get_gamma()), float(c.get_focal_distance()),
                float(c.get_zoom()), *map(float, c.frame_center)]
