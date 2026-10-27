import type { ElectronApplication } from '@playwright/test'
import { expect, firstLesson, fixture, test } from './app'

// These use the one system clipboard, so they run one after the other, and leave it as they found it.
test.describe.configure({ mode: 'serial' })

// On macOS ⌘V/⌘C are the Edit menu's native role items (AppKit's paste:/copy: down the responder chain), which a
// script cannot click; a test checks that the menu carries them, and drives the same command the role sends.
const role = (app: ElectronApplication, id: string) =>
  app.evaluate(({ Menu }, id) => Menu.getApplicationMenu()!.getMenuItemById(id)?.role ?? null, id)
// The clipboard's text, HTML and RTF are put back afterwards (Minh may be using the machine). An image on it is
// lost: this Electron's main-process clipboard has no readImage (measured).
const withClipboard = async (app: ElectronApplication, f: () => Promise<void>) => {
  await app.evaluate(({ clipboard }) => {
    const g = globalThis as unknown as { saved: object }
    g.saved = { text: clipboard.readText(), html: clipboard.readHTML(), rtf: clipboard.readRTF() }
  })
  try {
    await f()
  } finally {
    await app.evaluate(({ clipboard }) => {
      clipboard.clear()
      clipboard.write(
        (globalThis as unknown as { saved: Parameters<typeof clipboard.write>[0] }).saved
      )
    })
  }
}

test('paste works in the editor', async ({ launch }, info) => {
  const app = await launch([fixture(info.outputDir)])
  const page = await firstLesson(app)
  expect(await role(app, 'paste')).toBe('paste')
  await withClipboard(app, async () => {
    await app.evaluate(({ clipboard }) => clipboard.writeText('PASTED'))
    await page.locator('.cell .md').nth(2).dblclick({ force: true })
    await page.locator('.editor .cm-content').waitFor()
    await page.keyboard.press('Meta+a')
    await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].webContents.paste())
    await expect(page.locator('.editor .cm-content')).toHaveText('PASTED')
  })
})

test('⌘C puts the source on the clipboard', async ({ launch }, info) => {
  const app = await launch([fixture(info.outputDir)])
  const page = await firstLesson(app)
  expect(await role(app, 'copy')).toBe('copy')
  await withClipboard(app, async () => {
    // inside "{n_tokens}" (shown as 6) in cell 1
    await page.evaluate(() => {
      const ref = document.querySelectorAll('.cell')[0].querySelector('.ref')!
      const text = document.createTreeWalker(ref, NodeFilter.SHOW_TEXT).nextNode()!
      const r = document.createRange()
      r.setStart(text, 0)
      r.setEnd(text, 1)
      document.getSelection()!.removeAllRanges()
      document.getSelection()!.addRange(r)
    })
    await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].webContents.copy())
    await expect
      .poll(() => app.evaluate(({ clipboard }) => clipboard.readText()))
      .toBe('{n_tokens}')
  })
})
