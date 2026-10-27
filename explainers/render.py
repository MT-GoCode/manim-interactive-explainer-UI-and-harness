"""Pass 2: render a checked lesson into one clip per cell, in parallel chunks.

The width comes from measured per-worker peaks (DECISIONS: one encoder thread keeps a worker at ~1 core); each
worker renders a contiguous range of animations, fast-forwarding the ones before it without drawing them."""
import hashlib
import io
import os
import shutil
import subprocess
import sys
import threading
from math import floor
from pathlib import Path

ENCODER = {"threads": "1", "g": "6", "crf": "18", "preset": "veryfast"}  # g 6: worst seek 9.7 ms (DECISIONS)
FPS, WIDTH, HEIGHT = 30, 1920, 1080
WORKER_CORES, WORKER_RAM = 1.1, 0.7 * 2**30  # measured peaks of one worker (DECISIONS)
SEED = 0  # every process draws the same random numbers, so chunks and pass 1 agree


def width(cores: int, ram: int, cells: int) -> int:
    """How many workers fit in half the machine, by their measured peaks; never more than there are cells."""
    return max(1, min(floor(0.5 * cores / WORKER_CORES), floor(0.5 * ram / WORKER_RAM), cells))


def chunks(durations: list[float], k: int, cuttable: list[bool]) -> list[list[int]]:
    """Cut the cells (by index) into at most k contiguous runs of near-equal video length: for j = 1..k-1, cut after
    the cell whose running total is nearest j·total/k (ties to the earlier cell), among cells after which a cut is
    allowed (the next cell is cuttable); no run is empty."""
    total, run, cuts = sum(durations), 0.0, []
    sums = []
    for d in durations:
        run += d
        sums.append(run)
    allowed = [i for i in range(len(sums) - 1) if cuttable[i + 1]]
    for j in range(1, k):
        if not allowed:
            break
        target = j * total / k
        i = min(allowed, key=lambda i: (abs(sums[i] - target), i))
        if not cuts or i > cuts[-1]:
            cuts.append(i)
    bounds = [-1] + cuts + [len(durations) - 1]
    return [list(range(a + 1, b + 1)) for a, b in zip(bounds, bounds[1:])]


def worker(bundle: Path, first: int, last: int, media: Path) -> None:
    """One chunk, in its own interpreter. TeX is deliberately not on PATH: the warm caches from pass 1 must hit.
    Each worker reads private copies of them: even on a hit, Manim writes and deletes a temp SVG in the cache dir."""
    from manim import tempconfig
    from explainers.build import exec_lesson, manim_config
    shared = manim_config(bundle)
    for key in ("tex_dir", "text_dir"):
        if Path(shared[key]).exists():
            shutil.copytree(shared[key], media / key)
        shared[key] = str(media / key)
    _, cls = exec_lesson(bundle, (bundle / "build" / ".lesson.py").read_bytes())
    with tempconfig({**shared, "from_animation_number": first, "upto_animation_number": last,
                     "media_dir": str(media), "pixel_width": WIDTH, "pixel_height": HEIGHT, "frame_rate": FPS,
                     "disable_caching": True, "video_encoder_options": ENCODER}):
        cls().render()


def _watch_parent() -> None:
    parent = os.getppid()

    def watch():
        while True:
            threading.Event().wait(1)
            if os.getppid() != parent:  # the build died; a worker must not outlive it
                os._exit(1)
    threading.Thread(target=watch, daemon=True).start()


def render(bundle: Path, lock_fd: int, cells, k: int) -> tuple[dict[int, Path], list[list[int]]]:
    """Render every animation; returns ({global animation index: partial file}, the chunks of cell indices)."""
    media = bundle / "build" / ".media"
    shutil.rmtree(media, ignore_errors=True)
    groups = chunks([sum(c.run_times) for c in cells], k, [c.cuttable for c in cells])
    starts = [c.first_anim for c in cells] + [cells[-1].first_anim + len(cells[-1].run_times)]
    env = {**os.environ, "PATH": os.pathsep.join(p for p in os.environ["PATH"].split(os.pathsep) if ".tinytex" not in p)}
    procs = []
    for n, g in enumerate(groups):
        first, last = starts[g[0]], starts[g[-1] + 1] - 1
        out = media / f"chunk-{n}"
        out.mkdir(parents=True)
        log = open(out / "stderr.log", "w")
        p = subprocess.Popen([sys.executable, "-m", "explainers.render", str(bundle), str(first), str(last), str(out)],
                             stdout=log, stderr=log, pass_fds=(lock_fd,), env=env)
        procs.append((p, first, last, out))
    failed = threading.Event()
    first_failure: list = []

    def wait(p, out):
        if p.wait() != 0 and not failed.is_set():
            failed.set()
            first_failure.append(out)
            for q, *_ in procs:
                q.kill()
    waiters = [threading.Thread(target=wait, args=(p, out)) for p, _, _, out in procs]
    for t in waiters:
        t.start()
    for t in waiters:
        t.join()
    if first_failure:
        from explainers.build import BuildError
        raise BuildError(1, ["render failed:", (first_failure[0] / "stderr.log").read_text().rstrip()])
    parts: dict[int, Path] = {}
    for _, first, last, out in procs:
        found = {int(f.name[9:14]): f for f in out.rglob("uncached_*.mp4")}
        assert set(found) == set(range(first, last + 1)), f"chunk {first}-{last} produced {sorted(found)}"
        parts.update(found)
    return parts, groups


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
    _watch_parent()
    worker(Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4]))
