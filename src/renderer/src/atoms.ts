import type { ElementContent, Properties } from 'hast'
import type { PhrasingContent, Root, Text } from 'mdast'
import { visit } from 'unist-util-visit'
import type { VFile } from 'vfile'
import { LINK, matchesIn, refsIn } from '../../../tools/grammar.mjs'

// A ref ({key}) or a link ([[slug#cell]]), with its place in the source and in its text node's value.
type Hit = ReturnType<typeof matchesIn>[number] & ({ key: string } | { link: string })

// An mdast text node rendered as a <span> with these properties and hast children. Each atom carries its own source
// range: mdast-util-to-hast gives an hName element no position, so stamp.ts could not stamp it.
const span = (properties: Properties, children: ElementContent[]): Text => ({
  type: 'text',
  value: '',
  data: { hName: 'span', hProperties: properties, hChildren: children }
})

// Value references become their built values (unknown ones stay literal, in red), and [[slug#cell]] links become
// clickable `slug#cell` (data-link carries the target), each an atom that copies as its source. A text node whose value is its source slice splits into exact pieces around them; any other (escapes,
// entities) becomes one atom, since its characters do not map one to one onto the source.
export const atoms = (values: Record<string, string>) => () => (tree: Root, file: VFile) => {
  const source = String(file)
  const byNode = new Map<Text, Hit[]>()
  const hits: Hit[] = [
    ...refsIn(tree, source),
    ...matchesIn(tree, source, LINK).map((h) => ({ ...h, link: `${h.match[1]}#${h.match[2]}` }))
  ]
  for (const h of hits.sort((a, b) => a.start - b.start))
    byNode.set(h.node, [...(byNode.get(h.node) ?? []), h])
  const swaps: {
    parent: { children: PhrasingContent[] }
    index: number
    pieces: PhrasingContent[]
  }[] = []
  visit(tree, 'text', (node, index, parent) => {
    const hits = byNode.get(node)
    if (!hits || index === undefined || !parent) return
    const s0 = node.position!.start.offset!
    const e0 = node.position!.end.offset!
    const shown = (h: Hit): ElementContent[] => [
      {
        type: 'text',
        value: 'link' in h ? h.link : Object.hasOwn(values, h.key) ? values[h.key] : h.match[0]
      }
    ]
    // what a hit is, whether or not it carries its own source range
    const props = (h: Hit) =>
      'link' in h
        ? { dataLink: h.link, className: ['link'] }
        : { className: [Object.hasOwn(values, h.key) ? 'ref' : 'unresolved'] }
    // The node's value as segments: text between hits, and the hits.
    const segs: ({ text: [number, number] } | { hit: Hit })[] = []
    let at = 0
    for (const h of hits) {
      if (h.vstart > at) segs.push({ text: [at, h.vstart] })
      segs.push({ hit: h })
      at = h.vend
    }
    if (at < node.value.length) segs.push({ text: [at, node.value.length] })
    let pieces: PhrasingContent[]
    if (node.value === source.slice(s0, e0)) {
      // exact: a value offset is a source offset from the node's start
      pieces = segs.map((g) =>
        'text' in g
          ? {
              type: 'text',
              value: node.value.slice(...g.text),
              position: {
                start: { ...node.position!.start, offset: s0 + g.text[0] },
                end: { ...node.position!.start, offset: s0 + g.text[1] }
              }
            }
          : span(
              { dataAtom: '', dataS: g.hit.start, dataE: g.hit.end, ...props(g.hit) },
              shown(g.hit)
            )
      )
    } else {
      const children: ElementContent[] = segs.map((g) =>
        'text' in g
          ? { type: 'text', value: node.value.slice(...g.text) }
          : {
              type: 'element',
              tagName: 'span',
              properties: props(g.hit),
              children: shown(g.hit)
            }
      )
      pieces = [span({ dataAtom: '', dataS: s0, dataE: e0 }, children)]
    }
    swaps.push({ parent: parent as { children: PhrasingContent[] }, index, pieces })
  })
  for (const { parent, index, pieces } of swaps.reverse())
    parent.children.splice(index, 1, ...pieces)
}
