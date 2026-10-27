import { useEffect, useState } from 'react'
import type { Cell } from '../../shared/lesson'
import { bound } from './copy'

// What a new comment is on: a cell's whole prose, or a span of it, measured on `base` (the prose as rendered).
export type Draft = {
  cell: string
  base: string
  span: [number, number] | null
  quote: string | null
}

// A selection inside one built cell's prose offers a "Comment" button beside it; its span is the source the
// selection covers (bound(), as copy uses), measured on the prose as rendered.
export function useSelectionDraft(cells: Cell[]): { at: DOMRect; draft: Draft } | null {
  const [found, setFound] = useState<{ at: DOMRect; draft: Draft } | null>(null)
  useEffect(() => {
    const look = () => {
      const sel = document.getSelection()
      if (!sel || sel.isCollapsed) return setFound(null)
      const r = sel.getRangeAt(0)
      if ((r.startContainer.parentElement ?? (r.startContainer as Element)).closest('.comment-box'))
        return
      const a = bound(r.startContainer, r.startOffset, 'start', cells)
      const b = bound(r.endContainer, r.endOffset, 'end', cells)
      const cell = a && b && a.cell === b.cell && a.off < b.off ? cells[a.cell] : null
      if (!cell || !cell.clip) return setFound(null)
      const span: [number, number] = [a!.off, b!.off]
      setFound({
        at: r.getBoundingClientRect(),
        draft: { cell: cell.slug, base: cell.md, span, quote: cell.md.slice(...span) }
      })
    }
    document.addEventListener('selectionchange', look)
    return () => document.removeEventListener('selectionchange', look)
  }, [cells])
  return found
}
