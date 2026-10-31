#!/usr/bin/env bash
# Mutation check: each mutant plants one named bug in a throwaway APFS clone of the working tree and must make its
# named test FAIL. A mutant that does not apply, survives, or only breaks collection fails the run.
#   scripts/mutants.sh            all mutants          scripts/mutants.sh VGroup     only those whose name matches
# A clone runs its own code: it goes first on PYTHONPATH, the repo's venv is shared read-only (UV_NO_SYNC), and TeX
# and node_modules are shared by symlink.
set -uo pipefail
# Lowest priority and macOS background QoS, one mutant at a time: the machine stays usable while this runs.
[ -z "${EXPLAINERS_NICE:-}" ] && EXPLAINERS_NICE=1 exec nice -n 19 taskpolicy -b "$0" "$@"
root="$(cd "$(dirname "$0")/.." && pwd)"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
filter=${1:-}

# name % file % perl substitution (applied with -0pi) % the test that must kill it   (% never occurs in a pattern)
MUTANTS=$(cat <<'EOF'
autolink text counted%tools/grammar.mjs%s/if \(ancestors.some\(\(a\) => isAutolink\(source, a\)\)\) return/if (false) return/%tests/py/test_grammar.py::test_reader_matches_golden[link-url-and-autolink]
autolink decided by label text%tools/grammar.mjs%s/source\[n.position.start.offset\] !== '\['/n.url === n.children.map((c) => c.value).join('')/%tests/py/test_grammar.py::test_reader_matches_golden[link-url-and-autolink]
escaped brace counted%tools/grammar.mjs%s/\(\?<!\\\\\)\\\{/\\{/%tests/py/test_grammar.py::test_reader_matches_golden[escaped-brace-is-literal]
uppercase slug accepted%tools/cells.mjs%s/\^## \(\[a-z0-9-\]\+\)/^## ([A-Za-z0-9-]+)/%tests/py/test_grammar.py::test_reader_matches_golden[uppercase-heading-is-error]
closing hashes accepted%tools/cells.mjs%s/\[ \\t\]\*\$\/.exec/[ \\t#]*\$\/.exec/%tests/py/test_grammar.py::test_reader_matches_golden[closing-hashes-is-error]
section end off by one%tools/cells.mjs%s/heads\[i \+ 1\].start : text.length/heads[i + 1].start - 1 : text.length/%tests/py/test_grammar.py::test_reader_matches_golden[basic]
section starts at the #, not the line%tools/cells.mjs%s/start: lineStart\(n.position.start.offset\)/start: n.position.start.offset/%tests/py/test_grammar.py::test_reader_matches_golden[indented-heading-is-a-heading]
CR endings accepted%tools/cells.mjs%s/if \(text.includes\('\\r'\)\)/if (false)/%tests/py/test_grammar.py::test_reader_matches_golden[crlf-is-error]
preamble accepted%tools/cells.mjs%s/if \(pre.trim\(\)\)\n    errors.push/if (false)\n    errors.push/%tests/py/test_grammar.py::test_reader_matches_golden[preamble-is-error]
order not checked%explainers/build.py%s/if not errs and heads != calls:/if False:/%tests/py/test_pairing.py::test_reordered
duplicates not reported%explainers/build.py%s/if s\[\"slug\"\] in seen:/if False:/%tests/py/test_pairing.py::test_duplicates_come_first
unknown ref not reported%explainers/build.py%s/if name not in namespace:\n            errs.append\(f\"unknown ref \{\{\{r\['key'\]\}\}\} \(cells.md:\{r\['line'\]\}\)\"\)\n            continue\n//%tests/py/test_cli.py::test_unknown_ref_counts_but_a_ref_in_code_does_not
bad format swallowed%explainers/build.py%s/errs.append\(f\"bad format/pass  # errs.append(f\"bad format/%tests/py/test_cli.py::test_bad_format
format spec ignored%explainers/build.py%s/format\(namespace\[name\], fmt\)/format(namespace[name], \"\")/%tests/py/test_cli.py::test_report_from_outside_the_repo_without_tex_on_path
lock not taken%explainers/build.py%s/fcntl.flock\(lock, fcntl.LOCK_EX \| fcntl.LOCK_NB\)/pass/%tests/py/test_cli.py::test_second_build_on_the_same_bundle_is_refused
TeX not put on PATH%explainers/build.py%s/os.environ\[\"PATH\"\] = /_unused = /%tests/py/test_cli.py::test_report_from_outside_the_repo_without_tex_on_path
scene built outside the dry-run config%explainers/build.py%s/            scene = cls\(\)\n            scene.render\(\)/            scene.render()/; s/    try:\n        # The scene is constructed/    scene = cls()\n    try:\n        # The scene is constructed/%tests/py/test_cli.py::test_report_from_outside_the_repo_without_tex_on_path
missing files not checked%explainers/build.py%s/    if missing:\n        raise BuildError\(2/    if False:\n        raise BuildError(2/%tests/py/test_cli.py::test_missing_files
class filter counts imported subclasses%explainers/build.py%s/ and v.__module__ == \"lesson\"//%tests/py/test_cli.py::test_exactly_one_lesson_class_counting_only_lesson_py
opened files not inputs%explainers/build.py%s/ \| opened\n/\n/%tests/py/test_pass1.py::test_inputs_are_the_files_the_lesson_used
build dir files become inputs%explainers/build.py%s/        if p.is_relative_to\(bundle\) and not p.is_relative_to\(bundle \/ "build"\):/        if p.is_relative_to(bundle):/%tests/py/test_pass1.py::test_inputs_are_the_files_the_lesson_used
stale bytecode becomes an input%explainers/build.py%s/ and p.suffix != \".pyc\"//%tests/py/test_pass1.py::test_stale_bytecode_in_the_bundle_is_not_an_input
lesson.py listed as its own input%explainers/build.py%s/ - before - \{\"lesson\"\} \|/ - before |/%tests/py/test_pass1.py::test_inputs_are_the_files_the_lesson_used
bytecode written into bundle%explainers/build.py%s/sys.dont_write_bytecode = True/sys.dont_write_bytecode = False/%tests/py/test_pass1.py::test_nothing_written_into_the_bundle_but_build
cells errors ignored%explainers/build.py%s/    if cells.errors:  # known before the scene runs: fail fast\n        raise BuildError\(1, cells.errors\)\n//%tests/py/test_cli.py::test_text_before_first_heading
no-cell lesson accepted%explainers/lesson.py%s/raise LessonError\(\"no self.cell\(\) in the lesson\"\)/pass/%tests/py/test_cli.py::test_no_cell_at_all
animation before first cell accepted%explainers/lesson.py%s/        if not self._cells:\n            raise LessonError\(f\"animation before/        if False:\n            raise LessonError(f\"animation before/%tests/py/test_cli.py::test_animation_before_first_cell
plain group not opened%explainers/lesson.py%s/if type\(m\) in \(VGroup, Group\):/if False:/%tests/py/test_pass1.py::test_plain_group_is_opened_into_its_numbers
copy keeps original line%explainers/lesson.py%s/        for x in c.get_family\(\):\n            x._born = line\n//%tests/py/test_pass1.py::test_end_state_kinds_and_creation_lines
run time from the clock%explainers/lesson.py%s/        super\(\).play\(\*args, \*\*kwargs\)\n        self._cells\[-1\].run_times.append\(self.duration\)/        t0 = self.renderer.time\n        super().play(*args, **kwargs)\n        self._cells[-1].run_times.append(self.renderer.time - t0)/%tests/py/test_pass1.py::test_cells_and_exact_run_times
outermost lesson frame%explainers/lesson.py%s/while f is not None and f.f_code.co_filename != source:\n        f = f.f_back\n    return f.f_lineno if f is not None else None/hit = None\n    while f is not None:\n        hit = f if f.f_code.co_filename == source else hit\n        f = f.f_back\n    return hit.f_lineno if hit is not None else None/%tests/py/test_pass1.py::test_end_state_kinds_and_creation_lines
partials pruned past 100%explainers/build.py%s/"max_files_cached": -1,/"max_files_cached": 100,/%tests/py/test_parallel.py::test_chunked_equals_one_chunk
chunk renders one animation too many%explainers/render.py%s/starts\[r\[-1\] \+ 1\] - 1\) for r in runs/starts[r[-1] + 1]) for r in runs/%tests/py/test_parallel.py::test_chunked_equals_one_chunk
join drops a cell's first partial%explainers/build.py%s/join\(\[parts\[i\] for i in range\(c.first_anim, /join([parts[i] for i in range(c.first_anim + 1, /%tests/py/test_render.py::test_clips_equal_a_one_pass_render_cut_at_cells
previous build's clips deleted%explainers/build.py%s/keep = \{c\["clip"\] for c in cells \+ previous\["cells"\]\}/keep = {c["clip"] for c in cells}/%tests/py/test_render.py::test_an_edit_inside_one_cell_changes_only_that_cells_clip_and_old_clips_last_one_rebuild
width ignores cores%explainers/render.py%s/return max\(1, min\(floor\(0.5 \* cores \/ WORKER_CORES\), /return max(1, min(/%tests/py/test_schedule.py::test_width_is_bound_by_cpu_ram_and_cells
seed not fixed%explainers/build.py%s/"seed": 0, //%tests/py/test_parallel.py::test_chunked_equals_one_chunk
encoder threads not pinned%explainers/render.py%s/ENCODER = \{"threads": "1", /ENCODER = {"threads": "0", /%tests/py/test_render.py::test_every_clip_is_single_threaded_keyint_6_crf_18
keyframe interval changed%explainers/render.py%s/"g": "6"/"g": "12"/%tests/py/test_render.py::test_every_clip_is_single_threaded_keyint_6_crf_18
stale media not cleared%explainers/render.py%s/    shutil.rmtree\(media, ignore_errors=True\)\n    groups/    groups/%tests/py/test_render.py::test_killed_build_keeps_the_previous_build_and_leaves_no_worker
worker outlives the build%explainers/render.py%s/if __name__ == \"__main__\":\n    _watch_parent\(\)\n/if __name__ == \"__main__\":\n/%tests/py/test_render.py::test_killed_build_keeps_the_previous_build_and_leaves_no_worker
no-animation cell accepted%explainers/build.py%s/errs = \[f'cell \"\{c.slug\}\" has no animation \(lesson.py:\{c.line\}\)' for c in scene._cells if not c.run_times\]/errs = []/%tests/py/test_render.py::test_a_cell_with_no_animation_is_an_error
chunk starts under a live updater%explainers/render.py%s/allowed = \[i for i in range\(len\(sums\) - 1\) if cuttable\[i \+ 1\]\]/allowed = list(range(len(sums) - 1))/%tests/py/test_schedule.py::test_chunks_never_start_where_a_time_based_updater_is_live
chunk cut not nearest%explainers/render.py%s/i = min\(allowed, key=lambda i: \(abs\(sums\[i\] - target\), i\)\)/i = max(i for i in allowed if sums[i] <= target) if any(sums[i] <= target for i in allowed) else allowed[0]/%tests/py/test_schedule.py::test_chunks_golden
clip named by something else%explainers/render.py%s/return hashlib.sha256\(path.read_bytes\(\)\).hexdigest\(\)/return hashlib.sha256(str(path).encode()).hexdigest()/%tests/py/test_render.py::test_index_validates_and_clips_are_named_by_content
frame stretched to the pixels%explainers/build.py%s/"frame_width": 8.0 \* WIDTH \/ HEIGHT, //%tests/py/test_render.py::test_clips_equal_a_one_pass_render_cut_at_cells
font size from constructor%explainers/lesson.py%s/return float\(m.font_size\), None/return float(m._font_size), None/%tests/py/test_pass1.py::test_font_sizes_follow_scale_and_class_for_text_latex_and_text_inside_containers
LaTeX sized as plain text%explainers/lesson.py%s/return None, float\(m.font_size\)/return float(m.font_size), None/%tests/py/test_pass1.py::test_font_sizes_follow_scale_and_class_for_text_latex_and_text_inside_containers
container text not measured%explainers/lesson.py%s/found = \[_sizes\(c\) for c in m.submobjects\]/found = []/%tests/py/test_pass1.py::test_font_sizes_follow_scale_and_class_for_text_latex_and_text_inside_containers
placeholders counted%explainers/lesson.py%s/if not \(g or d or s or f\):/if False:/%tests/py/test_pass1.py::test_end_state_kinds_and_creation_lines
attach ignored%explainers/geometry.py%s/if a.attached_to in b.owners or b.attached_to in a.owners:/if False:/%tests/py/test_geometry.py::test_cell_end_geometry[attached]
attach to a group ignored%explainers/lesson.py%s/visit\(s, born, groups \+ \[id\(m\)\], attached, transient\)/visit(s, born, groups, attached, transient)/%tests/py/test_geometry.py::test_cell_end_geometry[attached-to-a-group]
attach to a part ignored%explainers/lesson.py%s/groups \+ \[id\(x\) for x in m.get_family\(\)\]/groups + [id(m)]/%tests/py/test_geometry.py::test_cell_end_geometry[attached-to-a-part]
parent path skipped%explainers/lesson.py%s/elif isinstance\(m, VMobject\) and len\(m.points\):/elif isinstance(m, VMobject) and len(m.points) and not m.submobjects:/%tests/py/test_geometry.py::test_cell_end_geometry[text-on-an-arrow]
glyph on stroke skipped%explainers/geometry.py%s/ or _segment_hits\(g, p, d, s\)//%tests/py/test_geometry.py::test_cell_end_geometry[text-on-an-arrow]
parallel segment always inside%explainers/geometry.py%s/flat, inside = d == 0, \(lo < p\) & \(p < hi\)/flat, inside = d == 0, (lo < p) | True/%tests/py/test_geometry.py::test_cell_end_geometry[label-beside-a-line]
dot not a marker%explainers/lesson.py%s/elif isinstance\(m, Dot\):/elif False:/%tests/py/test_geometry.py::test_cell_end_geometry[dot-on-dot]
dot meets strokes%explainers/lesson.py%s/        if glyph:\n/        if glyph or isinstance(m, Dot):\n/%tests/py/test_geometry.py::test_cell_end_geometry[dot-on-an-arrow]
overlap without slack%explainers/geometry.py%s/_box_hits\(np.concatenate\(\[g, m\]\), solid, s\)/_box_hits(np.concatenate([g, m]), solid, 0)/%tests/py/test_geometry.py::test_cell_end_geometry[dots-touch-by-under-half-a-pixel]
own strokes ignored by the move%explainers/geometry.py%s/,\n                  \(_chords\(x.strokes\), _boxes\(y.glyphs\)\)\]/]/%tests/py/test_geometry.py::test_cell_end_geometry[number-line-under-text]
move along x only%explainers/geometry.py%s/_, axis, d = min\(best\)/_, axis, d = best[0]/%tests/py/test_geometry.py::test_cell_end_geometry[text-on-text]
both directions reported%explainers/geometry.py%s/\n                        break\n/\n/%tests/py/test_geometry.py::test_cell_end_geometry[text-on-text]
frame bound too wide%explainers/geometry.py%s/fx, fy = frame_width \/ 2, /fx, fy = frame_width \/ 2 + 0.4, /%tests/py/test_geometry.py::test_cell_end_geometry[off-frame-right]
left edge ignored%explainers/geometry.py%s/"left": -fx - ink\[:, 0\].min\(\),/"left": 0.0,/%tests/py/test_geometry.py::test_cell_end_geometry[off-frame-left]
top edge ignored%explainers/geometry.py%s/"top": ink\[:, 3\].max\(\) - fy,/"top": 0.0,/%tests/py/test_geometry.py::test_cell_end_geometry[off-frame-top]
fills ignored off frame%explainers/geometry.py%s/_boxes\(u.markers\), _boxes\(u.fills\)\]/_boxes(u.markers)]/%tests/py/test_geometry.py::test_cell_end_geometry[off-frame-fill]
images not drawn%explainers/lesson.py%s/if isinstance\(m, ImageMobject\):\n        out/if False:\n        out/%tests/py/test_geometry.py::test_cell_end_geometry[off-frame-image]
no sub-pixel slack%explainers/geometry.py%s/if over\[edge\] > s:/if over[edge] > 0:/%tests/py/test_geometry.py::test_cell_end_geometry[under-half-a-pixel-past-the-edge]
text minimum lowered%explainers/geometry.py%s/MIN_TEXT, MIN_LATEX = 32, 40/MIN_TEXT, MIN_LATEX = 24, 40/%tests/py/test_geometry.py::test_cell_end_geometry[small-text]
LaTeX minimum 32%explainers/geometry.py%s/MIN_TEXT, MIN_LATEX = 32, 40/MIN_TEXT, MIN_LATEX = 32, 32/%tests/py/test_geometry.py::test_cell_end_geometry[small-latex]
transients never checked%explainers/geometry.py%s/if u.transient_cell == n:/if False:/%tests/py/test_geometry.py::test_cell_end_geometry[leftover-transient]
transient not inherited through a group%explainers/lesson.py%s/transient = t if t is not None else transient/transient = t/%tests/py/test_geometry.py::test_cell_end_geometry[leftover-transient-group]
background strokes counted%explainers/lesson.py%s/if not background:/if True:/%tests/py/test_geometry.py::test_cell_end_geometry[text-on-a-plane]
world coordinates, not screen%explainers/lesson.py%s/screen = lambda m, p: \(self.camera.transform_points_pre_display\(m, p\) - self.camera.frame_center\)\[:, :2\]/screen = lambda m, p: p[:, :2]/%tests/py/test_geometry.py::test_cell_end_geometry_is_checked_where_the_3d_camera_draws[apart-in-the-world]
fixed-in-frame projected%explainers/lesson.py%s/self.camera.transform_points_pre_display\(m, p\)/self.camera.project_points(p)/%tests/py/test_geometry.py::test_cell_end_geometry_is_checked_where_the_3d_camera_draws[label-fixed-in-frame]
frame centre subtracted once%explainers/lesson.py%s/ - self.camera.frame_center\)\[:, :2\]/)[:, :2]/%tests/py/test_geometry.py::test_cell_end_geometry_is_checked_where_the_3d_camera_draws[apart-in-the-world]
camera move ignored%explainers/lesson.py%s/if self._camera_state\(\) != self._camera:/if False:/%tests/py/test_geometry.py::test_a_moved_3d_camera_is_an_error[theta=30 * DEGREES]
zoom not in the camera state%explainers/lesson.py%s/float\(c.get_zoom\(\)\), //%tests/py/test_geometry.py::test_a_moved_3d_camera_is_an_error[zoom=1.5]
frame centre not in the camera state%explainers/lesson.py%s/, \*map\(float, c.frame_center\)\]/]/%tests/py/test_geometry.py::test_a_moved_3d_camera_is_an_error[frame_center=[1, 0, 0]]
frame step wrong%src/renderer/src/Player.tsx%s/Math.round\(t \* fps - 0.5\)/Math.round(t * fps)/%e2e:player.spec.ts:seek and step land on frames k and k+1
r without rewind%src/renderer/src/Player.tsx%s/      v.currentTime = 0\n      void play\(v\)/      void play(v)/%e2e:player.spec.ts:r mid-clip rewinds and plays
rebuild resets the time%src/renderer/src/Player.tsx%s/const same = prev\?.el === v && prev.slug === slug/const same = false/%e2e:player.spec.ts:a rebuild while paused keeps the frame
rebuild pauses the playing clip%src/renderer/src/Player.tsx%s/if \(!resume\?.paused\) void play\(v\)/if (!resume) void play(v)/%e2e:player.spec.ts:a rebuild while playing keeps playing from where it was
media errors silent%src/renderer/src/Player.tsx%s/\{failed\?.url === clip.url && /{false && /%e2e:player.spec.ts:a clip that cannot load says so
watch off%src/main/windows.ts%s/!!rel && \(!rel.startsWith\('build\/'\) \|\| rel === 'build\/index.json'\)/false/%e2e:alerts.spec.ts:editing lesson.py raises the alert and restoring clears it
repo dirs not watched%src/main/windows.ts%s/\.filter\(\(x\) => existsSync\(x\)\)/.filter(() => false)/%e2e:alerts.spec.ts:editing a repo file the build read raises the alert
bundle inputs not checked%src/main/bundle.ts%s/\.filter\(\(\[rel, h\]\) => sha\(join\(dir, rel\)\) !== h\)/.filter(() => false)/%unit:bundle.spec.ts:an edited bundle input is stale
repo inputs not checked%src/main/bundle.ts%s/\.filter\(\(\[rel, h\]\) => sha\(join\(build.repo_root, rel\)\) !== h\)/.filter(() => false)/%unit:bundle.spec.ts:an edited repo input is stale
slug order not checked%src/main/bundle.ts%s/if \(slugs.join\('\\n'\) !== built.join\('\\n'\)\)/if (false)/%unit:bundle.spec.ts:swapped headings raise the order alert
schema not validated%src/main/bundle.ts%s/if \(index !== null && !validate\(index\)\)/if (false)/%unit:bundle.spec.ts:an index without fps is a load error
empty cells.md accepted%src/main/bundle.ts%s/if \(!found.sections.length\) throw/if (false) throw/%unit:bundle.spec.ts:an empty cells.md is a load error
duplicate slugs accepted%src/main/bundle.ts%s/if \(dup\) throw/if (false) throw/%unit:bundle.spec.ts:duplicate headings are a load error
disk errors escape as raw errors%src/main/bundle.ts%s/throw new LoadError\(`\$\{path\}: \$\{\(e as Error\).message\}`\)/throw e/%unit:bundle.spec.ts:a vanished cells.md and a half-written index.json are load errors
clip served outside the bundle%src/main/bundle.ts%s/return real.endsWith\('.mp4'\) && dirs.some/return real.endsWith('.mp4') || dirs.some/%unit:bundle.spec.ts:clipPath serves only open bundles' clips
clip url not percent-safe%src/main/bundle.ts%s/u.pathname = pathToFileURL\(abs\).pathname/u.pathname = abs/%unit:bundle.spec.ts:clipPath serves only open bundles' clips
refs spliced at source offsets%tools/grammar.mjs%s/const vstart = nth\(node.value, lit, ordinal\)/const vstart = m.index/%unit:grammar.spec.ts:refsIn value offsets survive escapes, entities and quotes
position not reported%src/renderer/src/App.tsx%s/if \(slug\) window.api.at\(slug\)/if (slug) void 0/%e2e:open.spec.ts:relaunch restores window, bounds and cell
session not written at quit%src/main/windows.ts%s/app.on\('before-quit', \(\) => \{\n  saveSession\(\)\n/app.on('before-quit', () => {\n/%e2e:open.spec.ts:relaunch restores window, bounds and cell
reload loses the slug%src/renderer/src/App.tsx%s/cur: i >= 0 \? i : Math.min/cur: false ? i : Math.min/%e2e:alerts.spec.ts:swapped headings keep the current cell
go to off by one%src/renderer/src/GoTo.tsx%s/setCur\(k - 1\)/setCur(k)/%e2e:find.spec.ts:go to cell
find does not move the current cell%src/renderer/src/Find.tsx%s/    setCur\(x.cell\)\n//%e2e:find.spec.ts:find steps across cells
find jumps on reload%src/renderer/src/Find.tsx%s/if \(jump.current && found.length\) show/if (found.length) show/%e2e:find.spec.ts:a reload while Find is open leaves the reader on their cell
find counts hidden MathML%src/renderer/src/Find.tsx%s/n.parentElement!.closest\('.katex-mathml'\)/false/%e2e:find.spec.ts:find skips formula annotations
clip not seekable%src/main/index.ts%s/const r = byteRange\(req.headers.get\('range'\), size\)/const r = null/; s/        'Accept-Ranges': 'bytes',\n//; s/      headers\['Content-Length'\] = String\(end - start \+ 1\)\n//%e2e:player.spec.ts:seek and step land on frames k and k+1
range parsed wrong%src/main/bundle.ts%s/start: Math.max\(0, size - n\)/start: n/%unit:bundle.spec.ts:byteRange answers what a video asks for
open-file ignored%src/main/windows.ts%s/  if \(app.isReady\(\)\) openPath\(p\)/  if (app.isReady()) void p/%e2e:open.spec.ts:a bundle handed over by Finder (open-file) opens in its own window
other cells not preserved%src/main/bundle.ts%s/ \+ body \+ text0.slice\(s.end\)/ + body/%e2e:edit.spec.ts:editing cell 3 while cell 5 changes keeps both
conflict not detected%src/main/bundle.ts%s/if \(md !== base\) return/if (false) return/%e2e:edit.spec.ts:editing cell 3 while cell 3 changes shows the conflict and writes nothing
invalid text written%src/main/bundle.ts%s/if \(after.errors.length \|\| slugs\(after\) !== slugs\(found\)\)/if (false)/%unit:bundle.spec.ts:saveSection refuses text that changes the cells
Keep mine uses the old base%src/renderer/src/App.tsx%s/if \(p\?.t === 'conflict'\) save\(p.disk\)/if (p?.t === 'conflict') save()/%e2e:edit.spec.ts:Keep mine saves over the disk version
a reload ends the edit%src/renderer/src/App.tsx%s/          return setS\(\(old\) => \{/          setEditingState(null)\n          return setS((old) => {/%e2e:edit.spec.ts:a reload while editing keeps the buffer
buffer lost when the heading vanishes%src/renderer/src/App.tsx%s/\{gone && editor /{false && editor /%e2e:edit.spec.ts:a heading renamed while editing keeps the buffer and says the cell is gone
leaving does not save%src/renderer/src/Editor.tsx%s/if \(!e.currentTarget.contains\(e.relatedTarget as Node \| null\) && document.hasFocus\(\)\)/if (false)/%e2e:edit.spec.ts:moving to another cell saves
Esc saves%src/renderer/src/Editor.tsx%s/\{ key: 'Escape', run: \(\) => \(onCancel\(\), true\) \}/{ key: 'Escape', run: () => (onSave(), true) }/%e2e:edit.spec.ts:Esc discards the edit
keys handled inside the editor%src/renderer/src/App.tsx%s/      if \(\(e.target as Element\).closest\?.\('.cm-editor'\)\) return \/\/ typing in a cell\n//%e2e:edit.spec.ts:keys typed in the editor stay in the editor
paste role missing%src/main/index.ts%s/            \{ id: 'paste', role: 'paste' \},\n//%e2e:clipboard.spec.ts:paste works in the editor
unresolved ref not red%src/renderer/src/atoms.ts%s/\? 'ref' : 'unresolved'/? 'ref' : 'ref'/%e2e:edit.spec.ts:an unknown ref is red
rendered text copied%src/renderer/src/copy.ts%s/(export function copySource\(e: ClipboardEvent, cells: Cell\[\]\): void \{)/$1\n  if (cells) return/%e2e:copy.spec.ts:copy across a formula, a bold word and a code span is the exact source
no widening%src/renderer/src/copy.ts%s/const atom = atomOf\(el, md\)/const atom = null/%e2e:copy.spec.ts:a selection inside a formula is the whole formula
display math unwrapped%src/renderer/src/stamp.ts%s/else if \(display && c.position\) parent/else if (false) parent/%e2e:copy.spec.ts:a selection inside a formula is the whole formula
code not an atom%src/renderer/src/stamp.ts%s/if \(c.tagName === 'a' \|\| c.tagName === 'code'\) c.properties.dataAtom/if (c.tagName === 'a') c.properties.dataAtom/%e2e:copy.spec.ts:a selection inside a fenced code block is the whole block
inexact treated as exact%src/renderer/src/stamp.ts%s/c.value === md.slice\(r.dataS, r.dataE\) \? \{ dataX: '' \} : \{\}/{ dataX: '' }/%e2e:copy.spec.ts:a selection inside an escaped run is its whole source
ref not an atom%src/renderer/src/atoms.ts%s/\{ dataAtom: '', dataS: g.hit.start, dataE: g.hit.end, \.\.\.props\(g.hit\) \}/{ dataS: g.hit.start, dataE: g.hit.end, ...props(g.hit) }/%e2e:copy.spec.ts:a selection inside a ref is the whole ref
atom unstamped%src/renderer/src/atoms.ts%s/\{ dataAtom: '', dataS: g.hit.start, dataE: g.hit.end, \.\.\.props\(g.hit\) \}/{ dataAtom: '', ...props(g.hit) }/%unit:grammar.spec.ts:atoms carry their source range
cross-cell join without heads%src/renderer/src/copy.ts%s/return out \+ cells\[b.cell\].head \+ '\\n' \+ /return out + /%e2e:copy.spec.ts:copy across cells is the file between the two points
container points not normalized%src/renderer/src/copy.ts%s/return l \? \{ cell: ci, off: num\(l, 'e'\) \} : prev\(\)/return l ? { cell: ci, off: num(l, 'e') } : null/%e2e:copy.spec.ts:a triple-clicked paragraph is its source
an open edit replaced%src/renderer/src/App.tsx%s/if \(edit.current === null\)\n\s*setEditing/setEditing/%e2e:edit.spec.ts:double-clicking another cell keeps an edit with a conflict
problem cleared while saving%src/renderer/src/App.tsx%s/const sending = \{ ...e, base: from, saving: true \}/const sending = { ...e, base: from, saving: true, problem: null }/%e2e:edit.spec.ts:double-clicking another cell keeps an edit with a conflict
transcript room as padding%src/renderer/src/theme.css%s/  padding-top: 8px;/  padding: 8px 0 40vh;/%e2e:player.spec.ts:in a wide window the player stays in view as the cells move
the bar does nothing%src/renderer/src/App.tsx%s/      setScale\(s\)\n//%e2e:player.spec.ts:dragging the bar under the video shrinks its frame, keeps the picture whole and is remembered
the video size forgotten%src/renderer/src/App.tsx%s/      localStorage.setItem\(SCALE, String\(s\)\)\n//%e2e:player.spec.ts:dragging the bar under the video shrinks its frame, keeps the picture whole and is remembered
a small frame stretches the picture%src/renderer/src/theme.css%s/  object-fit: contain;/  object-fit: fill;/%e2e:player.spec.ts:dragging the bar under the video shrinks its frame, keeps the picture whole and is remembered
saving unfocuses the editor%src/renderer/src/Editor.tsx%s/EditorState.readOnly.of\(saving\)/EditorView.editable.of(!saving)/%e2e:edit.spec.ts:editing cell 3 while cell 3 changes shows the conflict and writes nothing
a failed write escapes%src/main/bundle.ts%s/  try \{\n    atomicWrite\(path, next\)\n  \} catch \(e\) \{\n    return \{ t: 'invalid', message: `\$\{path\}: \$\{\(e as Error\).message\}; nothing was saved` \}\n  \}/  atomicWrite(path, next)/%unit:bundle.spec.ts:saveSection reports a failed write as invalid and writes nothing
link not opened%src/renderer/src/Transcript.tsx%s/const link = \(e.target as Element\).closest\('\[data-link\]'\)/const link = null/%e2e:link.spec.ts:a link into this bundle moves to its cell
lessons folder ignored%src/main/windows.ts%s/const LESSONS = process.env.EX_LESSONS \?\? /const LESSONS = /%e2e:link.spec.ts:a link to another bundle opens it at its cell
an open target is focused but not moved%src/main/windows.ts%s/    send\(open, \{ t: 'show', slug: cell \}\)\n//%e2e:link.spec.ts:a link to another bundle opens it at its cell
missing cell silent%src/main/windows.ts%s/if \(!lesson.cells.some\(\(c\) => c.slug === cell\)\) throw/if (false) throw/%e2e:link.spec.ts:a link to a missing cell says so
links carry no target%src/renderer/src/atoms.ts%s/\{ dataLink: h.link, className: \['link'\] \}/{ className: ['link'] }/%unit:grammar.spec.ts:links are atoms with their target
fingerprint without frames_sha%src/main/bundle.ts%s/\|\| cell.clip.frames_sha === c.fingerprint.frames_sha/|| true/%e2e:comments.spec.ts:a rebuild changing one cell's frames drops that cell's comments only
fingerprint of the wrong cell%src/main/bundle.ts%s/if \(sectionSha\(cell\) !== c.fingerprint.section_sha\)/if (sectionSha(cells[0]) !== c.fingerprint.section_sha)/%e2e:comments.spec.ts:editing its cell drops it and keeps others
silent orphan drop%src/main/bundle.ts%s/if \(!cell\) return true \/\/ an orphan/if (!cell) return false/%e2e:comments.spec.ts:a removed slug shows its comments as orphaned
an unbuilt cell's comments dropped%src/main/bundle.ts%s/return !cell.clip \|\| cell.clip.frames_sha/return !!cell.clip \&\& cell.clip.frames_sha/%unit:bundle.spec.ts:an unbuilt bundle keeps comments whose prose is unchanged and drops those whose prose changed
pruned in memory only%src/main/windows.ts%s/    writeComments\(dir, r.comments.kept\)\n//%e2e:comments.spec.ts:editing its cell drops it and keeps others
prune only on reload%src/main/windows.ts%s/  const \{ lesson, repoFiles \} = loadAndPrune\(dir\)/  const { lesson, repoFiles } = load(dir)/%e2e:comments.spec.ts:a bundle whose comments went stale while closed is pruned when it opens
addComment from memory%src/main/bundle.ts%s/    fingerprint: fingerprint\(cell\)/    fingerprint: { section_sha: '0'.repeat(64), frames_sha: '0'.repeat(64) }/%unit:bundle.spec.ts:addComment writes a schema-valid comment with its fingerprint
invalid comments.json accepted%src/main/bundle.ts%s/if \(!validateComments\(file\)\) throw/if (false) throw/%unit:bundle.spec.ts:an invalid comments.json is a LoadError naming the schema path
created not checked as a date-time%src/main/bundle.ts%s/addFormats\(new Ajv2020\(\{ allErrors: true \}\), \['date-time'\]\)/new Ajv2020({ allErrors: true }).addFormat('date-time', true)/%unit:bundle.spec.ts:an invalid comments.json is a LoadError naming the schema path
addComment ignores the prose it was measured on%src/main/bundle.ts%s/if \(cell.md !== base\) throw/if (false) throw/%unit:bundle.spec.ts:addComment refuses a span measured on older prose
resolve not written%src/main/bundle.ts%s/comments.kept.filter\(\(c\) => c.id !== id\)/comments.kept/%e2e:comments.spec.ts:✕ removes a comment from the file
ping without the lesson folder%src/main/windows.ts%s/EXPLAINER: w.dir/EXPLAINER: ''/%e2e:comments.spec.ts:each Ping runs the command once, in the lesson's folder
a failing ping silent%src/main/windows.ts%s/if \(err\) dialog.showErrorBox/if (false) dialog.showErrorBox/%e2e:comments.spec.ts:a failing Ping command says so
unset ping runs the template%src/renderer/src/Comments.tsx%s/if \(command\) window.api.ping\(command\)/if (true) window.api.ping(command ?? TEMPLATE)/%e2e:comments.spec.ts:Ping with no command shows the template
comment keys taken by the player%src/renderer/src/App.tsx%s/      if \(e.target instanceof HTMLTextAreaElement\) return.*\n//%e2e:comments.spec.ts:typing a comment keeps every key
quote by code points%explainers/comments.py%s/return text.encode\("utf-16-le"\)\[2 \* start:2 \* end\].decode\("utf-16-le"\)/return text[start:end]/%tests/py/test_comments.py::test_prints_exactly_the_files_comments_in_cell_order
span from rendered text%src/renderer/src/selection.ts%s/const span: \[number, number\] = \[a!.off, b!.off\]/const span: [number, number] = [r.startOffset, r.endOffset]/%e2e:comments.spec.ts:a highlight comment stores the exact span
unbuilt cells' prose not judged%src/main/bundle.ts%s/if \(sectionSha\(cell\) !== c.fingerprint.section_sha\) return false/if (cell.clip \&\& sectionSha(cell) !== c.fingerprint.section_sha) return false/%unit:bundle.spec.ts:an unbuilt bundle keeps comments whose prose is unchanged and drops those whose prose changed
a failed prune escapes%src/main/windows.ts%s/  \} catch \(e\) \{\n    \/\/ the lesson still shows the pruned list/  } catch (e) {\n    throw e\n    \/\/ the lesson still shows the pruned list/%e2e:comments.spec.ts:a stale comment that cannot be pruned says so
box closes before the answer%src/renderer/src/Comments.tsx%s/      if \(r.ok\) close\(\)\n      else setRefused\(r.message\)/      close()/%e2e:comments.spec.ts:a refused comment keeps its text in the box
colour not recorded%explainers/fingerprint.py%s/        def record\(\*args\):\n/        def record(*args):\n            if name == "set_source_rgba": return\n/%tests/py/test_frames.py::test_a_different_picture_records_different_frames[fill]
line width not recorded%explainers/fingerprint.py%s/        def record\(\*args\):\n/        def record(*args):\n            if name == "set_line_width": return\n/%tests/py/test_frames.py::test_a_different_picture_records_different_frames[stroke]
drawing order lost%explainers/fingerprint.py%s/repr\(self._ops\)/repr(sorted(self._ops, key=repr))/%tests/py/test_frames.py::test_a_different_picture_records_different_frames[order]
gradient stops ignored%explainers/fingerprint.py%s/a.get_color_stops_rgba\(\)/()/%tests/py/test_frames.py::test_a_different_picture_records_different_frames[gradient]
static frame not folded in%explainers/fingerprint.py%s/self._canvas = frame.digest/self._canvas = b""/%tests/py/test_frames.py::test_a_different_picture_records_different_frames[static]
image pixels ignored%explainers/fingerprint.py%s/pixels.tobytes\(\), //%tests/py/test_frames.py::test_a_different_picture_records_different_frames[image]
point colours ignored%explainers/fingerprint.py%s/np.asarray\(rgbas, float\).tobytes\(\)/b""/%tests/py/test_frames.py::test_a_different_picture_records_different_frames[points]
frame repeats ignored%explainers/fingerprint.py%s/\(frame.digest, repeat\)/(frame.digest, 1)/%tests/py/test_frames.py::test_a_different_picture_records_different_frames[hold]
animation boundaries lost%explainers/lesson.py%s/        if self.RECORDING:\n            self._cells\[-1\].drawn.append\(self._recorder.play_digest\(\)\)\n//; s/        c.end = self._end_state\(\)/        c.drawn.append(self._recorder.play_digest())\n        c.end = self._end_state()/%tests/py/test_frames.py::test_each_animation_records_its_own_digest
background ignored%explainers/fingerprint.py%s/self._canvas = self._array\(self._cam.background\)/self._canvas = b""/%tests/py/test_frames.py::test_a_different_picture_records_different_frames[background]
background image ignored%explainers/fingerprint.py%s/self._ops \+= \[\("background-image"/_ = [("background-image"/%tests/py/test_frames.py::test_a_different_picture_records_different_frames[backimage]
pass 1 not at the render's rate%explainers/build.py%s/"frame_rate": FPS,//%tests/py/test_frames.py::test_the_same_picture_records_the_same_frames[rate]
world-to-pixel matrix not recorded%explainers/fingerprint.py%s/self._ops.append\(\("matrix", /(lambda *_: None)(("matrix", /%tests/py/test_frames.py::test_where_the_camera_looks_is_in_every_frame[centre]
world-to-pixel scale not recorded%explainers/fingerprint.py%s/\*map\(float, \(sx, -sy, /*map(float, (0.0, 0.0, /%tests/py/test_frames.py::test_where_the_camera_looks_is_in_every_frame[width]
recording context answers any query%explainers/fingerprint.py%s/if name not in self.DRAWING:/if False:/%tests/py/test_frames.py::test_the_recording_context_refuses_what_it_cannot_answer
pass 1 hashes animations%explainers/build.py%s/"disable_caching": True, //%tests/py/test_incremental.py::test_a_rebuild_starts_its_chunks_only_where_fast_forwarding_is_exact
numpy version not fingerprinted%explainers/build.py%s/"manim", "numpy", /"manim", /%tests/py/test_incremental.py::test_fingerprints_cover_everything_after_the_frames
encoder code not fingerprinted%explainers/build.py%s/ *"code": \{n: sha256\(\(PICTURE_CODE \/ n\).read_bytes\(\)\) for n in \("fingerprint.py", "render.py"\)\},\n//%tests/py/test_incremental.py::test_fingerprints_cover_everything_after_the_frames
inputs not fingerprinted%explainers/build.py%s/after = json.dumps\(\{"inputs": inputs,/after = json.dumps({/%tests/py/test_incremental.py::test_an_edit_to_a_helper_module_renders_every_cell
one fingerprint for the whole lesson%explainers/build.py%s/json.dumps\(\[after, d\]\)/json.dumps([after, drawn])/%tests/py/test_incremental.py::test_an_edit_inside_one_cell_renders_that_cell
only the first changed cell rendered%explainers/render.py%s/    todo = set\(range\(len\(cuttable\)\)\) - reusable\n/    todo = set(range(len(cuttable))) - reusable\n    todo = set(sorted(todo)[:1]) if reusable else todo\n/%tests/py/test_incremental.py::test_an_edit_whose_effect_persists_renders_every_cell_it_reaches
previous build ignored%explainers/build.py%s/json.loads\(path.read_text\(\)\) if path.exists\(\) else/{"cells": []} if True else/%tests/py/test_incremental.py::test_no_change_renders_nothing
reused clip not checked%explainers/build.py%s/if f in old and clip\(old\[f\]\).is_file\(\) and frames_sha\(clip\(old\[f\]\)\) == old\[f\]\["frames_sha"\]\}/if f in old}/%tests/py/test_incremental.py::test_a_missing_or_altered_clip_is_rendered_again
reused clip checked by existence only%explainers/build.py%s/ and frames_sha\(clip\(old\[f\]\)\) == old\[f\]\["frames_sha"\]\}/}/%tests/py/test_incremental.py::test_a_missing_or_altered_clip_is_rendered_again
no reach back to a cuttable cell%explainers/render.py%s/            todo.add\(n\)/            pass/%tests/py/test_incremental.py::test_a_rebuild_starts_its_chunks_only_where_fast_forwarding_is_exact
reach back stops one cell early%explainers/render.py%s/while n > 0 and not cuttable\[n\]:/while n > 0 and not cuttable[n - 1]:/%tests/py/test_schedule.py::test_to_render_reaches_back_to_the_last_cell_a_chunk_may_start_at
pulled-in cells not reported%explainers/build.py%s/    spans \+= f"; \{pulled\} pulled in by a live updater" \* \(pulled > 0\)\n//%tests/py/test_incremental.py::test_a_rebuild_starts_its_chunks_only_where_fast_forwarding_is_exact
output format not pinned%explainers/render.py%s/"video_encoder_options": ENCODER, \*\*OUTPUT\}/"video_encoder_options": ENCODER}/%tests/py/test_render.py::test_a_manim_cfg_where_the_build_runs_does_not_change_the_clips
size tolerance removed%explainers/geometry.py%s/u.latex_size < MIN_LATEX - SIZE_EPS:/u.latex_size < MIN_LATEX:/%tests/py/test_geometry.py::test_cell_end_geometry[latex-at-the-minimum-moved]
EOF
)

run() {  # name file expr test-id: killed only if that exact test FAILS (an import error or collection error is not a kill)
  local name=$1 file=$2 expr=$3 test=$4 dir
  dir="$work/$(echo "$name" | tr -c 'a-zA-Z0-9\n' '-')"
  clone "$dir"
  cp "$dir/$file" "$dir/.orig"
  perl -0pi -e "$expr" "$dir/$file"
  if cmp -s "$dir/$file" "$dir/.orig"; then echo "NOT APPLIED: $name"; return 1; fi
  suite "$dir" "$test" >/dev/null 2>&1
  if python3 - "$dir/junit.xml" <<'PY'
import sys, xml.etree.ElementTree as E
try: cases = E.parse(sys.argv[1]).getroot().iter("testcase")
except Exception: sys.exit(1)
sys.exit(0 if any(c.find("failure") is not None for c in cases) else 1)
PY
  then echo "killed: $name"
  elif [ -f "$dir/junit.xml" ] && grep -q "<error" "$dir/junit.xml"; then echo "BROKE (error, not a failure): $name   ($test)"; return 1
  else echo "SURVIVED: $name   (should be killed by $test)"; return 1; fi
}
clone() {  # the working tree's own files (tracked and not ignored, edits included); big shared dirs by symlink
  mkdir -p "$1"
  (cd "$root" && git ls-files -co --exclude-standard -z) | rsync -a --from0 --files-from=- "$root/" "$1/"
  ln -s "$root/node_modules" "$1/node_modules"; ln -s "$root/.tinytex" "$1/.tinytex"
}
suite() {  # dir [test ids...]: run the tests in the clone on its own code. A pytest node id, or an app test named
  # <unit|e2e>:<spec file>:<exact title> (Playwright; e2e first rebuilds the clone's out/).
  local dir=$1; shift
  case "${1:-}" in
    unit:* | e2e:*)
      local kind=${1%%:*} rest=${1#*:}; local spec=${rest%%:*} title=${rest#*:}
      local grep; grep=$(printf '%s' "$title" | sed 's/[][\.*^$+?(){}|/]/\\&/g')
      (cd "$dir" && export PYTHONPATH="$dir" UV_NO_SYNC=1 UV_PROJECT_ENVIRONMENT="$root/.venv" EX_PROJECT=mutant &&
        { [ "$kind" = unit ] || npx electron-vite build >/dev/null; } &&
        npx playwright test "tests/$kind/$spec" -g "$grep" --project "$kind" --workers 1)
      cp "$dir/test-results/mutant/junit.xml" "$dir/junit.xml" ;;
    *)
      (cd "$dir" && PYTHONPATH="$dir" UV_NO_SYNC=1 UV_PROJECT_ENVIRONMENT="$root/.venv" \
        uv run -q --project "$dir" pytest "${@:-tests/py}" -q -p no:cacheprovider --junitxml="$dir/junit.xml") ;;
  esac
}
export -f run clone suite; export work root

# Control: the same clone setup with no mutation must pass, or every "killed" below would mean nothing.
ctl="$work/control"; clone "$ctl"
if ! suite "$ctl" -n "${JOBS:-2}" --dist loadgroup >/dev/null 2>&1; then
  echo "CONTROL FAILED: the unmutated clone does not pass; fix the harness first"; exit 1
fi
echo "control: unmutated clone passes"

echo "$MUTANTS" | while IFS='%' read -r name file expr test; do
  [ -n "$filter" ] && [[ "$name" != *"$filter"* ]] && continue
  printf '%s\0%s\0%s\0%s\0' "$name" "$file" "$expr" "$test"
done | xargs -0 -n 4 -P "${JOBS:-1}" bash -c 'run "$@"' _ | tee "$work/out"
total=$(wc -l < "$work/out" | tr -d ' '); killed=$(grep -c '^killed' "$work/out")
echo "mutants: $killed/$total killed"
[ -d "$root/test-results" ] && echo "mutants $killed/$total killed" >> "$root/test-results/summary.txt"
[ "$killed" = "$total" ]
