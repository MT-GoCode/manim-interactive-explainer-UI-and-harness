"""A rebuild renders only the cells whose fingerprints changed, and its clips are byte-identical to a from-scratch build
of the same lesson (frames_sha per cell)."""
import importlib.metadata
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import cairo
import pytest

from conftest import FIXTURES, explain_build
from explainers import build as B
from explainers import fingerprint as F

pytestmark = pytest.mark.xdist_group("render")  # builds that render run one at a time


def build(b: Path) -> tuple[str, list[str]]:
    """(the report's render line, frames_sha per cell)."""
    r = explain_build(b)
    assert r.returncode == 0, r.stderr
    line = next(l for l in r.stdout.splitlines() if l.startswith("render:"))
    return line, [c["frames_sha"] for c in json.loads((b / "build" / "index.json").read_text())["cells"]]


def edit(b: Path, name: str, old: str, new: str) -> Path:
    f = b / name
    assert old in f.read_text()
    f.write_text(f.read_text().replace(old, new))
    return b


def fresh(tmp: Path, fixture: str, src: Path | None = None) -> Path:
    """A copy of the fixture, or of src with its build (a previous build to rebuild from)."""
    dst = tmp / fixture
    shutil.copytree(src or FIXTURES / fixture, dst, ignore=None if src else shutil.ignore_patterns("build"))
    return dst


@pytest.fixture(scope="module")
def softmax(tmp_path_factory):
    b = fresh(tmp_path_factory.mktemp("first"), "softmax.explainer")
    return b, build(b)


def rebuild(softmax, tmp_path, name, old, new):
    """(render line of the rebuild after the edit, its shas, the shas of a from-scratch build of the edited lesson)."""
    line, shas = build(edit(fresh(tmp_path / "inc", "softmax.explainer", softmax[0]), name, old, new))
    return line, shas, build(edit(fresh(tmp_path / "scratch", "softmax.explainer"), name, old, new))[1]


def test_no_change_renders_nothing(softmax, tmp_path):
    b = fresh(tmp_path, "softmax.explainer", softmax[0])
    index = (b / "build" / "index.json").read_text()
    assert build(b) == ("render: 0 cells · 6 reused", softmax[1][1])
    assert (b / "build" / "index.json").read_text() == index


def test_a_missing_or_altered_clip_is_rendered_again(softmax, tmp_path):
    b = fresh(tmp_path, "softmax.explainer", softmax[0])
    cells = json.loads((b / "build" / "index.json").read_text())["cells"]
    (b / "build" / cells[1]["clip"]).unlink()
    (b / "build" / cells[4]["clip"]).write_bytes(b"not the clip")
    line, shas = build(b)
    assert re.fullmatch(r"render: 2 cells \(2, 5\) in \d chunks? · 4 reused", line), line
    assert shas == softmax[1][1]


def test_an_edit_inside_one_cell_renders_that_cell(softmax, tmp_path):
    line, shas, scratch = rebuild(softmax, tmp_path, "lesson.py", "self.play(FadeOut(title), run_time=0.5)",
                                  "self.play(FadeOut(title), run_time=0.7)")
    assert line == "render: 1 cell (5) in 1 chunk · 5 reused"
    assert shas == scratch


def test_an_edit_whose_effect_persists_renders_every_cell_it_reaches(softmax, tmp_path):
    # s stays on screen from "sum" to the end, and "divide" transforms a copy of it.
    line, shas, scratch = rebuild(softmax, tmp_path, "lesson.py", "next_to(z, DOWN, buff=0.8)",
                                  "next_to(z, DOWN, buff=0.9)")
    assert re.fullmatch(r"render: 4 cells \(3–6\) in \d chunks? · 2 reused", line), line
    assert shas == scratch


def test_a_helper_edit_that_changes_no_frame_renders_no_cell(softmax, tmp_path):
    before = json.loads((softmax[0] / "build" / "index.json").read_text())["inputs"]["bundle"]
    b = edit(fresh(tmp_path, "softmax.explainer", softmax[0]), "helpers.py", "import numpy as np\n", "import numpy as np  # edited\n")
    assert build(b) == ("render: 0 cells · 6 reused", softmax[1][1])
    assert json.loads((b / "build" / "index.json").read_text())["inputs"]["bundle"] != before  # the app's stale alert still fires


