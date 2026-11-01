import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "tests" / "fixtures"
TEX_BIN = (REPO / ".tinytex" / "bin-path").read_text().strip()


@pytest.fixture
def bundle(tmp_path):
    """A fresh copy of a fixture bundle (no build/, cold TeX cache), so tests can break it."""
    def copy(name="softmax.explainer"):
        dst = tmp_path / name
        shutil.copytree(FIXTURES / name, dst, ignore=shutil.ignore_patterns("build"))
        return dst
    return copy


def explain_build(*args, cwd=None, env=None):
    """Run this checkout's explain-build with TeX removed from PATH: the build must find the repo's own TeX."""
    path = os.pathsep.join(p for p in os.environ["PATH"].split(os.pathsep) if p != TEX_BIN)
    return subprocess.run([str(REPO / "bin" / "explain-build"), *map(str, args)], capture_output=True, text=True,
                          cwd=cwd, env={**os.environ, "PATH": path, **(env or {})})


def run_pass1(bundle, keys="[]"):
    """Pass 1 alone, as the build runs it: on a snapshot kept for the caller, with a fresh cache and TeX on PATH. Returns
    (the process, its out folder, the snapshot)."""
    work = Path(tempfile.mkdtemp(dir=bundle.parent))
    snapshot, cache, out = work / "src", work / "cache", work / "out"
    shutil.copytree(bundle, snapshot, ignore=shutil.ignore_patterns("build", "__pycache__"))
    cache.mkdir()
    out.mkdir()
    env = {**os.environ, "EXPLAINERS_BUILD_PID": str(os.getpid()), "PATH": TEX_BIN + os.pathsep + os.environ["PATH"], "PYTHONHASHSEED": "0"}
    r = subprocess.run([sys.executable, "-P", "-m", "explainers.pass1", str(snapshot), str(cache), str(out), keys],
                       capture_output=True, text=True, env=env, start_new_session=True)
    return r, out, snapshot


def records(bundle) -> dict:
    r, out, _ = run_pass1(bundle)
    assert r.returncode == 0, r.stderr
    return json.loads((out / "records.json").read_text())


def engine_copy(tmp_path, *edits):
    """This engine in another folder, with (file, old text, new text) applied. PYTHONPATH reaches it through the build's
    fixed environment. cells.py finds its reader from its own file, so tools comes too."""
    copy = tmp_path / "engine"
    shutil.copytree(REPO / "explainers", copy / "explainers", ignore=shutil.ignore_patterns("__pycache__"))
    for name in (".tinytex", "schema", "tools"):
        (copy / name).symlink_to(REPO / name)
    for name, old, new in edits:
        f = copy / "explainers" / name
        assert old in f.read_text()
        f.write_text(f.read_text().replace(old, new))
    return {"PYTHONPATH": str(copy)}
