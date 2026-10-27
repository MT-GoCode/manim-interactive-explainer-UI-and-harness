"""The geometry check through explain-build: one fixture cell per case, each expecting exactly its messages (none
for the cases that must pass). Dots, squares and straight strokes make the numbers hand-checkable (see the fixtures)."""
import shutil

import pytest

from conftest import FIXTURES, explain_build

GEOMETRY = {
    "dot-on-dot": ["lesson.py:20 · Dot at (0.00, 0.00) × Dot at (0.10, 0.00) (lesson.py:20) · move Dot by (-0.06, +0.00)"],
    "dots-touch-by-under-half-a-pixel": [],
    "text-on-text": ["lesson.py:22 · Text at (0.00, 0.00) × Text at (0.30, 0.00) (lesson.py:22) · move Text by (+0.00, +0.44)"],
    "text-on-text-moved-as-told": [],  # exactly the move printed for text-on-text
    "text-on-an-arrow": ["lesson.py:25 · Text at (0.00, 0.00) × Arrow at (0.00, 0.00) (lesson.py:25) · move Text by (+0.00, +0.11)"],
    "dot-on-an-arrow": [],
    "hidden-in-a-group": ["lesson.py:27 · Dot at (0.00, 0.00) × Dot at (0.10, 0.00) (lesson.py:27) · move Dot by (-0.06, +0.00)"],
    "off-frame-right": ["lesson.py:29 · Square at (7.00, 0.00) is off frame by 0.39 (right)"],
    "off-frame-left": ["lesson.py:30 · Square at (-7.00, 0.00) is off frame by 0.39 (left)"],
    "off-frame-top": ["lesson.py:31 · Square at (0.00, 4.00) is off frame by 0.50 (top)"],
    "off-frame-fill": ["lesson.py:32 · Square at (0.00, -4.00) is off frame by 0.50 (bottom)"],
    "off-frame-image": ["lesson.py:33 · ImageMobject at (7.00, 0.00) is off frame by 0.39 (right)"],
    "under-half-a-pixel-past-the-edge": [],
    "small-text": ["lesson.py:35 · Text at (0.00, 0.00) font size 28.0 < 32"],
    "small-latex": ["lesson.py:36 · MathTex at (0.00, 0.00) LaTeX font size 36.0 < 40",
                    "lesson.py:36 · Matrix at (0.00, -2.00) LaTeX font size 24.0 < 40"],
    "leftover-transient": ["lesson.py:39 · Circle at (0.00, 0.00) was made transient in this cell and is still on "
                           "screen at its end"],
    "leftover-transient-group": [
        "lesson.py:42 · Circle at (0.00, 0.00) was made transient in this cell and is still on screen at its end",
        "lesson.py:42 · Square at (0.00, 0.00) was made transient in this cell and is still on screen at its end"],
    "attached": [],
    "attached-to-a-group": [],
    "attached-to-a-part": [],
    "attached-and-copied": [],
    "punctuation-at-the-minimum": [],
    "text-on-a-plane": [],
    "transient-gone": [],
    "label-beside-a-line": [],
    "matmul-with-cursors": [],
    "plane-with-vectors-and-points": [],
    "arrow-label-number-in-a-box-highlight": [],
    "brace-underline-root": [],
    "point-on-a-curve": [],
    "graph-edge-with-nodes": [],
    "number-line-under-text": ["lesson.py:93 · NumberLine at (-0.14, -0.22) × Text at (1.00, -0.30) (lesson.py:94) · "
                               "move NumberLine by (+0.00, +0.30)"],
    "number-line-moved-as-told": [],  # exactly the move printed for number-line-under-text
}
GEOMETRY3D = {
    "apart-in-the-world": ["lesson.py:14 · Dot at (1.00, 0.00) × Dot at (1.04, 0.00) (lesson.py:14) · "
                           "move Dot by (-0.44, +0.00)"],
    "label-fixed-in-frame": [],
}


def build(tmp_path_factory, name):
    b = tmp_path_factory.mktemp("geo") / name
    shutil.copytree(FIXTURES / name, b)
    return b, explain_build(b)


def messages(built) -> dict[str, list[str]]:
    """The failed build's messages by cell; asserted here, in each test, so a build that wrongly passes fails it."""
    b, r = built
    assert r.returncode == 1, r.stdout + r.stderr
    assert not (b / "build" / "index.json").exists() and not (b / "build" / ".media").exists()  # nothing rendered
    by_cell = {}
    for line in r.stderr.splitlines():
        cell, _, msg = line.removeprefix("error: ").partition(" · ")
        by_cell.setdefault(cell, []).append(msg)
    return by_cell


@pytest.fixture(scope="module")
def geometry(tmp_path_factory):
    return build(tmp_path_factory, "geometry.explainer")


@pytest.fixture(scope="module")
def geometry3d(tmp_path_factory):
    return build(tmp_path_factory, "geometry3d.explainer")


@pytest.mark.parametrize("cell", GEOMETRY)
def test_cell_end_geometry(geometry, cell):
    found = messages(geometry)
    assert set(found) <= set(GEOMETRY)
    assert found.get(cell, []) == GEOMETRY[cell]


@pytest.mark.parametrize("cell", GEOMETRY3D)
def test_cell_end_geometry_is_checked_where_the_3d_camera_draws(geometry3d, cell):
    found = messages(geometry3d)
    assert set(found) <= set(GEOMETRY3D)
    assert found.get(cell, []) == GEOMETRY3D[cell]


@pytest.mark.parametrize("move", ["theta=30 * DEGREES", "phi=30 * DEGREES", "gamma=10 * DEGREES", "zoom=1.5",
                                  "focal_distance=10", "frame_center=[1, 0, 0]"])
def test_a_moved_3d_camera_is_an_error(bundle, move):
    b = bundle("camera-moved.explainer")
    src = b / "lesson.py"
    src.write_text(src.read_text().replace("theta=30 * DEGREES", move))
    r = explain_build(b)
    assert r.returncode == 1
    assert r.stderr.splitlines() == ['error: the camera moved in cell "turns" (lesson.py:11); the camera is static: '
                                     "set it before the first self.cell()"]
