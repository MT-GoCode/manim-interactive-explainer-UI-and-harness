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
const sha = (path: string): string | null =>
  existsSync(path) ? createHash('sha256').update(readFileSync(path)).digest('hex') : null

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

// The file a clip: URL names, only if it is an existing .mp4 inside one of these bundles' build/clips/ (after
// symlinks are resolved). A malformed URL names nothing.
export function clipPath(url: string, dirs: string[]): string | null {
  let p: string
  try {
    p = resolve(decodeURIComponent(new URL(url).pathname))
  } catch {
    return null
  }
  if (!p.endsWith('.mp4') || !existsSync(p)) return null
  const real = realpathSync(p)
  return dirs.some((d) => real.startsWith(join(realpathSync(d), 'build', 'clips') + sep))
    ? real
    : null
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
