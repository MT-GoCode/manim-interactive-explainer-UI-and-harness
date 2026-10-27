// Reads one bundle into a Lesson snapshot. Pure Node (no Electron), so the unit suite runs it directly.
import { createHash } from 'crypto'
import { existsSync, readFileSync, realpathSync } from 'fs'
import { basename, join, resolve, sep } from 'path'
import { pathToFileURL } from 'url'
import Ajv2020 from 'ajv/dist/2020'
import { readCells } from '../../tools/cells.mjs'
import schema from '../../schema/index.schema.json'
import type { Alert, Lesson } from '../shared/lesson'

// Everything that can be wrong with a bundle on disk; shown to the reader, never thrown past main.
export class LoadError extends Error {}

type Index = {
  lesson_sha: string
  inputs: { bundle: Record<string, string>; repo: Record<string, string> }
  repo_root: string
  fps: number
  refs: Record<string, string>
  cells: { slug: string; clip: string; frames: number }[]
}

const validate = new Ajv2020({ allErrors: true }).compile<Index>(schema)
// null for a file that is gone or cannot be read (mid-save, a directory now): not what the build read, so stale.
const sha = (path: string): string | null => {
  try {
    return createHash('sha256').update(readFileSync(path)).digest('hex')
  } catch {
    return null
  }
}

// The disk is outside the app: a file can vanish mid-save (editors that save by rename, git checkout) or hold a
// half-written edit. Each read is where that becomes a LoadError.
function read<T>(path: string, parse: (text: string) => T): T {
  try {
    return parse(readFileSync(path, 'utf8'))
  } catch (e) {
    throw new LoadError(`${path}: ${(e as Error).message}`)
  }
}

// pathToFileURL percent-encodes every character a URL path cannot hold as-is, `%` included.
export const clipUrl = (abs: string): string => {
  const u = new URL('clip://local/')
  u.pathname = pathToFileURL(abs).pathname
  return u.href
}

// The file a clip: URL names, only if it is an existing .mp4 inside one of these bundles' build/clips/, symlinks
// resolved. `dirs` are the open bundles' real paths (resolved once, when each opened). A malformed URL, or a file
// that is gone, names nothing.
export function clipPath(url: string, dirs: string[]): string | null {
  let real: string
  try {
    real = realpathSync(resolve(decodeURIComponent(new URL(url).pathname)))
  } catch {
    return null
  }
  return real.endsWith('.mp4') && dirs.some((d) => real.startsWith(join(d, 'build', 'clips') + sep))
    ? real
    : null
}

// The bytes an HTTP Range header asks of a file of `size` bytes: null for the whole file (no header, or one this
// does not parse: RFC 9110 says to ignore it), 'unsatisfiable' for a range that starts past the end.
// <video> treats a clip as seekable only if its responses carry Content-Length and Accept-Ranges and ranges get 206.
export function byteRange(
  header: string | null,
  size: number
): { start: number; end: number } | null | 'unsatisfiable' {
  const m = header === null ? null : /^bytes=(\d*)-(\d*)$/.exec(header)
  if (!m || (m[1] === '' && m[2] === '')) return null
  if (m[1] === '') {
    const n = Number(m[2]) // the last n bytes
    return n === 0 || size === 0 ? 'unsatisfiable' : { start: Math.max(0, size - n), end: size - 1 }
  }
  const start = Number(m[1])
  const end = m[2] === '' ? size - 1 : Math.min(Number(m[2]), size - 1)
  if (start >= size) return 'unsatisfiable'
  return end < start ? null : { start, end }
}

// The lesson, and the repo files its build read (main watches them for the stale alert).
export function load(dir: string): { lesson: Lesson; repoFiles: string[] } {
  const text = read(join(dir, 'cells.md'), (t) => t)
  const found = readCells(text)
  if (found.errors.length) throw new LoadError(found.errors.join('\n'))
  if (!found.sections.length) throw new LoadError('cells.md has no cells') // an editor caught mid-write
  const slugs = found.sections.map((s) => s.slug)
  const dup = slugs.find((s, i) => slugs.indexOf(s) !== i)
  if (dup) throw new LoadError(`cells.md has "## ${dup}" twice; a slug names one cell`)
  const indexPath = join(dir, 'build', 'index.json')
  const index = existsSync(indexPath) ? read(indexPath, (t) => JSON.parse(t) as unknown) : null
  if (index !== null && !validate(index))
    throw new LoadError(
      `${indexPath}: ` +
        validate.errors!.map((e) => `${e.instancePath || '/'} ${e.message}`).join('; ')
    )
  const build = index as Index | null
  const clips = new Map(build?.cells.map((c) => [c.slug, c]))
  const cells = found.sections.map((s) => {
    const c = clips.get(s.slug)
    const section = text.slice(s.start, s.end)
    return {
      slug: s.slug,
      md: section.slice(section.indexOf('\n') + 1),
      clip: c
        ? { url: clipUrl(join(dir, 'build', c.clip)), frames: c.frames, fps: build!.fps }
        : null
    }
  })
  const alerts: Alert[] = []
  if (build) {
    const files = [
      ...(sha(join(dir, 'lesson.py')) === build.lesson_sha ? [] : ['lesson.py']),
      ...Object.entries(build.inputs.bundle)
        .filter(([rel, h]) => sha(join(dir, rel)) !== h)
        .map(([rel]) => rel),
      ...Object.entries(build.inputs.repo)
        .filter(([rel, h]) => sha(join(build.repo_root, rel)) !== h)
        .map(([rel]) => `repo/${rel}`)
    ]
    if (files.length) alerts.push({ t: 'stale', files })
    const built = build.cells.map((c) => c.slug)
    if (slugs.join('\n') !== built.join('\n'))
      alerts.push({ t: 'order', prose: slugs, build: built })
  }
  return {
    lesson: {
      dir,
      title: basename(dir, '.explainer'),
      cells,
      alerts,
      build: build && { refs: build.refs }
    },
    repoFiles: build ? Object.keys(build.inputs.repo).map((rel) => join(build.repo_root, rel)) : []
  }
}
