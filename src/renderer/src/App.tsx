import { useCallback, useEffect, useRef, useState } from 'react'
import type { Command } from '../../shared/ipc'
import type { Alert, Lesson } from '../../shared/lesson'
import { CommentBox, Orphans, PingButton } from './Comments'
import { useSelectionDraft, type Draft } from './selection'
import { Editor, type Problem } from './Editor'
import { Find } from './Find'
import { GoTo } from './GoTo'
import { Player, type PlayerHandle } from './Player'
import { Transcript } from './Transcript'

type State = { lesson: Lesson; cur: number }
// The one edit in progress: the cell, the text it began from, the text now, and what the last save answered.
type Editing = { slug: string; base: string; buf: string; saving: boolean; problem: Problem | null }

const banner = (lesson: Lesson): string[] => [
  ...(lesson.build === null ? ['Not built yet — run explain-build'] : []),
  ...lesson.alerts.map((a: Alert) => {
    switch (a.t) {
      case 'stale':
        return `Changed since last build: ${a.files.join(', ')}`
      case 'order':
        return `Prose and build disagree — cells.md: ${a.prose.join(', ')} · build: ${a.build.join(', ')}`
      case 'invalid':
        return a.message
      default:
        return a satisfies never
    }
  })
]

export function App() {
  const [s, setS] = useState<State | null>(null)
  const [finding, setFinding] = useState(0) // bumped by each ⌘F
  const [going, setGoing] = useState(0) // bumped by each ⌘G
  const player = useRef<PlayerHandle>(null)
  const [editing, setEditingState] = useState<Editing | null>(null)
  const [draft, setDraft] = useState<Draft | null>(null) // a comment being written
  // The handlers below read the edit through this ref: an editor's focusout fired after Esc or a finished save
  // (when it unmounts) finds no edit, or another one, and saves nothing.
  const edit = useRef<Editing | null>(null)
  const setEditing = useCallback((e: Editing | null) => {
    edit.current = e
    setEditingState(e)
  }, [])

  useEffect(() => {
    window.api.init().then(({ lesson, slug }) =>
      setS({
        lesson,
        cur: Math.max(
          0,
          lesson.cells.findIndex((c) => c.slug === slug)
        )
      })
    )
    window.api.onCommand((c: Command) => {
      switch (c.t) {
        case 'lesson':
          // The reader stays on their cell by slug; if it is gone, on the same position (a cell always exists).
          // Before init has answered there is nothing to update: init's answer is this lesson or a newer one.
          return setS((old) => {
            if (!old) return old
            const i = c.lesson.cells.findIndex((x) => x.slug === old.lesson.cells[old.cur].slug)
            return {
              lesson: c.lesson,
              cur: i >= 0 ? i : Math.min(old.cur, c.lesson.cells.length - 1)
            }
          })
        case 'find':
          return setFinding((n) => n + 1)
        case 'goto':
          return setGoing((n) => n + 1)
        case 'show':
          // main checked the cell exists; a reload that dropped it since leaves the reader where they are
          return setS((o) => {
            const i = o ? o.lesson.cells.findIndex((x) => x.slug === c.slug) : -1
            return o && i >= 0 ? { ...o, cur: i } : o
          })
        default:
          return c satisfies never
      }
    })
  }, [])

  const slug = s && s.lesson.cells[s.cur].slug
  useEffect(() => {
    if (slug) window.api.at(slug)
  }, [slug])

  useEffect(() => {
    // Captured before anything else; only a text input (Find, Go to) keeps its keys.
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement && e.target.type === 'text') return
      if ((e.target as Element).closest?.('.cm-editor')) return // typing in a cell
      if (e.metaKey || e.ctrlKey || e.altKey) return
      const act: Record<string, () => void> = {
        ArrowUp: () => setS((o) => o && { ...o, cur: Math.max(0, o.cur - 1) }),
        ArrowDown: () =>
          setS((o) => o && { ...o, cur: Math.min(o.lesson.cells.length - 1, o.cur + 1) }),
        ' ': () => player.current?.toggle(),
        r: () => player.current?.replay(),
        ',': () => player.current?.step(-1),
        '.': () => player.current?.step(1)
      }
      const f = act[e.key]
      if (!f) return
      e.preventDefault()
      e.stopPropagation()
      f()
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [])

  // Stable, so a cell that did not change does not re-render (the transcript's cells are memoised on it).
  const setCur = useCallback((i: number) => setS((o) => o && { ...o, cur: i }), [])

  // One edit at a time: while one is open (a problem showing, or a save in flight) another cannot replace it; a
  // successful leave-save has already ended it by the time a second click lands.
  const startEdit = useCallback(
    (slug: string, md: string) => {
      if (edit.current === null)
        setEditing({ slug, base: md, buf: md, saving: false, problem: null })
    },
    [setEditing]
  )
  const save = useCallback(
    (base?: string) => {
      const e = edit.current
      if (!e || e.saving) return
      const from = base ?? e.base
      if (e.buf === from && base === undefined) return setEditing(null)
      const sending = { ...e, base: from, saving: true, problem: null }
      setEditing(sending)
      window.api.save(e.slug, from, e.buf).then((r) => {
        if (edit.current !== sending) return // this edit was ended or replaced meanwhile
        if (r.t === 'saved') return setEditing(null)
        // gone: the reload that dropped the heading already shows it (derived below)
        setEditing({ ...sending, saving: false, problem: r.t === 'gone' ? null : r })
      })
    },
    [setEditing]
  )
  const cancel = useCallback(() => setEditing(null), [setEditing])
  const keepMine = useCallback(() => {
    const p = edit.current?.problem
    if (p?.t === 'conflict') save(p.disk)
  }, [save])
  const change = useCallback(
    (buf: string) => edit.current && setEditing({ ...edit.current, buf }),
    [setEditing]
  )

  const selection = useSelectionDraft(s?.lesson.cells ?? [])
  const commentCell = useCallback(
    (slug: string, md: string) => setDraft({ cell: slug, base: md, span: null, quote: null }),
    []
  )

  if (!s) return null
  const { lesson, cur } = s
  const lines = banner(lesson)
  const gone = !!editing && !lesson.cells.some((c) => c.slug === editing.slug)
  const editor = editing && (
    <Editor
      buf={editing.buf}
      saving={editing.saving}
      problem={editing.problem}
      gone={gone}
      onChange={change}
      onSave={save}
      onCancel={cancel}
      onKeepMine={keepMine}
      onBlurOut={save}
    />
  )
  return (
    <div className="app">
      {lines.length > 0 && (
        <div className="banner">
          {lines.map((l) => (
            <div key={l}>{l}</div>
          ))}
        </div>
      )}
      <Player ref={player} slug={lesson.cells[cur].slug} clip={lesson.cells[cur].clip} />
      {gone && editor /* its cell is gone from cells.md: the edit stays, above the transcript */}
      <Orphans comments={lesson.comments.filter((c) => c.on === 'orphan')} />
      <Transcript
        lesson={lesson}
        cur={cur}
        setCur={setCur}
        editing={gone ? null : (editing?.slug ?? null)}
        editor={gone ? null : editor}
        startEdit={startEdit}
        commentCell={commentCell}
      />
      {selection && !draft && (
        <button
          className="comment-sel"
          style={{ top: selection.at.bottom + 4, left: selection.at.left }}
          onMouseDown={(e) => e.preventDefault() /* keep the selection */}
          onClick={() => setDraft(selection.draft)}
        >
          Comment
        </button>
      )}
      {draft && <CommentBox draft={draft} close={() => setDraft(null)} />}
      <PingButton pinging={lesson.pinging} />
      {finding > 0 && (
        <Find ask={finding} lesson={lesson} setCur={setCur} close={() => setFinding(0)} />
      )}
      {going > 0 && (
        <GoTo ask={going} n={lesson.cells.length} setCur={setCur} close={() => setGoing(0)} />
      )}
    </div>
  )
}
