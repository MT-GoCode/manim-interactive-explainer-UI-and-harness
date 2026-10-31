"""cells-tokens <max tokens> <bundle or cells.md>...: print each "## slug" cell over <max tokens> (DeepSeek-V4 tokenizer)."""
import re
import sys

from tokenizers import Tokenizer

REVISION = "b5968e9190ef611bbf34a7229255be88a0e937c1"  # a commit: cached after the first run, no network after


def main() -> int:
    tok, (limit, *paths) = Tokenizer.from_pretrained("deepseek-ai/DeepSeek-V4-Pro", revision=REVISION), sys.argv[1:]
    over = 0
    for f in (p if p.endswith(".md") else f"{p}/cells.md" for p in paths):
        for slug, body in re.findall(r"^## (\S+)\n(.*?)(?=^## |\Z)", open(f).read(), re.M | re.S):
            if (n := len(tok.encode(body).ids)) > int(limit):
                over += 1
                print(f"{f} ## {slug}: {n} tokens")
    return 1 if over else 0
