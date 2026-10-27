"""The how-to's example lesson, taken from SKILL.md as written, builds."""
import json
import re

from conftest import REPO, explain_build

SKILL = REPO / ".claude" / "skills" / "lesson-heuristics" / "SKILL.md"


def test_the_how_to_example_builds(tmp_path):
    text = SKILL.read_text()
    b = tmp_path / "total.explainer"
    b.mkdir()
    (b / "cells.md").write_text(re.search(r"```markdown\n(.*?)```", text, re.S).group(1))
    (b / "lesson.py").write_text(re.search(r"```python\n(.*?)```", text, re.S).group(1))
    r = explain_build(b)
    assert r.returncode == 0, r.stdout + r.stderr
    index = json.loads((b / "build" / "index.json").read_text())
    assert [c["slug"] for c in index["cells"]] == ["numbers", "total"]
    assert index["refs"] == {"n": "3", "total": "6"}
