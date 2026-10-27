import { useEffect, useRef, useState } from 'react'
import type { Lesson } from '../../shared/lesson'

type Match = { cell: number; range: Range }

// Every case-insensitive occurrence of q in the rendered prose, in document order, each marked with its cell.
// KaTeX's hidden MathML annotation repeats a formula's TeX source as text; it is not what the reader sees.
function search(q: string): Match[] {
  if (!q) return []
  // Matched on the text itself (lowercasing can change a string's length, e.g. 'İ', and shift every offset).
  const re = new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi')
  const out: Match[] = []
  document.querySelectorAll('.cell .md').forEach((md, cell) => {
    const walk = document.createTreeWalker(md, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) =>
        n.parentElement!.closest('.katex-mathml')
          ? NodeFilter.FILTER_REJECT
          : NodeFilter.FILTER_ACCEPT
    })
    for (let n = walk.nextNode(); n; n = walk.nextNode()) {
      for (const m of n.textContent!.matchAll(re)) {
        const range = new Range()
        range.setStart(n, m.index)
        range.setEnd(n, m.index + m[0].length)
        out.push({ cell, range })
      }
    }
  })
  return out
}

// ⌘F: searches what the transcript shows; the active match's cell becomes the current one.
export function Find(props: {
  ask: number
  lesson: Lesson
  setCur: (i: number) => void
  close: () => void
}) {
  const { ask, lesson, setCur, close } = props
  const input = useRef<HTMLInputElement>(null)
  const [q, setQ] = useState('')
  const [at, setAt] = useState(0)
  const [matches, setMatches] = useState<Match[]>([])
  // Only the reader moves the current cell (a new query, Enter, ⇧Enter); a reload re-highlights and leaves it.
  // A new query's matches exist only after the DOM search, so the query marks the jump and the search makes it.
  const jump = useRef(false)
  const show = (x: Match) => {
    setCur(x.cell)
    void x.range.startContainer.parentElement!.scrollIntoView({ block: 'center' })
  }
  // Matches are ranges into the rendered prose, so they are read from the DOM after React commits it (a reload
  // re-renders the prose and the old ranges are gone): the DOM is the outside system this effect syncs from.
  useEffect(() => {
    const found = search(q)
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMatches(found)
    if (jump.current && found.length) show(found[0])
    jump.current = false
  }, [q, lesson]) // eslint-disable-line react-hooks/exhaustive-deps
  const n = matches.length
  const m = n ? matches[at % n] : undefined

  useEffect(() => {
    input.current!.focus()
    input.current!.select()
  }, [ask])

  useEffect(() => {
    CSS.highlights.set('find', new Highlight(...matches.map((x) => x.range)))
    CSS.highlights.set('find-active', new Highlight(...(m ? [m.range] : [])))
  }, [matches, m])

  const clear = () => {
    CSS.highlights.delete('find')
    CSS.highlights.delete('find-active')
    close()
  }
  return (
    <div className="bar find">
      <input
        ref={input}
        type="text"
        spellCheck={false}
        placeholder="Find"
        value={q}
        onChange={(e) => {
          jump.current = true
          setQ(e.target.value)
          setAt(0)
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && n) {
            const next = (at + (e.shiftKey ? n - 1 : 1)) % n
            setAt(next)
            show(matches[next])
          } else if (e.key === 'Escape') clear()
          else return
          e.preventDefault()
        }}
      />
      <span className="count">{!q ? '' : n ? `${(at % n) + 1} of ${n}` : 'No results'}</span>
    </div>
  )
}
