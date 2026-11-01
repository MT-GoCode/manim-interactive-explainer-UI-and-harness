"""The build's child processes (vendored from presenters' build.py and talk.py): each runs in its own process group, in a
fixed environment, with its output in files, and dies with the build."""
import contextlib
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

# The only variables a child sees: a caller's environment is not an input of any clip.
CHILD_ENV = ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE", "PYTHONPATH")


def child_env(path: str) -> dict[str, str]:
    return {**{k: os.environ[k] for k in CHILD_ENV if k in os.environ}, "PATH": path, "PYTHONHASHSEED": "0"}


@dataclass(frozen=True)
class Done:
    rss: int      # peak RSS, bytes
    cores: float  # CPU seconds over wall seconds


@dataclass(frozen=True)
class Job:
    module: str
    args: list[str]
    out: Path


class ChildFailed(Exception):
    def __init__(self, job: Job, code: int):
        super().__init__(job.module)
        self.job, self.code = job, code  # negative: killed by that signal


def spawn(job: Job, env: dict[str, str]) -> int:
    """`python -P -m <module> args...`: -P keeps the caller's folder off sys.path. Output goes to files (pipes would
    deadlock a parent blocked in wait4), and its own process group lets its TeX children die with it."""
    job.out.mkdir(parents=True, exist_ok=True)
    actions = [(os.POSIX_SPAWN_OPEN, 1, str(job.out / "stdout"), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644),
               (os.POSIX_SPAWN_OPEN, 2, str(job.out / "stderr"), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)]
    return os.posix_spawn(sys.executable, [sys.executable, "-P", "-m", job.module, *job.args],
                          {**env, "EXPLAINERS_BUILD_PID": str(os.getpid())}, file_actions=actions, setsid=True)


def run_all(jobs: list[Job], width: int, env: dict[str, str]) -> list[Done]:
    """Run jobs with at most `width` alive. The first failure kills the rest and raises. Returns each job's peaks."""
    pending, alive, done = list(jobs), {}, []
    try:
        while pending or alive:
            while pending and len(alive) < width:
                job = pending.pop(0)
                alive[spawn(job, env)] = (job, time.monotonic())
            pid, status, usage = os.wait4(-1, 0)
            job, started = alive.pop(pid)
            done.append(Done(usage.ru_maxrss, (usage.ru_utime + usage.ru_stime) / max(time.monotonic() - started, 1e-6)))
            if code := os.waitstatus_to_exitcode(status):
                raise ChildFailed(job, code)
    finally:
        for pid in alive:
            with contextlib.suppress(PermissionError):  # macOS: EPERM for a group whose leader already exited
                os.killpg(pid, signal.SIGKILL)
        for pid in list(alive):
            os.waitpid(pid, 0)
    return done


def watch_parent() -> None:
    """A killed build never leaves a child writing into build/.media. The build's pid comes from the build itself: a child
    that started after its parent died would otherwise read launchd's pid as its parent and never notice."""
    parent = int(os.environ["EXPLAINERS_BUILD_PID"])

    def watch():
        while True:
            threading.Event().wait(1)
            if os.getppid() != parent:
                os.killpg(0, signal.SIGKILL)  # this child leads its group (setsid), which holds its TeX children
    threading.Thread(target=watch, daemon=True).start()
