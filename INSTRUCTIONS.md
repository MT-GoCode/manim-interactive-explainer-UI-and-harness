# Instructions
   
Each lesson is a folder `~/Documents/explainers/<slug>.explainer/`: `cells.md` (the transcript), `lesson.py` (the
   Manim scene) and any helper scripts or data. Never touch `build/`, `comments.json` or `understood.json`.

If the lesson needs numbers or samples, write `generate.py`: run it once; it does all computation (use the GPU if
   that is faster) and saves an artifact (any format) that `lesson.py` loads. Never import `generate.py`; `lesson.py`
   does no computation. `helpers.py` holds Manim components written once and reuse if you need; `lesson.py` imports it. Prose
   never types a number: it writes `{name}` or `{name:.3f}`, filled in from `lesson.py` at build time.
   Write these outside backticks and `$...$`: code and math show their raw text. The build refuses a `lesson.py` name inside code.

`cells.md` and `lesson.py` contain one `## slug` section per `self.cell("slug")`, same order.

Build with `explain-build <bundle>`; it renders the cells whose frames changed, in parallel. Fix each error at the `lesson.py` line it names, and rebuild until it prints `built`.
When Minh gives a length limit, run `cells-tokens <limit> <bundle>`: it lists each cell over that many tokens (the whole cell: prose, math and code as written). Shorten each cell it lists.

In order, what you should do is write a scratch storyboard.md in /tmp/ that walks through how you'll structure the lesson to follow the lesson heuristics below to the T. 
1. Then write `generate.py`. While it runs, 
2. Write `lesson.py` and `cells.md` in parallel
3. Ask a FRESH subagent to read this instruction file, your lesson.py, your cells.md, and critique how closely you follow the heuristics by looking at your lesson plan and prose. NOT to debug your code. Have it separate concerns into INACCURACIES (anything false: a fact the source contradicts, or a picture or explanation that teaches a false model) to PEDAGOGY VIOLATION (a heuristic clearly broken, sloppy phrasing included) to PEDAGOGY SMOOTHING (all else). Only INACCURACIES need fixing. Repeat (with fresh agent!) until there are no INACCURACIES.
4. Build & debug

The phases are GENERATION, CONSTRUCTION, CRITIQUE, and BUILD. Announce which one you are in, and move as fast as possible because the user wants to learn fast. Do not try to debug the internals of explainer. If there seems to be something wrong with the app's core, message user and stop.

SUBAGENTS
Reduce the amount of work the subagent needs to do. Run a command that concatenates and titles lesson.py, cells.py, instructions.md section after lesson heuristics (below) and wraps it in a prompt when spinning up paseo agent with haiku 5.5 with empty system prompt and prompt: You are a subagent. Do not spin up your own subagents. Do not debug my code. Please critique lessons.py and cells.md based on the lesson heuristics attached, and sort it into INACCURACIES (anything false) to PEDAGOGY VIOLATION (a heuristic clearly broken) to PEDAGOGY SMOOTHING (all else). Do not run any code or try to explore the surrounding system. 

VIEWING THE LESSON
Minh opens the lesson in the Explainers app. He can make comments in there and press a button which sends you a message to check comments. Then run
   `fetch-comments <bundle>`: it prints each open comment. Answer them directly in chat, and do not edit cells and lessons -- unless asked to in comments or explicitly messaged to.

When the user asks for a link between lessons, write `[[lesson#cell]]` in cells.md: `lesson` is the lesson's folder
   name in `~/Documents/explainers` without `.explainer`, `cell` is one of its `## slug` headings (both required, e.g.
   `[[postmortem#bf16]]`). In the app, clicking it opens that lesson at that cell.

Follow the heuristics below.

# What `explain-build` prints

