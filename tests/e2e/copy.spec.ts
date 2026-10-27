import { readFileSync, writeFileSync } from 'fs'
import { join } from 'path'
import type { Page } from '@playwright/test'
import { click, expect, firstLesson, fixture, test, winId } from './app'

// Cell "divide" is rewritten to hold every kind of piece; expectations are slices of the file read back from disk.
const DIVIDE = 3
const PROSE =
  'A **bold** word, `code`, a \\* star and $x^2$ then {n_tokens} more.\n\n$$\ny^2\n$$\n\n```\nfenced\n```\n\n'

async function open(
  launch: (f: string[]) => Promise<import('@playwright/test').ElectronApplication>,
  dir: string
) {
  const b = fixture(dir)
  const md = join(b, 'cells.md')
  // a replacer function: in a replacement string, `$$` would mean a literal `$`
  writeFileSync(
    md,
    readFileSync(md, 'utf8').replace(/## divide\n[^#]*/, () => `## divide\n${PROSE}`)
  )
  const app = await launch([b])
  const page = await firstLesson(app)
  await expect(page.locator('.cell').nth(DIVIDE).locator('.katex-display')).toHaveCount(1)
  return { app, page, file: readFileSync(md, 'utf8') }
}

// A point in the rendered page: the text node of `cell` (inside `within`, if given) that contains `needle`, at
// `needle`'s start plus `delta`. `end` instead names a block start: (the first element matching it, offset 0).
type Pt =
  { cell: number; needle: string; delta: number; within?: string } | { cell: number; block: string }

// Dispatches a copy event over the range between two points; returns what the handler put on the event.
const copied = (page: Page, a: Pt, b: Pt) =>
  page.evaluate(
    ([a, b]) => {
      const point = (p: typeof a): [Node, number] => {
        const cell = document.querySelectorAll('.cell')[p.cell]
        if ('block' in p) return [cell.querySelector(p.block)!, 0]
        const root = p.within ? cell.querySelector(p.within)! : cell.querySelector('.md')!
        const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
        for (let n = walk.nextNode(); n; n = walk.nextNode()) {
          const i = n.textContent!.indexOf(p.needle)
          if (i >= 0) return [n, i + p.delta]
        }
        throw new Error(`no "${p.needle}" in cell ${p.cell}`)
      }
      const r = document.createRange()
      r.setStart(...point(a))
      r.setEnd(...point(b))
      const sel = document.getSelection()!
      sel.removeAllRanges()
      sel.addRange(r)
      const data = new DataTransfer()
      const ev = new ClipboardEvent('copy', {
        clipboardData: data,
        bubbles: true,
        cancelable: true
      })
      ;(r.startContainer.parentElement ?? r.startContainer).dispatchEvent(ev)
      return data.getData('text/plain')
    },
    [a, b] as const
  )

const between = (file: string, from: string, fromDelta: number, to: string, toDelta: number) =>
  file.slice(file.indexOf(from) + fromDelta, file.indexOf(to) + toDelta)

test('copy across a formula, a bold word and a code span is the exact source', async ({
  launch
}, info) => {
  const { page, file } = await open(launch, info.outputDir)
  const got = await copied(
    page,
    { cell: DIVIDE, needle: 'A ', delta: 0 },
    { cell: DIVIDE, needle: ' then', delta: 3 }
  )
  expect(got).toBe(between(file, 'A **bold**', 0, ' then', 3))
  expect(got).toContain('**bold**')
  expect(got).toContain('`code`')
  expect(got).toContain('$x^2$')
})

test('a selection inside a formula is the whole formula', async ({ launch }, info) => {
  const { page } = await open(launch, info.outputDir)
  const inline = { cell: DIVIDE, needle: 'x', delta: 0, within: '.katex' }
  expect(await copied(page, inline, { ...inline, delta: 1 })).toBe('$x^2$')
  const display = { cell: DIVIDE, needle: 'y', delta: 0, within: '.katex-display' }
  expect(await copied(page, display, { ...display, delta: 1 })).toBe('$$\ny^2\n$$')
})

test('a selection inside a code span is the whole code span', async ({ launch }, info) => {
  const { page } = await open(launch, info.outputDir)
  const c = { cell: DIVIDE, needle: 'code', delta: 1, within: 'code' }
  expect(await copied(page, c, { ...c, delta: 3 })).toBe('`code`')
})

test('a selection inside a fenced code block is the whole block', async ({ launch }, info) => {
  const { page } = await open(launch, info.outputDir)
  const c = { cell: DIVIDE, needle: 'fenced', delta: 1, within: 'pre' }
  expect(await copied(page, c, { ...c, delta: 3 })).toBe('```\nfenced\n```')
})

test('a selection inside an escaped run is its whole source', async ({ launch }, info) => {
  const { page } = await open(launch, info.outputDir)
  const c = { cell: DIVIDE, needle: '* star', delta: 2 }
  expect(await copied(page, c, { ...c, delta: 4 })).toBe(', a \\* star and ')
})

test('a selection inside a ref is the whole ref', async ({ launch }, info) => {
  const { page } = await open(launch, info.outputDir)
  const c = { cell: DIVIDE, needle: '6', delta: 0, within: '.ref' }
  expect(await copied(page, c, { ...c, delta: 1 })).toBe('{n_tokens}')
})

test('copy across cells is the file between the two points', async ({ launch }, info) => {
  const { page, file } = await open(launch, info.outputDir)
  const got = await copied(
    page,
    { cell: 2, needle: 'Add', delta: 0 },
    { cell: DIVIDE, needle: 'A ', delta: 1 }
  )
  expect(got).toBe(between(file, 'Add them all', 0, 'A **bold**', 1))
})

test('a triple-clicked paragraph is its source', async ({ launch }, info) => {
  const { page, file } = await open(launch, info.outputDir)
  // cell 3's last (only) paragraph, ending where a triple click ends: the next cell's first block
  const got = await copied(page, { cell: 2, block: '.md p' }, { cell: DIVIDE, block: '.md p' })
  expect(got).toBe(between(file, 'Add them all', 0, '## divide', 0))
})

test('⌘C through the menu puts the source on the clipboard', async ({ launch }, info) => {
  const { app, page } = await open(launch, info.outputDir)
  const saved = await app.evaluate(({ clipboard }) => clipboard.readText())
  try {
    await page.evaluate(() => {
      const el = document.querySelectorAll('.cell')[3].querySelector('code')!
      const code = document.createTreeWalker(el, NodeFilter.SHOW_TEXT).nextNode()!
      const r = document.createRange()
      r.setStart(code, 1)
      r.setEnd(code, 2)
      document.getSelection()!.removeAllRanges()
      document.getSelection()!.addRange(r)
    })
    await click(app, 'copy', await winId(app, page))
    await expect.poll(() => app.evaluate(({ clipboard }) => clipboard.readText())).toBe('`code`')
  } finally {
    await app.evaluate(({ clipboard }, s) => clipboard.writeText(s), saved)
  }
})
