import { test as base, _electron, type ElectronApplication, type Page } from '@playwright/test'
import { execFileSync } from 'child_process'
import { mkdirSync } from 'fs'
import { join } from 'path'

export const ROOT = join(__dirname, '../..')
// Built once in global setup; each test works on its own clone of it.
export const BUILT = join(ROOT, 'test-results/fixtures/softmax.explainer')
export const FRAMES = join(ROOT, 'test-results/fixtures/frames.json')

// A private APFS clone of the built fixture, named softmax.explainer, inside the test's output dir.
export const fixture = (dir: string): string => {
  mkdirSync(dir, { recursive: true }) // Playwright creates a test's output dir lazily
  const b = join(dir, 'softmax.explainer')
  execFileSync('cp', ['-c', '-R', BUILT, b])
  return b
}

// Every launch gets its own userData unless one is passed (to relaunch over it), runs without taking focus, and
// leaves a trace.zip. It does not wait for a window: some launches must open none.
export const test = base.extend<{
  launch: (
    files?: string[],
    userData?: string,
    opts?: { stubErrorBox?: boolean }
  ) => Promise<ElectronApplication>
}>({
  launch: async ({}, use, info) => {
    const apps: ElectronApplication[] = []
    const exited = new Set<ElectronApplication>()
    await use(
      async (files = [], userData = info.outputPath(`userdata-${apps.length}`), opts = {}) => {
        // EX_EXECUTABLE runs the whole suite against a packaged app instead of out/.
        const packaged = process.env.EX_EXECUTABLE
        const app = await _electron.launch({
          executablePath: packaged,
          args: packaged
            ? files
            : [
                ...(opts.stubErrorBox ? ['-r', join(__dirname, 'stub-error-box.cjs')] : []),
                join(ROOT, 'out/main/index.js'),
                ...files
              ],
          env: { ...process.env, EX_INVISIBLE: '1', EX_USER_DATA: userData }
        })
        apps.push(app)
        app.on('close', () => exited.add(app))
        await app.context().tracing.start({ screenshots: true, snapshots: true })
        return app
      }
    )
    for (const [k, app] of apps.entries()) {
      if (exited.has(app)) continue
      await app.context().tracing.stop({ path: info.outputPath(`trace-${k}.zip`) })
      await app.close()
    }
  }
})
export { expect } from '@playwright/test'

// The first window, once its transcript has rendered.
export async function firstLesson(app: ElectronApplication): Promise<Page> {
  const page = await app.firstWindow()
  await page.waitForSelector('.cell')
  return page
}

export const winId = async (app: ElectronApplication, page: Page) =>
  (await app.browserWindow(page)).evaluate((w) => w.id)

// Clicks an app-menu item as if from window `id` (menu handlers act on the window they are given).
export const click = (app: ElectronApplication, item: string, id?: number) =>
  app.evaluate(
    ({ BrowserWindow, Menu }, [item, id]) =>
      Menu.getApplicationMenu()!
        .getMenuItemById(item)!
        .click(undefined, id === undefined ? undefined : BrowserWindow.fromId(id)!),
    [item, id] as const
  )

// The index of the current cell, and how many cells are lit (always exactly one).
export const current = (page: Page) =>
  page.evaluate(() => {
    const cells = [...document.querySelectorAll('.cell')]
    return {
      i: cells.findIndex((c) => c.classList.contains('current')),
      lit: cells.filter((c) => c.classList.contains('current')).length
    }
  })
