"""explain-build as a person runs it: this checkout's command, from any directory, with TeX not on PATH."""
import hashlib
import subprocess
import sys

import pytest

from conftest import REPO, explain_build

pytestmark = pytest.mark.xdist_group("render")  # builds that render run one at a time


def test_report_from_outside_the_repo_without_tex_on_path(bundle, tmp_path):
    b = bundle()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    r = explain_build(b, cwd=cwd)
    assert r.returncode == 0, r.stderr
    assert list(cwd.iterdir()) == []  # a build writes nowhere but the bundle's build/
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()[:12]
    lines = r.stdout.splitlines()
    assert lines[0] == f"softmax.explainer · 6 cells · lesson {sha(b / 'lesson.py')}"
    assert lines[2] == "   2  exp     2 animations   0.75 s   (lesson.py:19)"
    assert lines[7:9] == ["refs:   n_tokens = 6", "refs:   p_top:.4f = 0.5456"]
    assert lines[6] == "   6  top     2 animations   0.62 s   (lesson.py:33)"
    assert lines[9] == (f"inputs: bundle/helpers.py {sha(b / 'helpers.py')}; bundle/scores.csv {sha(b / 'scores.csv')}; "
                        f"repo/explainers/lesson.py {sha(REPO / 'explainers/lesson.py')}; manim 0.22.0")


def test_renamed_heading(bundle):
    b = bundle()
    md = b / "cells.md"
    md.write_text(md.read_text().replace("## sum\n", "## total\n"))
    r = explain_build(b)
    assert r.returncode == 1
    assert r.stderr.splitlines() == [
        'error: cells.md has "## total" (cells.md:7) but lesson.py has no self.cell("total")',
        'error: lesson.py has self.cell("sum") (lesson.py:23) but cells.md has no "## sum"']


def test_unknown_ref_counts_but_a_ref_in_code_does_not(bundle):
    b = bundle()
    md = b / "cells.md"
    md.write_text(md.read_text() + "Also {nope} but not `{also_nope}`.\n")
    r = explain_build(b)
    assert r.returncode == 1 and r.stderr.splitlines() == ["error: unknown ref {nope} (cells.md:18)"]


def test_bad_format(bundle):
    b = bundle()
    md = b / "cells.md"
    md.write_text(md.read_text() + "Bad {n_tokens:.2q}.\n")
    r = explain_build(b)
    assert r.returncode == 1
    assert r.stderr.splitlines() == ["error: bad format {n_tokens:.2q} (cells.md:18): Unknown format code 'q' for object of type 'int'"]


def test_animation_before_first_cell(bundle):
    b = bundle()
    src = b / "lesson.py"
    src.write_text(src.read_text().replace('        self.cell("scores")\n', '        self.wait(0.1)\n        self.cell("scores")\n'))
    r = explain_build(b)
    assert r.returncode == 1 and r.stderr.strip() == "error: animation before the first self.cell() (lesson.py:16)"


def test_text_before_first_heading(bundle):
    b = bundle()
    md = b / "cells.md"
    md.write_text("stray intro\n\n" + md.read_text())
    r = explain_build(b)
    assert r.returncode == 1 and r.stderr.strip() == "error: cells.md has text before the first heading (cells.md:1)"


def test_second_build_on_the_same_bundle_is_refused(bundle):
    b = bundle()
    (b / "build").mkdir()
    holder = subprocess.Popen([sys.executable, "-c", f"import fcntl,time;f=open('{b}/build/.lock','w');"
                               "fcntl.flock(f,fcntl.LOCK_EX);print('held',flush=True);time.sleep(60)"],
                              stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "held"
        r = explain_build(b)
        assert r.returncode == 3 and r.stderr.strip() == f"error: another explain-build is running on {b}"
    finally:
        holder.kill()


def test_missing_files(tmp_path):
    r = explain_build(tmp_path)
    assert r.returncode == 2 and r.stderr.splitlines() == [f"error: missing {tmp_path}/lesson.py",
                                                            f"error: missing {tmp_path}/cells.md"]


def test_no_cell_at_all(bundle):
    b = bundle()
    (b / "lesson.py").write_text("from manim import Dot\nfrom explainers import Lesson\n\n\nclass Empty(Lesson):\n"
                                 "    def construct(self):\n        self.add(Dot())\n")
    (b / "cells.md").write_text("## only\nx\n")
    r = explain_build(b)
    assert r.returncode == 1 and r.stderr.strip() == "error: no self.cell() in the lesson"


def test_exactly_one_lesson_class_counting_only_lesson_py(bundle):
    b = bundle()
    (b / "helpers.py").write_text((b / "helpers.py").read_text() + "\nfrom explainers import Lesson\nclass Helper(Lesson):\n    pass\n")
    src = b / "lesson.py"
    src.write_text(src.read_text().replace("from helpers import P, Z", "from helpers import *"))
    assert explain_build(b).returncode == 0  # a Lesson subclass imported from a helper is not the lesson
    src.write_text(src.read_text() + "\n\nclass Second(Lesson):\n    pass\n")
    r = explain_build(b)
    assert r.returncode == 1 and r.stderr.strip() == "error: lesson.py must define exactly one Lesson subclass; found ['Softmax', 'Second']"
