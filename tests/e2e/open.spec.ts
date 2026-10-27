import { readFileSync, writeFileSync } from 'fs'
import { join } from 'path'
import type { ElectronApplication } from '@playwright/test'
import { click, current, expect, firstLesson, fixture, test } from './app'

const windows = (app: ElectronApplication) =>
  app.evaluate(({ BrowserWindow }) =>
    BrowserWindow.getAllWindows().map((w) => ({ title: w.getTitle(), bounds: w.getBounds() }))
  )

// Opens through File > Open… with the native dialog stubbed.
const openViaDialog = (app: ElectronApplication, path: string) =>
  app
    .evaluate(({ dialog }, p) => {
      dialog.showOpenDialog = (async () => ({ canceled: false, filePaths: [p] })) as never
    }, path)
    .then(() => click(app, 'open'))

async function quit(app: ElectronApplication): Promise<void> {
  await Promise.all([
    app.waitForEvent('close'),
    app.evaluate(({ app }) => void setTimeout(() => app.quit()))
  ])
}

test('Open… opens the bundle in one window titled by its name', async ({ launch }, info) => {
  const b = fixture(info.outputDir)
  const app = await launch()
  await Promise.all([app.waitForEvent('window'), openViaDialog(app, b)])
  const page = await firstLesson(app)
  expect((await windows(app)).map((w) => w.title)).toEqual(['softmax'])
  expect(await page.locator('.cell').count()).toBe(6)
  await openViaDialog(app, b) // already open: focused, not opened twice
  expect((await windows(app)).length).toBe(1)
})

test('a bundle handed over by Finder (open-file) opens in its own window', async ({
  launch
}, info) => {
  const b = fixture(info.outputDir)
  const app = await launch()
  // What macOS delivers to a running app on a Finder double-click (the live delivery is checked by hand).
  await Promise.all([
    app.waitForEvent('window'),
    app.evaluate(({ app }, p) => app.emit('open-file', { preventDefault: () => undefined }, p), b)
  ])
  await firstLesson(app)
  expect((await windows(app)).map((w) => w.title)).toEqual(['softmax'])
})

test('relaunch restores window, bounds and cell', async ({ launch }, info) => {
  const b = fixture(info.outputDir)
  const userData = info.outputPath('userdata')
  const app = await launch([b], userData)
  const page = await firstLesson(app)
  for (let i = 0; i < 3; i++) await page.keyboard.press('ArrowDown')
  await expect.poll(() => current(page)).toEqual({ i: 3, lit: 1 })
  // Main has recorded the cell (its session file names it) before the window moves.
  const session = () => readFileSync(join(userData, 'session.json'), 'utf8')
  await expect.poll(session).toContain('"slug":"divide"')
  // After the last per-cell save: only the quit-time write can record these bounds.
  const rect = { x: 137, y: 91, width: 1111, height: 888 }
  await app.evaluate(({ BrowserWindow }, r) => BrowserWindow.getAllWindows()[0].setBounds(r), rect)
  await quit(app)
  const again = await launch([], userData)
  const page2 = await firstLesson(again)
  expect(await windows(again)).toEqual([{ title: 'softmax', bounds: rect }])
  await expect.poll(() => current(page2)).toEqual({ i: 3, lit: 1 })
})

test('reload returns to the cell', async ({ launch }, info) => {
  const app = await launch([fixture(info.outputDir)])
  const page = await firstLesson(app)
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('ArrowDown')
  await expect.poll(() => current(page)).toEqual({ i: 2, lit: 1 })
  await page.reload()
  await page.waitForSelector('.cell')
  await expect.poll(() => current(page)).toEqual({ i: 2, lit: 1 })
})

test('Reopen Closed Window returns to the bundle and its cell', async ({ launch }, info) => {
  const app = await launch([fixture(info.outputDir)])
  const page = await firstLesson(app)
  await page.keyboard.press('ArrowDown')
  await expect.poll(() => current(page)).toEqual({ i: 1, lit: 1 })
  await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].close())
  await expect.poll(() => windows(app)).toEqual([])
  await Promise.all([app.waitForEvent('window'), click(app, 'reopenClosed')])
  const page2 = await firstLesson(app)
  await expect.poll(() => current(page2)).toEqual({ i: 1, lit: 1 })
})

// Error boxes are recorded by a script preloaded with `electron -r`, which a packaged app does not accept.
test('an index that fails the schema shows the schema path and opens no window', async ({
  launch
}, info) => {
  test.skip(!!process.env.EX_EXECUTABLE, 'needs electron -r (the dev app)')
  const b = fixture(info.outputDir)
  const index = join(b, 'build', 'index.json')
  writeFileSync(
    index,
    JSON.stringify({ ...JSON.parse(readFileSync(index, 'utf8')), fps: undefined })
  )
  const app = await launch([b], undefined, { stubErrorBox: true })
  const boxes = () =>
    app.evaluate(() => (globalThis as unknown as { errorBoxes: unknown[] }).errorBoxes)
  await expect
    .poll(boxes)
    .toEqual([
      { title: `Cannot open ${b}`, message: `${index}: / must have required property 'fps'` }
    ])
  expect(await windows(app)).toEqual([])
})
