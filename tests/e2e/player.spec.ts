import { readFileSync, writeFileSync } from 'fs'
import { execFileSync } from 'child_process'
import { join } from 'path'
import type { Page } from '@playwright/test'
import { current, expect, firstLesson, fixture, FRAMES, ROOT, test } from './app'

const ref = JSON.parse(readFileSync(FRAMES, 'utf8')) as {
  k: number
  fps: number
  frames: number[][]
}
const { k, fps } = ref
// Cell "divide": a formula moving across the frame. Frames must differ by motion, not only brightness (a fade):
// Chromium's and FFmpeg's colour conversions differ slightly, so brightness alone does not name a frame.
const DIVIDE = 3

// Which decoded frame the video shows: its 64×36 canvas readback, nearest (L1) among all frames of the clip.
const shown = (page: Page) =>
  page.evaluate((frames) => {
    const v = document.querySelector('video')!
    const c = document.createElement('canvas')
    c.width = 64
    c.height = 36
    const g = c.getContext('2d', { willReadFrequently: true })!
    g.drawImage(v, 0, 0, 64, 36)
    const px = [...g.getImageData(0, 0, 64, 36).data].filter((_, i) => i % 4 !== 3)
    const dist = frames.map((f) => f.reduce((s, x, i) => s + Math.abs(x - px[i]), 0))
    return dist.indexOf(Math.min(...dist))
  }, ref.frames)

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
  await page.waitForFunction(() => document.querySelector('video')!.readyState >= 2)
}

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
  expect(await shown(page)).toBe(k)
  await seekedAfter(page, '.')
  expect(await shown(page)).toBe(k + 1)
  await seekedAfter(page, ',')
  expect(await shown(page)).toBe(k)
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
  await page.waitForFunction(() => document.querySelector('video')!.readyState >= 2)
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(r)))
  expect(await shown(page)).toBe(k)
  expect((await video(page)).paused).toBe(true)
  expect(await page.evaluate(() => (globalThis as unknown as { errors: number }).errors)).toBe(0)
})
