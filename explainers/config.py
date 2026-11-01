"""The Manim config every scene process renders under (vendored from presenters' clip.py): Manim's packaged defaults plus
Explainers' render settings, rebuilt in place, so no ~/.config/manim/manim.cfg or ./manim.cfg reaches a frame. Paths and
play ranges are set by the caller on top. This module imports manim only inside its functions: the build itself never
imports it."""
import configparser
from pathlib import Path
from typing import Any

ENCODER = {"threads": "1", "g": "6", "crf": "18", "preset": "veryfast"}  # g 6: worst seek 9.7 ms (DECISIONS)
# What Manim's "auto" picks for an opaque mp4, pinned: a manim.cfg (cwd or user) must not change the clips' bytes.
OUTPUT = {"format": "mp4", "transparent": False, "video_codec": "libx264", "pixel_format": "yuv420p"}
FPS, WIDTH, HEIGHT = 30, 2160, 1080  # 2:1: the app shows the player full width over three quarters of the window
SEED = 0  # every process draws the same random numbers, so chunks and pass 1 agree
# Manim keeps its 14.22-wide frame at any pixel size: the frame takes the pixels' shape, so a unit stays square. No
# animation hashing: Manim's hash reads the source of updaters (inspect.getsource).
RENDER = {"pixel_width": WIDTH, "pixel_height": HEIGHT, "frame_width": 8.0 * WIDTH / HEIGHT, "frame_height": 8.0,
          "frame_rate": FPS, "seed": SEED, "renderer": "cairo", "disable_caching": True, "max_files_cached": -1,
          "verbosity": "ERROR", "progress_bar": "none", "video_encoder_options": ENCODER, **OUTPUT}
_applied: dict[str, Any] = {}  # what render_config set, as Manim stores it


def render_config() -> None:
    """The global `config` becomes exactly Manim's packaged defaults plus RENDER, in place (modules hold references)."""
    import manim
    from manim import config
    from manim._config.utils import ManimConfig
    parser = configparser.ConfigParser()
    parser.read(Path(manim.__file__).parent / "_config" / "default.cfg")
    config.update(ManimConfig().digest_parser(parser))
    config.update(RENDER)
    _applied.clear()
    _applied.update({k: config[k] for k in RENDER})


def check_render_config() -> None:
    """Nothing outside this file changed how frames are drawn or encoded while the scene ran."""
    from manim import config
    drift = {k: (config[k], _applied[k]) for k in RENDER if repr(config[k]) != repr(_applied[k])}
    assert not drift, f"render config changed outside config.py: {drift}"
