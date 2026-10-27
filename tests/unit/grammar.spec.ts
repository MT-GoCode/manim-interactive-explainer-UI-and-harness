import { unified } from 'unified'
import remarkParse from 'remark-parse'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import { expect, test } from '@playwright/test'
import { refsIn } from '../../tools/grammar.mjs'

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
