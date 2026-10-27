import os
import shutil
import subprocess
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


def explain_build(*args, cwd=None):
    """Run this checkout's explain-build with TeX removed from PATH: the build must find the repo's own TeX."""
    path = os.pathsep.join(p for p in os.environ["PATH"].split(os.pathsep) if p != TEX_BIN)
    return subprocess.run([str(REPO / "bin" / "explain-build"), *map(str, args)], capture_output=True, text=True,
                          cwd=cwd, env={**os.environ, "PATH": path})
