"""Pass 1's guard through explain-build: a lesson reads only its own bundle and starts no program, and each refusal names
its lesson line. Plus what pass 1 records beside the frames: its inputs, and the cost of reaching each play."""
import re
import tempfile
from os.path import realpath
from types import SimpleNamespace

import pytest

from conftest import REPO, explain_build, records, run_pass1
from explainers.pass1 import install_cost_clock

pytestmark = pytest.mark.xdist_group("render")  # builds that render run one at a time
ANCHOR = '        self.cell("scores")\n'
OUTSIDE = "read {}, outside the bundle; copy it into the bundle and read it from there"
NO_PROGRAM = "started {}; a lesson may not start other programs"
NETWORK = "reached the network; a lesson reads only its own bundle"
LESSON_ERROR = 'raise __import__("explainers").LessonError'


def add(b, *lines):
    """The lines added at the top of the first cell. Returns the lesson line of the first."""
    src = b / "lesson.py"
    text = src.read_text()
    src.write_text(text.replace(ANCHOR, ANCHOR + "".join(f"        {line}\n" for line in lines)))
    return text[:text.index(ANCHOR) + len(ANCHOR)].count("\n") + 1


def refused(b):
    r = explain_build(b)
    assert r.returncode == 1, r.stdout + r.stderr
    assert not (b / "build" / ".media").exists()
    return r.stderr.strip().splitlines()


@pytest.mark.parametrize("code, violation", [
    (f"open({str(REPO / 'pyproject.toml')!r}).read()", OUTSIDE.format(REPO / "pyproject.toml")),
    ('__import__("subprocess").run(["/bin/echo", "hi"])', NO_PROGRAM.format("/bin/echo")),
    ('__import__("os").system("true")', NO_PROGRAM.format("os.system")),
    ('__import__("os").posix_spawn("/bin/echo", ["/bin/echo"], {})', NO_PROGRAM.format("/bin/echo")),
    ('__import__("os").listdir(__import__("tempfile").gettempdir())', OUTSIDE.format(realpath(tempfile.gettempdir()))),
    ('__import__("os").chdir(__import__("tempfile").gettempdir()); __import__("os").listdir()', OUTSIDE.format(realpath(tempfile.gettempdir()))),
    ('__import__("socket").getaddrinfo("localhost", 9)', NETWORK),
    ('__import__("socket").socket().connect(("127.0.0.1", 9))', NETWORK),
    ('__import__("os").fork()', NO_PROGRAM.format("os.fork")),
    ('__import__("os").execv("/bin/echo", ["/bin/echo"])', NO_PROGRAM.format("/bin/echo")),
    (f'__import__("os").listdir({str(REPO / "tests")!r})', OUTSIDE.format(realpath(REPO / "tests"))),
    ('next(__import__("os").walk(__import__("tempfile").gettempdir()))', OUTSIDE.format(realpath(tempfile.gettempdir()))),
], ids=["read-in-the-repo", "subprocess", "shell", "posix-spawn", "listing", "bare-listing", "network-lookup", "network-connect", "fork", "exec",
        "listing-under-a-path-entry", "walk"])
def test_a_refusal_names_its_lesson_line(bundle, code, violation):
    b = bundle()
    line = add(b, code)
    assert refused(b) == [f"error: lesson.py:{line} {violation}"]


def test_a_read_outside_the_bundle_fails_at_its_line(bundle, tmp_path):
    outside = tmp_path / "elsewhere.txt"
    outside.write_text("x")
    b = bundle()
    line = add(b, f"open({str(outside)!r}).read()")
    assert refused(b) == [f"error: lesson.py:{line} {OUTSIDE.format(realpath(outside))}"]


@pytest.mark.parametrize("code", [
    '__import__("multiprocessing").get_context("spawn").Process(target=print).start()',
    '__import__("multiprocessing.util").util.spawnv_passfds(__import__("sys").executable, [__import__("sys").executable, "-c", "pass"], ())',
    '__import__("multiprocessing.util").util.spawnv_passfds(__import__("sys").executable, [__import__("sys").executable, "-c", "from multiprocessing.resource_tracker import main;print()"], ())',
], ids=["spawn-context", "named-like-the-tracker", "starts-like-the-tracker"])
def test_a_python_child_fails_at_its_line(bundle, code):
    """Manim's own resource tracker is allowed by its exact command, and no other python child is."""
    b = bundle()
    line = add(b, code)
    out = refused(b)
    assert len(out) == 1 and re.fullmatch(rf"error: lesson\.py:{line} started \S*python\S*; a lesson may not start other programs", out[0]), out


def test_a_temporary_file_is_allowed(bundle):
    b = bundle()
    add(b, '__import__("tempfile").NamedTemporaryFile().close()')
    r = explain_build(b)
    assert r.returncode == 0, r.stderr


def caught_read(path):
    return "try:", f"    open({str(path)!r}).read()", "except PermissionError:", "    pass"


