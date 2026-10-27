import { useEffect, useRef, useState } from 'react'
import type { Comment } from '../../shared/lesson'
import type { Draft } from './selection'

export function CommentBox({ draft, close }: { draft: Draft; close: () => void }) {
  const [text, setText] = useState('')
  const [refused, setRefused] = useState<string | null>(null)
  const [sending, setSending] = useState(false) // one comment per press, however fast the keys
  const box = useRef<HTMLTextAreaElement>(null)
  useEffect(() => box.current!.focus(), [])
  const send = () => {
    if (!text.trim() || sending) return
    setSending(true)
    window.api.comment(draft.cell, draft.base, draft.span, text).then((r) => {
      setSending(false)
      if (r.ok) close()
      else setRefused(r.message)
    })
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
      {refused && <div className="refused">{refused}</div>}
      <button onClick={send} disabled={!text.trim() || sending}>
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

const KEY = 'pingCommand'
const TEMPLATE = 'paseo send --no-wait <agent-id> "Check my comments: fetch-comments $EXPLAINER"'

// The command lives in localStorage, one store for every window, read at each press. Unset, Ping shows the template.
export function PingButton() {
  const [open, setOpen] = useState(false)
  const ping = () => {
    const command = localStorage.getItem(KEY)
    if (command) window.api.ping(command)
    else setOpen(true)
  }
  return (
    <div className="ping">
      {open && (
        <textarea
          autoFocus
          spellCheck={false}
          defaultValue={localStorage.getItem(KEY) ?? TEMPLATE}
          onChange={(e) => localStorage.setItem(KEY, e.target.value)}
        />
      )}
      <button className="send" onClick={ping}>
        Ping
      </button>
      <button className="settings" title="Ping command" onClick={() => setOpen(!open)}>
        ⚙
      </button>
    </div>
  )
}
