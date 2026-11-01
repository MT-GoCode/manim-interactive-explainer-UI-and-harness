"""Clips: exactly the frames of a plain one-pass render, cut at the cell boundaries; content-named; atomic."""
import contextlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import jsonschema
import psutil
import pytest

from conftest import FIXTURES, REPO, engine_copy, explain_build, run_pass1
from explainers.build import costs
from explainers.schedule import SEED_S_PER_VIDEO_S

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


def clips_equal_a_one_pass_render(b, index, tmp_path):
    ref = subprocess.run([sys.executable, str(REFERENCE), str(b), str(tmp_path)], capture_output=True, text=True)
    assert ref.returncode == 0, ref.stderr
    parts = sorted(tmp_path.rglob("uncached_*.mp4"))
    starts = json.loads(ref.stdout)  # first animation index of each cell, then the total
    for n, c in enumerate(index["cells"]):
        want = [f for p in parts[starts[n]:starts[n + 1]] for f in frames(p)]
        got = frames(b / "build" / c["clip"])
        assert len(got) == len(want) == c["frames"]
        assert all((g == w).all() for g, w in zip(got, want)), c["slug"]


def test_clips_equal_a_one_pass_render_cut_at_cells(built, tmp_path):
    clips_equal_a_one_pass_render(*ok(built), tmp_path)


def test_images_and_point_clouds_reach_the_clips(bundle, tmp_path):
    """A digest cannot see a tee that records a call and does not draw it: only a stock render can."""
    b = bundle("frames.explainer")
    clips_equal_a_one_pass_render(b, built_ok(b), tmp_path)


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
    # Kill the build itself, the workers' parent (uv's shim runs it as a child, not via exec).
    os.kill(parent_of(workers_of(b)), signal.SIGKILL)
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


CFG = "[CLI]\nframe_rate = 10\nbackground_color = RED\n[video_encoder]\npixel_format = yuv444p\n"


