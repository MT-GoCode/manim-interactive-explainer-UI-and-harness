// What counts as a value reference or a cell link in cells.md: one implementation, used by the build's reader
// (cells.mjs) and the app's renderer, so they cannot disagree. Pure: no Node imports (it runs in the renderer too).
import { visitParents } from 'unist-util-visit-parents'

// Searched in the source of text nodes, so an escaped `\{x}` or `\[[a#b]]` is literal text, not a reference.
export const REF = /(?<!\\)\{([A-Za-z_][A-Za-z0-9_]*(?::[^{}\n]*)?)\}/g
export const LINK = /(?<!\\)\[\[([a-z0-9-]+)#([a-z0-9-]+)\]\]/g
// Code and math carry their content as a raw value with no text children, so walking text nodes skips them.
// An autolink (`<url>` or a bare URL) is a link whose source does not start with "[": its text is a URL, not prose.
export const isAutolink = (source, n) =>
  n.type === 'link' && source[n.position.start.offset] !== '['

// Every prose text node with its source slice: [{ node, start, src }].
export function textsIn(tree, source) {
  const out = []
  visitParents(tree, 'text', (node, ancestors) => {
    if (ancestors.some((a) => isAutolink(source, a))) return
    const start = node.position.start.offset
    out.push({ node, start, src: source.slice(start, node.position.end.offset) })
  })
  return out
}

const nth = (s, needle, n) => {
  let i = -1
  for (let k = 0; k <= n; k++) i = s.indexOf(needle, i + 1)
  return i
}
const count = (s, needle) => s.split(needle).length - 1

// Every value reference: [{ node, key, start, end, vstart, vend }]; start/end index `source`, vstart/vend index
// node.value. Each literal `{key}` in a node's source, escaped or not, is exactly one `{key}` in its value (escapes,
// entities and `> ` prefixes change lengths, not that count), so a hit's ordinal among them locates it in the value.
export function refsIn(tree, source) {
  const out = []
  for (const { node, start, src } of textsIn(tree, source))
    for (const m of src.matchAll(REF)) {
      const lit = `{${m[1]}}`
      // An entity-written brace (`&#123;x}`) is a `{x}` in the value that is not one in the source: the ordinals no
      // longer line up, so the reference cannot be placed. It is the author's to fix, never a guess.
      if (count(node.value, lit) !== count(src, lit))
        throw Object.assign(
          new Error(`reference ${lit} beside a brace written as an entity; write it as {`),
          {
            offset: start + m.index
          }
        )
      const ordinal = src.slice(0, m.index).split(lit).length - 1
      const vstart = nth(node.value, lit, ordinal)
      out.push({
        node,
        key: m[1],
        start: start + m.index,
        end: start + m.index + lit.length,
        vstart,
        vend: vstart + lit.length
      })
    }
  return out
}
