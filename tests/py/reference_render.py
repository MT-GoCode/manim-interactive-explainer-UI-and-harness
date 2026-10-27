"""A plain one-pass Manim render of a bundle's scene with literal settings (not explain-build's code), for
test_render. Prints the first animation index of each cell, then the total, as JSON."""
import json
import sys
from pathlib import Path

from manim import tempconfig

bundle, out = Path(sys.argv[1]), Path(sys.argv[2])
import os  # noqa: E402
os.environ["PATH"] = (Path(__file__).resolve().parents[2] / ".tinytex" / "bin-path").read_text().strip() + os.pathsep + os.environ["PATH"]
sys.dont_write_bytecode = True
sys.path.insert(0, str(bundle))
import types  # noqa: E402
module = types.ModuleType("lesson")
exec(compile((bundle / "lesson.py").read_bytes(), str(bundle / "lesson.py"), "exec"), module.__dict__)
from explainers import Lesson  # noqa: E402
cls = next(v for v in vars(module).values() if isinstance(v, type) and issubclass(v, Lesson) and v is not Lesson)
with tempconfig({"media_dir": str(out), "pixel_width": 2160, "pixel_height": 1080, "frame_width": 16.0, "frame_rate": 30, "seed": 0,
                 "disable_caching": True, "max_files_cached": -1, "verbosity": "ERROR", "progress_bar": "none",
                 "video_encoder_options": {"threads": "1", "g": "6", "crf": "18", "preset": "veryfast"}}):
    scene = cls()
    scene.render()
cells = scene._cells
print(json.dumps([c.first_anim for c in cells] + [cells[-1].first_anim + len(cells[-1].run_times)]))
