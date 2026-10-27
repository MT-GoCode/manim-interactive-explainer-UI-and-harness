import { execFileSync } from 'child_process'
import { resolve } from 'path'
import { pathToFileURL } from 'url'
import { expect, firstLesson, fixture, test } from './app'

// Only a packaged, registered app owns .explainer (exported UTI, document type), so these run against one. Each fact
// Finder relies on is read from macOS itself; a live LaunchServices launch is not used, because an ad-hoc signed app
// launched that way waits on Gatekeeper's first-launch check, which an unattended machine never answers (measured).
test.skip(!process.env.EX_EXECUTABLE, 'needs EX_EXECUTABLE (a packaged, registered Explainers.app)')

const osa = (js: string) =>
  execFileSync('osascript', ['-l', 'JavaScript', '-e', js], { encoding: 'utf8' }).trim()

test('Finder opens a bundle with this app, as one document', async ({}, info) => {
  const b = fixture(info.outputDir)
  // The app LaunchServices picks to open the bundle (what a Finder double-click would launch) is this very copy:
  // ./test registers only it for the run, so a broken build cannot pass on another registered copy's record.
  const handler = osa(
    `ObjC.import('AppKit'); $.NSWorkspace.sharedWorkspace.URLForApplicationToOpenURL($.NSURL.URLWithString(${JSON.stringify(pathToFileURL(b).href)})).path.js`
  )
  expect(handler).toBe(resolve(process.env.EX_EXECUTABLE!, '../../..'))
  // Typed as our exported UTI, which conforms to a package: Finder shows the folder as one file.
  const types = execFileSync('mdls', ['-raw', '-name', 'kMDItemContentTypeTree', b], {
    encoding: 'utf8'
  })
  expect(types).toContain('"com.mtgocode.explainer"')
  expect(types).toContain('"com.apple.package"')
})

test('an opened bundle lands in Open Recent', async ({ launch }, info) => {
  const b = fixture(info.outputDir)
  const app = await launch([b])
  await firstLesson(app)
  await expect.poll(() => app.evaluate(({ app }) => app.getRecentDocuments())).toContain(b)
})
