import { useEffect, useRef, useState } from 'react'

// ⌘G: a cell number, Enter.
export function GoTo({
  n,
  setCur,
  close
}: {
  n: number
  setCur: (i: number) => void
  close: () => void
}) {
  const input = useRef<HTMLInputElement>(null)
  const [v, setV] = useState('')
  const [bad, setBad] = useState<string | null>(null)
  useEffect(() => input.current!.focus(), [])
  return (
    <div className="bar goto">
      <input
        ref={input}
        type="text"
        spellCheck={false}
        placeholder="Go to cell"
        value={v}
        onChange={(e) => {
          setV(e.target.value)
          setBad(null)
        }}
        onKeyDown={(e) => {
          if (e.key === 'Escape') close()
          else if (e.key === 'Enter') {
            const k = /^\d+$/.test(v) ? Number(v) : 0
            if (k >= 1 && k <= n) {
              setCur(k - 1)
              close()
            } else setBad(`No cell ${v} (1–${n})`)
          } else return
          e.preventDefault()
        }}
      />
      <span className="count">{bad ?? ''}</span>
    </div>
  )
}
