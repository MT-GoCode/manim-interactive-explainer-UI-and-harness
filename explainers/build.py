"""explain-build <bundle>: lock, snapshot, pass 1 in its own process, checks, render the cells whose fingerprints changed,
commit. This process never imports manim."""
import fcntl
import hashlib
import importlib.metadata
import json
import os
import shutil
import sys
import time
from pathlib import Path

from explainers.cells import read_cells
from explainers.children import ChildFailed, Job, child_env, run_all
from explainers.config import FPS, WIDTH
from explainers.geometry import check as geometry
from explainers.records import load
from explainers.render import frames_sha, join, render, runs, to_render, width

REPO = Path(__file__).resolve().parents[1]
PICTURE_CODE = REPO / "explainers"  # repo code that can change a picture (the base class; parts.py later)


class BuildError(Exception):
    def __init__(self, code: int, lines: list[str]):
        super().__init__("\n".join(lines))
        self.code, self.lines = code, lines


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def pairing(sections, cells) -> list[str]:
    """Every way cells.md headings and self.cell() calls disagree, in this order: duplicates, set differences,
    then (only when the sets agree) the first position where the order differs."""
    errs, seen = [], set()
    for s in sections:
        if s["slug"] in seen:
            errs.append(f'duplicate heading "## {s["slug"]}" (cells.md:{s["line"]})')
        seen.add(s["slug"])
    seen = set()
    for c in cells:
        if c.slug in seen:
            errs.append(f'duplicate self.cell("{c.slug}") (lesson.py:{c.line})')
        seen.add(c.slug)
    heads, calls = [s["slug"] for s in sections], [c.slug for c in cells]
    errs += [f'cells.md has "## {s["slug"]}" (cells.md:{s["line"]}) but lesson.py has no self.cell("{s["slug"]}")'
             for s in sections if s["slug"] not in calls]
    errs += [f'lesson.py has self.cell("{c.slug}") (lesson.py:{c.line}) but cells.md has no "## {c.slug}"'
             for c in cells if c.slug not in heads]
    if not errs and heads != calls:
        n = next(i for i, (a, b) in enumerate(zip(heads, calls)) if a != b)
        errs.append(f'order differs at cell {n + 1}: cells.md "## {heads[n]}", lesson.py self.cell("{calls[n]}")')
    return errs


