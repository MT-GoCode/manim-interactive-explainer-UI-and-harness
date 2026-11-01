"""Pass 1, in its own process: run the lesson in a dry run under the frame recorder and a read guard, and write what the
build checks and fingerprints to <out>/records.json, or the errors a lesson must see to <out>/errors.json.

    python -P -m explainers.pass1 <snapshot> <cache> <out> <ref-keys-json>

The first statement changes into the snapshot, before anything imports manim (Manim reads ./manim.cfg at import)."""
import os
import sys

if __name__ == "__main__":
    os.chdir(sys.argv[1])

import _posixsubprocess
import json
import re
import shutil
import tempfile
import threading
import time
from os.path import realpath
from pathlib import Path
from typing import Any

import explainers
from explainers.children import watch_parent
from explainers.config import check_render_config, render_config
from explainers.fingerprint import Recorder
from explainers.records import Records, dump

PACKAGE = Path(explainers.__file__).resolve().parent
REPO = PACKAGE.parent
READ_EVENTS = frozenset({"open", "os.listdir", "os.scandir", "glob.glob"})
# A child process reads files no audit event shows, so a lesson may start only TinyTeX's own programs (Manim's latex and
# dvisvgm calls).
SPAWN_EVENTS = frozenset({"os.posix_spawn", "os.exec"})  # with the program they start
NO_PROGRAM_EVENTS = frozenset({"os.fork", "os.forkpty", "os.system"})  # a shell or a copy of this process: refused
SYSTEM_ROOTS = ("/System", "/usr", "/Library", "/opt/homebrew", "/dev/null")
EXCLUSIVE_CREATE = os.O_CREAT | os.O_EXCL
TRACKER = re.compile(rb"from multiprocessing\.resource_tracker import main;main\(\d+\)")


def cannot_read(flags: int) -> bool:
    """An open that cannot return existing bytes: write-only, or an exclusive create (`tempfile` opens its files that way)."""
    return flags & os.O_ACCMODE == os.O_WRONLY or flags & EXCLUSIVE_CREATE == EXCLUSIVE_CREATE


def tracker(args: Any) -> bool:
    """multiprocessing's own resource tracker: Manim's `tqdm(disable=True)` makes a multiprocessing lock before it looks at
    `disable`, which starts it. An exact command that reads no bundle file."""
    tail = [os.fsencode(a) for a in args[-2:]]
    return len(tail) == 2 and tail[0] == b"-c" and TRACKER.fullmatch(tail[1]) is not None


class ReadGuard:
    """An audit hook, live only while `active`. It fails any read outside an exact allow-list of roots (raising in the audited
    call and listing the violation, so a try/except in lesson code cannot swallow it), and records which cache entries were
    opened or created and which bundle files and folders were read. Roots are compared after realpath: /tmp and /var are
    symlinks into /private."""

    def __init__(self, snapshot: Path, cache: Path, line_of: Any, source: str):
        self.cache = realpath(cache)
        self.snapshot = realpath(snapshot)
        self.tex = realpath(Path((REPO / ".tinytex" / "bin-path").read_text().strip()).parents[1])
        self.roots = tuple(realpath(p) for p in (snapshot, PACKAGE, sys.prefix, sys.base_prefix, REPO / ".tinytex", cache,
                                                 *SYSTEM_ROOTS))
        self.listing_roots = tuple(realpath(p) for p in sys.path if p)  # importlib scans every sys.path entry
        # NamedTemporaryFile creates its file through an opener, so the audited open names the folder; nothing inside it
        self.tempdir = realpath(tempfile.gettempdir())
        self.line_of, self.source = line_of, source
        self.active = False
        self.violations: list[str] = []
        self.cache_entries: set[str] = set()
        self.inputs: set[str] = set()
        self.quiet = threading.local()  # per thread: the guard's own stats (in realpath) are not the lesson's

    def own(self, path: str) -> str:
        """realpath without noting the stats it makes."""
        self.quiet.on = True
        try:
            return realpath(path)
        finally:
            self.quiet.on = False

    def __call__(self, event: str, args: tuple[Any, ...]) -> None:
        if not self.active:
            return
        if event == "subprocess.Popen":  # (executable, args, cwd, env); args is the list run, a shell's included
            self.started(args[0] or args[1][0])
            return
        if event in SPAWN_EVENTS:
            self.started(args[0])
            return
        if event in NO_PROGRAM_EVENTS:
            self.refuse(event)
        if event.startswith("socket."):  # what comes back is an input no key can cover
            self.violate("reached the network; a lesson reads only its own bundle")
            raise PermissionError("a lesson reads only its own bundle; it reached the network")
        if event not in READ_EVENTS:
            return
        path = "." if args[0] is None else args[0]  # a bare os.listdir() lists the current folder
        if not isinstance(path, (str, bytes, os.PathLike)):  # a file descriptor: already opened
            return
        p = self.own(os.fsdecode(path))
        if event == "open":
            if p.startswith(self.cache + os.sep):
                self.cache_entries.add(os.path.basename(p))
            if cannot_read(args[2]):  # only reads are checked or noted: Manim's SVGMobject writes beside its source file
                return
        self.note(p, listed=event != "open")
        listed_entry = event != "open" and p in self.listing_roots
        tempdir = event == "open" and p == self.tempdir
        if not (listed_entry or tempdir or any(p == r or p.startswith(r + os.sep) for r in self.roots)):
            self.violate(f"read {p}, outside the bundle; copy it into the bundle and read it from there")
            raise PermissionError(f"a lesson reads only files inside its own bundle; {p} is outside it")

    def note(self, p: str, listed: bool) -> None:
        """A bundle path the lesson depends on: a file it opened or stat'ed, or a folder it listed ("dir/")."""
        if p == self.snapshot or p.startswith(self.snapshot + os.sep):
            rel = os.path.relpath(p, self.snapshot)
            self.inputs.add(rel + "/" if listed else rel)

    def started(self, command: Any) -> None:
        """Refuse any child process but TinyTeX's programs: what a child reads is invisible to this guard."""
        program = self.own(shutil.which(os.fsdecode(command)) or os.fsdecode(command))
        if not program.startswith(self.tex + os.sep):
            self.refuse(program)

    def refuse(self, what: str) -> None:
        self.violate(f"started {what}; a lesson may not start other programs")
        raise PermissionError(f"a lesson may not start other programs; it started {what}")

    def violate(self, violation: str) -> None:
        line = self.line_of(self.source)
        self.violations.append(f"lesson.py:{line} {violation}" if line is not None else violation)

    def fork_exec(self, real: Any) -> Any:
        """_posixsubprocess.fork_exec checking its program: multiprocessing starts children through it with no audit event
        (subprocess binds it at import and is checked by its own audit event). Its second argument is the list of paths it
        will try for the program."""

        def checked(args: Any, executables: Any, *rest: Any) -> Any:
            if self.active and not tracker(args):
                for program in executables:
                    self.started(program)
            return real(args, executables, *rest)

        return checked

    def stat(self, real: Any) -> Any:
        """os.stat/os.lstat/os.access noting their path: CPython raises no audit event for these, yet `Path.exists()`,
        `.stat()` and `os.access()` decide what a lesson draws as surely as a read does."""

        def noted(path: Any, *args: Any, **kwargs: Any) -> Any:
            if self.active and not getattr(self.quiet, "on", False) and isinstance(path, (str, bytes, os.PathLike)):
                self.note(self.own(os.fsdecode(path)), listed=False)
            return real(path, *args, **kwargs)

        return noted


