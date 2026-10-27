"""cells.md is read by one implementation, tools/cells.mjs (remark, the app's renderer); this runs it."""
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

READER = Path(__file__).resolve().parents[1] / "tools" / "cells.mjs"


@dataclass(frozen=True)
class Cells:
    sections: list[dict]  # {slug, start, end, line}; offsets in UTF-16 code units
    refs: list[dict]      # {key, name, line}; key = the exact text between the braces
    links: list[dict]     # {slug, cell, line}
    errors: list[str]


def read_cells(path: Path) -> Cells:
    r = subprocess.run(["node", str(READER), str(path)], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"tools/cells.mjs failed on {path}:\n{r.stderr.strip()}")
    return Cells(**json.loads(r.stdout))
