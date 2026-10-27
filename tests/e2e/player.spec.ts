import { readFileSync, rmSync, writeFileSync } from 'fs'
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
// media time. The loop runs on the one <video> element, which a new clip (a new src) keeps. (Measured in the logged-in
// session's transparent test window: a paused seek to frame k presents exactly frame k.)
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

// A new last animation in "divide": a new clip, whose earlier frames are the same bytes (per-animation partials).
// Returns once the player holds the new clip and has applied its resume.
async function rebuildDivide(page: Page, b: string): Promise<void> {
  const before = (await video(page)).src
  const lesson = join(b, 'lesson.py')
  const src = readFileSync(lesson, 'utf8')
  const next = src.indexOf('        self.cell("probs")')
  writeFileSync(lesson, src.slice(0, next) + '        self.wait(0.5)\n' + src.slice(next))
  execFileSync(join(ROOT, 'bin/explain-build'), [b])
  await expect.poll(async () => (await video(page)).src, { timeout: 30000 }).not.toBe(before)
  await settled(page)
}

const countErrors = (page: Page) =>
  page.evaluate(() => {
    const g = globalThis as unknown as { errors: number }
    g.errors = 0
    document.querySelector('video')!.addEventListener('error', () => g.errors++)
  })
const errors = (page: Page) =>
  page.evaluate(() => (globalThis as unknown as { errors: number }).errors)

test('a rebuild while paused keeps the frame', async ({ launch }, info) => {
  test.slow() // it runs a real build, which under the full suite's load can take tens of seconds
  const b = fixture(info.outputDir)
  const app = await launch([b])
  const page = await firstLesson(app)
  await onDivide(page)
  await countErrors(page)
  await seek(page, (k + 0.5) / fps)
  await rebuildDivide(page, b)
  await expect.poll(() => shown(page)).toBe(k)
  expect((await video(page)).paused).toBe(true)
  expect(await errors(page)).toBe(0)
})

test('a rebuild while playing keeps playing from where it was', async ({ launch }, info) => {
  test.slow() // it runs a real build, which under the full suite's load can take tens of seconds
  const b = fixture(info.outputDir)
  const app = await launch([b])
  const page = await firstLesson(app)
  await onDivide(page)
  await countErrors(page)
  // A sixteenth of normal speed (Chromium's minimum; kept across a src change): from frame 3 the 1.3 s clip plays
  // ~19 s, far longer than a rebuild even under nice 19 beside other work, so it is still playing when it lands.
  await page.evaluate(() => {
    const v = document.querySelector('video')!
    v.defaultPlaybackRate = v.playbackRate = 0.0625
  })
  await seek(page, 3.5 / fps)
  await page.evaluate(() => document.querySelector('video')!.play())
  await rebuildDivide(page, b)
  const v = await video(page)
  expect(v.paused).toBe(false)
  expect(v.t).toBeGreaterThanOrEqual(3.5 / fps) // resumed past frame 3, not restarted
  expect(await errors(page)).toBe(0)
})

test('a clip that cannot load says so', async ({ launch }, info) => {
  const b = fixture(info.outputDir)
  const index = JSON.parse(readFileSync(join(b, 'build', 'index.json'), 'utf8'))
  rmSync(join(b, 'build', index.cells[1].clip)) // cell 2's clip is gone from disk
  const app = await launch([b])
  const page = await firstLesson(app)
  await page.keyboard.press('ArrowDown')
  await expect(page.locator('.player .failed')).toHaveText(/^This clip cannot play \(\d\): /)
})

test('in a wide window the player stays in view as the cells move', async ({ launch }, info) => {
  const app = await launch([fixture(info.outputDir)])
  const page = await firstLesson(app)
  // 2:1 at this width is taller than the window minus the transcript's scroll room
  await app.evaluate(({ BrowserWindow }) =>
    BrowserWindow.getAllWindows()[0].setContentSize(1280, 968)
  )
  for (let i = 0; i < 5; i++) await page.keyboard.press('ArrowDown')
  await expect.poll(() => current(page)).toEqual({ i: 5, lit: 1 })
  expect(
    await page.evaluate(() => document.querySelector('.player')!.getBoundingClientRect().top)
  ).toBe(0)
})
