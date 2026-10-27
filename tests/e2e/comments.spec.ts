import { spawn, execFileSync } from 'child_process'
import { createHash } from 'crypto'
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'fs'
import { join } from 'path'
import type { ElectronApplication, Page } from '@playwright/test'
import { expect, firstLesson, fixture, ROOT, test } from './app'

const SUM = 2
const PROBS = 4
const TOP = 5
const stored = (b: string): { id: string; cell: string; span: [number, number] | null }[] =>
  existsSync(join(b, 'comments.json'))
    ? JSON.parse(readFileSync(join(b, 'comments.json'), 'utf8')).comments
    : []
const prose = (b: string, slug: string) => {
  const md = readFileSync(join(b, 'cells.md'), 'utf8')
  const at = md.indexOf(`## ${slug}\n`) + `## ${slug}\n`.length
  const next = md.indexOf('\n## ', at)
  return md.slice(at, next < 0 ? md.length : next + 1)
}
const edit = (path: string, f: (s: string) => string) =>
  writeFileSync(path, f(readFileSync(path, 'utf8')))

async function open(launch: (f: string[]) => Promise<ElectronApplication>, dir: string) {
  const b = fixture(dir)
  const app = await launch([b])
  return { b, app, page: await firstLesson(app) }
}
async function send(page: Page, text: string) {
  await page.locator('.comment-box textarea').fill(text)
  await page.locator('.comment-box button', { hasText: 'Comment' }).click({ force: true })
  await expect(page.locator('.comment-box')).toHaveCount(0)
}
async function commentCell(page: Page, i: number, text: string) {
  await page.locator('.cell').nth(i).locator('.add-comment').click({ force: true })
  await send(page, text)
}

test('a highlight comment stores the exact span', async ({ launch }, info) => {
  const { b, page } = await open(launch, info.outputDir)
  // "tokens" in cell 1's text after its ref ("… the {n_tokens} tokens a score."): there the rendered offset (after
  // "6") and the source offset (after "{n_tokens}") differ, so only bound() gives the source span
  await page.evaluate(() => {
    const t = document.querySelectorAll('.cell')[0].querySelectorAll('[data-x]')[1].firstChild!
    const r = document.createRange()
    r.setStart(t, 1)
    r.setEnd(t, 7)
    document.getSelection()!.removeAllRanges()
    document.getSelection()!.addRange(r)
  })
  await page.locator('.comment-sel').click({ force: true })
  await send(page, 'How many?')
  const at = prose(b, 'scores').indexOf('tokens a score')
  await expect
    .poll(() => stored(b))
    .toMatchObject([{ cell: 'scores', span: [at, at + 'tokens'.length] }])
  await expect(page.locator('.cell').nth(0).locator('.card .quote')).toHaveText('“tokens”')
})

test('a refused comment keeps its text in the box', async ({ launch }, info) => {
  const { b, page } = await open(launch, info.outputDir)
  await page.locator('.cell').nth(SUM).locator('.add-comment').click({ force: true })
  await page.locator('.comment-box textarea').fill('Keep this text')
  edit(join(b, 'cells.md'), (s) => s.replace('Add them all', 'Add every one')) // the cell changes meanwhile
  await expect.poll(() => page.locator('.cell').nth(SUM).innerText()).toContain('Add every one')
  await page.locator('.comment-box button', { hasText: 'Comment' }).click({ force: true })
  await expect(page.locator('.comment-box .refused')).toHaveText(
    'This cell changed while you were commenting; select again'
  )
  await expect(page.locator('.comment-box textarea')).toHaveValue('Keep this text')
  expect(stored(b)).toEqual([])
})

test('a stale comment that cannot be pruned says so', async ({ launch }, info) => {
  test.skip(!!process.env.EX_EXECUTABLE, 'needs electron -r (the dev app)')
  const b = fixture(info.outputDir)
  const index = JSON.parse(readFileSync(join(b, 'build', 'index.json'), 'utf8'))
  const frames = index.cells.find((c: { slug: string }) => c.slug === 'sum').frames_sha
  const sha = createHash('sha256').update(prose(b, 'sum')).digest('hex')
  writeFileSync(
    join(b, 'comments.json'),
    JSON.stringify({
      format: 'explainer-comments',
      version: 1,
      comments: [
        {
          id: 'aaaaaaa1',
          cell: 'sum',
          span: null,
          text: 'x',
          created: '2026-10-27T00:00:00.000Z',
          fingerprint: { section_sha: sha, frames_sha: frames }
        }
      ]
    })
  )
  edit(join(b, 'cells.md'), (s) => s.replace('Add them all', 'Add every one'))
  const before = readFileSync(join(b, 'comments.json'), 'utf8')
  // the write-back cannot make its temporary file (a directory is in the way); nothing to undo if the test dies
  mkdirSync(join(b, 'comments.json.tmp'))
  const app = await launch([b], undefined, { stubErrorBox: true })
  // the bundle opens (asserted before waiting on a window, so a failure to open fails here, not by a hang)
  await expect
    .poll(() => app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows().length))
    .toBe(1)
  expect(
    await app.evaluate(() => (globalThis as unknown as { errorBoxes: unknown[] }).errorBoxes)
  ).toEqual([])
  const page = await firstLesson(app)
  await expect(page.locator('.banner')).toContainText('comments.json could not be pruned')
  await expect(page.locator('.card')).toHaveCount(0) // the pruned list is what shows
  expect(readFileSync(join(b, 'comments.json'), 'utf8')).toBe(before)
})

