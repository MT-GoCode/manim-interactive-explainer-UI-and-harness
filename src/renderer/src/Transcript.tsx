import { useEffect, useRef } from 'react'
import Markdown from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import type { Lesson } from '../../shared/lesson'
import { refs } from './refs'

export function Transcript({
  lesson,
  cur,
  setCur
}: {
  lesson: Lesson
  cur: number
  setCur: (i: number) => void
}) {
  const current = useRef<HTMLElement>(null)
  useEffect(() => {
    void current.current?.scrollIntoView({ block: 'nearest' }) // returns a Promise here: never the effect's cleanup
  }, [cur])
  const values = lesson.build?.refs ?? {} // unbuilt: no values yet, every reference stays literal
  return (
    <div className="transcript">
      {lesson.cells.map((c, i) => (
        <section
          key={c.slug}
          ref={i === cur ? current : undefined}
          className={'cell' + (i === cur ? ' current' : '')}
          data-slug={c.slug}
          onClick={() => setCur(i)}
        >
          <span className="n">{i + 1}</span>
          <div className="md">
            <Markdown
              remarkPlugins={[remarkGfm, remarkMath, refs(values)]}
              rehypePlugins={[rehypeKatex]}
            >
              {c.md}
            </Markdown>
          </div>
        </section>
      ))}
    </div>
  )
}
