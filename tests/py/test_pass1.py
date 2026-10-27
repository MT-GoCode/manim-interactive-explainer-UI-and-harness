"""Pass 1 records what later strata need: boundaries, exact run times, creation lines, units, font sizes, inputs."""
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import FIXTURES, REPO

SRC = (FIXTURES / "softmax.explainer" / "lesson.py").read_text().splitlines()
LINE = {m[1]: i for i, l in enumerate(SRC, 1) if (m := re.search(r"# L:([\w-]+)", l))}


def run_pass1(bundle: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(Path(__file__).parent / "pass1_records.py"), str(bundle)],
                          capture_output=True, text=True)


def records(bundle: Path) -> dict:
    r = run_pass1(bundle)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    dst = tmp_path_factory.mktemp("p1") / "softmax.explainer"
    shutil.copytree(FIXTURES / "softmax.explainer", dst, ignore=shutil.ignore_patterns("build"))
    return dst, run_pass1(dst)


def ok(built) -> dict:
    """Called first in each test (not in a fixture), so a crashing build is a test failure, not a fixture error."""
    bundle, r = built
    assert r.returncode == 0, r.stderr
    return {**json.loads(r.stdout), "bundle": bundle}


def units(rec, i):
    return {(u["kind"], u["line"]) for u in rec["cells"][i]["end"]}


def test_cells_and_exact_run_times(built):
    rec = ok(built)
    assert [c["slug"] for c in rec["cells"]] == ["scores", "exp", "sum", "divide", "probs", "top"]
    # 0.1234 s is not a whole number of frames: a real render (not a dry run) would quantize it.
    assert [c["run_times"] for c in rec["cells"]] == [[1.0], [0.5, 0.25], [0.75], [1.25], [0.5], [0.5, 0.1234]]
    assert [c["first_anim"] for c in rec["cells"]] == [0, 1, 3, 4, 5, 6]


def test_end_state_kinds_and_creation_lines(built):
    rec = ok(built)
    # title is made inside a lesson.py helper: its line is the helper's (the innermost lesson.py frame).
    assert units(rec, 1) == {("DecimalNumber", LINE["z"]), ("Text", LINE["label-helper"])}
    # frac replaced a copy of s (ReplacementTransform); twin is a copy of note made on its own line.
    assert units(rec, 5) == {("DecimalNumber", LINE["z"]), ("MathTex", LINE["sum"]), ("MathTex", LINE["frac"]),
                             ("Text", LINE["note"]), ("SurroundingRectangle", LINE["box"]), ("Text", LINE["twin"]),
                             ("Matrix", LINE["matrix"])}


def test_plain_group_is_opened_into_its_numbers(built):
    rec = ok(built)
    assert [u["kind"] for u in rec["cells"][0]["end"]] == ["DecimalNumber"] * 6


def test_font_sizes_follow_scale_and_class_for_text_latex_and_text_inside_containers(built):
    rec = ok(built)
    size = {u["line"]: (u["text_size"], u["latex_size"]) for u in rec["cells"][5]["end"]}
    assert size[LINE["note"]] == (pytest.approx(64 * 0.75), None)
    assert size[LINE["sum"]] == (None, pytest.approx(48))
    assert size[LINE["matrix"]] == (None, pytest.approx(48 * 0.9))   # its entries, not the stretched brackets
    assert size[LINE["box"]] == (None, None)


def test_faded_out_object_is_gone_at_cell_end(built):
    rec = ok(built)
    assert all(u["line"] != LINE["label-helper"] for u in rec["cells"][4]["end"])


def test_inputs_are_the_files_the_lesson_used(built):
    rec = ok(built)
    b = FIXTURES / "softmax.explainer"
    assert rec["inputs"]["bundle"] == {n: hashlib.sha256((b / n).read_bytes()).hexdigest()
                                      for n in ("helpers.py", "scores.csv")}
    assert set(rec["inputs"]["repo"]) == {"explainers/lesson.py"}
    assert rec["repo_root"] == str(REPO)


def test_nothing_written_into_the_bundle_but_build(built):
    rec = ok(built)
    assert sorted(p.name for p in rec["bundle"].iterdir()) == ["build", "cells.md", "helpers.py", "lesson.py",
                                                                 "scores.csv"]


def test_stale_bytecode_in_the_bundle_is_not_an_input(bundle):
    b = bundle()
    subprocess.run([sys.executable, "-c", "import helpers"], cwd=b, check=True)  # leaves __pycache__/helpers.*.pyc
    assert any((b / "__pycache__").iterdir())
    assert set(records(b)["inputs"]["bundle"]) == {"helpers.py", "scores.csv"}


def test_object_made_at_helper_import_time_reports_the_import_line(bundle):
    b = bundle()
    (b / "helpers.py").write_text((b / "helpers.py").read_text() + "\nfrom manim import Dot\nSPOT = Dot([-6.5, -3.5, 0])\n")
    src = b / "lesson.py"
    src.write_text(src.read_text().replace("from helpers import P, Z", "from helpers import P, SPOT, Z")
                   .replace("        self.play(Write(z), run_time=1.0)", "        self.add(SPOT)\n        self.play(Write(z), run_time=1.0)"))
    first = records(b)["cells"][0]["end"]
    assert ("Dot", LINE["import-helpers"]) in {(u["kind"], u["line"]) for u in first}
