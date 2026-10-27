from pathlib import Path

import numpy as np

Z = np.array([float(v) for v in (Path(__file__).parent / "scores.csv").read_text().split(",")])
P = np.exp(Z) / np.exp(Z).sum()
