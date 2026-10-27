import { memo, useEffect, useMemo, useRef, type ReactNode } from 'react'
import Markdown from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import type { Comment, Lesson } from '../../shared/lesson'
import { Cards } from './Comments'
import { atoms } from './atoms'
import { copySource } from './copy'
import { stamp } from './stamp'

const NONE: Comment[] = []

type Plugins = {
  remark: Parameters<typeof Markdown>[0]['remarkPlugins']
  rehype: Parameters<typeof Markdown>[0]['rehypePlugins']
}

// A cell re-renders only when its prose, its values, its own current flag or its editor change: moving the current
// cell (every arrow key) re-parses no markdown and re-runs no KaTeX.
const Cell = memo(function Cell(props: {
  n: number
  slug: string
  md: string
  current: boolean
  plugins: Plugins
  editor: ReactNode | null
  built: boolean
  comments: Comment[]
  select: (i: number) => void
  startEdit: (slug: string, md: string) => void
  commentCell: (slug: string, md: string) => void
}) {
  const { n, slug, md, current, plugins, editor, built, comments, select, startEdit, commentCell } =
    props
  const el = useRef<HTMLElement>(null)
  useEffect(() => {
    if (current) void el.current!.scrollIntoView({ block: 'nearest' }) // a Promise here: never an effect cleanup
  }, [current])
  return (
    <section
      ref={el}
      className={'cell' + (current ? ' current' : '')}
      data-slug={slug}
      onClick={(e) => {
        const link = (e.target as Element).closest('[data-link]')
        if (!link) return select(n - 1)
        if (e.detail > 1) return // the second click of a double-click: already opened
        const [lesson, cell] = link.getAttribute('data-link')!.split('#')
        window.api.openLink(lesson, cell)
      }}
    >
      <span className="n">{n}</span>
      {editor ?? (
        <div
          className="md"
          onDoubleClick={(e) => {
            if (!(e.target as Element).closest('a, [data-link]')) startEdit(slug, md)
          }}
        >
          <Markdown remarkPlugins={plugins.remark} rehypePlugins={plugins.rehype}>
            {md}
          </Markdown>
        </div>
      )}
      <Cards comments={comments} />
      {built && (
        <button
          className="add-comment"
          title="Comment on this cell"
          onClick={(e) => {
            e.stopPropagation()
            commentCell(slug, md)
          }}
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.3"
          >
            <path d="M2.5 3h11v7.5h-6.5l-3 2.5v-2.5h-1.5z" strokeLinejoin="round" />
          </svg>
        </button>
      )}
    </section>
  )
})

export function Transcript(props: {
  lesson: Lesson
  cur: number
  setCur: (i: number) => void
  editing: string | null
  editor: ReactNode | null
  startEdit: (slug: string, md: string) => void
  commentCell: (slug: string, md: string) => void
}) {
  const { lesson, cur, setCur, editing, editor, startEdit, commentCell } = props
  // Each cell's comments, as stable arrays: a cell re-renders only when its own change.
  const byCell = useMemo(() => {
    const m = new Map<string, Comment[]>()
    for (const c of lesson.comments)
      if (c.on !== 'orphan') m.set(c.cell, [...(m.get(c.cell) ?? []), c])
    return m
  }, [lesson.comments])
  const values = lesson.build?.refs // unbuilt: no values yet, every reference stays literal
  const plugins = useMemo(
    () => ({
      remark: [remarkGfm, remarkMath, atoms(values ?? {})],
      rehype: [stamp, rehypeKatex]
    }),
    [values]
  )
  return (
    <div className="transcript" onCopy={(e) => copySource(e.nativeEvent, lesson.cells)}>
      {lesson.cells.map((c, i) => (
        <Cell
          key={c.slug}
          n={i + 1}
          slug={c.slug}
          md={c.md}
          current={i === cur}
          plugins={plugins}
          editor={c.slug === editing ? editor : null}
          built={c.clip !== null}
          comments={byCell.get(c.slug) ?? NONE}
          select={setCur}
          startEdit={startEdit}
          commentCell={commentCell}
        />
      ))}
    </div>
  )
}
