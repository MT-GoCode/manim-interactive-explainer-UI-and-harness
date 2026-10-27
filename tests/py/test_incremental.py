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


def test_an_edit_to_a_helper_module_renders_every_cell(softmax, tmp_path):
    line, shas, scratch = rebuild(softmax, tmp_path, "helpers.py", "import numpy as np\n",
                                  "import numpy as np  # edited\n")
    assert re.fullmatch(r"render: 6 cells \(1–6\) in \d chunks? · 0 reused", line), line
    assert shas == scratch == softmax[1][1]


def test_fingerprints_cover_everything_after_the_frames(monkeypatch, tmp_path):
    inputs = {"bundle": {"helpers.py": "1" * 64}, "repo": {"explainers/lesson.py": "2" * 64}}
    base = B.fingerprints([["a"], ["b"]], inputs)
    assert len(set(base)) == 2
    one = B.fingerprints([["a"], ["c"]], inputs)
    assert one[0] == base[0] and one[1] != base[1]
    changed = [B.fingerprints([["a"], ["b"]], {**inputs, k: {p: "3" * 64 for p in v}}) for k, v in inputs.items()]
    version = importlib.metadata.version
    for dist in ("manim", "numpy", "pycairo", "av", "pillow"):
        with monkeypatch.context() as m:
            m.setattr(importlib.metadata, "version", lambda d, dist=dist: "0" if d == dist else version(d))
            changed.append(B.fingerprints([["a"], ["b"]], inputs))
    with monkeypatch.context() as m:
        m.setattr(cairo, "cairo_version_string", lambda: "0")
        changed.append(B.fingerprints([["a"], ["b"]], inputs))
    for name in ("fingerprint.py", "render.py"):
        code = tmp_path / name.partition(".")[0]
        shutil.copytree(B.PICTURE_CODE, code)
        (code / name).write_text((code / name).read_text() + "\n")
        with monkeypatch.context() as m:
            m.setattr(B, "PICTURE_CODE", code)
            changed.append(B.fingerprints([["a"], ["b"]], inputs))
    assert all(f[0] != base[0] and f[1] != base[1] for f in changed)


LONG_EDIT = ("self.play(FadeOut(v), run_time=0.3)", "self.play(FadeOut(v), run_time=0.3 + 0.1 * (k in EDITED))")


def long_edited(b: Path, cells: str) -> Path:
    edit(b, "lesson.py", *LONG_EDIT)
    return edit(b, "lesson.py", "N = 30\n", f"N = 30\nEDITED = {cells}\n")


def build_k(b: Path, k: int) -> dict:
    r = subprocess.run([sys.executable, str(Path(__file__).parent / "build_with_width.py"), str(b), str(k)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_a_rebuild_starts_its_chunks_only_where_fast_forwarding_is_exact(tmp_path):
    b = fresh(tmp_path / "inc", "long.explainer")
    build(b)
    line, shas = build(long_edited(b, "(20,)"))  # after the spinner is gone: cell 21 alone changes
    assert line == "render: 1 cell (21) in 1 chunk · 29 reused"
    assert shas == build(long_edited(fresh(tmp_path / "scratch1", "long.explainer"), "(20,)"))[1]
    # Cell 6 runs while the spinner turns: it changes cells 6-10, and its chunk starts at cell 1, the last cell
    # with no live updater at its start. Cell 21 is back to its first build's frames. One worker, two ranges.
    out = build_k(edit(b, "lesson.py", "EDITED = (20,)", "EDITED = (5,)"), 1)
    assert out["line"] == "render: 11 cells (1–10, 21; 5 pulled in by a live updater) in 1 chunk · 19 reused"
    assert out["shas"] == build(long_edited(fresh(tmp_path / "scratch2", "long.explainer"), "(5,)"))[1]
