"""Every way cells.md headings and self.cell() calls can disagree gives its own exact message, in a fixed order."""
from types import SimpleNamespace as N

from explainers.build import pairing

S = lambda *slugs: [{"slug": s, "line": i + 1} for i, s in enumerate(slugs)]
C = lambda *slugs: [N(slug=s, line=10 + i) for i, s in enumerate(slugs)]


def test_agreeing_lists_give_no_message():
    assert pairing(S("a", "b"), C("a", "b")) == []


def test_renamed_heading_gives_both_differences_and_no_order_message():
    assert pairing(S("a", "x"), C("a", "b")) == [
        'cells.md has "## x" (cells.md:2) but lesson.py has no self.cell("x")',
        'lesson.py has self.cell("b") (lesson.py:11) but cells.md has no "## b"']


def test_reordered():
    assert pairing(S("a", "b"), C("b", "a")) == ['order differs at cell 1: cells.md "## a", lesson.py self.cell("b")']


def test_duplicates_come_first():
    assert pairing(S("a", "a"), C("a", "a")) == ['duplicate heading "## a" (cells.md:2)',
                                                  'duplicate self.cell("a") (lesson.py:11)']
