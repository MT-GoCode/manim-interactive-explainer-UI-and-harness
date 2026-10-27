import { cpSync, mkdirSync, readFileSync, writeFileSync } from 'fs'
import { join } from 'path'
import type { Page } from '@playwright/test'
import { current, expect, firstLesson, fixture, ROOT, test } from './app'

const banner = (page: Page) => page.locator('.banner div').allTextContents()
const edit = (path: string, f: (s: string) => string) =>
  writeFileSync(path, f(readFileSync(path, 'utf8')))
const swap = (s: string) =>
  s.replace('## sum', '## SWAP').replace('## exp', '## sum').replace('## SWAP', '## exp')

test('editing lesson.py raises the alert and restoring clears it', async ({ launch }, info) => {
  const b = fixture(info.outputDir)
  const app = await launch([b])
  const page = await firstLesson(app)
  expect(await banner(page)).toEqual([])
  const lesson = join(b, 'lesson.py')
  const bytes = readFileSync(lesson)
  writeFileSync(lesson, Buffer.concat([bytes, Buffer.from('\n')]))
  await expect.poll(() => banner(page)).toEqual(['Changed since last build: lesson.py'])
  writeFileSync(lesson, bytes)
  await expect.poll(() => banner(page)).toEqual([])
  edit(join(b, 'helpers.py'), (s) => s + '\n')
  await expect.poll(() => banner(page)).toEqual(['Changed since last build: helpers.py'])
})

test('editing a repo file the build read raises the alert', async ({ launch }, info) => {
  const b = fixture(info.outputDir)
  const repo = join(info.outputDir, 'repo')
  mkdirSync(repo)
  cpSync(join(ROOT, 'explainers'), join(repo, 'explainers'), { recursive: true })
  edit(join(b, 'build', 'index.json'), (s) => JSON.stringify({ ...JSON.parse(s), repo_root: repo }))
  const app = await launch([b])
  const page = await firstLesson(app)
  expect(await banner(page)).toEqual([])
  edit(join(repo, 'explainers', 'lesson.py'), (s) => s + '\n')
  await expect
    .poll(() => banner(page))
    .toEqual(['Changed since last build: repo/explainers/lesson.py'])
})

test('swapped headings keep the current cell', async ({ launch }, info) => {
  const b = fixture(info.outputDir)
  const app = await launch([b])
  const page = await firstLesson(app)
  await page.keyboard.press('ArrowDown') // on "exp", cell 2
  await expect.poll(() => current(page)).toEqual({ i: 1, lit: 1 })
  edit(join(b, 'cells.md'), swap)
  await expect
    .poll(() => banner(page))
    .toEqual([
      'Prose and build disagree — cells.md: scores, sum, exp, divide, probs, top · build: scores, exp, sum, divide, probs, top'
    ])
  await expect.poll(() => current(page)).toEqual({ i: 2, lit: 1 }) // "exp" moved to 3rd; the reader stays on it
  expect(await page.locator('.cell.current').getAttribute('data-slug')).toBe('exp')
})

test('a heading with no clip says so, and an empty cells.md keeps the last lesson', async ({
  launch
}, info) => {
  const b = fixture(info.outputDir)
  const app = await launch([b])
  const page = await firstLesson(app)
  edit(join(b, 'cells.md'), (s) => s + '\n## extra\nMore.\n')
  await expect.poll(() => page.locator('.cell').count()).toBe(7)
  for (let i = 0; i < 6; i++) await page.keyboard.press('ArrowDown')
  await expect(page.locator('.player .noclip')).toHaveText(
    'No clip for this cell — run explain-build'
  )
  writeFileSync(join(b, 'cells.md'), '')
  await expect.poll(() => banner(page)).toContain('cells.md has no cells')
  expect(await page.locator('.cell').count()).toBe(7)
})
