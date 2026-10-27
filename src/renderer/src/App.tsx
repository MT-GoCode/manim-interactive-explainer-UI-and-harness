import { useCallback, useEffect, useRef, useState } from 'react'
import type { Command } from '../../shared/ipc'
import type { Alert, Lesson } from '../../shared/lesson'
import { Find } from './Find'
import { GoTo } from './GoTo'
import { Player, type PlayerHandle } from './Player'
import { Transcript } from './Transcript'

type State = { lesson: Lesson; cur: number }

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

  if (!s) return null
  const { lesson, cur } = s
  const lines = banner(lesson)
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
      <Transcript lesson={lesson} cur={cur} setCur={setCur} />
      {finding > 0 && (
        <Find ask={finding} lesson={lesson} setCur={setCur} close={() => setFinding(0)} />
      )}
      {going > 0 && (
        <GoTo ask={going} n={lesson.cells.length} setCur={setCur} close={() => setGoing(0)} />
      )}
    </div>
  )
}
