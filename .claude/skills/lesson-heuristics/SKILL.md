---
name: lesson-heuristics
description: How to make a visual lesson (explainer) and Minh's binding rules for every one. Read before writing, editing or reviewing any lesson, cell, scene or transcript. The rules list only grows.
---

# How to make a lesson

A lesson is a folder `~/Documents/explainers/<slug>.explainer/`: `cells.md` (the transcript), `lesson.py` (one
continuous Manim scene), and any `helpers.py` / data files they use. You write only those. Never write `build/`,
`comments.json` or `ping`; the build and the app own them.

1. **Numbers come from code.** If the lesson needs numbers (a matrix, a hash, a probability), write a script that
   computes them: a `helpers.py` or a data file in the bundle, imported by `lesson.py` (`from helpers import ...`).
   Prose never types a number: `{name}` or `{name:fmt}` in cells.md is a module-level name of lesson.py formatted with
   Python's format spec (`{n}`, `{p:.3f}`), filled in at build time.
2. **Meanwhile, write both files in parallel.** One `## <slug>` section in cells.md per `self.cell("<slug>")` in
   lesson.py, in the same order. Each `self.cell()` is followed by at least one animation; what is on screen at a
   cell's end is the next cell's start.
3. **Build once:** `explain-build <bundle>` checks everything, renders all cells in parallel, and prints `built`. Later
   builds re-render only the cells that changed.
4. **Fix every error line and rebuild until it prints `built`.** Each line is `<cell> · lesson.py:<line> · <what>`;
   fix it at that line:
   - `Text at (0.00, 0.00) × Text at (0.30, 0.00) (lesson.py:22) · move Text by (+0.00, +0.44)`: two things overlap;
     move the first by the amount shown, or `self.attach(label, obj)` if the label belongs on that object.
   - `Square at (7.00, 0.00) is off frame by 0.39 (right)`: move it in by that much, or make it smaller.
   - `Text at (0.00, 0.00) font size 28.0 < 32` / `MathTex at (0.00, 0.00) LaTeX font size 36.0 < 40`: Text is at
     least 32, MathTex at least 40, after scaling. Axis numbers: `axis_config={"font_size": 40}`.
   - `Circle at (0.00, 0.00) was made transient in this cell and is still on screen at its end`: FadeOut it in its cell.
   - `the camera moved in cell "turns" (lesson.py:11); the camera is static: set it before the first self.cell()`.
5. **Follow Minh's heuristics below.** They decide what the lesson shows and in what order.

## The files

```markdown
## numbers
Here are {n} numbers.

## total
Add them: the total is {total}.
```

```python
from manim import *

from explainers import Lesson

xs = [3, 1, 2]
n, total = len(xs), sum(xs)


class Total(Lesson):
    def construct(self):
        self.cell("numbers")
        row = VGroup(*[MathTex(str(x), font_size=48) for x in xs]).arrange(RIGHT, buff=0.6)
        self.play(Write(row), run_time=1)
        self.cell("total")
        s = MathTex(f"= {total}", font_size=48).next_to(row, RIGHT, buff=0.4)
        self.play(Write(s), run_time=1)
```

- cells.md: only `## <slug>` sections (slug `[a-z0-9-]+`, unique), nothing before the first one, LF line ends, no
  BOM. Prose is Markdown with `$…$` / `$$…$$` KaTeX. `[[lesson#cell]]` links to a cell of this or another lesson.
- lesson.py: exactly one `Lesson` subclass (`Lesson3D` for 3D: call `self.set_camera_orientation(...)` once before
  the first `self.cell()`; labels that must not turn with the scene go through `self.add_fixed_in_frame_mobjects`).
- `self.attach(child, to)`: child sits on `to` (a label on its arrow, a number in its box); they may overlap.
- `self.transient(*mobs)`: cursors and highlights; each must be gone by the end of the cell it was made in.

## The app and Minh's comments

Minh opens the bundle in the Explainers app (double-click it). Prose edits in cells.md show at once. Until the next
`explain-build`, the app's banner says "Changed since last build: lesson.py" after a lesson.py edit, and "Prose and
build disagree" after headings are added, removed or reordered. He comments on a cell or a highlighted span and presses
Ping.

- Keep exactly one `fetch-comments --wait <bundle>` running in the background. On Ping it prints one line per open
  comment, `<id> · #<n> <slug> · "<quote>" → <comment>` (`whole cell` without a quote; `#– <slug>` for a cell that is
  gone), and exits. Answer, then start the next one.
- Answer in chat. Edit only when the comment asks for a change or Minh says so: that cell's section and/or its
  lesson.py lines, then `explain-build`. A cell's comments clear themselves once it changes.

Never: move the camera; write build/, comments.json or ping; leave a cell without its section or a section without its
cell; type a number into prose; skip the build.

# Minh's lesson heuristics (binding for every lesson)

1. **Low to high level, always.** Go straight to the meat: the actual math and transforms, in execution order. Never open
   with a high-level overview ("the block has attention and an FFN"). Name a mechanism only after it has been computed
   ("the operation you just ran is called RMSNorm"). High level comes last, as a summary that re-references what was seen.
   A fundamentals chapter first is fine.
2. **Case, then full.** For every matrix formula: compute one example (a cell, a row), then show the full matrices with
   that case highlighted.
3. **One orientation everywhere.** A T × dim matrix is drawn with T rows and dim columns. A token is always a row, in
   every matrix, every equation and every chapter. Matrix products use one layout: left factor beside the output,
   right factor above it, so row i and column j meet at cell (i, j). A transpose appears only as an animated transpose.
4. **Show every matrix.** Every weight matrix and every intermediate the computation touches is on screen at its step.
5. **When the subject is a model, show the full model.** Not one token's vector: all T rows, every layer, the real sum.
6. **Animations must carry information**: a process such as addition, a row coming out of a product, a row being
   copied, a rotation. Never animate the construction of a flowchart or an overview diagram.
7. **Geometry must be big.** A plane takes the full stage, is zoomed to its data, and shows the two coordinates in which
   the picture is legible. Labels never sit on top of each other.
8. Transcript: ASD-STE100 style, one continuous stream, current paragraph lit, ↓ / ↑ to move.
9. **Matrix products animate cell by cell, always.** One cursor slides along row i of the left factor, one slides down
   column j of the right factor, and cell (i, j) of the result appears; j moves first, then i. Batched products do the
   same per batch. Products that share a left factor run their cursors together.
10. **Composite matrices keep divider lines** at their block boundaries (head groups in W_q, Q, C; row blocks in W_o).
11. **Down to the digits, always.** Never stop at an analogy or a "shared notebook" gloss. Reach the mechanism and the
    actual bytes: show the real hash hex, the real storage slot, the real transaction fields. The root of the thing (the
    hash function, the keypair, the bytecode) is the lesson, not a footnote. Analogies ride alongside the mechanism, never
    replace it. If one step is genuinely out of scope (e.g. elliptic-curve math), mark that boundary explicitly and say a
    separate lesson covers it — do not fake it or skip it silently.
