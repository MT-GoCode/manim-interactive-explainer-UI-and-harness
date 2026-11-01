"""Pass 1 runs again exactly when something it read changed, or the engine, a library, the cache or the set of refs; otherwise its stored
records are reused, and the build's clips equal a cold build's. Vendored from presenters' test_pass1_reuse and test_pass1_key, adapted."""
import json
import os
import shutil

import pytest

from conftest import FIXTURES, engine_copy, explain_build
from explainers import build as B
from explainers import fingerprint as F

pytestmark = pytest.mark.xdist_group("render")  # builds that render run one at a time


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    b = tmp_path_factory.mktemp("first") / "softmax.explainer"
    shutil.copytree(FIXTURES / "softmax.explainer", b)
    r = explain_build(b)
    assert r.returncode == 0 and "pass 1: ran" in r.stdout, r.stdout + r.stderr
    return b


@pytest.fixture
def b(built, tmp_path):
    dst = tmp_path / "softmax.explainer"
    shutil.copytree(built, dst)
    return dst


def pass1(b, env=None):
    r = explain_build(b, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    return next(l for l in r.stdout.splitlines() if l.startswith("pass 1: "))


def append(b, name, text="\n"):
    (b / name).write_text((b / name).read_text() + text)


def shas(b):
    return [c["frames_sha"] for c in json.loads((b / "build" / "index.json").read_text())["cells"]]


def test_a_rebuild_runs_no_pass_1(b):
    assert pass1(b) == "pass 1: reused"


def test_a_prose_edit_runs_no_pass_1(b):
    """A new line above every ref moves each ref's line, and the set of refs stays."""
    text = (b / "cells.md").read_text()
    first = text.index("\n") + 1
    (b / "cells.md").write_text(text[:first] + "\nA new line of prose.\n" + text[first:])
    assert pass1(b) == "pass 1: reused"


def test_a_heading_edit_is_paired_fresh(b):
    (b / "cells.md").write_text((b / "cells.md").read_text().replace("## scores", "## scored"))
    r = explain_build(b)
    assert r.returncode == 1 and 'cells.md has "## scored"' in r.stderr, r.stderr


@pytest.mark.parametrize("name", ["lesson.py", "helpers.py", "scores.csv"])
def test_a_file_it_read_runs_pass_1(b, name):
    append(b, name)
    assert pass1(b) == "pass 1: ran"


def test_a_new_ref_key_runs_pass_1(b):
    append(b, "cells.md", "\nAnd {p_top:.2f}.\n")
    assert pass1(b) == "pass 1: ran"


def test_a_new_file_in_a_listed_folder_runs_pass_1(b):
    """Importing a bundle helper lists the bundle's folder: a new module there can change what an import resolves to."""
    (b / "extra.py").write_text("X = 1\n")
    assert pass1(b) == "pass 1: ran"


def test_an_engine_edit_runs_pass_1(b, tmp_path):
    env = engine_copy(tmp_path)
    assert pass1(b, env=env) == "pass 1: ran"  # the environment changed
    assert pass1(b, env=env) == "pass 1: reused"
    append(tmp_path / "engine" / "explainers", "schedule.py", "# an engine edit\n")
    assert pass1(b, env=env) == "pass 1: ran"


def test_a_library_change_runs_pass_1(b, tmp_path):
    info = tmp_path / "libs" / "zz_probe-1.0.dist-info"
    info.mkdir(parents=True)
    (info / "METADATA").write_text("Metadata-Version: 2.1\nName: zz-probe\nVersion: 1.0\n")
    (info / "RECORD").write_text("one\n")
    env = {"PYTHONPATH": os.pathsep.join(filter(None, [str(tmp_path / "libs"), os.environ.get("PYTHONPATH")]))}
    assert pass1(b, env=env) == "pass 1: ran"  # the environment changed
    assert pass1(b, env=env) == "pass 1: reused"
    (info / "RECORD").write_text("two\n")
    assert pass1(b, env=env) == "pass 1: ran"


def test_a_removed_cache_runs_pass_1(b):
    shutil.rmtree(b / "build" / "cache")
    assert pass1(b) == "pass 1: ran"


def test_a_store_from_another_engine_is_not_read(b, tmp_path):
    records = b / "build" / "pass1" / "records.json"
    records.write_text(json.dumps({**json.loads(records.read_text()), "a_field_this_engine_has_not": 1}))
    env = engine_copy(tmp_path, ("schedule.py", "START_COST_S = 0.89\n", "START_COST_S = 0.89  # an engine edit\n"))
    assert pass1(b, env=env) == "pass 1: ran"


def test_a_build_that_fails_at_commit_stores_nothing(tmp_path):
    b = tmp_path / "softmax.explainer"
    shutil.copytree(FIXTURES / "softmax.explainer", b, ignore=shutil.ignore_patterns("build"))
    r = explain_build(b, env=engine_copy(tmp_path, ("render.py", "for packet in src.demux(src.streams.video[0]):",
                                                    "for packet in list(src.demux(src.streams.video[0]))[:-2]:")))
    assert r.returncode == 1 and "joined" in r.stderr, r.stderr
    assert not (b / "build" / "pass1").exists()


def test_an_engine_edit_during_a_build_is_not_stored_as_the_new_engine(tmp_path):
    """The store names the code pass 1 ran, so the next build sees the edit."""
    env = engine_copy(tmp_path)
    b = tmp_path / "softmax.explainer"
    shutil.copytree(FIXTURES / "softmax.explainer", b, ignore=shutil.ignore_patterns("build"))
    schedule = tmp_path / "engine" / "explainers" / "schedule.py"
    (b / "lesson.py").write_text((b / "lesson.py").read_text().replace(
        "    def construct(self):\n", f"    def construct(self):\n        if self.RECORDING:\n            open({str(schedule)!r}, \"a\").write(\"# edit\\n\")\n"))
    assert pass1(b, env=env) == "pass 1: ran"
    assert pass1(b, env=env) == "pass 1: ran"


def test_each_part_moves_the_code(monkeypatch):
    before = B.pass1_code()
    for module, part in ((B, "engine_code"), (B, "library_code"), (F, "identity")):
        with monkeypatch.context() as m:
            m.setattr(module, part, lambda: "changed")
            assert B.pass1_code() != before, part


def test_the_other_parts_move_the_base(tmp_path):
    (tmp_path / "id1").mkdir()
    (tmp_path / "id2").mkdir()
    base = B.pass1_base(["c"], ["k"], tmp_path / "id1", {"PATH": "/usr/bin"})
    assert B.pass1_base(["c2"], ["k"], tmp_path / "id1", {"PATH": "/usr/bin"}) != base
    assert B.pass1_base(["c"], ["k2"], tmp_path / "id1", {"PATH": "/usr/bin"}) != base
    assert B.pass1_base(["c"], ["k"], tmp_path / "id1", {"PATH": "/opt/bin"}) != base
    assert B.pass1_base(["c"], ["k"], tmp_path / "id2", {"PATH": "/usr/bin"}) != base  # the cache id
    (tmp_path / "id1" / "entry.svg").write_text("x")
    assert B.pass1_base(["c"], ["k"], tmp_path / "id1", {"PATH": "/usr/bin"}) != base  # the cache's names


def test_an_input_moves_the_key_by_its_content_and_its_existence(tmp_path):
    absent = B.pass1_key("b", tmp_path, ["assets/x"])
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "x").write_text("one")
    one = B.pass1_key("b", tmp_path, ["assets/x"])
    os.utime(tmp_path / "assets" / "x", ns=(1, 1))
    touched = B.pass1_key("b", tmp_path, ["assets/x"])
    (tmp_path / "assets" / "x").write_text("two")
    two = B.pass1_key("b", tmp_path, ["assets/x"])
    assert len({absent, one, touched, two}) == 4
    listed = B.pass1_key("b", tmp_path, ["assets/"])
    (tmp_path / "assets" / "y").write_text("")
    assert B.pass1_key("b", tmp_path, ["assets/"]) != listed
    assert B.pass1_key("b", tmp_path, ["assets"]) == B.pass1_key("b", tmp_path, ["assets"]) != B.pass1_key("b", tmp_path, ["gone"])


def test_an_incremental_build_equals_a_cold_one(b, tmp_path):
    """After a prose edit (pass 1 reused) and after a data edit that changes frames (pass 1 ran)."""
    before = shas(b)
    append(b, "cells.md", "\nMore prose.\n")
    assert pass1(b) == "pass 1: reused"
    assert shas(b) == before
    (b / "scores.csv").write_text((b / "scores.csv").read_text().replace("1", "3"))
    assert pass1(b) == "pass 1: ran"
    assert shas(b) != before
    cold = tmp_path / "cold" / "softmax.explainer"
    shutil.copytree(b, cold, ignore=shutil.ignore_patterns("build"))
    assert pass1(cold) == "pass 1: ran"
    assert shas(b) == shas(cold)
