"""The base class every lesson's scene subclasses. One continuous Manim scene; self.cell(slug) marks where each cell
starts. In a dry run it records what the build needs: cell boundaries, run times, and what is on screen at each
cell's end (with the lesson.py line that created each thing)."""
import sys
from dataclasses import dataclass, field

from manim import DecimalNumber, Group, MarkupText, Mobject, Scene, SingleStringMathTex, Text, VGroup

TEXT = (Text, MarkupText, SingleStringMathTex, DecimalNumber)  # units whose font size is checked (MathTex, Tex too)


class LessonError(Exception):
    pass


@dataclass
class Unit:
    """One thing on screen at a cell's end."""
    kind: str
    line: int                 # lesson.py line that created it (a helper's import-time objects: the import line)
    font_size: float | None   # smallest font size of the text in it (itself, or e.g. a Matrix's entries); None: no text


@dataclass
class CellRec:
    slug: str
    line: int | None
    first_anim: int
    cuttable: bool = True  # nothing on screen at this cell's start has a time-based updater, so a render chunk may
    #                        start here (fast-forwarding runs such updaters once with dt = run_time, not per frame)
    run_times: list[float] = field(default_factory=list)
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


def _draws(m) -> bool:
    return any(len(x.points) for x in m.get_family())  # images have 4 corner points, so they count


def _font_size(m) -> float | None:
    """A text unit's own size; otherwise the smallest size among the text inside it (Matrix entries, Table cells)."""
    if isinstance(m, TEXT):
        return float(m.font_size)
    sizes = [s for c in m.submobjects if (s := _font_size(c)) is not None]
    return min(sizes) if sizes else None


class Lesson(Scene):
    SOURCE: str = ""     # the path lesson.py is compiled under; set by explain-build
    RECORDING = False    # pass 1 (the check) records each cell's end state; render workers do not

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cells: list[CellRec] = []

    def play(self, *args, **kwargs):
        if not self._cells:
            raise LessonError(f"animation before the first self.cell() (lesson.py:{_lesson_line(self.SOURCE)})")
        super().play(*args, **kwargs)
        self._cells[-1].run_times.append(self.duration)  # the play's exact run time (the clock accumulates float error)

    def cell(self, slug: str):
        if self._cells and self.RECORDING:
            self._cells[-1].end = self._end_state()
        live = any(x.has_time_based_updater() for m in self.mobjects for x in m.get_family())
        self._cells.append(CellRec(slug, _lesson_line(self.SOURCE), self.renderer.num_plays, cuttable=not live))

    def tear_down(self):
        if not self._cells:
            raise LessonError("no self.cell() in the lesson")
        if self.RECORDING:
            self._cells[-1].end = self._end_state()
        super().tear_down()

    def _end_state(self) -> list[Unit]:
        units: list[Unit] = []

        def visit(m, born):
            born = getattr(m, "_born", None) or born
            if type(m) in (VGroup, Group):  # plain groups are opened: grouping never hides anything
                for s in m.submobjects:
                    visit(s, born)
            elif _draws(m):  # placeholders that draw nothing (wait() adds one) are not on screen
                assert born is not None, f"{type(m).__name__} has no creation line"  # all lesson code runs from lesson.py
                units.append(Unit(type(m).__name__, born, _font_size(m)))

        for m in self.mobjects:
            visit(m, None)
        return units
