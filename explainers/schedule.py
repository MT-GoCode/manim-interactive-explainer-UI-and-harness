"""Where render work is cut into chunks: a pure function of the plays to render and the measured costs, never of the machine's
load. A chunk never spans a gap, so it is one contiguous range of one run and pays exactly one fast-forward, to its first play."""

# Measured on postmortem with the frame check on: a play's seconds per video second on a first build, and what
# starting one more worker costs. A split that saves less than a start costs CPU and RAM for nothing.
SEED_S_PER_VIDEO_S = 0.5277
START_COST_S = 0.89
# How much of a forward estimate a cut charges. Full weight assumes each worker forwards at its solo speed; in fact the early,
# short chunks finish and free the fast cores for the late ones. Swept on postmortem at 8 workers, 0 to 1: best at 0.5.
FORWARD_WEIGHT = 0.5


def runs(plays: list[int]) -> list[list[int]]:
    """Sorted indices split into maximal runs of consecutive ones."""
    out: list[list[int]] = []
    for n in plays:
        if out and out[-1][-1] == n - 1:
            out[-1].append(n)
        else:
            out.append([n])
    return out


def fill(run: list[int], forward: dict[int, float], work: dict[int, float], bound: float) -> list[tuple[int, int]] | None:
    """Greedy over one run, or None if one play alone does not fit."""
    out, i = [], 0
    while i < len(run):
        start, cost = run[i], forward[run[i]] + work[run[i]]
        if cost > bound:
            return None
        while i + 1 < len(run) and cost + work[run[i + 1]] <= bound:
            i += 1
            cost += work[run[i]]
        out.append((start, run[i]))
        i += 1
    return out


def makespan(chunks: list[tuple[int, int]], forward: dict[int, float], work: dict[int, float]) -> float:
    return max(forward[a] + sum(work[n] for n in range(a, b + 1)) for a, b in chunks)


def chunks_at(rs: list[list[int]], forward: dict[int, float], work: dict[int, float], width: int) -> list[tuple[int, int]]:
    """The chunks of the least bound whose fill of all runs has at most `width` chunks, or one per run if there are more runs."""
    limit = max(width, len(rs))
    lo, hi = 0.0, sum(forward[n] + work[n] for r in rs for n in r)

    def at(bound: float) -> list[tuple[int, int]] | None:
        filled = [fill(r, forward, work, bound) for r in rs]
        return None if None in filled else [c for f in filled for c in f]

    for _ in range(60):
        mid = (lo + hi) / 2
        c = at(mid)
        lo, hi = (lo, mid) if c is not None and len(c) <= limit else (mid, hi)
    return at(hi)


def cut(plays: list[int], forward: dict[int, float], work: dict[int, float], width: int,
        start_cost: float = START_COST_S) -> list[tuple[int, int]]:
    """The fewest chunks whose makespan is within one worker's start cost of the best at `width`."""
    rs = runs(plays)
    best = makespan(chunks_at(rs, forward, work, width), forward, work)
    for n in range(1, width + 1):
        chunks = chunks_at(rs, forward, work, n)
        if makespan(chunks, forward, work) <= best + start_cost:
            return chunks
    raise AssertionError("the search at width itself is within its own bound")