def test_a_manim_cfg_where_the_build_runs_does_not_change_the_clips(built, bundle, tmp_path):
    _, index = ok(built)
    (tmp_path / "manim.cfg").write_text(CFG)
    b = bundle()
    r = explain_build(b, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert [c["frames_sha"] for c in json.loads((b / "build" / "index.json").read_text())["cells"]] == \
           [c["frames_sha"] for c in index["cells"]]


def edit(b, name, old, new):
    f = b / name
    assert old in f.read_text()
    f.write_text(f.read_text().replace(old, new))
    return b


def index_of(b):
    return json.loads((b / "build" / "index.json").read_text())


def built_ok(b, args=(), **kwargs):
    r = explain_build(b, *args, **kwargs)
    assert r.returncode == 0, r.stderr
    return index_of(b)


def workers_of(b):
    return [int(p) for p in subprocess.run(["pgrep", "-f", f"explainers.render {b}"], capture_output=True, text=True).stdout.split()]


def parent_of(workers):
    for w in workers:  # the first may already have finished
        with contextlib.suppress(psutil.NoSuchProcess):
            return psutil.Process(w).ppid()
    raise AssertionError("every worker had exited")


def kill_all(pids):
    for p in pids:
        try:
            os.kill(p, signal.SIGKILL)
        except ProcessLookupError:
            pass


def test_a_manim_cfg_in_the_bundle_does_not_change_the_clips(built, bundle):
    _, index = ok(built)
    b = bundle()
    (b / "manim.cfg").write_text(CFG)
    new = built_ok(b)
    assert [(c["frames_sha"], c["fingerprint"]) for c in new["cells"]] == [(c["frames_sha"], c["fingerprint"]) for c in index["cells"]]


def test_a_broken_manim_cfg_where_the_build_runs_is_never_read(bundle, tmp_path):
    (tmp_path / "manim.cfg").write_text("this is not an ini file\n")
    built_ok(bundle(), cwd=tmp_path)


def test_a_module_in_the_callers_cwd_is_never_imported(bundle, tmp_path):
    (tmp_path / "explainers").mkdir()
    (tmp_path / "explainers" / "__init__.py").write_text('raise SystemExit("cwd copy ran")\n')
    built_ok(bundle(), cwd=tmp_path)


def test_the_hash_seed_is_fixed(bundle):
    b = edit(bundle(), "lesson.py", "n_tokens = len(Z)\n", 'n_tokens = len(Z)\nh = hash("explainers")\n')
    (b / "cells.md").write_text((b / "cells.md").read_text() + "\nHash {h}.\n")
    env = {k: v for k, v in os.environ.items() if k != "PYTHONHASHSEED"}
    r = subprocess.run([str(REPO / "bin" / "explain-build"), str(b)], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    want = subprocess.run([sys.executable, "-c", 'print(hash("explainers"))'], capture_output=True, text=True,
                          env={**os.environ, "PYTHONHASHSEED": "0"}).stdout.strip()
    assert index_of(b)["refs"]["h"] == want


def test_a_tex_object_made_at_import_time_builds(bundle):
    built_ok(edit(bundle(), "lesson.py", "n_tokens = len(Z)\n", 'n_tokens = len(Z)\nEQ = MathTex("x", font_size=48)\n'))


def test_an_edit_while_pass_1_runs_reaches_nothing_of_that_build(built, bundle):
    """scores.csv and helpers.py feed the drawn numbers and the ref p_top: edited once the snapshot holds every file, they
    change neither the refs, the clips, nor the inputs this build records."""
    _, index = ok(built)
    b = bundle()
    names = ("lesson.py", "helpers.py", "scores.csv", "cells.md")
    snap = b / "build" / ".media" / "src"
    p = subprocess.Popen([str(REPO / "bin" / "explain-build"), str(b)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    deadline = time.time() + 60
    while not all((snap / n).exists() and (snap / n).stat().st_size == (b / n).stat().st_size for n in names):
        assert time.time() < deadline and p.poll() is None, "the snapshot never appeared"
        time.sleep(0.01)
    (b / "scores.csv").write_text((b / "scores.csv").read_text().replace("1", "3"))
    (b / "helpers.py").write_text((b / "helpers.py").read_text() + "\nP = P * 0\n")
    (b / "lesson.py").write_text((b / "lesson.py").read_text() + "\n# edited\n")
    _, err = p.communicate(timeout=300)
    assert p.returncode == 0, err
    new = index_of(b)
    assert (new["refs"], new["inputs"]["bundle"]) == (index["refs"], index["inputs"]["bundle"])
    assert [c["frames_sha"] for c in new["cells"]] == [c["frames_sha"] for c in index["cells"]]
    assert new["lesson_sha"] == index["lesson_sha"]  # the app compares it with the live file, so these clips show as stale


def test_the_check_reads_cells_md_from_the_snapshot(bundle, tmp_path):
    b = bundle()
    snap = b / "build" / ".media" / "src"
    shutil.copytree(b, snap, ignore=shutil.ignore_patterns("build"))
    (b / "cells.md").write_text("## another-cell\n\nText.\n")
    (tmp_path / "shared").mkdir()
    r = subprocess.run([sys.executable, "-c", "import sys\nfrom pathlib import Path\nfrom explainers.build import check\n"
                        "check(Path(sys.argv[1]), Path(sys.argv[2]))\n", str(snap), str(tmp_path / "shared")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_a_worker_reads_relative_paths_in_the_snapshot(bundle, tmp_path):
    """The lesson draws from a relative path. Run from a folder holding another file of that name, the clips do not change."""
    def lesson(b):
        return edit(b, "helpers.py", '(Path(__file__).parent / "scores.csv").read_text()', 'open("scores.csv").read()')
    same, other = tmp_path / "same", tmp_path / "other"
    same.mkdir()
    other.mkdir()
    a = lesson(bundle())
    (same / "scores.csv").write_text((a / "scores.csv").read_text())
    (other / "scores.csv").write_text((a / "scores.csv").read_text().replace("1", "3"))
    first = [c["frames_sha"] for c in built_ok(a, cwd=same)["cells"]]
    shutil.rmtree(a / "build")
    assert [c["frames_sha"] for c in built_ok(a, cwd=other)["cells"]] == first


def build_with_probe(b):
    r = subprocess.run([str(REPO / "bin" / "explain-build"), str(b)], capture_output=True, text=True,
                       env={**os.environ, "EXPLAINERS_TEST_PROBE": "1"})
    assert r.returncode == 0, r.stderr
    return index_of(b)


def test_no_variable_of_the_callers_environment_reaches_a_worker(built, bundle):
    _, index = ok(built)
    b = edit(bundle(), "lesson.py", ".arrange(RIGHT, buff=0.5)  # L:z",
             '.arrange(RIGHT, buff=0.5).shift(RIGHT * (0.5 if __import__("os").environ.get("EXPLAINERS_TEST_PROBE") else 0))')
    assert build_with_probe(b)["cells"][0]["frames_sha"] == index["cells"][0]["frames_sha"]


def test_no_variable_of_the_callers_environment_reaches_pass_1(bundle):
    b = edit(bundle(), "lesson.py", "n_tokens = len(Z)\n",
             'n_tokens = len(Z)\nprobe = __import__("os").environ.get("EXPLAINERS_TEST_PROBE", "unset")\n')
    (b / "cells.md").write_text((b / "cells.md").read_text() + "\nProbe {probe}.\n")
    assert build_with_probe(b)["refs"]["probe"] == "unset"


def test_a_second_build_starts_pass_1_with_the_cache_warm(bundle):
    b = edit(bundle(), "lesson.py", "n_tokens = len(Z)\n",
             'n_tokens = len(Z)\nwarm = len(list(__import__("pathlib").Path(config.tex_dir).glob("*.svg")))\n')
    (b / "cells.md").write_text((b / "cells.md").read_text() + "\nWarm {warm}.\n")
    assert built_ok(b)["refs"]["warm"] == "0"
    (b / "lesson.py").write_text((b / "lesson.py").read_text() + "\n# so pass 1 runs\n")
    assert int(built_ok(b)["refs"]["warm"]) > 0


def test_a_changed_cache_id_starts_a_fresh_cache(bundle):
    b = bundle()
    stale = b / "build" / "cache" / "0000000000000000" / "tex"
    stale.mkdir(parents=True)
    (stale / "old.svg").write_text("<svg/>")
    (b / "build" / "cache" / ".DS_Store").write_text("")
    built_ok(b)
    caches = list((b / "build" / "cache").iterdir())
    assert len(caches) == 1 and caches[0].name != "0000000000000000" and any(caches[0].rglob("*.svg"))


def test_an_unused_cache_entry_is_pruned_and_a_used_one_kept(bundle):
    b = bundle()
    built_ok(b)
    tex = next((b / "build" / "cache").iterdir()) / "tex"
    used = {f.name for f in tex.glob("*.svg")}
    assert used
    (tex / "junk.svg").write_text("<svg/>")
    built_ok(edit(b, "lesson.py", "self.play(FadeOut(title), run_time=0.5)", "self.play(FadeOut(title), run_time=0.7)"))
    assert not (tex / "junk.svg").exists() and used <= {f.name for f in tex.glob("*.svg")}


def test_a_killed_build_during_pass_1_leaves_no_pass_1(bundle, tmp_path):
    b = bundle().resolve()
    marker = tmp_path / "in-pass-1"
    edit(b, "lesson.py", "n_tokens = len(Z)\n", f'n_tokens = len(Z)\nopen({str(marker)!r}, "w").close()\n__import__("time").sleep(60)\n')
    p = subprocess.Popen([str(REPO / "bin" / "explain-build"), str(b)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    deadline = time.time() + 60
    while not marker.exists():
        assert time.time() < deadline and p.poll() is None, "pass 1 never reached the lesson"
        time.sleep(0.05)
    found = lambda: [int(x) for x in subprocess.run(["pgrep", "-f", f"explainers.pass1 {b}"], capture_output=True, text=True).stdout.split()]
    alive = found()
    try:
        assert alive
        os.kill(psutil.Process(alive[0]).ppid(), signal.SIGKILL)
        deadline = time.time() + 3
        while found() and time.time() < deadline:
            time.sleep(0.1)
        assert not found()
    finally:
        kill_all(found())


def test_a_failed_worker_kills_its_siblings(bundle):
    """The first chunk sleeps until killed, and only the build's killpg can end it: its parent stays alive."""
    b = bundle().resolve()
    edit(b, "lesson.py", "self.play(Write(z), run_time=1.0)", "self.play(Write(z), run_time=60)")  # so k=2 cuts after it
    edit(b, "lesson.py", "    def construct(self):\n", "    def construct(self):\n"
         '        if not self.RECORDING:\n'
         '            raise RuntimeError("late chunk fails") if config.from_animation_number > 0 else __import__("time").sleep(3600)\n')
    try:
        # 120 s: far above a softmax build's few seconds, far below the sleep. Without the kill the build blocks in waitpid.
        r = subprocess.run([sys.executable, str(Path(__file__).parent / "build_with_width.py"), str(b), "2"],
                           capture_output=True, text=True, timeout=120)
    finally:
        kill_all(workers_of(b))
    assert r.returncode != 0 and "render failed:" in r.stderr and "late chunk fails" in r.stderr, r.stderr


@pytest.mark.parametrize("condition", ["not self.RECORDING", "self.RECORDING"], ids=["worker", "pass-1"])
def test_a_render_config_change_fails_the_build(bundle, condition):
    b = edit(bundle(), "lesson.py", "    def construct(self):\n",
             f'    def construct(self):\n        if {condition}:\n            config.pixel_format = "yuv444p"\n')
    r = explain_build(b)
    assert r.returncode == 1 and "render config changed outside config.py" in r.stderr, r.stderr


@pytest.mark.parametrize("condition, what", [("self.RECORDING", "pass 1"), ("not self.RECORDING", "render")], ids=["pass-1", "worker"])
def test_a_child_killed_by_a_signal_names_its_exit_code(bundle, condition, what):
    b = edit(bundle(), "lesson.py", "    def construct(self):\n",
             f'    def construct(self):\n        if {condition}:\n            __import__("os").kill(__import__("os").getpid(), 9)\n')
    r = explain_build(b)
    assert r.returncode == 1 and r.stderr.strip() == f"error: {what} failed: exit code -9", r.stderr


def test_a_killed_build_takes_a_workers_own_children_with_it(bundle):
    b = edit(bundle().resolve(), "lesson.py", "run_time=1.25", "run_time=60")
    command = f"/bin/sleep {10_000_000 + os.getpid()}"
    edit(b, "lesson.py", "    def construct(self):\n",
         f'    def construct(self):\n        if not self.RECORDING:\n            __import__("subprocess").Popen({command.split()!r})\n')

    def sleeps():
        return [int(p) for p in subprocess.run(["pgrep", "-f", command], capture_output=True, text=True).stdout.split()]

    p = subprocess.Popen([sys.executable, str(Path(__file__).parent / "build_with_width.py"), str(b), "1"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.time() + 60
        while not sleeps() and time.time() < deadline:
            time.sleep(0.1)
        assert sleeps(), "the worker did not start its child"
        p.kill()
        p.wait()
        deadline = time.time() + 10
        while sleeps() and time.time() < deadline:
            time.sleep(0.1)
        assert not sleeps()
    finally:
        p.kill()
        kill_all(sleeps() + workers_of(b))


def test_run_all_keeps_to_its_width(tmp_path):
    (tmp_path / "span.py").write_text("import pathlib, sys, time\nstart = time.time()\ntime.sleep(1)\n"
                                      "pathlib.Path(sys.argv[1]).write_text(f'{start} {time.time()}')\n")
    files = [tmp_path / f"{n}.span" for n in range(3)]
    # in its own process: run_all waits for any child, and a pytest worker may have others
    r = subprocess.run([sys.executable, "-c", "from pathlib import Path\nfrom explainers.children import Job, run_all\n"
                        f"t = Path({str(tmp_path)!r})\n"
                        "run_all([Job('span', [str(t / f'{n}.span')], t / str(n)) for n in range(3)], 1,"
                        " {'PATH': '/usr/bin', 'PYTHONPATH': str(t)})\n"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    spans = sorted(tuple(map(float, f.read_text().split())) for f in files)
    assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:])), spans


def line_of(b, text):
    source = (b / "lesson.py").read_text()
    return source[:source.index(text)].count("\n") + 1


def worker_direct(snapshot, cache, out, chunk):
    """{play: (digest, partial bytes)} of a real worker run on its own."""
    r = subprocess.run([sys.executable, "-P", "-m", "explainers.render", str(snapshot), str(cache), str(out), chunk], capture_output=True,
                       text=True, env={**os.environ, "EXPLAINERS_BUILD_PID": str(os.getpid()), "PYTHONHASHSEED": "0"}, start_new_session=True)
    assert r.returncode == 0, r.stderr
    plays = json.loads((out / "report.json").read_text())["plays"]
    return {p["anim"]: (p["digest"], Path(p["partial"]).read_bytes()) for p in plays}


def late_start_equals_one_chunk(b, first, last):
    r, out, snapshot = run_pass1(b)
    assert r.returncode == 0, r.stderr
    cache, work = out.parent / "cache", out.parent
    drawn = [d for c in json.loads((out / "records.json").read_text())["cells"] for d in c["drawn"]]
    late, whole = worker_direct(snapshot, cache, work / "late", f"{first}-{last}"), worker_direct(snapshot, cache, work / "whole", f"0-{last}")
    assert sorted(late) == list(range(first, last + 1))
    for n, (digest, partial) in late.items():
        assert digest == drawn[n] and (digest, partial) == whole[n], n


def test_a_chunk_starting_under_a_live_updater_equals_one_chunk(bundle):
    b = bundle("long.explainer")
    r, out, _ = run_pass1(b)
    assert r.returncode == 0, r.stderr
    cell = json.loads((out / "records.json").read_text())["cells"][5]  # the spinner turns from cell 0 to cell 9
    late_start_equals_one_chunk(b, cell["first_anim"], cell["first_anim"] + len(cell["run_times"]) - 1)


PROJECTED = """import numpy as np
from manim import *

from explainers import Lesson3D


class Projected(Lesson3D):
    def construct(self):
        self.set_camera_orientation(phi=60 * DEGREES, theta=30 * DEGREES)
        self.cell("one")
        self.play(FadeIn(Dot3D(RIGHT)), run_time=0.1)
        self.cell("two")
        label = Dot(self.camera.project_point(np.array([1.0, 1.0, 1.0])), color=RED)
        self.add_fixed_in_frame_mobjects(label)
        self.play(FadeIn(label), run_time=0.1)
"""


def test_a_chunk_in_a_3d_lesson_equals_one_chunk_with_a_live_updater(bundle):
    b = edit(bundle("geometry3d.explainer"), "lesson.py", '        self.cell("apart-in-the-world")\n',
             '        self.cell("apart-in-the-world")\n        self.add(Dot(RIGHT * -3).add_updater(lambda m, dt: m.shift(RIGHT * dt)))\n')
    late_start_equals_one_chunk(edit(b, "lesson.py", "        self.clear()\n", ""), 1, 1)


def test_a_chunk_in_a_3d_lesson_equals_one_chunk_reading_the_projection(bundle):
    b = bundle("geometry3d.explainer")
    (b / "lesson.py").write_text(PROJECTED)
    late_start_equals_one_chunk(b, 1, 1)


def nondeterministic(b, r, cell, anim, what):
    return r.returncode == 1 and r.stderr.strip() == (f"error: lesson.py:{line_of(b, cell)} cell {cell.split(chr(34))[1]}: animation {anim} {what}: "
                                                      "the lesson is nondeterministic. No clock reads, no sets of mobjects, no random draws outside construct.")


def test_a_clock_read_fails_as_nondeterministic(bundle):
    b = edit(bundle(), "lesson.py", '        self.cell("exp")\n',
             '        self.cell("exp")\n        self.add(Dot().to_corner(DL).shift(RIGHT * (__import__("time").time() % 1)))\n')
    r = explain_build(b)
    assert nondeterministic(b, r, 'self.cell("exp")', 1, "drew different frames in its worker than in pass 1"), r.stderr


@pytest.mark.parametrize("old, new, cell, anim", [
    ("        self.wait(0.1234)\n", "        self.wait(0.1234)\n        if self.RECORDING:\n            self.wait(0.1)\n", 'self.cell("top")', 8),
    ("    def construct(self):\n", '    def construct(self):\n        if not self.RECORDING:\n            __import__("sys").exit(0)\n', 'self.cell("scores")', 0),
], ids=["fewer-plays", "no-report"])
def test_a_lesson_running_differently_in_its_worker_fails_naming_the_cell(bundle, old, new, cell, anim):
    b = edit(bundle(), "lesson.py", old, new)
    r = explain_build(b)
    assert nondeterministic(b, r, cell, anim, "ran in only one of pass 1 and its worker"), r.stderr


def test_a_changed_encoder_setting_renders_every_cell(bundle, tmp_path):
    b = bundle()
    built_ok(b)
    r = explain_build(b, env=engine_copy(tmp_path, ("config.py", '"crf": "18"', '"crf": "20"')))
    assert r.returncode == 0, r.stderr
    assert re.search(r"render: 6 cells \(1–6\) in \d chunks? · 0 reused", r.stdout), r.stdout


WRONG_RATE = """    from fractions import Fraction
    from dataclasses import replace
    from manim.scene.video_segment_encoder import VideoSegmentEncoder
    writer = scene.renderer.file_writer
    writer._create_segment_encoder = lambda target: VideoSegmentEncoder(target=target, spec=replace(writer.video_encoder, frame_rate=Fraction(10)))
    scene.render()
"""


@pytest.mark.parametrize("edits, error", [
    ([("render.py", "    scene = cls()\n", '    config.pixel_format = "yuv444p"\n    scene = cls()\n'),
      ("render.py", "    check_render_config()\n", "")], "pix_fmt yuv444p ≠ yuv420p"),
    ([("render.py", "    scene.render()\n", WRONG_RATE)], "fps 10/1 ≠ 30"),
], ids=["pix-fmt", "wrong-rate"])
def test_a_clip_whose_stream_does_not_match_fails(bundle, tmp_path, edits, error):
    b = bundle()
    r = explain_build(b, env=engine_copy(tmp_path, *edits))
    assert r.returncode == 1 and f"""lesson.py:{line_of(b, 'self.cell("scores")')} cell scores: stream check failed: {error}""" in r.stderr, r.stderr


def test_a_short_play_before_another_passes_the_stream_check(bundle):
    """0.45 s then a second play: a join starts the second partial a few ticks early, so the average rate reads 81920/2729."""
    b = bundle()
    (b / "cells.md").write_text("## one\n\nText.\n")
    (b / "lesson.py").write_text("""from manim import *

from explainers import Lesson


class Short(Lesson):
    def construct(self):
        self.cell("one")
        s = Square(1.0)
        self.add(s)
        self.play(Transform(s, Circle(1.2).set_fill(BLUE, 0.7).shift(LEFT)), run_time=0.45)
        self.wait(0.5)
""")
    built_ok(b)


def test_a_join_that_loses_a_frame_fails_naming_the_cell(bundle, tmp_path):
    b = bundle()
    # the demuxer ends with an empty flush packet, so the last frame is second from the end
    r = explain_build(b, env=engine_copy(tmp_path, ("render.py", "for packet in src.demux(src.streams.video[0]):",
                                                    "for packet in list(src.demux(src.streams.video[0]))[:-2]:")))
    m = re.search(r"lesson\.py:\d+ cell scores: joined (\d+) frames, pass 1 wrote (\d+)", r.stderr)
    assert r.returncode == 1 and m and int(m[2]) - int(m[1]) == 1, r.stderr


@pytest.mark.parametrize("fixture", ["softmax", "frames", "long"])
def test_a_tee_on_every_fixture_matches_pass_1(bundle, fixture):
    r = subprocess.run([sys.executable, str(Path(__file__).parent / "build_with_width.py"), str(bundle(f"{fixture}.explainer")), "2"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr  # every digest is compared, so exit 0 is the proof


FADE_OUT, FIRST_WAIT = "self.play(FadeOut(v), run_time=0.3)\n", "self.wait(0.1)  # two waits per cell take the lesson past Manim's 100-file partial pruning limit\n"
LAST_WAIT = FIRST_WAIT + "            self.wait(0.1)\n"


def moved(field, value):
    return ((FADE_OUT, f"{FADE_OUT}            if k == 0:\n                saved = self.camera.{field}\n                self.camera.{field} = {value}\n"),
            (FIRST_WAIT, f"{FIRST_WAIT}            if k == 0:\n                self.camera.{field} = saved\n"))


INSIDE_A_PLAY = ((FADE_OUT, f'{FADE_OUT}            if k == 0:\n                saved = self.camera.frame_center\n                d = Dot().add_updater(lambda m, dt: setattr(self.camera, "frame_center", np.array([1.0, 0.0, 0.0])))\n                self.add(d)\n'),
                 (FIRST_WAIT, f"{FIRST_WAIT}            if k == 0:\n                self.remove(d)\n                self.camera.frame_center = saved\n"))
AFTER_THE_LAST_PLAY = ((LAST_WAIT, f"{LAST_WAIT}            if k == N - 1:\n                self.camera.frame_center = np.array([1.0, 0.0, 0.0])\n"),)


@pytest.mark.parametrize("edits, cell", [
    (moved("frame_center", "np.array([1.0, 0.0, 0.0])"), "step-00"), (moved("frame_width", "15.0"), "step-00"), (moved("frame_height", "7.0"), "step-00"),
    (moved("pixel_width", "1080"), "step-00"), (moved("pixel_height", "540"), "step-00"), (INSIDE_A_PLAY, "step-00"), (AFTER_THE_LAST_PLAY, "step-29"),
], ids=["frame_center", "frame_width", "frame_height", "pixel_width", "pixel_height", "inside-a-play", "after-the-last-play"])
def test_a_camera_moved_inside_a_cell_is_an_error(bundle, edits, cell):
    b = bundle("long.explainer")
    for old, new in edits:
        edit(b, "lesson.py", old, new)
    r = explain_build(b)
    line = line_of(b, 'self.cell(f"step-')
    assert r.returncode == 1 and r.stderr.strip() == f'error: the camera moved in cell "{cell}" (lesson.py:{line}); the camera is static: set it before the first self.cell()', r.stderr


def test_a_lesson_reading_the_cameras_pixels_is_an_error(bundle):
    line = "self.camera.get_image()\n"
    b = edit(bundle(), "lesson.py", "        self.play(Write(z), run_time=1.0)\n", f"        self.play(Write(z), run_time=1.0)\n        {line}")
    r = explain_build(b)
    assert r.returncode == 1 and r.stderr.strip() == f"error: a lesson may not read the camera's pixels (lesson.py:{line_of(b, line)})", r.stderr


def test_measured_times_are_recorded_and_kept(bundle):
    b = edit(bundle("long.explainer"), "lesson.py", "                self.play(FadeIn(row), FadeIn(spinner), run_time=1.0)\n",
             "                self.play(FadeIn(row), FadeIn(spinner), run_time=1.0)\n"
             '                __import__("time").sleep(2)\n'
             '                known = Dot().add_updater(lambda m, dt: __import__("time").sleep(0.05))\n'
             "                self.add(known)\n"
             "                self.wait(1.0)  # 30 frames at 0.05 s each\n"
             "                self.remove(known)\n")
    width = str(Path(__file__).parent / "build_with_width.py")
    started = time.monotonic()
    r = subprocess.run([sys.executable, width, str(b), "2"], capture_output=True, text=True)
    wall = time.monotonic() - started
    assert r.returncode == 0, r.stderr
    index = index_of(b)
    (_, first), (_, later) = sorted(index["fast_forward_s"])
    assert first < 2 <= later
    times = [c["render_s"] for c in index["cells"]]
    assert [len(t) for t in times] == [6] + [4] * 8 + [5] + [4] * 20
    assert times[0][1] >= 1.5 and sum(map(sum, times)) <= 2 * wall
    edit(b, "lesson.py", ".shift(RIGHT * jitter[k])", ".shift(RIGHT * (jitter[k] + 0.1 * (k == 20)))")
    r = subprocess.run([sys.executable, width, str(b), "1"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    edited = index_of(b)
    assert [c["render_s"] for n, c in enumerate(edited["cells"]) if n != 20] == times[:20] + times[21:]
    assert edited["cells"][20]["render_s"] != times[20]
    before = (b / "build" / "index.json").read_text()
    built_ok(b)
    assert (b / "build" / "index.json").read_text() == before


def test_a_rebuild_with_nothing_to_render_samples_nothing(bundle):
    b = bundle()
    first = explain_build(b)
    assert first.returncode == 0 and "machine: phase=render" in first.stdout, first.stderr
    assert re.search(r"^machine: .* jobs=8$", first.stdout, re.M), first.stdout  # softmax: 8 plays in 6 cells
    again = explain_build(b)
    assert again.returncode == 0 and "machine:" not in again.stdout and "render width:" not in again.stdout, again.stdout


def test_workers_overrides_the_width(bundle):
    b = bundle()
    r = explain_build(b, "--workers", "1")
    assert r.returncode == 0 and "render width: 1 (--workers)" in r.stdout and "in 1 chunk ·" in r.stdout, r.stdout + r.stderr
    assert explain_build(b, "--workers", "0").returncode == 2


def test_more_runs_than_the_width_still_run_one_at_a_time(bundle, tmp_path):
    b = bundle()
    built_ok(b)
    stamps = tmp_path / "stamps"
    edit(b, "lesson.py", "self.play(FadeIn(title), run_time=0.5)", "self.play(FadeIn(title), run_time=0.6)")  # cell 2
    edit(b, "lesson.py", "self.play(FadeOut(title), run_time=0.5)", "self.play(FadeOut(title), run_time=0.7)")  # cell 5
    edit(b, "lesson.py", "    def construct(self):\n", "    def construct(self):\n        if not self.RECORDING:\n"
         f'            start = __import__("time").time()\n            __import__("time").sleep(2)\n'
         f'            open({str(stamps)!r}, "a").write(f"{{start}} {{__import__(\'time\').time()}}\\n")\n')
    r = explain_build(b, "--workers", "1")
    assert r.returncode == 0 and "in 2 chunks" in r.stdout, r.stdout + r.stderr
    spans = sorted(tuple(map(float, l.split())) for l in stamps.read_text().splitlines())
    assert len(spans) == 2 and spans[0][1] <= spans[1][0], spans


def test_one_long_cell_runs_as_several_chunks(tmp_path):
    def one_cell(name):
        d = tmp_path / name
        shutil.copytree(FIXTURES / "long.explainer", d, ignore=shutil.ignore_patterns("build"))
        edit(d, "lesson.py", '            self.cell(f"step-{k:02d}")\n', '            if k == 0:\n                self.cell("all")\n')
        (d / "cells.md").write_text("## all\n\nText.\n")
        return d

    width = str(Path(__file__).parent / "build_with_width.py")
    outs = [subprocess.run([sys.executable, width, str(one_cell(f"w{w}")), str(w)], capture_output=True, text=True) for w in (1, 4)]
    assert all(r.returncode == 0 for r in outs), outs[0].stderr + outs[1].stderr
    one, many = (json.loads(r.stdout.splitlines()[-1]) for r in outs)
    assert len(one["chunks"]) == 1 and len(many["chunks"]) > 1
    assert one["shas"] == many["shas"]


def test_an_edit_to_two_distant_cells_gives_the_clips_of_a_cold_build(bundle, tmp_path):
    def edited(b):
        return edit(b, "lesson.py", ".shift(RIGHT * jitter[k])", ".shift(RIGHT * (jitter[k] + 0.1 * (k in (5, 20))))")

    b = bundle("long.explainer")
    built_ok(b)
    shas = [c["frames_sha"] for c in built_ok(edited(b))["cells"]]
    cold = tmp_path / "cold.explainer"
    shutil.copytree(FIXTURES / "long.explainer", cold, ignore=shutil.ignore_patterns("build"))
    assert shas == [c["frames_sha"] for c in built_ok(edited(cold))["cells"]]


def test_progress_lines_are_monotonic(bundle):
    r = explain_build(bundle("long.explainer"), "--workers", "2")
    assert r.returncode == 0, r.stderr
    seen = [(int(a), int(b)) for a, b in re.findall(r"^render: (\d+)/(\d+) animations$", r.stdout, re.M)]
    assert seen and all(total == 122 and n <= total for n, total in seen)
    assert all(a[0] < b[0] for a, b in zip(seen, seen[1:]))


def test_a_worker_too_big_for_the_machine_is_refused_and_workers_overrides_it(bundle):
    b = bundle()
    built_ok(b)
    index = index_of(b)
    index["worker_peak"]["rss"] = 2**60
    (b / "build" / "index.json").write_text(json.dumps(index, indent=1) + "\n")
    edit(b, "lesson.py", "self.play(FadeOut(title), run_time=0.5)", "self.play(FadeOut(title), run_time=0.7)")
    r = explain_build(b)
    assert r.returncode == 1 and r.stderr.strip().splitlines()[-1].startswith("error: one render job needs"), r.stderr
    assert "pass --workers 1" in r.stderr
    built_ok(b, args=("--workers", "1"))


def test_run_all_measures_a_jobs_peaks(tmp_path):
    (tmp_path / "heavy.py").write_text("import time\nblock = bytearray(200 * 2**20)\nfor i in range(0, len(block), 4096):\n    block[i] = 1\n"
                                       "end = time.time() + 1\nwhile time.time() < end:\n    pass\n")
    (tmp_path / "idle.py").write_text("import time\ntime.sleep(1)\n")
    # in its own process: run_all waits for any child, and a pytest worker may have others
    r = subprocess.run([sys.executable, "-c", "from pathlib import Path\nfrom explainers.children import Job, run_all\n"
                        f"t = Path({str(tmp_path)!r})\n"
                        "for m in ('heavy', 'idle'):\n"
                        "    d = run_all([Job(m, [], t / (m + '.out'))], 1, {'PATH': '/usr/bin', 'PYTHONPATH': str(t)})[0]\n"
                        "    print(m, d.rss, d.cores)\n"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    peaks = {m: (int(rss), float(cores)) for m, rss, cores in (l.split() for l in r.stdout.splitlines())}
    assert peaks["heavy"][0] >= 200 * 2**20 and peaks["heavy"][1] >= 0.5
    assert peaks["idle"][0] < 200 * 2**20 and peaks["idle"][1] < 0.5


def test_times_from_the_previous_build_shape_the_cuts():
    cell = lambda slug, first, runs: SimpleNamespace(slug=slug, first_anim=first, run_times=runs)
    rec = {"cost": [0.0, 1.0, 2.0, 3.0], "cells": [cell("kept", 0, [1.0, 1.0]), cell("changed", 2, [2.0, 1.0])]}
    previous = {"fast_forward_s": [[0, 0.5], [2, 4.0], [99, 7.0]],  # play 0 costs nothing in the table; play 99 is gone
                "cells": [{"slug": "kept", "render_s": [5.0, 6.0]}, {"slug": "changed", "render_s": [9.0]}]}
    forward, work = costs(rec, previous)
    assert forward == {0: 0.0, 1: 1.0, 2: 2.0, 3: 3.0}  # the table's 2.0 took 4.0, so the ratio is 2; charged at half weight
    assert work == {0: 5.0, 1: 6.0, 2: 2 * SEED_S_PER_VIDEO_S, 3: SEED_S_PER_VIDEO_S}
    assert costs(rec, {"cells": []})[0] == {0: 0.0, 1: 0.5, 2: 1.0, 3: 1.5}  # a first build: the table, at half weight


def test_a_second_build_is_refused_while_a_killed_builds_worker_lives(bundle):
    b = bundle().resolve()
    src = b / "lesson.py"
    original = src.read_text()
    src.write_text(original.replace("run_time=1.25", "run_time=60"))
    p = subprocess.Popen([str(REPO / "bin" / "explain-build"), str(b)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    deadline = time.time() + 60
    while not list((b / "build").glob(".media/*/**/uncached_*.mp4")) and time.time() < deadline:
        time.sleep(0.1)
    assert time.time() < deadline, "no partial appeared"
    workers = workers_of(b)
    assert workers
    stopped = []
    try:
        parent = parent_of(workers)
        for w in workers:
            try:
                os.kill(w, signal.SIGSTOP)
                stopped.append(w)
            except ProcessLookupError:
                pass  # a chunk that had already finished
        os.kill(parent, signal.SIGKILL)
        r = explain_build(b)
        assert r.returncode == 3 and r.stderr.strip() == f"error: another explain-build is running on {b}", r.stderr
    finally:
        for w in stopped:
            try:
                os.kill(w, signal.SIGCONT)
            except ProcessLookupError:
                pass
    deadline = time.time() + 10
    while workers_of(b) and time.time() < deadline:
        time.sleep(0.1)
    src.write_text(original.replace("run_time=1.25", "run_time=1.5"))
    built_ok(b)


def test_a_dangling_link_in_the_bundle_does_not_stop_the_build(bundle):
    b = bundle()
    (b / ".#lesson.py").symlink_to("editor@1234")  # what Emacs leaves while a buffer has unsaved changes
    built_ok(b)


def test_a_relative_link_in_the_bundle_is_in_the_snapshot(bundle, tmp_path):
    b = edit(bundle(), "lesson.py", "n_tokens = len(Z)\n", 'n_tokens = len(Z)\nopen("alias.csv").read()\n')
    (b / "alias.csv").symlink_to("scores.csv")
    assert "alias.csv" in built_ok(b, cwd=tmp_path)["inputs"]["bundle"]


def test_a_stale_build_is_not_in_the_snapshot(bundle):
    b = edit(bundle(), "lesson.py", "n_tokens = len(Z)\n", 'n_tokens = len(Z)\nnames = sorted(__import__("os").listdir("."))\n')
    (b / "cells.md").write_text((b / "cells.md").read_text() + "\nNames {names}.\n")
    (b / "comments.json").write_text("{}")
    built_ok(b)
    names = built_ok(b)["refs"]["names"]
    assert "helpers.py" in names and "build" not in names and "comments.json" not in names


def test_worker_peak_is_measured_and_kept(bundle):
    b = bundle()
    peak = built_ok(b)["worker_peak"]
    assert peak["rss"] > 0 and peak["cores"] > 0
    assert built_ok(b)["worker_peak"] == peak  # a rebuild that renders nothing keeps the last measurement


def test_importing_the_build_does_not_import_manim():
    r = subprocess.run([sys.executable, "-P", "-c", "import explainers.build, explainers.config, sys; assert 'manim' not in sys.modules"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