def acquire(bundle: Path):
    missing = [str(bundle / n) for n in ("lesson.py", "cells.md") if not (bundle / n).is_file()]
    if missing:
        raise BuildError(2, [f"missing {p}" for p in missing])
    build = bundle / "build"
    build.mkdir(exist_ok=True)
    lock = open(build / ".lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise BuildError(3, [f"another explain-build is running on {bundle}"])
    os.set_inheritable(lock.fileno(), True)  # every child holds the build lock until it exits
    return lock


def snapshot(bundle: Path) -> Path:
    """The bundle as this build sees it, copied once before pass 1: pass 1, the cells.md read and every worker use these
    bytes, whatever is edited meanwhile. No __pycache__ at any level: a copied .pyc keeps its mtime and stays valid, so the
    import would never open the source and an edit to that helper would go unseen. A dangling link (an editor's lock file) is
    skipped by its real place: copytree's own flag resolves links against the cwd."""
    media = bundle / "build" / ".media"
    shutil.rmtree(media, ignore_errors=True)
    shutil.copytree(bundle, media / "src", ignore=lambda d, names: [
        n for n in names if n == "__pycache__" or (d == str(bundle) and n in ("build", "comments.json"))
        or not os.path.exists(os.path.join(d, n))])
    return media / "src"


def cache_id() -> str:
    """The TeX/text cache is keyed by the tools that fill it (vendored from presenters): Manim keys entries on text and
    template only, so a Pango or TeX upgrade would otherwise keep old glyphs forever."""
    import manimpango
    parts = [manimpango.__version__, manimpango.pango_version(), manimpango.cairo_version(),
             sha256((REPO / ".tinytex" / "TinyTeX" / "tlpkg" / "texlive.tlpdb").read_bytes())]
    return sha256("\n".join(parts).encode())[:16]


def merge_cache(private: Path, shared: Path) -> None:
    """Only the parent writes the shared cache: each new entry, temp-written then renamed. Entries are content-addressed by
    file name, so the merge is idempotent."""
    for f in private.rglob("*"):
        dst = shared / f.relative_to(private)
        if f.is_file() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_name(f".tmp-{os.getpid()}-{f.name}")
            shutil.copy2(f, tmp)
            os.replace(tmp, dst)


def prune_cache(shared: Path, used: list[str]) -> None:
    """After commit: keep only the entries pass 1 opened or created, so the cache never grows past what the lesson uses."""
    keep = set(used)
    for f in shared.rglob("*"):
        if f.is_file() and f.name not in keep:
            f.unlink()


def fingerprints(drawn: list[list[str]], inputs: dict) -> list[str]:
    """Per cell: its frames as pass 1 recorded them (per animation), and everything after the frames that shapes the
    clip's bytes: the picture code and bundle files it ran with, how frames are digested (fingerprint.py), how they
    are encoded (config.py) and joined (render.py), and the drawing and encoding libraries."""
    import cairo
    after = json.dumps({"inputs": inputs,
                        "code": {n: sha256((PICTURE_CODE / n).read_bytes()) for n in ("fingerprint.py", "render.py",
                                                                                     "config.py")},
                        "versions": {d: importlib.metadata.version(d) for d in ("manim", "numpy", "pycairo", "av", "pillow")}
                        | {"cairo": cairo.cairo_version_string()}}, sort_keys=True)
    return [sha256(json.dumps([after, d]).encode()) for d in drawn]


def failed(what: str, e: ChildFailed) -> BuildError:
    stderr = (e.job.out / "stderr").read_text(errors="replace").rstrip()
    return BuildError(1, [f"{what} failed: exit code {e.code}"] + [stderr] * bool(stderr))


def check(snap: Path, shared: Path) -> dict:
    """Pass 1 and every check that needs no frames. Returns what the render pass and the report use."""
    cells = read_cells(snap / "cells.md")
    if cells.errors:  # known before the scene runs: fail fast
        raise BuildError(1, cells.errors)
    pass1 = snap.parent / "pass1"
    private = pass1 / "cache"
    shutil.copytree(shared, private)
    keys = [{"key": r["key"], "line": r["line"]} for r in cells.refs]
    tex = (REPO / ".tinytex" / "bin-path").read_text().strip()
    try:
        run_all([Job("explainers.pass1", [str(snap), str(private), str(pass1), json.dumps(keys)], pass1)], 1,
                child_env(tex + os.pathsep + os.environ["PATH"]))
    except ChildFailed as e:
        if (pass1 / "errors.json").exists():  # marked by pass 1: what the author must see, and nothing else
            raise BuildError(1, json.loads((pass1 / "errors.json").read_text()))
        raise failed("pass 1", e)
    if not (pass1 / "records.json").exists():
        raise BuildError(1, ["pass 1 exited with no result: a lesson must not end its own process"])
    recs = load(pass1 / "records.json")
    merge_cache(private, shared)
    errs = [f'cell "{c.slug}" has no animation (lesson.py:{c.line})' for c in recs.cells if not c.run_times]
    errs += pairing(cells.sections, recs.cells)
    if errs + recs.ref_errors:
        raise BuildError(1, errs + recs.ref_errors)
    if errs := geometry(recs.cells, *recs.frame, WIDTH):
        raise BuildError(1, errs)
    # lesson.py stays out: lesson_sha covers it, and per-cell digests decide what re-renders
    inputs = {"bundle": {p: sha256((snap / p).read_bytes()) for p in recs.inputs
                         if not p.endswith("/") and p != "lesson.py" and (snap / p).is_file()},
              "repo": {p: sha256((REPO / p).read_bytes()) for p in recs.repo}}
    return {"lesson_sha": sha256((snap / "lesson.py").read_bytes()), "cells": recs.cells, "refs": recs.refs, "inputs": inputs,
            "fingerprints": fingerprints([c.drawn for c in recs.cells], inputs),
            "manim_version": importlib.metadata.version("manim"), "repo_root": str(REPO),
            "cache_entries": recs.cache_entries}


def report(bundle: Path, rec: dict) -> str:
    cells = rec["cells"]
    width = max(len(c.slug) for c in cells)
    out = [f"{bundle.name} · {len(cells)} cells · lesson {rec['lesson_sha'][:12]}"]
    for i, c in enumerate(cells, 1):
        n = len(c.run_times)
        out.append(f"  {i:>2}  {c.slug:<{width}}  {n} animation{'s' if n != 1 else ' '}  {sum(c.run_times):5.2f} s"
                   f"   (lesson.py:{c.line})")
    out += [f"refs:   {k} = {v}" for k, v in rec["refs"].items()] or ["refs:   none"]
    files = [f"{k}/{p} {h[:12]}" for k in ("bundle", "repo") for p, h in sorted(rec["inputs"][k].items())]
    out.append("inputs: " + "; ".join(files + [f"manim {rec['manim_version']}"]))
    return "\n".join(out)


def previous_index(bundle: Path) -> dict:
    path = bundle / "build" / "index.json"
    return json.loads(path.read_text()) if path.exists() else {"cells": []}


def reusable(bundle: Path, fingerprints: list[str], previous: dict) -> dict[int, dict]:
    """{cell: the previous build's cell} where the fingerprints are equal and its clip on disk still has the bytes
    that build recorded. A previous cell without a fingerprint is never reusable."""
    old = {c["fingerprint"]: c for c in previous["cells"] if "fingerprint" in c}
    clip = lambda c: bundle / "build" / c["clip"]
    return {n: old[f] for n, f in enumerate(fingerprints)
            if f in old and clip(old[f]).is_file() and frames_sha(clip(old[f])) == old[f]["frames_sha"]}


def commit(bundle: Path, rec: dict, parts: dict[int, Path], reused: dict[int, dict], previous: dict) -> Path:
    """Write each rendered cell's clip under its content hash (a reused cell keeps its previous clip), then index.json
    last and atomically: a reader always sees a whole old build or a whole new one. Clips of neither the new nor the
    previous build are deleted."""
    import jsonschema
    build = bundle / "build"
    clips = build / "clips"
    clips.mkdir(exist_ok=True)
    index_path = build / "index.json"
    cells = []
    for n, (c, fingerprint) in enumerate(zip(rec["cells"], rec["fingerprints"])):
        if n in reused:
            old = reused[n]
            cells.append({"slug": c.slug, "clip": old["clip"], "frames_sha": old["frames_sha"], "frames": old["frames"],
                          "fingerprint": fingerprint})
            continue
        tmp = clips / f".tmp-{n}.mp4"
        frames = join([parts[i] for i in range(c.first_anim, c.first_anim + len(c.run_times))], tmp)
        sha = frames_sha(tmp)
        os.replace(tmp, clips / f"{sha}.mp4")
        cells.append({"slug": c.slug, "clip": f"clips/{sha}.mp4", "frames_sha": sha, "frames": frames,
                      "fingerprint": fingerprint})
    index = {"format": "explainer", "version": 1, "lesson_sha": rec["lesson_sha"], "inputs": rec["inputs"],
             "repo_root": rec["repo_root"], "manim_version": rec["manim_version"], "fps": FPS, "refs": rec["refs"],
             "cells": cells}
    if peak := rec["worker_peak"] or previous.get("worker_peak"):  # a build that rendered nothing keeps the last one
        index["worker_peak"] = peak
    jsonschema.validate(index, json.loads((REPO / "schema" / "index.schema.json").read_text()))
    tmp = build / "index.json.tmp"
    tmp.write_text(json.dumps(index, indent=1) + "\n")
    os.replace(tmp, index_path)
    keep = {c["clip"] for c in cells + previous["cells"]}
    for f in clips.glob("*"):  # glob matches dotfiles, so stale .tmp-* go too
        if f"clips/{f.name}" not in keep:
            f.unlink()
    return index_path


def build(bundle: Path, k: int | None = None) -> tuple[dict, Path]:
    """Check, render the cells whose fingerprints changed in k chunks (default: as many as half the machine holds), commit.
    The lock comes first and outside the try: a refused second build cannot delete the running build's snapshot."""
    lock = acquire(bundle)
    t = [time.monotonic()]
    try:
        snap = snapshot(bundle)
        shared = bundle / "build" / "cache" / cache_id()
        shared.mkdir(parents=True, exist_ok=True)
        for other in shared.parent.iterdir():
            if other != shared:
                shutil.rmtree(other) if other.is_dir() else other.unlink()  # Finder leaves .DS_Store here
        rec = check(snap, shared)
        t.append(time.monotonic())
        previous = previous_index(bundle)
        reused = reusable(bundle, rec["fingerprints"], previous)
        todo = to_render(set(reused), [c.cuttable for c in rec["cells"]])
        rec["pulled_in"] = sum(n in reused for n in todo)
        reused = {n: c for n, c in reused.items() if n not in todo}
        k = k or width(os.cpu_count(), _ram(), len(todo))
        try:
            parts, rec["chunks"], done = render(snap, shared, rec["cells"], todo, k) if todo else ({}, [], [])
        except ChildFailed as e:
            raise failed("render", e)
        rec["worker_peak"] = {"rss": max(d.rss for d in done), "cores": max(d.cores for d in done)} if done else None
        rec["rendered"] = todo
        t.append(time.monotonic())
        index = commit(bundle, rec, parts, reused, previous)
        prune_cache(shared, rec["cache_entries"])
        t.append(time.monotonic())
        rec["timing"] = [b - a for a, b in zip(t, t[1:])]
        return rec, index
    finally:
        shutil.rmtree(bundle / "build" / ".media", ignore_errors=True)


def _ram() -> int:
    return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")


def render_line(rec: dict) -> str:
    """e.g. "render: 3 cells (4–5, 9) in 2 chunks · 27 reused", or "render: 10 cells (1–10; 9 pulled in by a live
    updater) in 1 chunk · 20 reused"; cells numbered from 1."""
    todo, k, pulled = rec["rendered"], len(rec["chunks"]), rec["pulled_in"]
    reused = f" · {len(rec['cells']) - len(todo)} reused"
    if not todo:
        return "render: 0 cells" + reused
    spans = ", ".join(f"{r[0] + 1}–{r[-1] + 1}" if len(r) > 1 else f"{r[0] + 1}" for r in runs(todo))
    spans += f"; {pulled} pulled in by a live updater" * (pulled > 0)
    return f"render: {len(todo)} cell{'s' * (len(todo) != 1)} ({spans}) in {k} chunk{'s' * (k != 1)}" + reused


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: explain-build <bundle>", file=sys.stderr)
        return 2
    bundle = Path(args[0]).expanduser().resolve()
    try:
        rec, index = build(bundle)
    except BuildError as e:
        print("\n".join(f"error: {l}" for l in e.lines), file=sys.stderr)
        return e.code
    print(report(bundle, rec))
    print(render_line(rec))
    print("timing: check {:.2f} s · render {:.2f} s · commit {:.2f} s".format(*rec["timing"]))
    print(f"built  {index}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
