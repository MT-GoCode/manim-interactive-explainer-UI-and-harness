// The one reader of cells.md, used by explain-build (node tools/cells.mjs <file>) and, from stratum 4, by the app.
// remark decides what is text, code and math, so the build and the renderer cannot disagree.
// Offsets are UTF-16 code units (JS string indices). Output: {sections, refs, links, errors}.
import { readFileSync, realpathSync } from 'node:fs'
import { pathToFileURL } from 'node:url'
import { unified } from 'unified'
import remarkParse from 'remark-parse'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import { visitParents } from 'unist-util-visit-parents'

// Searched in the source of text nodes, so an escaped `\{x}` or `\[[a#b]]` is literal text, not a reference.
const REF = /(?<!\\)\{([A-Za-z_][A-Za-z0-9_]*(?::[^{}\n]*)?)\}/g
const LINK = /(?<!\\)\[\[([a-z0-9-]+)#([a-z0-9-]+)\]\]/g
// Code and math carry their content as a raw value with no text children, so walking text nodes skips them.
// An autolink (`<url>` or a bare URL) is a link whose source does not start with "[": its text is a URL, not prose.
const isAutolink = (text, n) => n.type === 'link' && text[n.position.start.offset] !== '['

export function readCells(text) {
  const errors = []
  if (text.charCodeAt(0) === 0xfeff) errors.push('cells.md starts with a byte-order mark; save it as plain UTF-8')
  if (text.includes('\r')) errors.push('cells.md has CR line endings; save it with LF only')
  if (errors.length) return { sections: [], refs: [], links: [], errors }
  const lineAt = (offset) => text.slice(0, offset).split('\n').length
  const lineStart = (offset) => text.lastIndexOf('\n', offset - 1) + 1
  const tree = unified().use(remarkParse).use(remarkGfm).use(remarkMath).parse(text)
  // A cell heading is a top-level depth-2 ATX heading "## <slug>"; any other depth-2 heading is an error, never a
  // silent merge into the previous cell. A section starts at its heading's line start (indent included).
  const heads = []
  for (const n of tree.children) {
    if (n.type !== 'heading' || n.depth !== 2) continue
    const raw = text.slice(n.position.start.offset, n.position.end.offset)
    const m = /^## ([a-z0-9-]+)[ \t]*$/.exec(raw)
    if (m) heads.push({ slug: m[1], start: lineStart(n.position.start.offset), line: n.position.start.line })
    else errors.push(`"${raw.split('\n')[0]}" (cells.md:${n.position.start.line}) is not a cell heading; cell headings are "## <slug>", slug [a-z0-9-]+`)
  }
  const sections = heads.map((h, i) => ({ ...h, end: i + 1 < heads.length ? heads[i + 1].start : text.length }))
  const first = heads.length ? heads[0].start : text.length
  const pre = text.slice(0, first)
  if (pre.trim()) errors.push(`cells.md has text before the first heading (cells.md:${pre.split('\n').findIndex((l) => l.trim()) + 1})`)
  const refs = [], links = []
  visitParents(tree, 'text', (node, ancestors) => {
    if (ancestors.some((a) => isAutolink(text, a))) return
    const start = node.position.start.offset
    const src = text.slice(start, node.position.end.offset)
    for (const m of src.matchAll(REF)) refs.push({ key: m[1], name: m[1].split(':')[0], line: lineAt(start + m.index) })
    for (const m of src.matchAll(LINK)) links.push({ slug: m[1], cell: m[2], line: lineAt(start + m.index) })
  })
  return { sections, refs, links, errors }
}

if (import.meta.url === pathToFileURL(realpathSync(process.argv[1])).href) {
  process.stdout.write(JSON.stringify(readCells(readFileSync(process.argv[2], 'utf8'))) + '\n')
}
