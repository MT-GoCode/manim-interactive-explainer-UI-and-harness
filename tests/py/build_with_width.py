"""Build a bundle with a forced render width (k), for test_parallel; prints the cells' frames_sha as JSON."""
import json
import sys
from pathlib import Path

from explainers import build as B
from explainers.render import render

bundle, k = Path(sys.argv[1]), int(sys.argv[2])
rec = B.check(bundle)
parts, groups = render(bundle, rec["lock"].fileno(), rec["cells"], k)
index = B.commit(bundle, rec, parts)
print(json.dumps({"shas": [c["frames_sha"] for c in json.loads(index.read_text())["cells"]], "chunks": groups}))
