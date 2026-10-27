import { memo, useEffect, useMemo, useRef, type ReactNode } from 'react'
import Markdown from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import type { Lesson } from '../../shared/lesson'
import { atoms } from './atoms'
import { copySource } from './copy'
import { stamp } from './stamp'

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
  select: (i: number) => void
  startEdit: (slug: string, md: string) => void
}) {
  const { n, slug, md, current, plugins, editor, select, startEdit } = props
  const el = useRef<HTMLElement>(null)
  useEffect(() => {
    if (current) void el.current!.scrollIntoView({ block: 'nearest' }) // a Promise here: never an effect cleanup
  }, [current])
  return (
    <section
      ref={el}
      className={'cell' + (current ? ' current' : '')}
      data-slug={slug}
      onClick={() => select(n - 1)}
    >
      <span className="n">{n}</span>
      {editor ?? (
        <div
          className="md"
          onDoubleClick={(e) => {
            if (!(e.target as Element).closest('a')) startEdit(slug, md)
          }}
        >
          <Markdown remarkPlugins={plugins.remark} rehypePlugins={plugins.rehype}>
            {md}
          </Markdown>
        </div>
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
}) {
  const { lesson, cur, setCur, editing, editor, startEdit } = props
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
          select={setCur}
          startEdit={startEdit}
        />
      ))}
    </div>
  )
}
