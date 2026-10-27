"""fetch-comments <bundle> [--wait]: the comments open in a lesson, one line each, in cell order (orphans last):
`<id> · #<n> <slug> · "<quote>" → <comment>`, or `whole cell`. The app is the only writer of comments.json and
writes it whole (write, then rename), so a read never sees half a file. --wait blocks until the app's Ping, then
prints and deletes `ping`."""
import json
import sys
import threading
from pathlib import Path

from explainers.cells import read_cells


def _utf16(text: str, start: int, end: int) -> str:
    """text[start:end] in UTF-16 code units, the app's (JavaScript's) string offsets."""
    return text.encode("utf-16-le")[2 * start:2 * end].decode("utf-16-le")


def _prose(bundle: Path) -> dict[str, tuple[int, str]]:
    """slug → (cell number, the cell's prose: its section without the heading line)."""
    text = (bundle / "cells.md").read_text()
    out = {}
    for n, s in enumerate(read_cells(bundle / "cells.md").sections, 1):
        section = _utf16(text, s["start"], s["end"])
        out[s["slug"]] = (n, section.partition("\n")[2])
    return out


def lines(bundle: Path) -> list[str]:
    path = bundle / "comments.json"
    if not path.exists():
        return []
    comments = json.loads(path.read_text())["comments"]
    prose = _prose(bundle)
    flat = lambda s: s.replace("\n", "⏎")
    out = []
    for c in sorted(comments, key=lambda c: prose[c["cell"]][0] if c["cell"] in prose else len(prose) + 1):
        if c["cell"] not in prose:
            out.append(f"{c['id']} · #– {c['cell']} · {flat(c['text'])}")
            continue
        n, md = prose[c["cell"]]
        quote = "whole cell" if c["span"] is None else f'"{flat(_utf16(md, *c["span"]))}"'
        out.append(f"{c['id']} · #{n} {c['cell']} · {quote} → {flat(c['text'])}")
    return out


def wait_for_ping(bundle: Path) -> None:
    """Returns once `ping` exists. The watch starts BEFORE the check, so a ping made between them is not missed."""
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
    ping, seen = bundle / "ping", threading.Event()

    class Handler(FileSystemEventHandler):
        def on_created(self, e):
            if Path(e.src_path) == ping:
                seen.set()

        def on_moved(self, e):
            if Path(e.dest_path) == ping:
                seen.set()

    observer = Observer()
    observer.schedule(Handler(), str(bundle))
    observer.start()
    try:
        if not ping.exists():
            seen.wait()
    finally:
        observer.stop()
        observer.join()


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    wait = "--wait" in args
    rest = [a for a in args if a != "--wait"]
    if len(rest) != 1:
        print("usage: fetch-comments <bundle> [--wait]", file=sys.stderr)
        return 2
    bundle = Path(rest[0]).expanduser().resolve()
    if wait:
        wait_for_ping(bundle)
    print("\n".join(lines(bundle)) or "no comments")
    if wait:
        (bundle / "ping").unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
