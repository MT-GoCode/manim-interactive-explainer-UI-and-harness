import type { ElectronApplication, Page } from '@playwright/test'
import { click, current, expect, firstLesson, fixture, test, winId } from './app'

const count = (page: Page) => page.locator('.bar .count').textContent()
const highlights = (page: Page) => page.evaluate(() => CSS.highlights.size)
async function open(app: ElectronApplication, page: Page, item: 'find' | 'goto'): Promise<void> {
  await click(app, item, await winId(app, page))
  await page.locator('.bar input').waitFor()
}
async function query(page: Page, q: string): Promise<void> {
  await page.locator('.bar input').fill(q)
}

test('find steps across cells', async ({ launch }, info) => {
  const app = await launch([fixture(info.outputDir)])
  const page = await firstLesson(app)
  await open(app, page, 'find')
  await query(page, 'probabilit') // "probabilities" in probs, "probability" in top
  await expect.poll(() => count(page)).toBe('1 of 2')
  await expect.poll(() => current(page)).toEqual({ i: 4, lit: 1 })
  await page.locator('.bar input').press('Enter')
  await expect.poll(() => count(page)).toBe('2 of 2')
  await expect.poll(() => current(page)).toEqual({ i: 5, lit: 1 })
  await page.locator('.bar input').press('Enter')
  await expect.poll(() => current(page)).toEqual({ i: 4, lit: 1 })
  await query(page, 'zzz')
  await expect.poll(() => count(page)).toBe('No results')
  expect(await current(page)).toEqual({ i: 4, lit: 1 })
  await page.locator('.bar input').press('Escape')
  await expect(page.locator('.bar')).toHaveCount(0)
  expect(await highlights(page)).toBe(0)
})

test('find skips formula annotations', async ({ launch }, info) => {
  const app = await launch([fixture(info.outputDir)])
  const page = await firstLesson(app)
  await open(app, page, 'find')
  // The prose says "the sum" once (cell 4); the TeX \sum hides in KaTeX's annotations of cells 3 and 4.
  await query(page, 'sum')
  await expect.poll(() => count(page)).toBe('1 of 1')
  await expect.poll(() => current(page)).toEqual({ i: 3, lit: 1 })
})

test('go to cell', async ({ launch }, info) => {
  const app = await launch([fixture(info.outputDir)])
  const page = await firstLesson(app)
  await open(app, page, 'goto')
  await query(page, '4')
  await page.locator('.bar input').press('Enter')
  await expect.poll(() => current(page)).toEqual({ i: 3, lit: 1 })
  for (const bad of ['99', '2x', '0']) {
    await open(app, page, 'goto')
    await query(page, bad)
    await page.locator('.bar input').press('Enter')
    await expect.poll(() => count(page)).toBe(`No cell ${bad} (1–6)`)
    expect(await current(page)).toEqual({ i: 3, lit: 1 })
    await page.locator('.bar input').press('Escape')
  }
})
