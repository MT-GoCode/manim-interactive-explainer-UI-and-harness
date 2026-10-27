"""Build a bundle with a forced render width (k), for the tests; prints the cells' frames_sha, the chunks and the
cells rendered, as JSON."""
import json
import sys
from pathlib import Path

from explainers.build import build

rec, index = build(Path(sys.argv[1]), int(sys.argv[2]))
print(json.dumps({"shas": [c["frames_sha"] for c in json.loads(index.read_text())["cells"]], "chunks": rec["chunks"],
                  "rendered": rec["rendered"]}))
