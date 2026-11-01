"""Pass 2: render a checked lesson into one clip per cell, in parallel chunks.

    python -P -m explainers.render <snapshot> <cache> <out> <first-last>...

Each worker runs from the build's snapshot of the bundle and renders contiguous animation ranges, fast-forwarding the ones
before each without drawing them. The first statement changes into the snapshot, before anything imports manim (Manim reads
./manim.cfg at import). The width comes from measured per-worker peaks (DECISIONS: one encoder thread keeps a worker at ~1
core)."""
import os
import sys

if __name__ == "__main__":
    os.chdir(sys.argv[1])

import hashlib
import io
import json
import shutil
import time
from math import floor
from pathlib import Path

from explainers.children import Job, child_env, run_all, watch_parent
from explainers.config import check_render_config, render_config

WORKER_CORES, WORKER_RAM = 1.22, 0.59 * 2**30  # measured peaks of one worker with the tee (DECISIONS)


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


def to_render(reusable: set[int], n: int) -> list[int]:
    return sorted(set(range(n)) - reusable)


def worker(snapshot: Path, cache: Path, out: Path, ranges: list[tuple[int, int]]) -> None:
    """One chunk: one scene per contiguous animation range (a chunk may span reused cells). TeX is not on PATH: the warm cache
    from pass 1 must hit. The worker reads a private copy of it: even on a hit, Manim writes and deletes a temp SVG in the
    cache dir. The folders are set before the lesson runs, because a lesson may make TeX at import time."""
    watch_parent()  # before the import: a build killed during it still ends this worker
    from manim import config, tempconfig

    from explainers import hooks
    from explainers.fingerprint import Tee
    from explainers.lesson import exec_lesson
    render_config()
    for name in ("tex", "text"):
        if (cache / name).exists():
            shutil.copytree(cache / name, out / name)
    config.update({"tex_dir": str(out / "tex"), "text_dir": str(out / "text")})
    _, cls = exec_lesson(snapshot, (snapshot / "lesson.py").read_bytes())
    cls.RECORDER = Tee
    report = []
    for j, (first, last) in enumerate(ranges):
        with tempconfig({"from_animation_number": first, "upto_animation_number": last,
                         "media_dir": str(out / f"range-{j}")}):  # what a lesson sets mid-scene ends with its range
            scene = cls()
            hooks.exact_fast_forward(scene)
            play, started, forwarded, times = scene.play, time.monotonic(), [None], {}

            def stamped(*a, **k):
                n, t = scene.renderer.num_plays, time.monotonic()
                if n == first:
                    forwarded[0] = t - started
                try:
                    return play(*a, **k)
                finally:
                    if first <= n <= last:
                        times[n] = time.monotonic() - t

            scene.play = stamped
            scene.render()
            check_render_config()
        digests, partials = [d for c in scene._cells for d in c.drawn], hooks.partial_files(scene)
        report.append({"first": first, "fast_forward_s": forwarded[0],
                       "plays": [{"anim": n, "digest": digests[n], "partial": str(partials[n]), "render_s": times[n]}
                                 for n in sorted(times)]})
    (out / "report.json").write_text(json.dumps({"ranges": report}))


def runs(cells: list[int]) -> list[list[int]]:
    """Sorted cell indices split into maximal runs of consecutive ones."""
    out: list[list[int]] = []
    for n in cells:
        if out and out[-1][-1] == n - 1:
            out[-1].append(n)
        else:
            out.append([n])
    return out


def render(snapshot: Path, cache: Path, cells, todo: list[int], k: int):
    """Render the animations of the cells in todo; returns each chunk's report, the chunks of cell indices, and each
    worker's peaks. A worker that exited 0 with no report has an empty one: the build's verify names its first missing play."""
    media = snapshot.parent
    groups = [[todo[i] for i in g] for g in chunks([sum(cells[n].run_times) for n in todo], k, [True] * len(todo))]
    starts = [c.first_anim for c in cells] + [cells[-1].first_anim + len(cells[-1].run_times)]
    ranges = [[(starts[r[0]], starts[r[-1] + 1] - 1) for r in runs(g)] for g in groups]
    jobs = [Job("explainers.render", [str(snapshot), str(cache), str(media / f"chunk-{n}"), *(f"{a}-{b}" for a, b in rs)],
                media / f"chunk-{n}") for n, rs in enumerate(ranges)]
    path = os.pathsep.join(p for p in os.environ["PATH"].split(os.pathsep) if ".tinytex" not in p)
    done = run_all(jobs, k, child_env(path))
    paths = [job.out / "report.json" for job in jobs]
    return [json.loads(p.read_text()) if p.exists() else {"ranges": []} for p in paths], groups, done


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
    worker(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), [tuple(map(int, r.split("-"))) for r in sys.argv[4:]])
