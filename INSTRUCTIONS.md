# Instructions

Read this before making or editing a lesson.

1. Each lesson is a folder `~/Documents/explainers/<slug>.explainer/`: `cells.md` (the transcript), `lesson.py` (the
   Manim scene) and any helper scripts or data. Never touch `build/` or `comments.json`.
2. If the lesson needs numbers, write a script that computes them (e.g. `helpers.py`, imported by `lesson.py`). Prose
   never types a number: it writes `{name}` or `{name:.3f}`, filled in from `lesson.py` at build time.
3. Meanwhile, write `cells.md` and `lesson.py` in parallel: one `## slug` section per `self.cell("slug")`, same order.
4. Build with `explain-build <bundle>`; it renders all cells in parallel. Fix each error at the `lesson.py` line it
   names, and rebuild until it prints `built`.
5. Minh opens the lesson in the Explainers app, comments, and presses Ping, which sends you a message. Then run
   `fetch-comments <bundle>`: it prints each open comment. Answer them. Edit a cell only when asked, then rebuild.
6. Follow the heuristics below.

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
12. **Few things at once (cognitive load).** Every element on screen costs the viewer attention. Show only what the
    current step uses, and fade out what is finished. Change one thing at a time, so the eye always knows where to
    look: at what just appeared or moved.
13. **Use the whole stage.** The frame is wide: 2:1, 16 × 8 units. Put things side by side on one line before
    stacking them. Prefer a few big, well-spaced elements to many small ones.
14. **A row of labels is one line.** Labels over a row of cells sit on one line, each centred over its cell. Never
    stagger them up and down to dodge an overlap: shorten them, widen the cells, or show fewer.
15. **Quiet visuals.** No decoration: no borders, shadows, gradients or icons that carry no information. One accent
    colour means "look here", one means "wrong", and a colour means the same thing in every cell.
16. **Align and space evenly.** Things that belong together share a row or a column edge, with equal gaps, so the
    picture reads as a grid.
17. **Words go in the transcript.** On screen: labels, numbers and formulas only. Sentences belong in cells.md.
18. **Things stay put.** An object that stays on screen keeps its place from cell to cell. Move it only when the
    movement is the point.
