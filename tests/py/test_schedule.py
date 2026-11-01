"""Where work is cut into chunks (golden, literal inputs)."""
from explainers.render import to_render
from explainers.schedule import cut

FLAT = {n: 0.0 for n in range(200)}


def test_to_render_is_what_is_not_reusable():
    assert to_render({0, 2}, 4) == [1, 3]


def test_cut_balances_forward_and_work():
    assert cut([0, 1, 2, 3], FLAT, {n: 1.0 for n in range(4)}, 2, start_cost=0) == [(0, 1), (2, 3)]


def test_cut_gives_a_late_chunk_less_work():
    # bound 5: five plays from 0 cost 5, and play 5 alone costs 4 + 1. Without forward it would be (0, 2), (3, 5).
    forward = dict(enumerate([0, 0, 4, 4, 4, 4]))
    assert cut(list(range(6)), forward, {n: 1.0 for n in range(6)}, 2, start_cost=0) == [(0, 4), (5, 5)]


def test_cut_keeps_runs_apart():
    plays, work = [0, 1, 2, 7, 8, 9], {n: 1.0 for n in range(10)}
    assert cut(plays, FLAT, work, 2, start_cost=0) == [(0, 2), (7, 9)]
    assert cut(plays, FLAT, work, 1, start_cost=0) == [(0, 2), (7, 9)]  # more runs than width: one chunk per run


def test_cut_on_the_p6_table():
    table = [(0, 0), (48, 9.25), (96, 14.08), (144, 19.02), (192, 22.96)]

    def real(k):
        for (a, fa), (b, fb) in zip(table, table[1:]):
            if k <= b:
                return fa + (fb - fa) * (k - a) / (b - a)

    forward = {k: 1.2 * real(k) for k in range(193)}
    assert cut(list(range(193)), forward, {k: 0.4058 for k in range(193)}, 8, start_cost=0.89) == [
        (0, 73), (74, 112), (113, 140), (141, 159), (160, 173), (174, 184), (185, 192)]


def test_a_split_that_saves_less_than_a_start_is_not_made():
    forward, work = {n: 22.0 for n in range(190, 193)}, {n: 0.4 for n in range(190, 193)}
    assert cut([190, 191, 192], forward, work, 8, start_cost=0.89) == [(190, 192)]
    assert cut([190, 191, 192], forward, work, 8, start_cost=0) == [(190, 190), (191, 191), (192, 192)]