A build prints, in this order:
- `machine: phase=render ...`: the exact inputs of the width below, for tests.
- `render width: 8 (idle 17.4 cores, 25 GB free) · 0.59 GB per job est`: how many workers run at once, up to 75% of what is free. `explain-build <bundle> --workers N` sets it exactly.
- `render: 40/193 animations`: progress, while workers draw.
- One line per cell, the refs, and the inputs.
- `pass 1: reused` or `pass 1: ran`. It runs only when something it read changed: a prose edit reuses it, and an edit to `lesson.py`, a helper or a data file it read, or a new `{ref}` runs it, and so does a build from a shell with a different PATH or locale.
- `render: 3 cells (4–5, 9) in 2 chunks · 27 reused`: only cells whose frames changed render.
- `timing:` and `built`.

Each error names what to fix:
- `lesson.py:N read <path>, outside the bundle`: copy the file into the bundle. A lesson also starts no program but TeX and reaches no network.
- `animation N drew different frames in its worker than in pass 1` or `ran in only one of pass 1 and its worker`: the lesson is nondeterministic. No clock reads, no sets of mobjects, no random draws outside `construct`.
- `the camera moved in cell`: set the camera once, before the first `self.cell()`.
- `a lesson may not read the camera's pixels`: remove the `camera.get_image()` call.
- `one render job needs ... GB`: close something, or pass `--workers 1`.
- `render failed` or `pass 1 failed`, with an exit code: read the traceback below it. A line in it is the lesson's line.

A lesson does not write into its own folder: the workers would see that file, and you would not.

# LESSON HEURISTICS

## Pedagogy

**Fundamentals, Process, Summarize..** At a high level, use a flow in lessons of going over fundamental concepts first needing to understand higher-level processes. Then when going into the processes, go Go straight to the meat: the actual math and transforms, in execution order. Never open with a high-level overview or try to go high level to low level ("the block has attention and an FFN"). Name a mechanism only after it has been shown to the user. "What you just saw is called LayerNorm" High level comes last, as a summary that re-references what was seen and helps the user learn a term for what they just saw. Then repeat. Fundamentals, Processes/Higher Level/Bigger Picture/Throughline, Summarize. Fundamentals, throughline, Summarize.

**An excessive amount of color-coded association**. Where did that number come from? where did every single number in an expression come from, from the table or visualization or previous expression? Color code, examples: Numbers originating from some drawing, highlight that part of the drawing/box it and color the number the same. Symbols and terms in expressions originating as simplifications or whatever of other ones from earlier expressions -- color them the same. Or aspects of different arrays, matrices, values within a table or matrix, dots on a plot representing a point from an earlier expression, etc -- color code everything to represent their origins.

**Few things at once (cognitive load).** Every element on screen costs the viewer attention. Show only what the current step uses, and fade out what is finished. Change one thing at a time, so the eye always knows where to look: at what just appeared or moved.

**Writing** In Cells.md, excessively contextualize and give deep information to a point that is reasonable enough the user has a full picture of the system. Start from where the user is. The user is someone who always asks "Why?" Every single cell must flow from one to the next. NEVER edit cells in isolation -- if you edit one, you must read the one above to the one below and make sure it flows together. 

**No dumbing it down.** I fucking hate abstractions or any explanation that doesn't just show me the damn bites, bytes, numbers moving around. Don't handwave. analogies that are entirely accurate, accompanying the content, and directly contribute to wisdom because they are these high-density insights. Don't just show me the simple case of systems. You can do that first, but always show me the full, real, actual thing. The full model, spelled out. The full block chain with what data might look like inside.

**WRITING STYLE** YOU MUST WRITE IN ASD-STE100! The single most high-value thing you can do is to assume the POV and style of a personal tutor who is trying to tell a fully connected narrative.

**NO CONFUSING OR INCORRECT OR SLOPPY PHRASING** Have absolutely unambiguous phrasing. Don't make comparisons, causal statements, or anything else of that nature that can be misinterpreted. 

**Signal.** You're trying to maximize highest learning value with lowest amount of content generated. Be as perfectly targeted, high-signal as possible.

**Visual grounding.** Adding in non-english sections can genuinely improve the understanding by adding conceptual or visual-based grounding. You can also use tables to organize ideas to create summaries and unifying mental models. But only if they map exactly onto the truth. Don't draw tables that over-simplify the underlying truth.

## Techniques

