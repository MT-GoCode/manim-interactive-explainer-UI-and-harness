// Reads one bundle into a Lesson snapshot. Pure Node (no Electron), so the unit suite runs it directly.
import { createHash } from 'crypto'
import { existsSync, readFileSync } from 'fs'
import { basename, join, resolve, sep } from 'path'
import { pathToFileURL } from 'url'
import Ajv2020 from 'ajv/dist/2020'
import { readCells } from '../../tools/cells.mjs'
import schema from '../../schema/index.schema.json'
import type { Alert, Lesson } from '../shared/lesson'

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

// pathToFileURL percent-encodes every character a URL path cannot hold as-is, `%` included.
export const clipUrl = (abs: string): string => {
  const u = new URL('clip://local/')
  u.pathname = pathToFileURL(abs).pathname
  return u.href
}

// The file a clip: URL names, only if it is an .mp4 inside one of these bundles' build/clips/.
export function clipPath(url: string, dirs: string[]): string | null {
  const p = resolve(decodeURIComponent(new URL(url).pathname))
  return p.endsWith('.mp4') && dirs.some((d) => p.startsWith(join(d, 'build', 'clips') + sep))
    ? p
    : null
}

// The lesson, and the repo files its build read (main watches them for the stale alert).
export function load(dir: string): { lesson: Lesson; repoFiles: string[] } {
  const text = readFileSync(join(dir, 'cells.md'), 'utf8')
  const read = readCells(text)
  if (read.errors.length) throw new LoadError(read.errors.join('\n'))
  if (!read.sections.length) throw new LoadError('cells.md has no cells') // an editor caught mid-write
  const indexPath = join(dir, 'build', 'index.json')
  const index = existsSync(indexPath)
    ? (JSON.parse(readFileSync(indexPath, 'utf8')) as unknown)
    : null
  if (index !== null && !validate(index))
    throw new LoadError(
      `${indexPath}: ` +
        validate.errors!.map((e) => `${e.instancePath || '/'} ${e.message}`).join('; ')
    )
  const build = index as Index | null
  const clips = new Map(build?.cells.map((c) => [c.slug, c]))
  const cells = read.sections.map((s) => {
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
    const prose = read.sections.map((s) => s.slug)
    const built = build.cells.map((c) => c.slug)
    if (prose.join('\n') !== built.join('\n')) alerts.push({ t: 'order', prose, build: built })
  }
  return {
    lesson: {
      dir,
      title: basename(dir, '.explainer'),
      cells,
      alerts,
      build: build && { fps: build.fps, refs: build.refs }
    },
    repoFiles: build ? Object.keys(build.inputs.repo).map((rel) => join(build.repo_root, rel)) : []
  }
}
