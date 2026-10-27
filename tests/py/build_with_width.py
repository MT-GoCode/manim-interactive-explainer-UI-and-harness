"""Build a bundle with a forced render width (k), for the tests; prints the cells' frames_sha, the chunks, the cells
rendered and the report's render line, as JSON."""
import json
import sys
from pathlib import Path

from explainers.build import build, render_line

rec, index = build(Path(sys.argv[1]), int(sys.argv[2]))
print(json.dumps({"shas": [c["frames_sha"] for c in json.loads(index.read_text())["cells"]], "chunks": rec["chunks"],
                  "rendered": rec["rendered"], "line": render_line(rec)}))
