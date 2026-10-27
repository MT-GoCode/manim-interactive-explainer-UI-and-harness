"""The geometry check through explain-build: one fixture cell per case, each expecting exactly its messages (none
for the cases that must pass). Dots and straight strokes make the numbers hand-checkable (see the fixtures)."""
import shutil

import pytest

from conftest import FIXTURES, explain_build

GEOMETRY = {
    "dot-on-dot": ["lesson.py:17 · Dot × Dot (lesson.py:17) · move Dot by (-0.06, +0.00)"],
    "text-on-text": ["lesson.py:18 · Text × Text (lesson.py:18) · move Text by (-0.21, +0.00)"],
    "dot-on-arrow-shaft": ["lesson.py:20 · Dot × Arrow (lesson.py:20) · move Dot by (+0.00, +0.05)"],
    "hidden-in-a-group": ["lesson.py:21 · Dot × Dot (lesson.py:21) · move Dot by (-0.06, +0.00)"],
    "off-frame-stroke": ["lesson.py:23 · Square is off frame by 0.39 (right)"],
    "off-frame-fill": ["lesson.py:25 · Square is off frame by 0.50 (bottom)"],
    "small-text": ["lesson.py:26 · Text font size 28.0 < 32"],
    "small-latex": ["lesson.py:27 · MathTex LaTeX font size 36.0 < 40", "lesson.py:27 · Matrix LaTeX font size 24.0 < 40"],
    "leftover-transient": ["lesson.py:30 · Circle was made transient in this cell and is still on screen at its end"],
    "attached": [],
    "attached-to-a-group": [],
    "punctuation-at-the-minimum": [],
    "text-on-a-plane": [],
    "transient-gone": [],
    "label-beside-an-arrow": [],
    "under-half-a-pixel-past-the-edge": [],
}
GEOMETRY3D = {
    "apart-in-the-world": ["lesson.py:13 · Dot × Dot (lesson.py:13) · move Dot by (-0.44, +0.00)"],
    "label-fixed-in-frame": [],
}


def failed_build(tmp_path_factory, name):
    b = tmp_path_factory.mktemp("geo") / name
    shutil.copytree(FIXTURES / name, b)
    r = explain_build(b)
    assert r.returncode == 1, r.stdout + r.stderr
    assert not (b / "build" / "index.json").exists() and not (b / "build" / ".media").exists()  # nothing rendered
    by_cell = {}
    for line in r.stderr.splitlines():
        cell, _, msg = line.removeprefix("error: ").partition(" · ")
        by_cell.setdefault(cell, []).append(msg)
    return by_cell


@pytest.fixture(scope="module")
def geometry(tmp_path_factory):
    return failed_build(tmp_path_factory, "geometry.explainer")


@pytest.fixture(scope="module")
def geometry3d(tmp_path_factory):
    return failed_build(tmp_path_factory, "geometry3d.explainer")


@pytest.mark.parametrize("cell", GEOMETRY)
def test_cell_end_geometry(geometry, cell):
    assert set(geometry) <= set(GEOMETRY)
    assert geometry.get(cell, []) == GEOMETRY[cell]


@pytest.mark.parametrize("cell", GEOMETRY3D)
def test_cell_end_geometry_is_checked_where_the_3d_camera_draws(geometry3d, cell):
    assert set(geometry3d) <= set(GEOMETRY3D)
    assert geometry3d.get(cell, []) == GEOMETRY3D[cell]


def test_a_moved_3d_camera_is_an_error(bundle):
    r = explain_build(bundle("camera-moved.explainer"))
    assert r.returncode == 1
    assert r.stderr.splitlines() == ['error: the camera moved in cell "turns" (lesson.py:11); the camera is static: '
                                     "set it before the first self.cell()"]