def test_fingerprints_cover_everything_after_the_frames(monkeypatch, tmp_path):
    drawn = [["a"], ["b"]]
    base = B.fingerprints(drawn, F.identity())
    assert len(set(base)) == 2
    one = B.fingerprints([["a"], ["c"]], F.identity())
    assert one[0] == base[0] and one[1] != base[1]
    changed = []
    version = importlib.metadata.version
    for dist in ("manim", "numpy", "pycairo", "av", "pillow"):
        with monkeypatch.context() as m:
            m.setattr(importlib.metadata, "version", lambda d, dist=dist: "0" if d == dist else version(d))
            changed.append(B.fingerprints(drawn, F.identity()))
    for target, name in ((cairo, "cairo_version_string"), (F, "_pixman")):
        with monkeypatch.context() as m:
            m.setattr(target, name, lambda: "0")
            changed.append(B.fingerprints(drawn, F.identity()))
    with monkeypatch.context() as m:
        m.setattr(sys, "version", "0")
        changed.append(B.fingerprints(drawn, F.identity()))
    for name in ("fingerprint.py", "render.py", "config.py"):
        code = tmp_path / name.partition(".")[0]
        shutil.copytree(F.ENGINE, code)
        (code / name).write_text((code / name).read_text() + "\n")
        with monkeypatch.context() as m:
            m.setattr(F, "ENGINE", code)
            changed.append(B.fingerprints(drawn, F.identity()))
    assert all(f[0] != base[0] and f[1] != base[1] for f in changed)


def test_the_cache_id_covers_the_tools_that_fill_it(monkeypatch, tmp_path):
    import manimpango
    base, changed = B.cache_id(), []
    with monkeypatch.context() as m:
        m.setattr(manimpango, "pango_version", lambda: "0")
        changed.append(B.cache_id())
    tlpdb = tmp_path / ".tinytex" / "TinyTeX" / "tlpkg" / "texlive.tlpdb"
    tlpdb.parent.mkdir(parents=True)
    tlpdb.write_text("another TeX")
    with monkeypatch.context() as m:
        m.setattr(B, "REPO", tmp_path)
        changed.append(B.cache_id())
    assert all(c != base for c in changed)


LONG_EDIT = ("self.play(FadeOut(v), run_time=0.3)", "self.play(FadeOut(v), run_time=0.3 + 0.1 * (k in EDITED))")


def long_edited(b: Path, cells: str) -> Path:
    edit(b, "lesson.py", *LONG_EDIT)
    return edit(b, "lesson.py", "N = 30\n", f"N = 30\nEDITED = {cells}\n")


def build_k(b: Path, k: int) -> dict:
    r = subprocess.run([sys.executable, str(Path(__file__).parent / "build_with_width.py"), str(b), str(k)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def shift_edited(b: Path, cells: str) -> Path:
    """An edit that stays inside its cell: v appears and leaves there, and no duration changes."""
    edit(b, "lesson.py", ".shift(RIGHT * jitter[k])", ".shift(RIGHT * (jitter[k] + 0.1 * (k in EDITED)))")
    return edit(b, "lesson.py", "N = 30\n", f"N = 30\nEDITED = {cells}\n")


def test_an_edit_under_a_live_updater_renders_only_its_cell(tmp_path):
    first = fresh(tmp_path / "first", "long.explainer")
    build(first)
    cases = [(shift_edited, "(5,)", "render: 1 cell (6) in 1 chunk · 29 reused"),
             (shift_edited, "(5, 20)", "render: 2 cells (6, 21) in 1 chunk · 28 reused"),  # one worker, two ranges
             (long_edited, "(5,)", "render: 5 cells (6–10) in 1 chunk · 25 reused")]  # a longer play turns the spinner further
    for n, (edited, cells, line) in enumerate(cases):
        out = build_k(edited(fresh(tmp_path / f"inc{n}", "long.explainer", first), cells), 1)
        assert out["line"] == line
        assert out["shas"] == build(edited(fresh(tmp_path / f"scratch{n}", "long.explainer"), cells))[1]
