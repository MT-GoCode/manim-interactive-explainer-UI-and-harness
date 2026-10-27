import { memo, useEffect, useMemo, useRef } from 'react'
import Markdown from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import type { Lesson } from '../../shared/lesson'
import { refs } from './refs'

type Plugins = { remark: Parameters<typeof Markdown>[0]['remarkPlugins'] }

// A cell re-renders only when its prose, its values or its own current flag change: moving the current cell (every
// arrow key) re-parses no markdown and re-runs no KaTeX.
const Cell = memo(function Cell(props: {
  n: number
  slug: string
  md: string
  current: boolean
  plugins: Plugins
  select: (i: number) => void
}) {
  const { n, slug, md, current, plugins, select } = props
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
      <div className="md">
        <Markdown remarkPlugins={plugins.remark} rehypePlugins={[rehypeKatex]}>
          {md}
        </Markdown>
      </div>
    </section>
  )
})

export function Transcript({
  lesson,
  cur,
  setCur
}: {
  lesson: Lesson
  cur: number
  setCur: (i: number) => void
}) {
  const values = lesson.build?.refs // unbuilt: no values yet, every reference stays literal
  const plugins = useMemo(() => ({ remark: [remarkGfm, remarkMath, refs(values ?? {})] }), [values])
  return (
    <div className="transcript">
      {lesson.cells.map((c, i) => (
        <Cell
          key={c.slug}
          n={i + 1}
          slug={c.slug}
          md={c.md}
          current={i === cur}
          plugins={plugins}
          select={setCur}
        />
      ))}
    </div>
  )
}