def test_a_caught_violation_still_fails(bundle, tmp_path):
    outside = tmp_path / "elsewhere.txt"
    outside.write_text("x")
    b = bundle()
    line = add(b, *caught_read(outside))
    assert refused(b) == [f"error: lesson.py:{line + 1} {OUTSIDE.format(realpath(outside))}"]


def test_a_violation_routes_before_a_lesson_error(bundle, tmp_path):
    outside = tmp_path / "elsewhere.txt"
    outside.write_text("x")
    b = bundle()
    line = add(b, *caught_read(outside), f'{LESSON_ERROR}("other")')
    assert refused(b) == [f"error: lesson.py:{line + 1} {OUTSIDE.format(realpath(outside))}"]


def test_a_violation_routes_before_a_lesson_exit(bundle, tmp_path):
    outside = tmp_path / "elsewhere.txt"
    outside.write_text("x")
    b = bundle()
    line = add(b, *caught_read(outside), '__import__("sys").exit(0)')
    assert refused(b) == [f"error: lesson.py:{line + 1} {OUTSIDE.format(realpath(outside))}"]


def test_a_lesson_printing_to_stderr_shows_only_its_error(bundle):
    b = bundle()
    add(b, 'print("noise", file=__import__("sys").stderr)', f'{LESSON_ERROR}("only this")')
    assert refused(b) == ["error: only this"]


def test_a_lesson_that_crashes_shows_its_own_error_and_line(bundle):
    """The path in the traceback is the build's deleted snapshot; its line number is the lesson's."""
    b = bundle()
    line = add(b, 'raise RuntimeError("boom")')
    err = "\n".join(refused(b))
    assert "error: pass 1 failed: exit code 1" in err and "RuntimeError: boom" in err and f'lesson.py", line {line}' in err, err


def test_a_lesson_that_exits_is_named_as_the_cause(bundle):
    b = bundle()
    add(b, '__import__("sys").exit(0)')
    assert refused(b) == ["error: pass 1 exited with no result: a lesson must not end its own process"]


def test_a_stat_and_a_listing_are_inputs(bundle):
    b = bundle()
    for name in ("statted.txt", "lstatted.txt", "accessed.txt"):
        (b / name).write_text("x")
    (b / "listed").mkdir()
    add(b, '__import__("os").stat("statted.txt")', '__import__("os").lstat("lstatted.txt")', '__import__("os").access("accessed.txt", 0)',
        '__import__("os").listdir("listed")')
    assert {"statted.txt", "lstatted.txt", "accessed.txt", "listed/"} <= set(records(b)["inputs"])


def test_a_file_the_lesson_only_writes_is_not_an_input(bundle):
    b = bundle()
    add(b, 'open("scratch.txt", "w").close()')
    assert "scratch.txt" not in records(b)["inputs"]


def test_an_svg_in_the_bundle_passes_the_guard(bundle):
    """Manim writes a temporary copy beside the source file while it parses an SVG."""
    b = bundle()
    (b / "diagram.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10"/></svg>')
    add(b, 'SVGMobject("diagram.svg")')
    assert "diagram.svg" in records(b)["inputs"]


def test_a_numpy_run_time_is_recorded(bundle):
    b = bundle()
    src = b / "lesson.py"
    src.write_text(src.read_text().replace("run_time=1.25", 'run_time=__import__("numpy").arange(3)[2]'))
    assert any(2.0 in c["run_times"] for c in records(b)["cells"])


def test_pass_1_draws_nothing(bundle):
    r, out, _ = run_pass1(bundle())
    assert r.returncode == 0, r.stderr
    assert not list(out.rglob("*.mp4"))


def test_pass_1_writes_no_bytecode_into_its_snapshot(bundle):
    r, _, snapshot = run_pass1(bundle())
    assert r.returncode == 0, r.stderr
    assert not list(snapshot.rglob("__pycache__"))


def test_the_inputs_are_what_the_lesson_read(bundle):
    inputs = records(bundle())["inputs"]
    assert {"lesson.py", "helpers.py", "scores.csv"} <= set(inputs) and "cells.md" not in inputs


def test_the_cost_clock_subtracts_what_fast_forward_suppresses():
    now = [0.0]

    def clock():
        return now[0]

    def suppressed_call(*_):
        now[0] += 2

    def play():
        now[0] += 1
        scene.camera.capture_mobjects()
        scene.camera.reset()
        scene.camera.set_frame_to_background()
        scene.renderer.get_frame()
        scene.renderer.file_writer.write_frame()

    scene = SimpleNamespace(
        camera=SimpleNamespace(capture_mobjects=suppressed_call, reset=suppressed_call, set_frame_to_background=suppressed_call),
        renderer=SimpleNamespace(get_frame=suppressed_call, file_writer=SimpleNamespace(write_frame=suppressed_call)),
        play=play)
    cost = install_cost_clock(scene, clock)
    scene.play()
    scene.play()
    scene.play()
    assert cost == [0, 1, 2]  # one second of lesson code per play; the two seconds of each suppressed call do not count


def test_the_cost_table_has_one_entry_per_play(bundle):
    cost = records(bundle())["cost"]
    assert len(cost) == 8 and cost == sorted(cost)
