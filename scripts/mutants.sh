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
autolink text counted%tools/cells.mjs%s/if \(ancestors.some\(\(a\) => isAutolink\(text, a\)\)\) return/if (false) return/%tests/py/test_grammar.py::test_reader_matches_golden[link-url-and-autolink]
autolink decided by label text%tools/cells.mjs%s/text\[n.position.start.offset\] !== '\['/n.url === n.children.map((c) => c.value).join('')/%tests/py/test_grammar.py::test_reader_matches_golden[link-url-and-autolink]
escaped brace counted%tools/cells.mjs%s/\(\?<!\\\\\)\\\{/\\{/%tests/py/test_grammar.py::test_reader_matches_golden[escaped-brace-is-literal]
uppercase slug accepted%tools/cells.mjs%s/\^## \(\[a-z0-9-\]\+\)/^## ([A-Za-z0-9-]+)/%tests/py/test_grammar.py::test_reader_matches_golden[uppercase-heading-is-error]
closing hashes accepted%tools/cells.mjs%s/\[ \\t\]\*\$\/.exec/[ \\t#]*\$\/.exec/%tests/py/test_grammar.py::test_reader_matches_golden[closing-hashes-is-error]
section end off by one%tools/cells.mjs%s/heads\[i \+ 1\].start : text.length/heads[i + 1].start - 1 : text.length/%tests/py/test_grammar.py::test_reader_matches_golden[basic]
section starts at the #, not the line%tools/cells.mjs%s/start: lineStart\(n.position.start.offset\)/start: n.position.start.offset/%tests/py/test_grammar.py::test_reader_matches_golden[indented-heading-is-a-heading]
CR endings accepted%tools/cells.mjs%s/if \(text.includes\('\\r'\)\)/if (false)/%tests/py/test_grammar.py::test_reader_matches_golden[crlf-is-error]
preamble accepted%tools/cells.mjs%s/if \(pre.trim\(\)\) errors.push/if (false) errors.push/%tests/py/test_grammar.py::test_reader_matches_golden[preamble-is-error]
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
chunk renders one animation too many%explainers/render.py%s/first, last = starts\[g\[0\]\], starts\[g\[-1\] \+ 1\] - 1/first, last = starts[g[0]], starts[g[-1] + 1]/%tests/py/test_parallel.py::test_chunked_equals_one_chunk
join drops a cell's first partial%explainers/build.py%s/join\(\[parts\[i\] for i in range\(c.first_anim, /join([parts[i] for i in range(c.first_anim + 1, /%tests/py/test_render.py::test_clips_equal_a_one_pass_render_cut_at_cells
previous build's clips deleted%explainers/build.py%s/keep = \{c\["clip"\] for c in cells \+ previous\["cells"\]\}/keep = {c["clip"] for c in cells}/%tests/py/test_render.py::test_an_edit_inside_one_cell_changes_only_that_cells_clip_and_old_clips_last_one_rebuild
width ignores cores%explainers/render.py%s/return max\(1, min\(floor\(0.5 \* cores \/ WORKER_CORES\), /return max(1, min(/%tests/py/test_schedule.py::test_width_is_bound_by_cpu_ram_and_cells
seed not fixed%explainers/build.py%s/return \{"seed": 0, /return {/%tests/py/test_parallel.py::test_chunked_equals_one_chunk
encoder threads not pinned%explainers/render.py%s/ENCODER = \{"threads": "1", /ENCODER = {"threads": "0", /%tests/py/test_render.py::test_every_clip_is_single_threaded_keyint_6_crf_18
keyframe interval changed%explainers/render.py%s/"g": "6"/"g": "12"/%tests/py/test_render.py::test_every_clip_is_single_threaded_keyint_6_crf_18
stale media not cleared%explainers/render.py%s/    shutil.rmtree\(media, ignore_errors=True\)\n    groups/    groups/%tests/py/test_render.py::test_killed_build_keeps_the_previous_build_and_leaves_no_worker
worker outlives the build%explainers/render.py%s/if __name__ == \"__main__\":\n    _watch_parent\(\)\n/if __name__ == \"__main__\":\n/%tests/py/test_render.py::test_killed_build_keeps_the_previous_build_and_leaves_no_worker
no-animation cell accepted%explainers/build.py%s/errs = \[f'cell \"\{c.slug\}\" has no animation \(lesson.py:\{c.line\}\)' for c in scene._cells if not c.run_times\]/errs = []/%tests/py/test_render.py::test_a_cell_with_no_animation_is_an_error
chunk starts under a live updater%explainers/render.py%s/allowed = \[i for i in range\(len\(sums\) - 1\) if cuttable\[i \+ 1\]\]/allowed = list(range(len(sums) - 1))/%tests/py/test_schedule.py::test_chunks_never_start_where_a_time_based_updater_is_live
chunk cut not nearest%explainers/render.py%s/i = min\(allowed, key=lambda i: \(abs\(sums\[i\] - target\), i\)\)/i = max(i for i in allowed if sums[i] <= target) if any(sums[i] <= target for i in allowed) else allowed[0]/%tests/py/test_schedule.py::test_chunks_golden
clip named by something else%explainers/render.py%s/return hashlib.sha256\(path.read_bytes\(\)\).hexdigest\(\)/return hashlib.sha256(str(path).encode()).hexdigest()/%tests/py/test_render.py::test_index_validates_and_clips_are_named_by_content
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
clone() {
  cp -cR "$root" "$1" 2>/dev/null || cp -R "$root" "$1"
  rm -rf "$1/.venv" "$1/node_modules" "$1/.tinytex" "$1/test-results"
  ln -s "$root/node_modules" "$1/node_modules"; ln -s "$root/.tinytex" "$1/.tinytex"
}
suite() {  # dir [test ids...]: run pytest in the clone on its own code
  local dir=$1; shift
  (cd "$dir" && PYTHONPATH="$dir" UV_NO_SYNC=1 UV_PROJECT_ENVIRONMENT="$root/.venv" \
    uv run -q --project "$dir" pytest "${@:-tests/py}" -q -p no:cacheprovider --junitxml="$dir/junit.xml")
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
