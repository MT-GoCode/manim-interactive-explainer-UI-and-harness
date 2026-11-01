"""What pass 1 hands the build, as JSON: pass 1 runs in its own process, and the build never imports manim."""
import dataclasses
import json
from dataclasses import dataclass, field
from pathlib import Path


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


@dataclass
class Records:
    cells: list[CellRec]
    refs: dict[str, str]
    ref_errors: list[str]
    inputs: list[str]         # snapshot-relative paths opened, stat'ed or accessed, folders listed as "dir/"; import attempts
    #                           that found nothing included (they are "absent", a stable value)
    repo: list[str]           # repo-relative picture code imported
    cache_entries: list[str]  # file names opened or created in the TeX/text cache
    cost: list[float]         # per play, in play order: what a fast-forward to it costs, by pass 1's clock
    frame: tuple[float, float]


def dump(records: Records, path: Path) -> None:
    path.write_text(json.dumps(dataclasses.asdict(records)))


def load(path: Path) -> Records:
    d = json.loads(path.read_text())
    cells = [CellRec(**{**c, "end": None if c["end"] is None else [Unit(**u) for u in c["end"]]}) for c in d.pop("cells")]
    return Records(cells=cells, frame=tuple(d.pop("frame")), **d)