def format_refs(refs: list[dict], namespace: dict) -> tuple[dict[str, str], list[str]]:
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


def install_cost_clock(scene: Any, clock: Any = time.monotonic, tex: Any = None) -> list[float]:
    """Per play, the seconds since the scene began minus the time in exactly the calls exact fast-forward suppresses, and in TeX,
    which a worker never pays because it reads the warm cache: the build's estimate of what a fast-forward to that play costs
    (1.18-1.22x the real one, probes/p6.out)."""
    suppressed, cost = [0.0], []

    def timed(f: Any) -> Any:
        def wrapped(*a: Any, **k: Any) -> Any:
            t = clock()
            try:
                return f(*a, **k)
            finally:
                suppressed[0] += clock() - t
        return wrapped

    cam, renderer = scene.camera, scene.renderer
    cam.capture_mobjects, cam.reset = timed(cam.capture_mobjects), timed(cam.reset)
    cam.set_frame_to_background = timed(cam.set_frame_to_background)
    renderer.get_frame, renderer.file_writer.write_frame = timed(renderer.get_frame), timed(renderer.file_writer.write_frame)
    if tex:
        tex.compile_tex, tex.convert_to_svg = timed(tex.compile_tex), timed(tex.convert_to_svg)
    play, start = scene.play, clock()

    def timed_play(*a: Any, **k: Any) -> Any:
        cost.append(clock() - start - suppressed[0])
        return play(*a, **k)

    scene.play = timed_play
    return cost


def errors(out: Path, lines: list[str]) -> int:
    (out / "errors.json").write_text(json.dumps(lines))
    return 1


def main(argv: list[str]) -> int:
    snapshot, cache, out, keys = Path(argv[0]), Path(argv[1]), Path(argv[2]), json.loads(argv[3])
    watch_parent()  # before the import: a build killed during it still ends this process
    from manim import config
    from manim.utils import tex_file_writing

    from explainers.lesson import LessonError, _lesson_line, exec_lesson, record_creation_lines

    source = str(snapshot / "lesson.py")
    guard = ReadGuard(snapshot, cache, _lesson_line, source)
    sys.addaudithook(guard)
    os.stat, os.lstat, os.access = guard.stat(os.stat), guard.stat(os.lstat), guard.stat(os.access)
    _posixsubprocess.fork_exec = guard.fork_exec(_posixsubprocess.fork_exec)
    render_config()
    config.update({"dry_run": True, "media_dir": str(out / "media"), "tex_dir": str(cache / "tex"),
                   "text_dir": str(cache / "text")})
    record_creation_lines(source)
    before, failure = set(sys.modules), None
    guard.active = True
    try:
        module, cls = exec_lesson(snapshot, (snapshot / "lesson.py").read_bytes())
        cls.RECORDING, cls.RECORDER = True, Recorder
        scene = cls()
        cost = install_cost_clock(scene, tex=tex_file_writing)
        scene.render()
        refs, ref_errors = format_refs(keys, vars(module))  # under the guard: a __format__ may read
    except (Exception, SystemExit) as e:  # routed below: the guard's own mark first, then an authoring error, then a real crash
        failure = e
    finally:
        guard.active = False
    if guard.violations:  # whether or not lesson code caught the PermissionError
        return errors(out, list(dict.fromkeys(guard.violations)))
    if isinstance(failure, LessonError):
        return errors(out, [str(failure)])
    if failure is not None:
        raise failure
    check_render_config()
    repo = {"explainers/lesson.py"} | {str(Path(sys.modules[m].__file__).resolve().relative_to(REPO))
                                       for m in set(sys.modules) - before if m.startswith("explainers.")}
    dump(Records(scene._cells, refs, ref_errors, sorted(guard.inputs), sorted(repo), sorted(guard.cache_entries), cost,
                 (config.frame_width, config.frame_height)), out / "records.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