test('editing its cell drops it and keeps others', async ({ launch }, info) => {
  const { b, page } = await open(launch, info.outputDir)
  await commentCell(page, SUM, 'on sum')
  await commentCell(page, PROBS, 'on probs')
  await expect.poll(() => stored(b).length).toBe(2)
  edit(join(b, 'cells.md'), (s) => s.replace('Add them all', 'Add every one'))
  await expect.poll(() => stored(b).map((c) => c.cell)).toEqual(['probs'])
})

test("a rebuild changing one cell's frames drops that cell's comments only", async ({
  launch
}, info) => {
  const { b, page } = await open(launch, info.outputDir)
  await commentCell(page, PROBS, 'on probs')
  await commentCell(page, TOP, 'on top')
  await expect.poll(() => stored(b).length).toBe(2)
  const shas = () =>
    Object.fromEntries(
      JSON.parse(readFileSync(join(b, 'build', 'index.json'), 'utf8')).cells.map(
        (c: { slug: string; frames_sha: string }) => [c.slug, c.frames_sha]
      )
    )
  const before = shas()
  // probs fades the title out more quickly: probs' frames change; top starts from the same picture
  edit(join(b, 'lesson.py'), (s) =>
    s.replace('FadeOut(title), run_time=0.5', 'FadeOut(title), run_time=0.4')
  )
  execFileSync(join(ROOT, 'bin/explain-build'), [b])
  const after = shas()
  expect(after.probs).not.toBe(before.probs) // the premise, from the build itself
  expect(after.top).toBe(before.top)
  await expect.poll(() => stored(b).map((c) => c.cell)).toEqual(['top'])
})

test('a removed slug shows its comments as orphaned', async ({ launch }, info) => {
  const { b, page } = await open(launch, info.outputDir)
  await commentCell(page, PROBS, 'on probs')
  edit(join(b, 'cells.md'), (s) => s.replace('## probs\n', '## odds\n'))
  await expect(page.locator('.orphans .card .text')).toHaveText('on probs')
  expect(stored(b).map((c) => c.cell)).toEqual(['probs'])
})

test('✕ removes a comment from the file', async ({ launch }, info) => {
  const { b, page } = await open(launch, info.outputDir)
  await commentCell(page, SUM, 'on sum')
  await commentCell(page, PROBS, 'on probs')
  await expect.poll(() => stored(b).length).toBe(2)
  await page.locator('.cell').nth(SUM).locator('.card .resolve').click({ force: true })
  await expect.poll(() => stored(b).map((c) => c.cell)).toEqual(['probs'])
})

test('a bundle whose comments went stale while closed is pruned when it opens', async ({
  launch
}, info) => {
  const b = fixture(info.outputDir)
  const index = JSON.parse(readFileSync(join(b, 'build', 'index.json'), 'utf8'))
  const frames = (slug: string) =>
    index.cells.find((c: { slug: string }) => c.slug === slug).frames_sha
  const pinned = (id: string, slug: string) => ({
    id,
    cell: slug,
    span: null,
    text: slug,
    created: '2026-10-27T00:00:00.000Z',
    fingerprint: {
      section_sha: createHash('sha256').update(prose(b, slug)).digest('hex'),
      frames_sha: frames(slug)
    }
  })
  writeFileSync(
    join(b, 'comments.json'),
    JSON.stringify({
      format: 'explainer-comments',
      version: 1,
      comments: [pinned('aaaaaaa1', 'sum'), pinned('aaaaaaa2', 'probs')]
    })
  )
  edit(join(b, 'cells.md'), (s) => s.replace('Add them all', 'Add every one')) // while no app is open
  const app = await launch([b])
  await firstLesson(app)
  await expect.poll(() => stored(b).map((c) => c.id)).toEqual(['aaaaaaa2'])
})

test('Ping writes ping and waits until it is gone', async ({ launch }, info) => {
  const { b, page } = await open(launch, info.outputDir)
  await page.locator('.ping').click({ force: true })
  await expect(page.locator('.ping')).toHaveText('waiting…')
  expect(existsSync(join(b, 'ping'))).toBe(true)
  rmSync(join(b, 'ping'))
  await expect(page.locator('.ping')).toHaveText('Ping')
})

test('a comment reaches fetch-comments --wait', async ({ launch }, info) => {
  const { b, page } = await open(launch, info.outputDir)
  const fetch = spawn(join(ROOT, 'bin/fetch-comments'), ['--wait', b])
  let out = ''
  fetch.stdout.on('data', (d) => (out += d))
  const done = new Promise<number | null>((r) => fetch.on('exit', r))
  await commentCell(page, SUM, 'Why add them?')
  await expect.poll(() => stored(b).length).toBe(1)
  await page.locator('.ping').click({ force: true })
  expect(await done).toBe(0)
  expect(out.trim()).toMatch(/^[0-9a-f]{8} · #3 sum · whole cell → Why add them\?$/)
  expect(existsSync(join(b, 'ping'))).toBe(false)
  await expect(page.locator('.ping')).toHaveText('Ping')
})
