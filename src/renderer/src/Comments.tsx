import { useEffect, useRef, useState } from 'react'
import type { Comment } from '../../shared/lesson'
import type { Draft } from './selection'

export function CommentBox({ draft, close }: { draft: Draft; close: () => void }) {
  const [text, setText] = useState('')
  const box = useRef<HTMLTextAreaElement>(null)
  useEffect(() => box.current!.focus(), [])
  const send = () => {
    if (!text.trim()) return
    window.api.comment(draft.cell, draft.base, draft.span, text)
    close()
  }
  return (
    <div className="comment-box">
      <div className="quote">{draft.quote === null ? 'whole cell' : `“${draft.quote}”`}</div>
      <textarea
        ref={box}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && e.metaKey) send()
          else if (e.key === 'Escape') close()
          else return
          e.preventDefault()
        }}
      />
      <button onClick={send} disabled={!text.trim()}>
        Comment
      </button>
    </div>
  )
}

// A cell's comments, beside it: the quote (or "whole cell"), the text, ✕ to resolve.
export function Cards({ comments }: { comments: Comment[] }) {
  return (
    <div className="margin">
      {comments.map((c) => (
        <div className="card" key={c.id} data-id={c.id}>
          <div className="quote">{c.on === 'span' ? `“${c.quote}”` : 'whole cell'}</div>
          <div className="text">{c.text}</div>
          <button className="resolve" title="Resolve" onClick={() => window.api.resolve(c.id)}>
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}

export function Orphans({ comments }: { comments: Comment[] }) {
  if (!comments.length) return null
  return (
    <div className="orphans">
      <div className="title">Comments on cells that are gone</div>
      {comments.map((c) => (
        <div className="card" key={c.id} data-id={c.id}>
          <div className="quote">{c.cell}</div>
          <div className="text">{c.text}</div>
          <button className="resolve" title="Resolve" onClick={() => window.api.resolve(c.id)}>
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}

export function PingButton({ pinging }: { pinging: boolean }) {
  return (
    <button className="ping" disabled={pinging} onClick={() => window.api.ping()}>
      {pinging ? 'waiting…' : 'Ping'}
    </button>
  )
}
