"""Rendering in parallel chunks gives bit-identical clips to rendering in one chunk: the long lesson has an updater
that runs through every animation and a random draw, so chunks only agree if fast-forwarding and seeding are right."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import FIXTURES
from explainers.build import _ram
from explainers.render import width

pytestmark = pytest.mark.xdist_group("render")  # builds that render run one at a time

SCRIPT = Path(__file__).parent / "build_with_width.py"


def shas(bundle, k):
    r = subprocess.run([sys.executable, str(SCRIPT), str(bundle), str(k)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_chunked_equals_one_chunk(tmp_path):
    k = width(os.cpu_count(), _ram(), 30)
    assert k > 1, "this machine cannot exercise chunking"
    a, b = tmp_path / "a" / "long.explainer", tmp_path / "b" / "long.explainer"
    for d in (a, b):
        shutil.copytree(FIXTURES / "long.explainer", d)
    one, many = shas(a, 1), shas(b, k)
    assert len(many["chunks"]) > 1 and all(g[0] >= 10 for g in many["chunks"][1:])  # no cut while the spinner runs
    assert one["shas"] == many["shas"]
