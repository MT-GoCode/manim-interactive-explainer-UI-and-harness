import { readFileSync, writeFileSync } from 'fs'
import { join } from 'path'
import type { ElectronApplication, Page } from '@playwright/test'
import { click, current, expect, firstLesson, fixture, test, winId } from './app'

const SUM = 2 // cell "sum": "Add them all: $\sum_j e^{z_j}$."
const cellsMd = (b: string) => readFileSync(join(b, 'cells.md'), 'utf8')
const edit = (b: string, f: (s: string) => string) =>
  writeFileSync(join(b, 'cells.md'), f(cellsMd(b)))
const editor = (page: Page) => page.locator('.editor .cm-content')
const cellText = (page: Page, i: number) => page.locator('.cell').nth(i).innerText()

async function open(launch: (f: string[]) => Promise<ElectronApplication>, dir: string) {
  const b = fixture(dir)
  const app = await launch([b])
  return { b, app, page: await firstLesson(app) }
}
// Double-click a cell's prose, then replace the whole buffer with `text`.
async function rewrite(page: Page, i: number, text: string) {
  await page.locator('.cell .md').nth(i).dblclick({ force: true })
  await editor(page).waitFor()
  await page.keyboard.press('Meta+a')
  await page.keyboard.type(text)
}

test('editing cell 3 while cell 5 changes keeps both', async ({ launch }, info) => {
  const { b, page } = await open(launch, info.outputDir)
  await rewrite(page, SUM, 'Sum edited.')
  edit(b, (s) => s.replace('Now they are probabilities', 'Now they are odds'))
  await expect.poll(() => cellText(page, 4)).toContain('odds') // the reload has landed
  await page.keyboard.press('Meta+Enter')
  await expect(page.locator('.editor')).toHaveCount(0)
  // the saved text is already rendered when the save completes (the reload came first)
  expect(await cellText(page, SUM)).toContain('Sum edited.')
  const md = cellsMd(b)
  expect(md).toContain('## sum\nSum edited.\n\n## divide')
  expect(md).toContain('Now they are odds')
})

test('editing cell 3 while cell 3 changes shows the conflict and writes nothing', async ({
  launch
}, info) => {
  const { b, page } = await open(launch, info.outputDir)
  await rewrite(page, SUM, 'Mine.')
  edit(b, (s) => s.replace('Add them all', 'Add every one'))
  const disk = cellsMd(b)
  await page.keyboard.press('Meta+Enter')
  await expect(page.locator('.editor .problem')).toContainText(
    'This cell changed on disk while you edited it'
  )
  await expect(page.locator('.editor .problem pre')).toContainText('Add every one')
  expect(cellsMd(b)).toBe(disk)
  await expect(editor(page)).toHaveText('Mine.')
})

test('Keep mine saves over the disk version', async ({ launch }, info) => {
  const { b, page } = await open(launch, info.outputDir)
  await rewrite(page, SUM, 'Mine.')
  edit(b, (s) => s.replace('Add them all', 'Add every one'))
  await page.keyboard.press('Meta+Enter')
  await page.locator('.editor .problem button', { hasText: 'Keep mine' }).click({ force: true })
  await expect(page.locator('.editor')).toHaveCount(0)
  expect(cellsMd(b)).toContain('## sum\nMine.\n\n## divide')
})

test('a reload while editing keeps the buffer', async ({ launch }, info) => {
  const { b, page } = await open(launch, info.outputDir)
  await rewrite(page, SUM, 'Half typed')
  edit(b, (s) => s.replace('Now they are probabilities', 'Now they are odds'))
  await expect.poll(() => cellText(page, 4)).toContain('odds')
  await expect(editor(page)).toHaveText('Half typed')
})

test('a heading renamed while editing keeps the buffer and says the cell is gone', async ({
  launch
}, info) => {
  const { b, page } = await open(launch, info.outputDir)
  await rewrite(page, SUM, 'Kept.')
  edit(b, (s) => s.replace('## sum\n', '## total\n'))
  await expect(page.locator('.editor .problem')).toContainText('This cell is no longer in cells.md')
  await expect(editor(page)).toHaveText('Kept.')
})

test('moving to another cell saves', async ({ launch }, info) => {
  const { b, page } = await open(launch, info.outputDir)
  await rewrite(page, SUM, 'Saved by leaving.')
  await page.locator('.cell .md').nth(0).click({ force: true })
  await expect(page.locator('.editor')).toHaveCount(0)
  expect(cellsMd(b)).toContain('## sum\nSaved by leaving.\n\n## divide')
})

test('Esc discards the edit', async ({ launch }, info) => {
  const { b, page } = await open(launch, info.outputDir)
  const before = cellsMd(b)
  await rewrite(page, SUM, 'Thrown away.')
  await page.keyboard.press('Escape')
  await expect(page.locator('.editor')).toHaveCount(0)
  expect(cellsMd(b)).toBe(before)
  expect(await cellText(page, SUM)).toContain('Add them all')
})

test('keys typed in the editor stay in the editor', async ({ launch }, info) => {
  const { page } = await open(launch, info.outputDir)
  await rewrite(page, SUM, 'x')
  const at = await current(page)
  const t = await page.evaluate(() => document.querySelector('video')!.currentTime)
  await page.keyboard.type('r,. ')
  await page.keyboard.press('ArrowDown')
  await expect(editor(page)).toHaveText('xr,. ')
  expect(await current(page)).toEqual(at)
  // r would have rewound the clip to 0 and played it
  expect(
    await page.evaluate(() => document.querySelector('video')!.currentTime)
  ).toBeGreaterThanOrEqual(t)
})

test('paste works in the editor', async ({ launch }, info) => {
  const { app, page } = await open(launch, info.outputDir)
  const saved = await app.evaluate(({ clipboard }) => clipboard.readText())
  try {
    await app.evaluate(({ clipboard }) => clipboard.writeText('PASTED'))
    await rewrite(page, SUM, '')
    await click(app, 'paste', await winId(app, page)) // the Edit menu's item, as ⌘V triggers it
    await expect(editor(page)).toHaveText('PASTED')
  } finally {
    await app.evaluate(({ clipboard }, s) => clipboard.writeText(s), saved)
  }
})

test('an unknown ref is red', async ({ launch }, info) => {
  const { b, page } = await open(launch, info.outputDir)
  edit(b, (s) => s.replace('Add them all', 'Add {nope} all'))
  await expect(page.locator('.cell').nth(SUM).locator('.unresolved')).toHaveText('{nope}')
})
