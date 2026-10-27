import { execFileSync, spawnSync } from 'child_process'
import { existsSync, readdirSync, readFileSync } from 'fs'
import { homedir } from 'os'
import { join } from 'path'
import { expect, fixture, test } from './app'

// Only a packaged, registered app owns .explainer (exported UTI), so only it is reached through LaunchServices or
// listed in Open Recent. LaunchServices launches it here, as Finder does: an app started by the test runner instead
// belongs to the runner's process, and LaunchServices cannot deliver to it (error -600, measured).
test.skip(!process.env.EX_EXECUTABLE, 'needs EX_EXECUTABLE (a packaged Explainers.app)')

const ID = 'com.mtgocode.explainers'
const RECENTS = join(
  homedir(),
  'Library/Application Support/com.apple.sharedfilelist/com.apple.LSSharedFileList.ApplicationRecentDocuments'
)

test('bundles opened through LaunchServices open in the app and land in Open Recent', async ({}, info) => {
  const first = fixture(join(info.outputDir, 'a'))
  const second = fixture(join(info.outputDir, 'b'))
  const userData = info.outputPath('userdata')
  const session = () => {
    const f = join(userData, 'session.json')
    return existsSync(f)
      ? (JSON.parse(readFileSync(f, 'utf8')) as { dir: string }[]).map((e) => e.dir)
      : []
  }
  const exe = process.env.EX_EXECUTABLE!
  try {
    // A fresh instance with its own userData, invisible: the bundle arrives as Finder's open-file at launch.
    execFileSync('open', [
      '-n',
      '-b',
      ID,
      '--env',
      `EX_USER_DATA=${userData}`,
      '--env',
      'EX_INVISIBLE=1',
      first
    ])
    await expect.poll(session, { timeout: 15000 }).toEqual([first])
    // The running instance receives the next one.
    execFileSync('open', ['-b', ID, second])
    await expect.poll(session, { timeout: 15000 }).toEqual([first, second])
    // macOS writes the recents list asynchronously; it names the bundle in its bookmark data.
    const listed = () =>
      readdirSync(RECENTS)
        .filter((f) => f.startsWith(`${ID}.sfl`))
        .some((f) => readFileSync(join(RECENTS, f)).includes('softmax.explainer'))
    await expect.poll(listed, { timeout: 15000 }).toBe(true)
  } finally {
    // The instance LaunchServices started is not the runner's to close: stop it by its executable.
    spawnSync('pkill', ['-f', exe.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')])
  }
})
