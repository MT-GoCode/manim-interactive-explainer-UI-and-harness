import { unified } from 'unified'
import remarkParse from 'remark-parse'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import { expect, test } from '@playwright/test'
import { readCells } from '../../tools/cells.mjs'
import { LINK, matchesIn, refsIn } from '../../tools/grammar.mjs'
import remarkRehype from 'remark-rehype'
import { VFile } from 'vfile'
import { visit } from 'unist-util-visit'
import type { Element } from 'hast'
import { atoms } from '../../src/renderer/src/atoms'
import { stamp } from '../../src/renderer/src/stamp'

const hits = (md: string) =>
  refsIn(unified().use(remarkParse).use(remarkGfm).use(remarkMath).parse(md), md).map((h) => ({
    key: h.key,
    source: md.slice(h.start, h.end),
    value: h.node.value.slice(h.vstart, h.vend),
    before: h.node.value.slice(0, h.vstart)
  }))

test('refsIn value offsets survive escapes, entities and quotes', () => {
  expect(hits('a \\* b {x}')).toEqual([{ key: 'x', source: '{x}', value: '{x}', before: 'a * b ' }])
  expect(hits('&amp; {x}')).toEqual([{ key: 'x', source: '{x}', value: '{x}', before: '& ' }])
  expect(hits('> a\n> {x}')).toEqual([{ key: 'x', source: '{x}', value: '{x}', before: 'a\n' }])
  expect(hits('\\{x} {x}')).toEqual([{ key: 'x', source: '{x}', value: '{x}', before: '{x} ' }])
})

test("a reference beside an entity-written brace is the author's error, never a guess", () => {
  expect(readCells('## a\n&#123;x} {x}\n').errors).toEqual([
    '{x} beside a character written as an entity; write it plainly (cells.md:2)'
  ])
})

// The renderer's pipeline up to KaTeX, on a string: what copy reads is the stamps this leaves on the tree.

async function stamped(md: string, values: Record<string, string>) {
  const p = unified()
    .use(remarkParse)
    .use(remarkGfm)
    .use(remarkMath)
    .use(atoms(values))
    .use(remarkRehype)
    .use(stamp)
  const file = new VFile(md)
  const tree = await p.run(p.parse(file), file)
  const text = (e: Element): string =>
    e.children
      .map((c) => (c.type === 'text' ? c.value : c.type === 'element' ? text(c) : ''))
      .join('')
  const atomsFound: [string, string][] = []
  const exact: string[] = []
  visit(tree, 'element', (e: Element) => {
    const p = e.properties
    if (p.dataAtom !== undefined)
      atomsFound.push([md.slice(Number(p.dataS), Number(p.dataE)), text(e)])
    if (p.dataX !== undefined) exact.push(md.slice(Number(p.dataS), Number(p.dataE)))
  })
  return { atomsFound, exact }
}

test('atoms carry their source range', async () => {
  const r = await stamped('Top {p} and {x} done, `c` [l](http://a.b) $m$.\n', { p: '0.5' })
  expect(r.atomsFound).toEqual([
    ['{p}', '0.5'],
    ['{x}', '{x}'],
    ['`c`', 'c'],
    ['[l](http://a.b)', 'l'],
    ['$m$', 'm']
  ])
  expect(r.exact).toEqual(['Top ', ' and ', ' done, ', ' ', 'l', ' ', '.']) // a link's text is exact (copy widens to the link)
  // escaped text cannot map one to one: the whole run is one atom
  expect((await stamped('a \\* b {p}\n', { p: '0.5' })).atomsFound).toEqual([
    ['a \\* b {p}', 'a * b 0.5']
  ])
  // display math and a fence are atoms as wholes
  expect((await stamped('$$\ny\n$$\n\n```\nz\n```\n', {})).atomsFound.map((a) => a[0])).toEqual([
    '$$\ny\n$$',
    '```\nz\n```'
  ])
})

test('matchesIn finds links in prose only', () => {
  const md = 'See [[a#b]], `[[c#d]]` and \\[[e#f]].\n'
  const tree = unified().use(remarkParse).use(remarkGfm).use(remarkMath).parse(md)
  expect(
    matchesIn(tree, md, LINK).map((h) => [h.match[1], h.match[2], md.slice(h.start, h.end)])
  ).toEqual([['a', 'b', '[[a#b]]']])
})
