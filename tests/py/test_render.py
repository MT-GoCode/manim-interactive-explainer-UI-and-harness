"""Clips: exactly the frames of a plain one-pass render, cut at the cell boundaries; content-named; atomic."""
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import jsonschema
import pytest

from conftest import FIXTURES, REPO, explain_build

pytestmark = pytest.mark.xdist_group("render")  # builds that render run one at a time

REFERENCE = Path(__file__).parent / "reference_render.py"


def frames(path):
    import av
    return [f.to_ndarray(format="rgb24") for f in av.open(str(path)).decode(video=0)]


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    b = tmp_path_factory.mktemp("r") / "softmax.explainer"
    shutil.copytree(FIXTURES / "softmax.explainer", b, ignore=shutil.ignore_patterns("build"))
    return b, explain_build(b)


def ok(built):
    b, r = built
    assert r.returncode == 0, r.stderr
    return b, json.loads((b / "build" / "index.json").read_text())


def test_clips_equal_a_one_pass_render_cut_at_cells(built, tmp_path):
    b, index = ok(built)
    ref = subprocess.run([sys.executable, str(REFERENCE), str(b), str(tmp_path)], capture_output=True, text=True)
    assert ref.returncode == 0, ref.stderr
    parts = sorted(tmp_path.rglob("uncached_*.mp4"))
    starts = json.loads(ref.stdout)  # first animation index of each cell, then the total
    for n, c in enumerate(index["cells"]):
        want = [f for p in parts[starts[n]:starts[n + 1]] for f in frames(p)]
        got = frames(b / "build" / c["clip"])
        assert len(got) == len(want) == c["frames"]
        assert all((g == w).all() for g, w in zip(got, want)), c["slug"]


def test_every_clip_is_single_threaded_keyint_6_crf_18(built):
    b, index = ok(built)
    for c in index["cells"]:
        sei = (b / "build" / c["clip"]).read_bytes()[:20000]
        opts = dict(re.findall(rb"(?<![\w])(\w+)=(\S+)", sei.partition(b"options: ")[2].partition(b"\0")[0]))
        assert (opts[b"threads"], opts[b"keyint"], opts[b"crf"]) == (b"1", b"6", b"18.0"), c["slug"]


def test_index_validates_and_clips_are_named_by_content(built):
    import hashlib
    b, index = ok(built)
    jsonschema.validate(index, json.loads((REPO / "schema" / "index.schema.json").read_text()))
    assert index["fps"] == 30
    for c in index["cells"]:
        clip = b / "build" / c["clip"]
        assert clip.name == f"{c['frames_sha']}.mp4" == f"{hashlib.sha256(clip.read_bytes()).hexdigest()}.mp4"
    assert sorted(p.name for p in (b / "build" / "clips").iterdir()) == sorted(Path(c["clip"]).name for c in index["cells"])
    assert not (b / "build" / ".media").exists()


def test_an_edit_inside_one_cell_changes_only_that_cells_clip_and_old_clips_last_one_rebuild(bundle):
    b = bundle()
    assert explain_build(b).returncode == 0
    first = json.loads((b / "build" / "index.json").read_text())
    src = b / "lesson.py"
    src.write_text(src.read_text().replace("self.play(FadeOut(title), run_time=0.5)", "self.play(FadeOut(title), run_time=0.7)"))
    assert explain_build(b).returncode == 0
    second = json.loads((b / "build" / "index.json").read_text())
    changed = [a["slug"] for a, z in zip(first["cells"], second["cells"]) if a["frames_sha"] != z["frames_sha"]]
    assert changed == ["probs"]
    old = b / "build" / next(c["clip"] for c in first["cells"] if c["slug"] == "probs")
    assert old.exists()  # the previous build's clip survives one rebuild (the app may still be playing it)
    src.write_text(src.read_text().replace("run_time=0.7)", "run_time=0.9)"))
    assert explain_build(b).returncode == 0
    assert not old.exists()


def test_killed_build_keeps_the_previous_build_and_leaves_no_worker(bundle):
    b = bundle().resolve()  # the build names its bundle resolved (/var is a link to /private/var on macOS)
    assert explain_build(b).returncode == 0
    before = (b / "build" / "index.json").read_text()
    clips = sorted((b / "build" / "clips").iterdir())
    src = b / "lesson.py"
    original = src.read_text()
    src.write_text(original.replace("run_time=1.25", "run_time=60"))  # its chunk is still rendering when the kill lands
    p = subprocess.Popen([str(REPO / "bin" / "explain-build"), str(b)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    deadline = time.time() + 60
    while not list((b / "build").glob(".media/*/**/uncached_*.mp4")) and time.time() < deadline:
        time.sleep(0.1)
    assert time.time() < deadline, "no partial appeared"
    workers = subprocess.run(["pgrep", "-f", f"explainers.render {b}"], capture_output=True, text=True).stdout.split()
    assert workers
    # Kill the build itself (the Python under uv's shim), not the shim: uv runs Python as a child, not via exec.
    build = subprocess.run(["pgrep", "-f", f"bin/explain-build {b}"], capture_output=True, text=True).stdout.split()
    builds = [pid for pid in build if "python" in subprocess.run(["ps", "-o", "command=", "-p", pid], capture_output=True, text=True).stdout]
    assert len(builds) == 1, builds
    os.kill(int(builds[0]), signal.SIGKILL)
    for _ in range(30):  # each worker notices its parent is gone within a second
        if not subprocess.run(["pgrep", "-f", f"explainers.render {b}"], capture_output=True).stdout:
            break
        time.sleep(0.1)
    assert not subprocess.run(["pgrep", "-f", f"explainers.render {b}"], capture_output=True).stdout
    assert (b / "build" / "index.json").read_text() == before
    assert all(c.exists() for c in clips)
    # a rebuild that renders the killed cell again, over whatever the killed build left in build/
    src.write_text(original.replace("run_time=1.25", "run_time=1.5"))
    assert explain_build(b).returncode == 0


def test_a_cell_with_no_animation_is_an_error(bundle):
    b = bundle()
    src = b / "lesson.py"
    src.write_text(src.read_text().replace('        self.cell("exp")\n', '        self.cell("exp")\n        self.cell("empty")\n'))
    md = b / "cells.md"
    md.write_text(md.read_text().replace("## sum\n", "## empty\nNothing.\n\n## sum\n"))
    r = explain_build(b)
    assert r.returncode == 1 and r.stderr.strip() == 'error: cell "exp" has no animation (lesson.py:19)'


def test_a_manim_cfg_where_the_build_runs_does_not_change_the_clips(built, bundle, tmp_path):
    _, index = ok(built)
    (tmp_path / "manim.cfg").write_text("[video_encoder]\npixel_format = yuv444p\n")
    b = bundle()
    r = explain_build(b, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert [c["frames_sha"] for c in json.loads((b / "build" / "index.json").read_text())["cells"]] == \
           [c["frames_sha"] for c in index["cells"]]
