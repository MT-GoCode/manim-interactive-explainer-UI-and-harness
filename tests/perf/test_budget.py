"""The build stays within half the machine: the worker tree, sampled every second, never uses more than 50% of the
cores. Runs alone and last (./test perf), so nothing else competes for the CPU it measures."""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import psutil

REPO = Path(__file__).resolve().parents[2]


def test_long_lesson_build_uses_at_most_half_the_cores(tmp_path):
    b = tmp_path / "long.explainer"
    shutil.copytree(REPO / "tests" / "fixtures" / "long.explainer", b)
    p = psutil.Popen([str(REPO / "bin" / "explain-build"), str(b)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    samples = []
    procs: dict[int, psutil.Process] = {}
    while p.poll() is None:
        try:
            tree = [p] + p.children(recursive=True)
        except psutil.NoSuchProcess:  # the build ended between poll() and the walk
            break
        for c in tree:
            try:
                procs.setdefault(c.pid, c).cpu_percent(None)  # first call primes the counter
            except psutil.NoSuchProcess:  # a worker that has exited uses no more CPU
                procs.pop(c.pid, None)
        time.sleep(1)
        used = 0.0
        for c in list(procs.values()):
            try:
                used += c.cpu_percent(None)
            except psutil.NoSuchProcess:
                procs.pop(c.pid, None)
        samples.append(used / 100)
    out, err = p.communicate()
    assert p.returncode == 0, err
    print(*out.splitlines()[-3:-1], f"peak {max(samples):.1f} cores of {os.cpu_count()}", sep="\n")
    assert max(samples) <= 0.5 * os.cpu_count()
