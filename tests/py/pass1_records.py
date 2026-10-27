"""Run pass 1 on a bundle in its own process (Manim's config and the creation-line hooks are process-global) and
print the records as JSON. Used by test_pass1."""
import dataclasses
import json
import sys
from pathlib import Path

from explainers.build import check

rec = check(Path(sys.argv[1]))
rec.pop("lock").close()
rec["cells"] = [dataclasses.asdict(c) for c in rec["cells"]]
print(json.dumps(rec))
