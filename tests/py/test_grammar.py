"""The one cells.md reader (tools/cells.mjs, remark) against hand-audited golden cases: what counts as a cell
heading, a value reference and a link, and where it is."""
import json

import pytest

from conftest import FIXTURES
from explainers.cells import read_cells

CASES = json.loads((FIXTURES / "grammar.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_reader_matches_golden(case, tmp_path):
    f = tmp_path / "cells.md"
    f.write_bytes(case["text"].encode())
    got = read_cells(f)
    assert (got.sections, got.refs, got.links, got.errors) == (case["sections"], case["refs"], case["links"],
                                                               case["errors"])
