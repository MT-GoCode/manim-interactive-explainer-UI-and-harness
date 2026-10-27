"""explain-build <bundle>: check a lesson and (from stratum 2) render it."""
import fcntl
import hashlib
import json
import os
import sys
import types
from pathlib import Path

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


def format_refs(refs, namespace: dict) -> tuple[dict[str, str], list[str]]:
    """{key: formatted value}; key is the exact text between the braces, e.g. "p_top:.4f"."""
    values, errs = {}, []
    for r in refs:
        name, _, fmt = r["key"].partition(":")
        if name not in namespace:
            errs.append(f"unknown ref {{{r['key']}}} (cells.md:{r['line']})")
            continue
        try:
            values[r["key"]] = format(namespace[name], fmt)
        except (ValueError, TypeError) as e:
            errs.append(f"bad format {{{r['key']}}} (cells.md:{r['line']}): {e}")
    return values, errs


def manim_config(bundle: Path) -> dict:
    """Settings both passes share: the same random numbers, the warm TeX and text caches, every partial kept."""
    build = bundle / "build"
    return {"seed": 0, "tex_dir": str(build / ".tex"), "text_dir": str(build / ".text"), "max_files_cached": -1,
            "verbosity": "ERROR", "progress_bar": "none"}


def exec_lesson(bundle: Path, src: bytes):
    """Compile lesson.py's bytes (read once) under its own path, so lines and tracebacks point at lesson.py."""
    from explainers.lesson import Lesson
    sys.dont_write_bytecode = True  # importing bundle helpers must not write __pycache__ into the bundle
    path = str(bundle / "lesson.py")
    sys.path.insert(0, str(bundle))
    module = types.ModuleType("lesson")
    module.__file__ = path
    sys.modules["lesson"] = module
    exec(compile(src, path, "exec"), module.__dict__)
    found = [v for v in vars(module).values()
             if isinstance(v, type) and issubclass(v, Lesson) and v.__module__ == "lesson"]
    if len(found) != 1:
        raise BuildError(1, [f"lesson.py must define exactly one Lesson subclass; found "
                             f"{[c.__name__ for c in found] or 'none'}"])
    found[0].SOURCE = path
    return module, found[0]


def _inputs(bundle: Path, modules: set[str], opened: set[Path]) -> dict[str, dict[str, str]]:
    """The files that can change a picture: bundle files the lesson imported or opened, and the picture code."""
    out = {"bundle": {}, "repo": {}}
    files = {Path(f).resolve() for n in modules if (f := getattr(sys.modules.get(n), "__file__", None))} | opened
    for p in files:
        if p.is_relative_to(bundle) and not p.is_relative_to(bundle / "build"):
            out["bundle"][str(p.relative_to(bundle))] = sha256(p.read_bytes())
        elif p.is_relative_to(PICTURE_CODE):
            out["repo"][str(p.relative_to(REPO))] = sha256(p.read_bytes())
    return out


def check(bundle: Path) -> dict:
    """Pass 1 and every check that needs no frames. Returns what the render pass and the report use."""
    from manim import __version__ as manim_version, config, tempconfig
    from explainers.cells import read_cells
    from explainers.geometry import check as geometry
    from explainers.lesson import LessonError, record_creation_lines
    from explainers.render import WIDTH

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
    src = (bundle / "lesson.py").read_bytes()
    (build / ".lesson.py").write_bytes(src)  # the exact bytes every render worker runs (lesson.py may change meanwhile)
    cells = read_cells(bundle / "cells.md")  # read at once, with lesson.py, not after the run
    if cells.errors:  # known before the scene runs: fail fast
        raise BuildError(1, cells.errors)
    os.environ["PATH"] = (REPO / ".tinytex" / "bin-path").read_text().strip() + os.pathsep + os.environ["PATH"]

    opened: set[Path] = set()

    def note_open(event, args):
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            p = Path(os.fsdecode(args[0])).resolve()
            if p.is_relative_to(bundle) and p.suffix != ".pyc" and p.is_file():
                opened.add(p)

    sys.addaudithook(note_open)
    before = set(sys.modules)
    record_creation_lines(str(bundle / "lesson.py"))
    module, cls = exec_lesson(bundle, src)
    cls.RECORDING = True
    try:
        # The scene is constructed inside the config: Scene.__init__ reads its output settings from it.
        with tempconfig({**manim_config(bundle), "dry_run": True, "media_dir": str(build / ".media")}):
            scene = cls()
            scene.render()
            frame = config.frame_width, config.frame_height
    except LessonError as e:
        raise BuildError(1, [str(e)])
    errs = [f'cell "{c.slug}" has no animation (lesson.py:{c.line})' for c in scene._cells if not c.run_times]
    errs += pairing(cells.sections, scene._cells)
    refs, ref_errs = format_refs(cells.refs, vars(module))
    if errs + ref_errs:
        raise BuildError(1, errs + ref_errs)
    if errs := geometry(scene._cells, *frame, WIDTH):
        raise BuildError(1, errs)
    return {"lock": lock, "lesson_sha": sha256(src), "cells": scene._cells, "refs": refs,
            "inputs": _inputs(bundle, set(sys.modules) - before - {"lesson"} | {"explainers.lesson"}, opened),
            "manim_version": manim_version, "repo_root": str(REPO)}


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


