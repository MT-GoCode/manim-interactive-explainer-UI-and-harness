"""The geometry check, on pass-1 records (screen coordinates): at each cell's end nothing overlaps unless attached,
nothing is off frame, no text is too small, and nothing made transient in the cell is still on screen."""
import numpy as np

from explainers.render import WIDTH

MIN_TEXT, MIN_LATEX = 32, 40  # Minh's picks from size-ladder.png (DECISIONS)


def _clear(box: np.ndarray, others: np.ndarray) -> tuple[float, float]:
    """The smallest single-axis move of box [x0, y0, x1, y1] that leaves it overlapping none of `others` (n×4)."""
    moves = []
    for axis in (0, 1):
        lo, hi = axis, axis + 2
        moves += [(float(np.max(others[:, hi] - box[lo])), axis), (-float(np.max(box[hi] - others[:, lo])), axis)]
    d, axis = min(moves, key=lambda m: abs(m[0]))
    return (d, 0.0) if axis == 0 else (0.0, d)


def _glyph_hit(glyphs: np.ndarray, boxes: np.ndarray):
    """The move that clears the first glyph overlapping any of `boxes`, or None."""
    if not len(glyphs) or not len(boxes):
        return None
    a, b = glyphs[:, None], boxes[None]
    hit = (a[..., 0] < b[..., 2]) & (b[..., 0] < a[..., 2]) & (a[..., 1] < b[..., 3]) & (b[..., 1] < a[..., 3])
    rows = np.flatnonzero(hit.any(axis=1))
    return _clear(glyphs[rows[0]], boxes[hit[rows[0]]]) if len(rows) else None


def _stroke_hit(glyphs: np.ndarray, strokes: list):
    """The move that clears the first glyph any stroke segment passes through (Liang–Barsky clip), or None."""
    if not len(glyphs) or not strokes:
        return None
    paths = [np.asarray(s) for s in strokes]
    p = np.concatenate([s[:-1] for s in paths])[None]          # 1×n×2 segment starts
    d = np.concatenate([s[1:] - s[:-1] for s in paths])[None]  # 1×n×2 segment directions
    lo, hi = glyphs[:, None, :2], glyphs[:, None, 2:]          # g×1×2
    with np.errstate(divide="ignore", invalid="ignore"):
        t0, t1 = (lo - p) / d, (hi - p) / d
    flat, inside = d == 0, (lo < p) & (p < hi)                 # a segment parallel to an axis: in or out on it
    enter = np.where(flat, np.where(inside, -np.inf, np.inf), np.minimum(t0, t1)).max(axis=2).clip(min=0)
    leave = np.where(flat, np.where(inside, np.inf, -np.inf), np.maximum(t0, t1)).min(axis=2).clip(max=1)
    hit = enter < leave                                        # g×n: the segment has a stretch strictly inside
    rows = np.flatnonzero(hit.any(axis=1))
    if not len(rows):
        return None
    i, j = rows[0], hit[rows[0]]
    ends = np.concatenate([p[0, j] + enter[i, j, None] * d[0, j], p[0, j] + leave[i, j, None] * d[0, j]])
    return _clear(glyphs[i], np.hstack([ends, ends]))


def _collision(x, y):
    """How to move x's glyphs off y's glyphs and strokes, or None."""
    g = np.asarray(x.glyphs).reshape(-1, 4)
    return _glyph_hit(g, np.asarray(y.glyphs).reshape(-1, 4)) or _stroke_hit(g, y.strokes)


def check(cells, frame_width: float, frame_height: float) -> list[str]:
    errs = []
    fx, fy = frame_width / 2, frame_height / 2
    slack = frame_width / WIDTH / 2  # under half a pixel past the edge draws nothing outside the frame
    for n, cell in enumerate(cells):
        units = cell.end
        for k, a in enumerate(units):
            for b in units[k + 1:]:
                if a.attached_to in b.owners or b.attached_to in a.owners:
                    continue
                for x, y in ((a, b), (b, a)):
                    move = _collision(x, y)
                    if move:
                        errs.append(f"{cell.slug} · lesson.py:{x.line} · {x.kind} × {y.kind} (lesson.py:{y.line}) · "
                                    f"move {x.kind} by ({move[0]:+.2f}, {move[1]:+.2f})")
                        break
        for u in units:
            ink = np.concatenate([np.asarray(u.glyphs).reshape(-1, 4), np.asarray(u.fills).reshape(-1, 4)]
                                 + [np.hstack([s, s]) for s in map(np.asarray, u.strokes)])
            over = {"right": ink[:, 2].max() - fx, "left": -fx - ink[:, 0].min(),
                    "top": ink[:, 3].max() - fy, "bottom": -fy - ink[:, 1].min()}
            edge = max(over, key=over.get)
            if over[edge] > slack:
                errs.append(f"{cell.slug} · lesson.py:{u.line} · {u.kind} is off frame by {over[edge]:.2f} ({edge})")
            if u.text_size is not None and u.text_size < MIN_TEXT:
                errs.append(f"{cell.slug} · lesson.py:{u.line} · {u.kind} font size {u.text_size:.1f} < {MIN_TEXT}")
            if u.latex_size is not None and u.latex_size < MIN_LATEX:
                errs.append(f"{cell.slug} · lesson.py:{u.line} · {u.kind} LaTeX font size {u.latex_size:.1f} < "
                            f"{MIN_LATEX}")
            if u.transient_cell == n:
                errs.append(f"{cell.slug} · lesson.py:{u.line} · {u.kind} was made transient in this cell and is "
                            "still on screen at its end")
    return errs
