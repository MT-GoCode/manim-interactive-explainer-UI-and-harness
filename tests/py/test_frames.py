"""Pass 1 records what each frame draws, never pixels: a pair of cells records equal frames exactly when the two cells
draw the same thing (tests/fixtures/frames.explainer: cells <case>-a and <case>-b)."""
import shutil
from pathlib import Path

import pytest

from conftest import FIXTURES, records
from explainers.fingerprint import _Context


def drawn(bundle: Path) -> dict[str, list[str]]:
    return {c["slug"]: c["drawn"] for c in records(bundle)["cells"]}


@pytest.fixture(scope="module")
def frames(tmp_path_factory):
    b = tmp_path_factory.mktemp("f") / "frames.explainer"
    shutil.copytree(FIXTURES / "frames.explainer", b)
    return drawn(b)


# rate: 0.2 s and 0.2167 s are both 6 frames at the render's 30 fps (12 and 13 at Manim's default 60).
@pytest.mark.parametrize("case", ["same", "rate"])
def test_the_same_picture_records_the_same_frames(frames, case):
    assert frames[f"{case}-a"] == frames[f"{case}-b"]


# hold: one frozen frame written 6 times vs 12. halves: the same 12 frames as one animation vs two (each partial file
# restarts its encoding, so the clips differ).
@pytest.mark.parametrize("case", ["fill", "stroke", "order", "gradient", "static", "image", "points", "hold",
                                  "halves", "background", "backimage"])
def test_a_different_picture_records_different_frames(frames, case):
    assert frames[f"{case}-a"] != frames[f"{case}-b"]


def test_each_animation_records_its_own_digest(frames):
    # the same frames as one animation vs two: the split itself is recorded, since each partial file is encoded apart
    assert (len(frames["halves-a"]), len(frames["halves-b"])) == (1, 2)


@pytest.mark.parametrize("setting", ["self.camera.frame_center = np.array([0.25, 0.0, 0.0])",
                                     "self.camera.frame_width = 15.0"], ids=["centre", "width"])
def test_where_the_camera_looks_is_in_every_frame(frames, bundle, setting):
    b = bundle("frames.explainer")
    src = b / "lesson.py"
    src.write_text(src.read_text().replace("    def construct(self):\n", f"    def construct(self):\n        {setting}\n"))
    moved = drawn(b)
    assert all(moved[s] != frames[s] for s in frames)


def test_the_recording_context_refuses_what_it_cannot_answer():
    ops = []
    ctx = _Context(ops)
    ctx.move_to(1, 2)
    assert ops == [("move_to", 1.0, 2.0)]
    with pytest.raises(AttributeError):
        ctx.get_matrix()