def commit(bundle: Path, rec: dict, parts: dict[int, Path]) -> Path:
    """Write each cell's clip under its content hash, then index.json last and atomically: a reader always sees a
    whole old build or a whole new one. Clips of neither the new nor the previous build are deleted."""
    import jsonschema
    from explainers.render import frames_sha, join
    build = bundle / "build"
    clips = build / "clips"
    clips.mkdir(exist_ok=True)
    index_path = build / "index.json"
    previous = json.loads(index_path.read_text()) if index_path.exists() else {"cells": []}
    cells = []
    for n, c in enumerate(rec["cells"]):
        tmp = clips / f".tmp-{n}.mp4"
        frames = join([parts[i] for i in range(c.first_anim, c.first_anim + len(c.run_times))], tmp)
        sha = frames_sha(tmp)
        os.replace(tmp, clips / f"{sha}.mp4")
        cells.append({"slug": c.slug, "clip": f"clips/{sha}.mp4", "frames_sha": sha, "frames": frames})
    index = {"format": "explainer", "version": 1, "lesson_sha": rec["lesson_sha"], "inputs": rec["inputs"],
             "repo_root": rec["repo_root"], "manim_version": rec["manim_version"], "refs": rec["refs"], "cells": cells}
    jsonschema.validate(index, json.loads((REPO / "schema" / "index.schema.json").read_text()))
    tmp = build / "index.json.tmp"
    tmp.write_text(json.dumps(index, indent=1) + "\n")
    os.replace(tmp, index_path)
    keep = {c["clip"] for c in cells + previous["cells"]}
    for f in clips.glob("*"):  # glob matches dotfiles, so stale .tmp-* go too
        if f"clips/{f.name}" not in keep:
            f.unlink()
    return index_path


def build(bundle: Path) -> tuple[dict, Path]:
    import shutil
    import time
    from explainers.render import render, width
    t = [time.monotonic()]
    rec = check(bundle)
    t.append(time.monotonic())
    try:
        k = width(os.cpu_count(), _ram(), len(rec["cells"]))
        parts, groups = render(bundle, rec["lock"].fileno(), rec["cells"], k)
        rec["chunks"] = groups
        t.append(time.monotonic())
        index = commit(bundle, rec, parts)
        t.append(time.monotonic())
        rec["timing"] = [b - a for a, b in zip(t, t[1:])]
        return rec, index
    finally:
        shutil.rmtree(bundle / "build" / ".media", ignore_errors=True)


def _ram() -> int:
    return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")


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
    runs = ", ".join(f"{g[0] + 1}–{g[-1] + 1}" if len(g) > 1 else f"{g[0] + 1}" for g in rec["chunks"])
    print(f"render: {len(rec['chunks'])} chunk{'s' * (len(rec['chunks']) != 1)} (cells {runs})")
    print("timing: check {:.2f} s · render {:.2f} s · commit {:.2f} s".format(*rec["timing"]))
    print(f"built  {index}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