Advice for writing explanatory prose. Obviously, tune to the subject matter at hand; i.e. No excessive prose is needed for a step-by-step math proof.

- Anchor before new (the master rule). Never introduce a new idea without first connecting it to something the student already knows. Open with the familiar, end with the new. For example "You know that recursion recomputes subproblems. Memoization caches each result so it's computed once."
- For large confusions, moonshot ideas, the user absolutely LOVES anchoring in what they know and building everything up step by step from it, capturing each of their questions/confusions along the way. Prioritize this style!
- START from what the student knows. "You know that xyz."
- When the question proposes my own assumption or model of thinking ("is it like X?", "so basically it's Y?"), do not answer with a fresh textbook explanation. Engage my version directly: (1) name the part of my model that's correct, explicitly, so I know what to keep; (2) isolate the incorrect parts that's wrong or imprecise; (3) correct only that, against my own words; (4) if my framing was right, say so and build on it rather than restating it differently. If completely wrong or way off, of course, help me correct & replace my model/assumption with a clean one. Otherwise, it wastes my understanding to start from scratch.
- Use questions as glue between different ideas in explanation, to suggest motivations.
- Use contradiction as a teaching tool, not an error to delete. When a new idea appears to conflict with something the student already believes (or something an earlier cell said), do not silently override it. Surface the tension — "this seems to contradict X you know" — then resolve it: either the student was wrong (correct them), the old thing was wrong (correct it), or both are true at different levels (name the distinction). The third case is where the student gets wiser; hunt for it.
- Motivate before you define. State the problem a concept solves — or the question it answers — before naming or formalizing it. The need comes first, then the noun. Definitions handed out cold have nothing to attach to.
- Mechanism over description. Explain how/why it works — the causal chain — not just what it is. A runnable mental model the student can simulate beats a static definition. Prefer one unifying cause over a list of separate local facts.
- No capability before mechanism. Never claim a thing can do something before you've given the mechanism that produces it. Every "this lets you do X" must be preceded by the why it can.
- Bridge from an anchoring intuition (for stuck/counterintuitive concepts). When something is hard to believe, find the nearest case where the student's gut is already correct, then build a chain of small steps from that anchor to the target — each step close enough that they can't reject it. A single analogy fails; the chain works. (Clement's table-pushes-up-on-book → spring → foam → board.)
- Contrast-first / "a time for telling." Before explaining a distinction, show two near-identical cases that differ only in the thing being taught, so the student notices the difference before you name it. The same explanation lands or bounces depending on whether their perception was first tuned to the distinction.
- Refutation structure. For a concept with a tempting wrong interpretation, name the wrong model explicitly, mark it false, then give the correct one. Co-activating the wrong and right ideas drives the correction harder than stating only the truth — and it pre-empts the follow-up.
- Concreteness before abstraction. Open with the specific, simplest case the student would never dispute; generalize after. Explain a typical 3×3 before the n×n, the example before the formula. (Halmos: motivate the definition, prove the special case first.)
- Teach once, then point. A concept gets its full explanation exactly once, on first introduction. Later mentions are pointers ("recall the bit budget — the packing idea"), never re-explanations. Do this excessively based on what came before!
- Calibrate smoothness to distance-from-mastery. Fill every gap for genuinely new material; leave deliberate inferential gaps for material adjacent to the student's expertise (the reverse-cohesion effect — too-smooth makes an expert skim).

## Cold reader checks

Before a lesson is done, run each check below. Adopt the described cold-student persona: pretend you know nothing about the world except what came before (earlier cells, earlier lessons, and what the user is known to know), reading the lesson for the first time. Fix everything each check finds.

### Object check
(cold student who has a tendency to rage at every unexplained term, seeing this for the first time)

For *every single* even remotely unfamiliar concept, jargon, technical term, structure, method of proof, idea, etc. that the student doesn't already know from what came before, and is not fully-explained or motivated in the lesson, point out that it needs an explanation.

Excessively ask "What the fuck is {entity from the lesson}?" "Where the fuck did you get {entity from the lesson}?" "Where did {entity, relationship, concept, etc. from the lesson} come from?"

You HATE explanations that don't excessively contextualize so you can piece it together with what you know, and instead speak as if you're a professional that's been exposed to it. For example, even though I've studied computer science for years, I've never learned what FPGAs are. An uncontextualized response is: Field programmable gate arrays are programmable integrated circuits often used for custom applications or designing ASICs. A well-contextualized response looks this: You know what digital logic circuits are. How do you build one physically? The direct way is to etch it into silicon — but then it's frozen; changing the design means fabricating a new chip. So what if you wanted a chip whose logic you could rewrite? That's a field-programmable gate array. The trick is two layers. First, instead of fixed gates, it's a grid of tiny lookup tables — each one a small memory that can store the truth table of any logic function, so a single cell can become an AND, an XOR, whatever you load into it. Second, the wires between cells are switchable, turned on or off by memory cells — the same SRAM you saw in CS 33. So "programming" the FPGA just means writing to all that memory: the LUTs decide what each cell computes, the switches decide how they connect. Configurable functions plus configurable wiring is what lets you assemble arbitrary circuits — and rewrite them whenever you want.

### Link check
(cold student who has a tendency to lose the thread at any unmotivated jump between sentences, seeing this for the first time)

For every sentence or bulletpoint, identify whether using only what was provided before it, one could understand the immediate next sentence or bulletpoint. Report every such violation.

Report every logical jump or unclear connection or line of reasoning. Ask excessive questions of the form "How did we go from X to Y?" "X is so fucking random. How did that come about?" or "It doesn't make sense that X motivates Y."

You LOVE explanations that flow smooth like water. You HATE when sentence-to-sentence, bulletpoint-to-bulletpoint there is only a microscopic logical jump that is trivial to see.

Logical jumps can can occur within a sentence or bullet too. Keep your eyes peeled.

### Arbitrary check
(cold student who has a tendency to demand "but WHY?" at every unmotivated design choice or arbitrary step, seeing this for the first time)

Point out
- In general, symptoms of the "expert blind spot", where an expert explains AT a problem instead of building it up, missing key foundations that motivate ideas. Anywhere a new student would ask "But why do we do that?" or "What allows us to do that?" or "Where did that come from?" It is highly recommended to phrase your feedback as these questions a frustrated, confused student would ask.
- Any new or seemingly arbitrary ideas, structures, logical steps that need more explaining to understand how it came to be.
- Hidden assumptions or ways of seeing things that aren't made obvious, yet critical to understand what's going on.
- Patterns within the lesson, or extended from what came before into the lesson, that would help a new student draw connections. Note down that the lesson ought to mention such a pattern.
- Arbitrary ideas or jumps that could be well-explained by concepts that already appeared before. Note down that the lesson ought to make that reference.
- Anything that can be easily understood better by getting closer to first principles by asking more WHY's.

Here are some examples.
- While studying GPU kernels for the first time, I got immensely confused at the arbitrary organization of threads being identified with {i,j,k}. A thorough explanation of GPU architecture was necessary to motivate blocks first. A smart but unaware teacher speaks of these concepts as if they are already known. A teacher who can put themselves in the mind of a student first explains the SM GPU architecture and how blocks are ingested flatly, then describes a kernel that breaks a problem down in a 1D manner, gives an example of single-dimensional indexing then explains that one use reorganize blocks and threads in a LOGICALLY MULTIDIMENSIONAL manner that doesn't change the way they are scheduled, but just helps one build corresponding mappings to different problem data, THEN describes multidimensional indexing.
The single-dimensional indexing and multidimensional indexing is a sort of pattern that you could point out if it were missing.
- While studying helical motion of charged particles in a magnetic field due to velocity vectors, it was explained that this was due to not being perpendicular to the magentic field vector. Intuitively, that makes sense, but WHY? It was then explained that was because the magnetic field didn't exert a force on the parallel component of velocity. But I had only a very elementary understanding of kinematics. So the next question is but WHY? Confused that "Forces" don't act on "velocities"... but on actual objects? The resulting explanation required an entire proof to show how a Force could act on a velocity component:
- Let’s play with Newton’s 2nd.
    $\vec{F}=m\vec{a} =m(\Delta \vec{v}/\Delta \vec{t})$

    We can always break apart by components. Let’s say $\Delta \vec{v}= \Delta \vec{v}_x+\Delta \vec{v}_y$

    $= m(\Delta \vec{v}_x+\Delta \vec{v}_y/\Delta \vec{t})$

    We can define $\vec{F}_x = m\Delta \vec{v}_x/\Delta \vec{t}$  and $\vec{F}_y = m\Delta \vec{v}_y/\Delta \vec{t}$

    And express full force as $\vec{F} = \vec{F}_x+\vec{F}_y$

    now instead of $x$ or $y$, let’s split by $\Delta \vec{v} = \Delta \vec{v}_\parallel + \Delta \vec{v}_\perp$, velocity components parallel to and perpendicular to $\vec{B}$, respectively.

    as above, we can express $\vec{F_B} = \vec{F}_\parallel+\vec{F}_\perp$. Let’s find these magnitudes, not using $ma$ formulas, but with our magnetism formulae:

    $|\vec{F}_\parallel| = |q|v_\parallel B \sin 0 \degree = 0$

    $|\vec{F}_\perp| = |q|v_\perp B \sin 90 \degree = |q|v_\perp B$

    Due to the zero, total force is only $\vec{F_B} = \vec{F}_\perp$ with magnitude $|q|v_\perp B$

    In other words, with initial velocity $\vec{v} \not \perp \vec{B}$, only part of the velocity, $v_\perp$, helps give rise to centripetal acceleration, while $v_\parallel$ encounters zero force →zero accereleration. In conclusion, we get a helix. In the diagram above, imagine an axis through the center of the helix. $\vec{F_B}$ constantly points to this from where the particle is parallel to the y-z plane. Notice at any point in the particle’s motion, this force vector still forms a right angle with $\vec{v}$, even though $\vec{v}$ is not perpendicular to y-z plane. Helical motion does not mean $\vec{F_B}$ ever loses perpendicularity

    If initial velocity were perpendicular to field; $\vec{v} \perp \vec{B}$, there exists no separate $v_\parallel$ and we have flat circular motion.

All that, just to express a simple idea: helical motion is due to nonperpendicularity. Ask WHY on every nonatomic logical jump!

### Idiot-student check
(cold student who has a tendency to want children's-novel ease, hating walls of text, bad analogies, and unanswered confusions, seeing this for the first time)

Put yourself in the shoes of the student. Speak like a frustrated, limited mental-capacity student who desires to just read easy-to-parse pedagogical prose and think as little as possible, achieving understanding as easily as possible, as if reading a children's novel.

You HATE when the lesson doesn't answer every IOTA of confusion or question you had.
You HATE explanations with low-signal to noise ratio, that drone on and on explaining AT a problem instead of motivating it.
You HATE explanations that don't deliver true clarity via wisely worded insights and instead give a wall of text.
You LOVE intuition and a full technical grasp of material even more. You LOVE explanations that use intuition to motivate, then technical details to fill in the picture -- suggest these where reasonable.
You HATE explanations that are over technical, too mathematically dense, too jargon-dense. While you don't like to skimp out on the technical details, you also hate it when it's not the sort of human-readable, english-dependent explanation one could give a half-asleep student and still communicate everything. Unless it's literally a linear math proof, in which case that's reasonable.
You LOVE it when ACCURATE, ERROR-FREE analogies or comparisons are used to build mental models of concepts -- suggest these where reasonable. You HATE it when analogies are poorly used or have so many differences from the true concepts that it is serves only to confuse, such as using a hose as an analogy
You HATE abstractions in general! You HATE it when abstractions serve only to build useless mental models that are not truly accurate to what's underneath, and would rather just learn the true mechanics and specifics of a system rather then generalize. Generalization is good, but it should be done after.
You HATE unclear or ambiguous statements.

### Consistency check
(cold student who has seen every earlier cell and lesson, and has a tendency to catch contradictions with them or with source docs)

- Ask all of these valid questions from perspective of a student: "You once told me that {quote/paraphrase from an earlier cell or lesson}, yet here you say {quote/paraphrase from the lesson}"
- Ask all of these valid questions from perspective of a student: "I thought that {reference document quote/paraphrase}, yet here you say {quote/paraphrase from the lesson}"
- As a trained model, you may understand parts of the lesson that a new student would find as an "inconsistency," when in reality perhaps it is a nuance or special-case relationship. Still, pretend to be the student who only knows what came before and recommend this be clarified.

### Accuracy check
Thoroughly check the lesson is accurate: factual correctness and faithfulness to the source material. Only report errors you are certain about, this is for clear-cut messups that affect a student's learning, not a space to spew noisy study advice. If helpful, use web search to verify information in the source material. You may discover inaccuracies that require the lesson to stray from the source material; then the truth wins.

### Length check (ADVERSARIAL — run LAST, after everything else passes)

**This check is deliberately adversarial and stands in opposition, in spirit, to every other check above.** Every other check pushes you to ADD — more context, more motivation, more linking, more building-up, more answering of every iota of confusion. The length check pushes the other way: it is the counterweight that fights bloat. Run it ONLY once all the other checks have passed and the student would learn the material 100% with no further questions. At that point, the explanation is complete and correct; the length check's sole job is to truncate and delete anything that is lowkey filler without harming that 100% understanding.

Advice for truncation:
- When the first X% (like 30%, 60%, 70%) of an answer or particular chunk is more than enough to get a point across, with the remaining just over-exploring or trivially reiterating it, point it out.
- Phrases, sentences, bulletpoints that are redundant to either other parts of the lesson or to what came before.
  - If these parts contribute no value to the explanation, suggest their deletion. If they help as connector language, then suggest their shortening to a mere reference.
- Sections that could be compressed to make them more high signal by shortening low-signal phrasing, unless such phrasing helps as glue.

Please be reasonable. We're not trying to hit a word limit, just increase signal-to-noise ratio. Crucially: never cut something whose removal would reintroduce a gap, an unmotivated jump, or an unanswered confusion that the other checks just worked to eliminate. You are trimming filler, not load-bearing build-up.

## Animations

**Animations must carry information**: a process such as addition, a row coming out of a product, a row being
   copied, a rotation. Never animate the construction of a flowchart or an overview diagram or something pointless, which also reduces the amount of tokens you need to generate and the overall signal-to-length ratio of videos.

**Geometry must be big.** A plane takes the full stage, is zoomed to its data, and shows the two coordinates in which
   the picture is legible. Labels never sit on top of each other.

**Use the whole stage.** The frame is wide: 2:1, 16 × 8 units. Put things side by side on one line before stacking them. Prefer a few big, well-spaced elements to many small ones. Nothing should look bunched together.

**Quiet visuals.** No decoration: no borders, shadows, gradients or icons that carry no information. One accent
 colour means "look here", one means "wrong", and a colour means the same thing in every cell.

**Align, space evenly, balance.** Things that belong together share a row or a column edge, with equal gaps, so
the picture reads as a grid. The picture as a whole is centred on the stage: two parts side by side share it
with an even gap, never pinned to the edges, and no large band of the frame stays empty.

**Words go in the transcript.** On screen: labels, numbers and formulas only. Sentences belong in cells.md.

## Matrices

**Case, then full.** For every matrix formula: compute one example (a cell, a row), then show the full matrices with
   that case highlighted.
**One orientation everywhere.** A T × dim matrix is drawn with T rows and dim columns. A token is always a row, in
   every matrix, every equation and every chapter. Matrix products use one layout: left factor beside the output,
   right factor above it, so row i and column j meet at cell (i, j). A transpose appears only as an animated transpose.
**Show every matrix.** Every weight matrix and every intermediate the computation touches is on screen at its step.

**Matrix products animate cell by cell, always.** One cursor slides along row i of the left factor, one slides down
   column j of the right factor, and cell (i, j) of the result appears; j moves first, then i. Batched products do the
   same per batch. Products that share a left factor run their cursors together.
**Composite matrices keep divider lines** at their block boundaries (head groups in W_q, Q, C; row blocks in W_o).

**Down to the digits, always.** Never stop at an analogy or a "shared notebook" gloss. Reach the mechanism and the
    actual bytes: show the real hash hex, the real storage slot, the real transaction fields. The root of the thing (the
    hash function, the keypair, the bytecode) is the lesson, not a footnote. Analogies ride alongside the mechanism, never
    replace it. If one step is genuinely out of scope (e.g. elliptic-curve math), mark that boundary explicitly and say a
    separate lesson covers it — do not fake it or skip it silently.

# Manim code landmines to avoid

Each of these has cost a build minutes of runtime or broken a picture.

1. **`Transform` and `TransformFromCopy` reshape an object in place, for good.** Manim pads the smaller object's tree
   of parts with copies until both trees match, and the padding stays after the animation ends. `Transform(a, b)`
   leaves `a` on screen in `b`'s shape (`b` itself is never added). `TransformFromCopy(src, dst)` leaves `dst` on
   screen, padded to `src`'s shape. So:
   - Transform only between objects with the same parts: one label to one label, a row of n to a row of n.
   - Never use a transform's result as the source of a later transform. Padding compounds: 10 → 80 → 2,046 → 8,058
     drawn paths in three steps, and every later frame draws all of them. For many-into-one, highlight the inputs and
     `FadeIn` the result, or transform a throwaway `.copy()`, then `self.remove` it and `self.add` a fresh object.
   - Use `ReplacementTransform` when later code refers to the destination variable.
2. **`import *` overwrites names silently.** A module-level name in your own code or loaded data (`LEFT`, `UP`, `T`,
   `Line`, `Text`, ...) replaces Manim's, and the error shows up far away (a broadcast error inside `next_to`). Never
   reuse a Manim name; assert that no loaded data key collides with an existing global.
3. **Color by TeX parts, never by glyph index.** `MathTex(a, b, c)` gives one part per argument; color `part[i]`.
   Slicing glyphs (`tex[0][7:10]`) breaks silently when the string changes. `substrings_to_isolate` and `{{ }}`
   cannot split inside `\frac`, `\sqrt` or a script group, so write the expression with each color-coded term as its
   own top-level argument.
4. **Size text at creation.** A `Text` or `MathTex` font size is derived from its height, so `.scale()`,
   `.set_width()` and `scale_to_fit_*` change it and can drop it under the build's minimum. Create text at its final
   size and never scale it. Do not pad the size to slip past the check.
5. **f-strings and TeX braces collide.** `{` in an f-string is a placeholder. Build TeX by concatenating raw strings
   (`r"\frac{" + value + "}{2}"`), not by doubling braces.
6. **Never build `Text` or `MathTex` per frame.** Each one runs Pango or LaTeX. A number that changes during an
   animation is a `DecimalNumber` or `Variable`, not a new text in an updater. Remove every updater before the cell
   ends.
7. **Copies are deep.** `.copy()` copies the whole family. Copy the smallest part you need, especially inside loops
   and `LaggedStart`.
8. **`self.mobjects` is what is on screen, not your variables.** A variable can name an object that is not on screen
   (a `Transform`'s destination), and an object can be on screen with no variable (what a `TransformFromCopy`
   leaves). Fade out what a step is finished with, and clear by `self.mobjects`.
9. **Text is written, not created.** `Create` on text traces glyph outlines; use `Write` or `FadeIn`.
   `TransformMatchingShapes` matches glyphs by shape and moves letters unpredictably; use it only between strings with
   the same letters.
10. **Images go in `Group`, not `VGroup`.** `VGroup` takes only vector objects.
11. **Leave `config` and the camera alone.** The build owns frame size, frame rate and seed.
12. **Test on the bundle with `explain-build`.** Bare `python` lacks the build's TeX path and settings. When a cell is
    slow, count what it draws (the sum of `len(m.get_family())` over `self.mobjects`) before suspecting Manim or the
    app.
