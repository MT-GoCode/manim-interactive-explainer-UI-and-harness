import { readFileSync, writeFileSync } from 'fs'
import { execFileSync } from 'child_process'
import { join } from 'path'
import type { Page } from '@playwright/test'
import { BUILT, current, expect, firstLesson, fixture, ROOT, test } from './app'

// Cell "divide" of the built fixture; k is its middle frame.
const DIVIDE = 3
const index = JSON.parse(readFileSync(join(BUILT, 'build', 'index.json'), 'utf8'))
const fps: number = index.fps
const k = Math.floor(index.cells[DIVIDE].frames / 2)

// The frame the video presents, as its decoder names it: requestVideoFrameCallback reports each presented frame's
// media time (exact, unlike matching pixels against another decoder's output). The loop runs on the one <video>
// element, which a new clip (a new src) keeps.
const watchFrames = (page: Page) =>
  page.evaluate(() => {
    const v = document.querySelector('video')!
    const g = globalThis as unknown as { presented: number }
    const tick = (_now: number, m: VideoFrameCallbackMetadata) => {
      g.presented = m.mediaTime
      v.requestVideoFrameCallback(tick)
    }
    v.requestVideoFrameCallback(tick)
  })
const shown = (page: Page) =>
  page.evaluate(
    (fps) => Math.round((globalThis as unknown as { presented: number }).presented * fps),
    fps
  )

const video = (page: Page) =>
  page.evaluate(() => {
    const v = document.querySelector('video')!
    return { src: v.src, t: v.currentTime, paused: v.paused }
  })

async function seek(page: Page, t: number): Promise<void> {
  await page.evaluate(
    (t) =>
      new Promise<void>((done) => {
        const v = document.querySelector('video')!
        v.pause()
        v.addEventListener('seeked', () => done(), { once: true })
        v.currentTime = t
      }),
    t
  )
}
const seekedAfter = (page: Page, key: string) =>
  Promise.all([
    page.evaluate(
      () =>
        new Promise<void>((done) =>
          document.querySelector('video')!.addEventListener('seeked', () => done(), { once: true })
        )
    ),
    page.keyboard.press(key)
  ])

async function onDivide(page: Page): Promise<void> {
  for (let i = 0; i < DIVIDE; i++) await page.keyboard.press('ArrowDown')
  await expect.poll(() => current(page)).toEqual({ i: DIVIDE, lit: 1 })
  await settled(page)
  await page.waitForFunction(() => !document.querySelector('video')!.paused) // a new cell plays its clip
  await watchFrames(page)
}

// The player is done with its own loading and seeking, so a test's seek is the only one in flight.
const settled = (page: Page) =>
  page.waitForFunction(() => {
    const v = document.querySelector('video')!
    return v.readyState >= 2 && !v.seeking
  })

test('arrows and clicks light exactly one cell and play its clip', async ({ launch }, info) => {
  const app = await launch([fixture(info.outputDir)])
  const page = await firstLesson(app)
  for (let i = 0; i < 3; i++) await page.keyboard.press('ArrowDown')
  await expect.poll(() => current(page)).toEqual({ i: 3, lit: 1 })
  const src = (await video(page)).src
  await expect.poll(async () => (await video(page)).paused).toBe(false)
  await page.keyboard.press('ArrowUp')
  await expect.poll(() => current(page)).toEqual({ i: 2, lit: 1 })
  expect((await video(page)).src).not.toBe(src)
  await page.locator('.cell').nth(5).click({ force: true })
  await expect.poll(() => current(page)).toEqual({ i: 5, lit: 1 })
})

test('seek and step land on frames k and k+1', async ({ launch }, info) => {
  const app = await launch([fixture(info.outputDir)])
  const page = await firstLesson(app)
  await onDivide(page)
  await seek(page, (k + 0.5) / fps)
  await expect.poll(() => shown(page)).toBe(k)
  await seekedAfter(page, '.')
  await expect.poll(() => shown(page)).toBe(k + 1)
  await seekedAfter(page, ',')
  await expect.poll(() => shown(page)).toBe(k)
})

test('r mid-clip rewinds and plays', async ({ launch }, info) => {
  const app = await launch([fixture(info.outputDir)])
  const page = await firstLesson(app)
  await onDivide(page)
  await seek(page, (k + 0.5) / fps)
  await page.keyboard.press('r')
  const v = await video(page)
  expect(v.t).toBeLessThan(2 / fps)
  expect(v.paused).toBe(false)
})

test('a rebuild while paused keeps the frame', async ({ launch }, info) => {
  const b = fixture(info.outputDir)
  const app = await launch([b])
  const page = await firstLesson(app)
  await onDivide(page)
  await page.evaluate(() => {
    const g = globalThis as unknown as { errors: number }
    g.errors = 0
    document.querySelector('video')!.addEventListener('error', () => g.errors++)
  })
  await seek(page, (k + 0.5) / fps)
  const before = await video(page)
  // A new last animation in "divide": a new clip, whose earlier frames are the same bytes (per-animation partials).
  const lesson = join(b, 'lesson.py')
  const src = readFileSync(lesson, 'utf8')
  const next = src.indexOf('        self.cell("probs")')
  writeFileSync(lesson, src.slice(0, next) + '        self.wait(0.5)\n' + src.slice(next))
  execFileSync(join(ROOT, 'bin/explain-build'), [b])
  await expect.poll(async () => (await video(page)).src, { timeout: 30000 }).not.toBe(before.src)
  await settled(page) // the new clip is loaded and the player's resume seek has landed
  await expect.poll(() => shown(page)).toBe(k)
  expect((await video(page)).paused).toBe(true)
  expect(await page.evaluate(() => (globalThis as unknown as { errors: number }).errors)).toBe(0)
})
