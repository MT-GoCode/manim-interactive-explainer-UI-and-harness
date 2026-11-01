"""cells-tokens <max tokens> <bundle or cells.md>...: print each cell over <max tokens> (DeepSeek-V4 tokenizer)."""
import sys
from pathlib import Path

from tokenizers import Tokenizer

from explainers.cells import read_cells

REVISION = "b5968e9190ef611bbf34a7229255be88a0e937c1"  # a commit: cached after the first run, no network after


def main() -> int:
    if len(sys.argv) < 3 or not sys.argv[1].isdigit():
        sys.exit("usage: cells-tokens <max tokens> <bundle or cells.md>...")
    tok = Tokenizer.from_pretrained("deepseek-ai/DeepSeek-V4-Pro", revision=REVISION)
    limit, over = int(sys.argv[1]), 0
    for f in (Path(p) if p.endswith(".md") else Path(p) / "cells.md" for p in sys.argv[2:]):
        cells = read_cells(f)
        if cells.errors:  # what explain-build refuses is never counted
            sys.exit(f"{f}:\n" + "\n".join(cells.errors))
        text = f.read_bytes().decode().encode("utf-16-le")  # the reader's offsets are UTF-16 code units of the raw text
        for s in cells.sections:
            body = text[2 * s["start"]:2 * s["end"]].decode("utf-16-le").split("\n", 1)[-1]  # minus its heading
            if (n := len(tok.encode(body, add_special_tokens=False).ids)) > limit:
                over += 1
                print(f"{f} ## {s['slug']}: {n} tokens")
    return 1 if over else 0
