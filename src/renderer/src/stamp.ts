import type { Element, ElementContent, Root, RootContent } from 'hast'
import type { VFile } from 'vfile'

// Before KaTeX: every rendered piece carries its range in the cell's source (data-s, data-e), so copying gives the
// source. A text whose characters are its source (data-x) maps one to one; formulas, code, links and other text are
// atoms (data-atom), copied whole. KaTeX replaces a math element (and display math's <pre>), so math is wrapped first.
export const stamp = () => (tree: Root, file: VFile) => {
  const md = String(file)
  const range = (n: { position?: { start: { offset?: number }; end: { offset?: number } } }) => ({
    dataS: n.position!.start.offset!,
    dataE: n.position!.end.offset!
  })
  const cls = (e: Element) => (e.properties.className as string[] | undefined) ?? []
  const wrap = (tagName: string, e: Element): Element => ({
    type: 'element',
    tagName,
    properties: { ...range(e), dataAtom: '' },
    children: [e]
  })
  const walk = (parent: { children: (RootContent | ElementContent)[] }) =>
    parent.children.forEach((c, i) => {
      if (c.type === 'text') {
        if (!c.position) return
        const r = range(c)
        const x = c.value === md.slice(r.dataS, r.dataE) ? { dataX: '' } : {}
        parent.children[i] = {
          type: 'element',
          tagName: 'span',
          properties: { ...r, dataT: '', ...x },
          children: [c]
        }
        return
      }
      if (c.type !== 'element') return
      const display =
        c.tagName === 'pre' &&
        c.children.some((k) => k.type === 'element' && cls(k).includes('math-display'))
      if (c.tagName === 'code' && cls(c).includes('math-inline') && c.position)
        parent.children[i] = wrap('span', c)
      else if (display && c.position) parent.children[i] = wrap('div', c)
      else if (c.tagName === 'pre' && c.position)
        Object.assign(c.properties, range(c), { dataAtom: '' }) // a fence
      else {
        if (c.position && c.properties.dataS === undefined) Object.assign(c.properties, range(c))
        if (c.tagName === 'a' || c.tagName === 'code') c.properties.dataAtom = ''
        walk(c)
      }
    })
  walk(tree)
}
