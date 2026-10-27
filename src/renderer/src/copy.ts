import type { Cell } from '../../shared/lesson'

// Copy gives the source: each end of the selection is mapped to an offset in its cell's markdown through the stamps
// stamp.ts put on the rendered pieces, widened to whole atoms (formulas, code, links, refs, escaped text).
type Pt = { cell: number; off: number }

const cellEls = () => [...document.querySelectorAll<HTMLElement>('.transcript .cell')]
const num = (el: Element, k: 's' | 'e') => Number((el as HTMLElement).dataset[k])

// The outermost atom around an element, inside md.
function atomOf(el: Element | null, md: Element): Element | null {
  let a: Element | null = null
  for (let e = el; e && e !== md; e = e.parentElement) if (e.hasAttribute('data-atom')) a = e
  return a
}

// The pieces of md that copy maps through, in document order: atoms, and stamped text outside any atom.
const leaves = (md: Element) =>
  [...md.querySelectorAll('[data-atom], [data-t]')].filter(
    (el) => atomOf(el.parentElement, md) === null
  )

function bound(node: Node, offset: number, side: 'start' | 'end', cells: Cell[]): Pt | null {
  const els = cellEls()
  const before = (el: Element) =>
    el.compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING
  let ci = els.findIndex((c) => c.contains(node))
  if (ci < 0) {
    // between or around cells: the next cell's start, or the previous cell's end
    ci = side === 'start' ? els.findIndex((c) => !before(c)) : els.findLastIndex((c) => before(c))
    if (ci < 0) return null
    return side === 'start' ? { cell: ci, off: 0 } : { cell: ci, off: cells[ci].md.length }
  }
  const md = els[ci].querySelector('.md')
  const prev = (): Pt | null => (ci > 0 ? { cell: ci - 1, off: cells[ci - 1].md.length } : null)
  const next = (): Pt | null => (ci < els.length - 1 ? { cell: ci + 1, off: 0 } : null)
  if (!md || !md.contains(node)) {
    // in the cell but outside its prose (its number, or an editor): before the prose, or after it
    const after = md ? md.compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING : 0
    if (side === 'start') return after ? next() : { cell: ci, off: 0 }
    return after ? { cell: ci, off: cells[ci].md.length } : prev()
  }
  const el = node.nodeType === Node.TEXT_NODE ? node.parentElement : (node as Element)
  const atom = atomOf(el, md)
  if (atom) return { cell: ci, off: num(atom, side === 'start' ? 's' : 'e') }
  if (node.nodeType === Node.TEXT_NODE && el?.hasAttribute('data-t'))
    return el.hasAttribute('data-x')
      ? { cell: ci, off: num(el, 's') + offset }
      : { cell: ci, off: num(el, side === 'start' ? 's' : 'e') }
  // a point between pieces (a container, or text with no source such as a line break): the nearest piece inward
  const point = document.createRange()
  point.setStart(node, offset)
  const ls = leaves(md)
  if (side === 'start') {
    const l = ls.find((x) => point.comparePoint(x, 0) >= 0)
    return l ? { cell: ci, off: num(l, 's') } : next()
  }
  const l = ls.findLast((x) => point.comparePoint(x, x.childNodes.length) <= 0)
  return l ? { cell: ci, off: num(l, 'e') } : prev()
}

// The source between two points, exactly as in cells.md (a cell's heading line sits between it and the one before).
export function sourceBetween(a: Pt, b: Pt, cells: Cell[]): string {
  if (a.cell === b.cell) return cells[a.cell].md.slice(a.off, b.off)
  let out = cells[a.cell].md.slice(a.off)
  for (let i = a.cell + 1; i < b.cell; i++) out += cells[i].head + '\n' + cells[i].md
  return out + cells[b.cell].head + '\n' + cells[b.cell].md.slice(0, b.off)
}

// The copy handler: the selection's source, or nothing (the native copy) when it holds no prose.
export function copySource(e: ClipboardEvent, cells: Cell[]): void {
  const sel = document.getSelection()
  if (!sel || sel.isCollapsed || (e.target as Element).closest?.('.cm-editor')) return
  const r = sel.getRangeAt(0)
  const a = bound(r.startContainer, r.startOffset, 'start', cells)
  const b = bound(r.endContainer, r.endOffset, 'end', cells)
  if (!a || !b || a.cell > b.cell || (a.cell === b.cell && a.off >= b.off)) return
  e.preventDefault()
  e.clipboardData!.setData('text/plain', sourceBetween(a, b, cells))
}
