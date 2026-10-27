import {
  app,
  BrowserWindow,
  dialog,
  ipcMain,
  screen,
  type MenuItemConstructorOptions,
  type Rectangle
} from 'electron'
import { existsSync, realpathSync, watch, type FSWatcher } from 'fs'
import { basename, dirname, join, resolve } from 'path'
import { CH, type Command } from '../shared/ipc'
import type { Lesson } from '../shared/lesson'
import { load, LoadError } from './bundle'
import { readSession, writeSession, type Entry } from './session'

// Main is the single owner of window state and of everything read from disk.
type W = {
  win: BrowserWindow
  dir: string
  real: string // dir with symlinks resolved, once at open: what clip: URLs are checked against
  slug: string | null
  lesson: Lesson
  watchers: FSWatcher[]
}

const wins = new Map<number, W>()
const closed: Entry[] = []
const early: string[] = []
let quitting = false

const ofWin = (win: { id: number } | null | undefined): W | undefined =>
  win ? wins.get(win.id) : undefined
const entry = (w: W): Entry => ({ dir: w.dir, slug: w.slug, bounds: w.win.getBounds() })
// After before-quit has written the session once, the windows closing (and late messages from them) never rewrite it.
const saveSession = (): void => {
  if (!quitting) writeSession([...wins.values()].map(entry))
}
const send = (w: W, c: Command): void => w.win.webContents.send(CH.command, c)
export const openDirs = (): string[] => [...wins.values()].map((w) => w.real)

// A failure is always shown, never swallowed.
function guarded(label: string, fn: () => unknown): void {
  try {
    fn()
  } catch (err) {
    dialog.showErrorBox(label, (err as Error).message)
  }
}

ipcMain.handle(CH.init, (e) => {
  const w = ofWin(BrowserWindow.fromWebContents(e.sender))!
  return { lesson: w.lesson, slug: w.slug }
})
ipcMain.on(CH.at, (e, slug: string) => {
  const w = ofWin(BrowserWindow.fromWebContents(e.sender))!
  w.slug = slug
  saveSession()
})

// Saved bounds are kept only if they still touch a display (a monitor may be gone).
const onScreen = (b: Rectangle): boolean =>
  screen
    .getAllDisplays()
    .some(
      ({ workArea: a }) =>
        b.x < a.x + a.width && a.x < b.x + b.width && b.y < a.y + a.height && a.y < b.y + b.height
    )

// Clips land in build/ before index.json, the commit point; render scratch under build/ is not the lesson.
const relevant = (rel: string | null): boolean =>
  !!rel && (!rel.startsWith('build/') || rel === 'build/index.json')

function reload(w: W): void {
  if (!wins.has(w.win.id)) return // a watch event queued before its window closed
  try {
    const { lesson, repoFiles } = load(w.dir)
    w.lesson = lesson
    watchRepo(w, repoFiles)
  } catch (e) {
    if (!(e instanceof LoadError)) throw e
    const alerts = w.lesson.alerts.filter((a) => a.t !== 'invalid')
    w.lesson = { ...w.lesson, alerts: [...alerts, { t: 'invalid', message: e.message }] }
  }
  send(w, { t: 'lesson', lesson: w.lesson })
}

// The bundle (recursive) plus the directories of the repo files its build read, filtered to those files.
function watchRepo(w: W, files: string[]): void {
  w.watchers.splice(1).forEach((x) => x.close())
  // A directory that is gone (the repo moved since the build) is not watched: its files already show as stale.
  for (const d of [...new Set(files.map(dirname))].filter((x) => existsSync(x))) {
    const names = new Set(files.filter((f) => dirname(f) === d).map((f) => basename(f)))
    w.watchers.push(watch(d, (_e, name) => name !== null && names.has(name) && reload(w)))
  }
}

function createWindow(dir: string, slug: string | null, bounds?: Rectangle): void {
  const { lesson, repoFiles } = load(dir)
  // 1280 wide: a 16:9 player 1260 px wide is 709 px tall, leaving ~250 px of transcript in a 1000 px window.
  const win = new BrowserWindow({
    width: 1280,
    height: 1000,
    ...(bounds && onScreen(bounds) ? bounds : {}),
    show: false,
    backgroundColor: '#000000',
    title: lesson.title,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: true,
      contextIsolation: true,
      spellcheck: false,
      // Inactive or covered windows must keep painting (measured: 0 fps otherwise).
      backgroundThrottling: false
    }
  })
  const w: W = { win, dir, real: realpathSync(dir), slug, lesson, watchers: [] }
  wins.set(win.id, w) // registered first: its close handlers below always find it
  w.watchers.push(watch(dir, { recursive: true }, (_e, rel) => relevant(rel) && reload(w)))
  watchRepo(w, repoFiles)
  win.setRepresentedFilename(dir)
  app.addRecentDocument(dir)
  win.on('page-title-updated', (e) => e.preventDefault())
  win.on('close', () => {
    if (!quitting) closed.push(entry(w))
  })
  win.on('closed', () => {
    wins.delete(win.id)
    w.watchers.forEach((x) => x.close())
    if (!quitting) saveSession()
  })
  win.once('ready-to-show', () => {
    if (!process.env.EX_INVISIBLE) return win.show()
    // Test runs: on screen for Chromium (so it renders and measures as usual), but
    // transparent, click-through and unfocused for whoever is using the machine.
    win.setOpacity(0)
    win.setIgnoreMouseEvents(true)
    win.showInactive()
  })
  const url = process.env.ELECTRON_RENDERER_URL
  if (url) win.loadURL(url)
  else win.loadFile(join(__dirname, '../renderer/index.html'))
  saveSession()
}

function openEntry({
  dir,
  slug,
  bounds
}: {
  dir: string
  slug: string | null
  bounds?: Rectangle
}): void {
  const open = [...wins.values()].find((w) => w.dir === dir)
  if (open) return open.win.focus()
  guarded(`Cannot open ${dir}`, () => createWindow(dir, slug, bounds))
}

const openPath = (p: string): void => openEntry({ dir: resolve(p).replace(/\/+$/, ''), slug: null })

// Quitting records the session once, before the windows close, so their closing never rewrites it.
app.on('before-quit', () => {
  saveSession()
  quitting = true
})

// Registered at import, before ready, so a Finder launch's bundle is not lost.
app.on('open-file', (e, p) => {
  e.preventDefault()
  if (app.isReady()) openPath(p)
  else early.push(p)
})

export const openPaths = (paths: string[]): void => paths.forEach(openPath)

export function openInitial(paths: string[]): void {
  guarded('Cannot restore the previous session', () => readSession().forEach(openEntry))
  ;[...paths, ...early.splice(0)].forEach(openPath)
}

export const fileMenu = (): MenuItemConstructorOptions[] => [
  {
    label: 'File',
    submenu: [
      {
        id: 'open',
        label: 'Open…',
        accelerator: 'CmdOrCtrl+O',
        click: async () =>
          (
            await dialog.showOpenDialog({
              properties: ['openFile', 'openDirectory', 'multiSelections'],
              filters: [{ name: 'Explainer', extensions: ['explainer'] }]
            })
          ).filePaths.forEach(openPath)
      },
      {
        label: 'Open Recent',
        role: 'recentDocuments',
        submenu: [{ role: 'clearRecentDocuments' }]
      },
      {
        id: 'reopenClosed',
        label: 'Reopen Closed Window',
        accelerator: 'CmdOrCtrl+Shift+T',
        click: () => {
          const e = closed.pop()
          if (e) openEntry(e)
        }
      },
      { type: 'separator' },
      { role: 'close' }
    ]
  }
]
