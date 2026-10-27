import { execFileSync } from 'child_process'
import { mkdirSync, readFileSync, writeFileSync } from 'fs'
import { join } from 'path'
import type { ElectronApplication, Page } from '@playwright/test'
import { current, expect, firstLesson, fixture, test } from './app'

const setLink = (b: string, link: string) => {
  const md = join(b, 'cells.md')
  writeFileSync(
    md,
    readFileSync(md, 'utf8').replace('[[softmax#scores]]', () => link)
  )
}
const clickLink = (page: Page) =>
  page.locator('.cell').nth(5).locator('[data-link]').click({ force: true })
const titles = (app: ElectronApplication) =>
  app.evaluate(({ BrowserWindow }) =>
    BrowserWindow.getAllWindows()
      .map((w) => w.getTitle())
      .sort()
  )
const errorBoxes = (app: ElectronApplication) =>
  app.evaluate(() => (globalThis as unknown as { errorBoxes: unknown[] }).errorBoxes)

// `other` (a second copy of the fixture) is the only lesson in the lessons folder; the sender lives elsewhere, so the
// target can only be found through that folder.
function other(dir: string): string {
  const lessons = join(dir, 'lessons')
  mkdirSync(lessons, { recursive: true })
  execFileSync('mv', [fixture(join(dir, 'staging')), join(lessons, 'other.explainer')])
  return lessons
}

test('a link into this bundle moves to its cell', async ({ launch }, info) => {
  const b = fixture(info.outputDir)
  const app = await launch([b], undefined, { env: { EX_LESSONS: info.outputDir } })
  const page = await firstLesson(app)
  await clickLink(page)
  await expect.poll(() => current(page)).toEqual({ i: 0, lit: 1 })
})

test('a link to another bundle opens it at its cell', async ({ launch }, info) => {
  test.skip(!!process.env.EX_EXECUTABLE, 'needs electron -r (the dev app)')
  const lessons = other(info.outputDir)
  const b = fixture(join(info.outputDir, 'home'))
  setLink(b, '[[other#probs]]')
  const app = await launch([b], undefined, { stubErrorBox: true, env: { EX_LESSONS: lessons } })
  const page = await firstLesson(app)
  await clickLink(page)
  await expect.poll(() => titles(app)).toEqual(['other', 'softmax'])
  const second = app.windows().find((w) => w !== page)!
  await second.waitForSelector('.cell')
  await expect.poll(() => current(second)).toEqual({ i: 4, lit: 1 })
  // already open: the same window is brought back to the cell
  await second.keyboard.press('ArrowUp')
  await expect.poll(() => current(second)).toEqual({ i: 3, lit: 1 })
  await clickLink(page)
  await expect.poll(() => current(second)).toEqual({ i: 4, lit: 1 })
  expect(await titles(app)).toEqual(['other', 'softmax'])
})

// Error boxes are recorded by a script preloaded with `electron -r`, which a packaged app does not accept.
test('a link to a missing cell says so', async ({ launch }, info) => {
  test.skip(!!process.env.EX_EXECUTABLE, 'needs electron -r (the dev app)')
  const lessons = other(info.outputDir)
  const b = fixture(join(info.outputDir, 'home'))
  setLink(b, '[[other#nope]]')
  const app = await launch([b], undefined, { stubErrorBox: true, env: { EX_LESSONS: lessons } })
  const page = await firstLesson(app)
  await clickLink(page)
  await expect
    .poll(() => errorBoxes(app))
    .toEqual([{ title: 'Cannot open [[other#nope]]', message: 'No cell "nope" in other' }])
  expect(await titles(app)).toEqual(['softmax'])
  expect(await current(page)).toEqual({ i: 0, lit: 1 })
})
