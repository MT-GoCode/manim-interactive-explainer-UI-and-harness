"""fetch-comments on the softmax fixture with hand-written comments.json files: exact lines, --wait, and reading
while the app's own atomic writer (Node writeFileSync + renameSync) replaces the file."""
import json
import subprocess
import time
from pathlib import Path

from conftest import REPO

from explainers.comments import lines


def write(b: Path, comments: list[dict]) -> None:
    (b / "comments.json").write_text(json.dumps({"format": "explainer-comments", "version": 1, "comments": comments}))


def c(id_: str, cell: str, span, text: str) -> dict:
    return {"id": id_, "cell": cell, "span": span, "text": text, "created": "2026-10-27T00:00:00.000Z",
            "fingerprint": {"section_sha": "0" * 64, "frames_sha": "0" * 64}}


def test_prints_exactly_the_files_comments_in_cell_order(bundle):
    b = bundle()
    md = (b / "cells.md").read_text().replace("The model gives", "🙂 The model gives")
    (b / "cells.md").write_text(md)
    sum_prose = "Add them all: $\\sum_j e^{z_j}$.\n\n"
    across = [sum_prose.index("them"), sum_prose.index("$.") + 1]  # no character above U+FFFF here: equal offsets
    # 🙂 is two UTF-16 units: "model" starts at 2 + 1 + 4 = 7 in the app's offsets (6 in Python's)
    write(b, [c("aaaaaaa3", "probs", None, "Say why\nthey sum to 1"), c("aaaaaaa4", "gone", [0, 2], "about gone"),
              c("aaaaaaa2", "sum", across, "which j?"), c("aaaaaaa1", "scores", [7, 12], "which model?")])
    assert lines(b) == [
        'aaaaaaa1 · #1 scores · "model" → which model?',
        'aaaaaaa2 · #3 sum · "them all: $\\sum_j e^{z_j}$" → which j?',
        "aaaaaaa3 · #5 probs · whole cell → Say why⏎they sum to 1",
        "aaaaaaa4 · #– gone · about gone",
    ]


def test_wait_wakes_on_ping_prints_and_deletes_it(bundle):
    b = bundle()
    write(b, [c("aaaaaaa1", "sum", None, "hello")])
    p = subprocess.Popen([str(REPO / "bin" / "fetch-comments"), "--wait", str(b)], stdout=subprocess.PIPE, text=True)
    time.sleep(1.5)  # it is waiting: nothing printed, still running
    assert p.poll() is None
    (b / "ping").write_text("")
    out, _ = p.communicate(timeout=30)
    assert p.returncode == 0
    assert out.splitlines() == ["aaaaaaa1 · #3 sum · whole cell → hello"]
    assert not (b / "ping").exists()


def test_a_reader_never_sees_half_a_file(bundle):
    b = bundle()
    one = json.dumps({"format": "explainer-comments", "version": 1, "comments": [c("aaaaaaa1", "sum", None, "one")]})
    two = json.dumps({"format": "explainer-comments", "version": 1,
                      "comments": [c(f"bbbbbb{i:02x}", "sum", None, "two " * 200) for i in range(40)]})
    write(b, [c("aaaaaaa1", "sum", None, "one")])
    # the app's writer: write a temporary file, rename it over comments.json (src/main/atomic.ts), 200 times
    js = (f"const fs = require('fs'); const p = {json.dumps(str(b / 'comments.json'))}; const a = {json.dumps(one)};"
          f" const b = {json.dumps(two)}; for (let i = 0; i < 200; i++) {{ fs.writeFileSync(p + '.tmp', i % 2 ? a : b);"
          " fs.renameSync(p + '.tmp', p) }")
    writer = subprocess.Popen(["node", "-e", js])
    seen = set()
    while writer.poll() is None:
        got = lines(b)
        assert len(got) in (1, 40), got  # one of the two files, whole
        seen.add(len(got))
    assert writer.returncode == 0
    assert seen  # the reader ran while the writer did
