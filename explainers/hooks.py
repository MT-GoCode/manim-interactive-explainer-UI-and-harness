"""The Manim internals a worker hooks, vendored from presenters' manim_hooks."""
from typing import Any


def exact_fast_forward(scene: Any) -> None:
    """Plays before `from_animation_number` run Manim's own `play_internal` unmodified (per-frame `update_to_time`,
    time advanced where frames are added, `stop_condition`, the closing `update_mobjects(0)`, frozen-wait arithmetic)
    with every draw and write suppressed, so a chunk starts from exactly pass 1's scene state, call for call. Manim's
    skip mode would collapse each play to one `update_to_time(run_time)` and miss per-frame updater effects."""
    from manim import config

    r = scene.renderer
    cam, writer = r.camera, r.file_writer
    real = {
        "status": r.update_skipping_status,
        "capture": cam.capture_mobjects,
        "reset": cam.reset,
        "load": cam.set_frame_to_background,
        "get_frame": r.get_frame,
        "add": writer.add_partial_movie_file,
        "begin": writer.begin_animation,
        "end": writer.end_animation,
        "write": writer.write_frame,
    }
    forwarding = {"on": False}

    def update_skipping_status() -> None:
        forwarding["on"] = config.from_animation_number > 0 and r.num_plays < config.from_animation_number
        if forwarding["on"]:
            r.skip_animations = False
        else:
            real["status"]()

    def gated(name: str, null: Any) -> Any:
        return lambda *a, **k: null(*a, **k) if forwarding["on"] else real[name](*a, **k)

    r.update_skipping_status = update_skipping_status
    cam.capture_mobjects = gated("capture", lambda *a, **k: None)
    cam.reset = gated("reset", lambda *a, **k: cam)
    cam.set_frame_to_background = gated("load", lambda *a, **k: None)
    r.get_frame = gated("get_frame", lambda *a, **k: None)
    writer.add_partial_movie_file = gated("add", lambda *a, **k: real["add"](None))
    writer.begin_animation = gated("begin", lambda *a, **k: real["begin"](False, **k))
    writer.end_animation = gated("end", lambda *a, **k: real["end"](False))
    writer.write_frame = gated("write", lambda *a, **k: None)


def partial_files(scene: Any) -> dict[int, str]:
    """{play index: the partial file Manim wrote for it}, for the plays this process rendered."""
    return {i: p for i, p in enumerate(scene.renderer.file_writer.partial_movie_files) if p is not None}
