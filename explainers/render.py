"""Pass 2: render a checked lesson into one clip per cell, in parallel chunks.

    python -P -m explainers.render <snapshot> <cache> <out> <first-last>

Each worker runs from the build's snapshot of the bundle and renders one contiguous animation range, fast-forwarding the plays
before it without drawing them. The first statement changes into the snapshot, before anything imports manim (Manim reads
./manim.cfg at import)."""
import os
import sys

if __name__ == "__main__":
    os.chdir(sys.argv[1])

import hashlib
import io
import json
import shutil
import threading
import time
from pathlib import Path

from explainers.children import Job, child_env, run_all, watch_parent
from explainers.config import check_render_config, render_config

WORKER_CORES, WORKER_RAM = 1.22, 0.59 * 2**30  # one worker's measured peaks, until a build has measured its own


def to_render(reusable: set[int], n: int) -> list[int]:
    return sorted(set(range(n)) - reusable)


def worker(snapshot: Path, cache: Path, out: Path, first: int, last: int) -> None:
    """One chunk: one contiguous animation range. TeX is not on PATH: the warm cache from pass 1 must hit. The worker reads a
    private copy of it: even on a hit, Manim writes and deletes a temp SVG in the cache dir. The folders are set before the
    lesson runs, because a lesson may make TeX at import time."""
    watch_parent()  # before the import: a build killed during it still ends this worker
    from manim import config

    from explainers import hooks
    from explainers.fingerprint import Tee
    from explainers.lesson import exec_lesson
    render_config()
    out.mkdir(parents=True, exist_ok=True)
    for name in ("tex", "text"):
        if (cache / name).exists():
            shutil.copytree(cache / name, out / name)
    config.update({"tex_dir": str(out / "tex"), "text_dir": str(out / "text"), "from_animation_number": first,
                   "upto_animation_number": last, "media_dir": str(out / "media")})
    _, cls = exec_lesson(snapshot, (snapshot / "lesson.py").read_bytes())
    cls.RECORDER = Tee
    scene = cls()
    hooks.exact_fast_forward(scene)
    play, started, forwarded, times = scene.play, time.monotonic(), [None], {}
    progress = (out / "progress").open("a", buffering=1)

    def stamped(*a, **k):
        n, t = scene.renderer.num_plays, time.monotonic()
        if n == first:
            forwarded[0] = t - started
        try:
            return play(*a, **k)
        finally:
            if first <= n <= last:
                times[n] = time.monotonic() - t
                progress.write(f"{n}\n")

    scene.play = stamped
    scene.render()
    check_render_config()
    digests, partials = [d for c in scene._cells for d in c.drawn], hooks.partial_files(scene)
    (out / "report.json").write_text(json.dumps({
        "fast_forward_s": forwarded[0],
        "plays": [{"anim": n, "digest": digests[n], "partial": str(partials[n]), "render_s": times[n]} for n in sorted(times)]}))


def render(snapshot: Path, cache: Path, chunks: list[tuple[int, int]], width: int):
    """Render each chunk in its own worker, at most `width` alive, printing progress as it moves. Returns each chunk's report and
    each worker's peaks. A worker that exited 0 with no report has an empty one: the build's verify names its first missing play."""
    media = snapshot.parent
    jobs = [Job("explainers.render", [str(snapshot), str(cache), str(media / f"chunk-{n}"), f"{a}-{b}"], media / f"chunk-{n}")
            for n, (a, b) in enumerate(chunks)]
    path = os.pathsep.join(p for p in os.environ["PATH"].split(os.pathsep) if ".tinytex" not in p)
    total, stop = sum(b - a + 1 for a, b in chunks), threading.Event()

    def tail():
        last = -1
        while not stop.wait(1.0):
            seen = sum((j.out / "progress").read_text().count("\n") for j in jobs if (j.out / "progress").exists())
            if seen != last:
                last = seen
                print(f"render: {seen}/{total} animations", flush=True)

    reader = threading.Thread(target=tail, daemon=True)
    reader.start()
    try:
        done = run_all(jobs, width, child_env(path))
    finally:
        stop.set()
        reader.join()
    paths = [job.out / "report.json" for job in jobs]
    return [json.loads(p.read_text()) if p.exists() else {"plays": []} for p in paths], done


def join(paths: list[Path], out: Path) -> int:
    """Concatenate a cell's partial files without re-encoding (Manim's own combine_files pattern); returns frames."""
    import av
    manifest = "".join(f"file 'file:{p}'\n" for p in paths).encode()
    src = av.open(io.BytesIO(manifest), options={"safe": "0", "an": "1"}, format="concat")
    dst = av.open(str(out), mode="w")
    stream = dst.add_stream_from_template(src.streams.video[0])
    frames = 0
    for packet in src.demux(src.streams.video[0]):
        if packet.dts is None:
            continue
        packet.dts = None
        packet.stream = stream
        dst.mux(packet)
        frames += 1
    dst.close()
    src.close()
    return frames


def frames_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    worker(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), *map(int, sys.argv[4].split("-")))
