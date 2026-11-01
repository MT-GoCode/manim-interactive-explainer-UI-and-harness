"""Width from measured per-worker peaks, and how cells are cut into chunks (golden, literal inputs)."""
from explainers.render import chunks, to_render, width

GiB = 2**30


def test_width_is_bound_by_cpu_ram_and_cells():
    assert width(cores=16, ram=128 * GiB, cells=30) == 6      # ⌊8 / 1.22⌋
    assert width(cores=64, ram=4 * GiB, cells=30) == 3        # ⌊2 GiB / 0.59 GiB⌋
    assert width(cores=16, ram=128 * GiB, cells=3) == 3
    assert width(cores=1, ram=1 * GiB, cells=10) == 1         # always at least one


T = lambda n: [True] * n


def test_chunks_golden():
    assert chunks([1, 1, 1, 1], 2, T(4)) == [[0, 1], [2, 3]]
    assert chunks([3, 1, 1, 1], 2, T(4)) == [[0], [1, 2, 3]]
    assert chunks([1, 1, 1, 1, 1, 1], 3, T(6)) == [[0, 1], [2, 3], [4, 5]]
    assert chunks([1, 1], 1, T(2)) == [[0, 1]]
    assert chunks([5, 1], 3, T(2)) == [[0], [1]]                  # never an empty chunk
    assert chunks([1, 2, 1], 2, T(3)) == [[0], [1, 2]]            # tie at 1.0 vs 3.0 from 2.0: earlier cell
    assert chunks([1, 3, 1, 1], 2, T(4)) == [[0, 1], [2, 3]]      # 4 is nearer 3 than 1 is: nearest, not floor


def test_chunks_never_start_where_a_time_based_updater_is_live():
    assert chunks([1, 1, 1, 1], 2, [True, True, False, True]) == [[0], [1, 2, 3]]  # nearest allowed cut
    assert chunks([1, 1, 1, 1], 4, [True, False, False, False]) == [[0, 1, 2, 3]]  # nowhere to cut: one chunk


def test_to_render_is_what_is_not_reusable():
    assert to_render({0, 2}, 4) == [1, 3]
