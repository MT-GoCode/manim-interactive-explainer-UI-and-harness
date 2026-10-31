"""cells-tokens: each cell's whole source (minus its `## slug` line) in o200k_base tokens, the limit inclusive, and only
cells over it and files it could not check reported. Token counts below were measured once with gpt-tokenizer 4.1.0."""
import subprocess

import pytest

from conftest import REPO

# body -> o200k_base tokens: a long jargon word costs more than three short ones
SHORT, JARGON = ("One two three.\n", 4), ("Antidisestablishmentarianism.\n", 7)


def tokens(limit, *paths) -> tuple[int, list[str]]:
    r = subprocess.run([str(REPO / "bin" / "cells-tokens"), str(limit), *map(str, paths)], capture_output=True,
                       text=True)
    return r.returncode, r.stdout.splitlines() + r.stderr.splitlines()


def test_counts_and_inclusive_limit(tmp_path):
    (tmp_path / "cells.md").write_text(f"## short\n{SHORT[0]}\n## jargon\n{JARGON[0]}")
    assert tokens(JARGON[1], tmp_path) == (0, [f"1 of 1 files checked · 2 cells · 0 over {JARGON[1]} tokens"])
    # the blank line after SHORT belongs to its cell: "\n" adds no token to "three.\n\n" in o200k_base
    assert tokens(SHORT[1], tmp_path) == (1, [
        f"over  {tmp_path}/cells.md ## jargon (cells.md:4): {JARGON[1]} tokens",
        f"1 of 1 files checked · 2 cells · 1 over {SHORT[1]} tokens"])


def test_a_file_the_reader_rejects_is_not_checked(tmp_path):
    f = tmp_path / "cells.md"
    f.write_bytes(b"## a\r\nHi.\r\n")
    assert tokens(99, f) == (1, [f"could not check  {f}: cells.md has CR line endings; save it with LF only",
                                 "0 of 1 files checked · 0 cells · 0 over 99 tokens"])


def test_a_missing_file_is_reported_and_the_rest_still_checked(tmp_path):
    missing, ok = tmp_path / "none.explainer", tmp_path / "ok.md"
    ok.write_text(f"## a\n{JARGON[0]}")
    code, out = tokens(SHORT[1], missing, ok)
    assert code == 1
    assert out[0].startswith(f"could not check  {missing}: ENOENT")
    assert out[1:] == [f"over  {ok} ## a (ok.md:1): {JARGON[1]} tokens",
                       f"1 of 2 files checked · 1 cells · 1 over {SHORT[1]} tokens"]


@pytest.mark.parametrize("args", [[], ["150"], ["many", "x.md"]])
def test_bad_usage(args):
    r = subprocess.run([str(REPO / "bin" / "cells-tokens"), *args], capture_output=True, text=True)
    assert r.returncode == 2 and r.stderr.startswith("usage: cells-tokens")
