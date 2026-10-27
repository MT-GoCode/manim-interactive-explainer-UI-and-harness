import { execFileSync } from 'child_process'
import { readdirSync, readFileSync } from 'fs'
import { homedir } from 'os'
import { join } from 'path'
import { expect, fixture, test } from './app'

// Only a packaged, registered app owns .explainer (exported UTI), so only it is reached through LaunchServices or
// listed in Open Recent.
test.skip(!process.env.EX_EXECUTABLE, 'needs EX_EXECUTABLE (a packaged Explainers.app)')

const RECENTS = join(
  homedir(),
  'Library/Application Support/com.apple.sharedfilelist/com.apple.LSSharedFileList.ApplicationRecentDocuments'
)

test('a bundle opened through LaunchServices opens in the running app and lands in Open Recent', async ({
  launch
}, info) => {
  const b = fixture(info.outputDir)
  const app = await launch()
  await Promise.all([
    app.waitForEvent('window'),
    execFileSync('open', ['-b', 'com.mtgocode.explainers', b])
  ])
  await expect
    .poll(() =>
      app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows().map((w) => w.getTitle()))
    )
    .toContain('softmax')
  // macOS writes the recents list asynchronously; it names the bundle in its bookmark data.
  const list = () =>
    readdirSync(RECENTS)
      .filter((f) => f.startsWith('com.mtgocode.explainers.sfl'))
      .map((f) => readFileSync(join(RECENTS, f)).includes('softmax.explainer'))
  await expect.poll(list, { timeout: 15000 }).toContain(true)
})
