"""Decode one cell's clip into 64×36 RGB frames and pick k: the frame whose neighbours k−1, k, k+1, k+2 are most
clearly pairwise distinct (so a step to either side, or a step that skips one, is told apart). Prints JSON."""
import json
import sys
from pathlib import Path

import av
import numpy as np

bundle, slug = Path(sys.argv[1]), sys.argv[2]
index = json.loads((bundle / "build" / "index.json").read_text())
clip = bundle / "build" / next(c["clip"] for c in index["cells"] if c["slug"] == slug)
with av.open(str(clip)) as f:
    frames = [fr.reformat(64, 36, "rgb24").to_ndarray().astype(int) for fr in f.decode(video=0)]
d = lambda a, b: int(np.abs(frames[a] - frames[b]).sum())
# Chromium and FFmpeg downscale slightly differently, so "nearest frame" needs margins on every side.
margin = lambda k: min(d(a, b) for a in range(k - 1, k + 3) for b in range(a + 1, k + 3))
k = max(range(1, len(frames) - 2), key=margin)
assert margin(k) > 0, "no frame with four distinct neighbours"
print(json.dumps({"k": k, "fps": index["fps"], "frames": [f.reshape(-1).tolist() for f in frames]}))
