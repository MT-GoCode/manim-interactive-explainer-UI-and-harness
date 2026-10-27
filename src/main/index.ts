import { resolve } from 'path'
import { pathToFileURL } from 'url'
import { app, BrowserWindow, Menu, net, protocol, shell } from 'electron'
import { CH, type Command } from '../shared/ipc'
import { clipPath } from './bundle'
import { fileMenu, openDirs, openInitial, openPaths } from './windows'

if (process.env.EX_USER_DATA) app.setPath('userData', process.env.EX_USER_DATA)
if (process.env.EX_INVISIBLE) app.dock?.hide()

// One instance per userData: two would both rewrite session.json. A second launch hands its
// bundles to the first and exits without running quit handlers (which would save a session).
const primary = app.requestSingleInstanceLock()
if (!primary) app.exit(0)
const bundles = (argv: string[], cwd: string) =>
  argv.map((a) => resolve(cwd, a).replace(/\/+$/, '')).filter((a) => a.endsWith('.explainer'))
app.on('second-instance', (_e, argv, cwd) => openPaths(bundles(argv, cwd)))

// Links in rendered markdown open in the browser; the app window never navigates away.
app.on('web-contents-created', (_e, wc) => {
  const external = (url: string) => {
    if (['http:', 'https:', 'mailto:'].includes(new URL(url).protocol)) shell.openExternal(url)
  }
  wc.on('will-navigate', (e, url) => {
    e.preventDefault()
    external(url)
  })
  wc.setWindowOpenHandler(({ url }) => {
    external(url)
    return { action: 'deny' }
  })
})

// Clips are served under full security from the open bundles only; stream + Range lets <video> seek, and
// CORS lets the canvas read frames back (probed).
protocol.registerSchemesAsPrivileged([
  {
    scheme: 'clip',
    privileges: {
      standard: true,
      secure: true,
      stream: true,
      supportFetchAPI: true,
      corsEnabled: true
    }
  }
])

const toWindow = (t: 'find' | 'goto') => (_i: unknown, win: unknown) =>
  (win as BrowserWindow | undefined)?.webContents.send(CH.command, { t } satisfies Command)

// The losing instance must not open windows (and so write a session) before it exits.
if (primary)
  app.whenReady().then(() => {
    protocol.handle('clip', async (req) => {
      const p = clipPath(req.url, openDirs())
      if (!p) return new Response(null, { status: 404 })
      const r = await net.fetch(pathToFileURL(p).href, { headers: req.headers })
      const headers = new Headers(r.headers)
      headers.set('Access-Control-Allow-Origin', '*')
      return new Response(r.body, { status: r.status, headers })
    })
    Menu.setApplicationMenu(
      Menu.buildFromTemplate([
        {
          label: app.name,
          submenu: [
            { role: 'about' },
            { type: 'separator' },
            { role: 'services' },
            { type: 'separator' },
            { role: 'hide' },
            { role: 'hideOthers' },
            { role: 'unhide' },
            { type: 'separator' },
            { role: 'quit' }
          ]
        },
        ...fileMenu(),
        {
          label: 'Edit',
          submenu: [
            { role: 'copy' },
            { role: 'selectAll' },
            { type: 'separator' },
            { id: 'find', label: 'Find…', accelerator: 'CmdOrCtrl+F', click: toWindow('find') },
            {
              id: 'goto',
              label: 'Go to Cell…',
              accelerator: 'CmdOrCtrl+G',
              click: toWindow('goto')
            }
          ]
        },
        { role: 'viewMenu' },
        { role: 'windowMenu' }
      ])
    )
    openInitial(bundles(process.argv, process.cwd()))
  })

// macOS: the app outlives its windows.
app.on('window-all-closed', () => {})
