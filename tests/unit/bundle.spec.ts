import { execFileSync } from 'child_process'
import {
  appendFileSync,
  existsSync,
  cpSync,
  mkdirSync,
  readFileSync,
  realpathSync,
  rmSync,
  symlinkSync,
  writeFileSync
} from 'fs'
import { createHash } from 'crypto'
import { join } from 'path'
import { pathToFileURL } from 'url'
import { expect, test } from '@playwright/test'
import {
  addComment,
  byteRange,
  clipPath,
  clipUrl,
  load,
  LoadError,
  resolveComment,
  saveSection
} from '../../src/main/bundle'
import { fixture, ROOT } from '../e2e/app'

const edit = (path: string, f: (s: string) => string) =>
  writeFileSync(path, f(readFileSync(path, 'utf8')))
const index = (b: string) => join(b, 'build', 'index.json')

test('a fresh build has every clip, its frame counts and refs, and no alert', async ({}, info) => {
  const b = fixture(info.outputDir)
  const built = JSON.parse(readFileSync(index(b), 'utf8'))
  const { lesson, repoFiles } = load(b)
  expect(lesson.alerts).toEqual([])
  expect(lesson.title).toBe('softmax')
  expect(lesson.build).toEqual({ refs: { n_tokens: '6', 'p_top:.4f': '0.5456' } })
  expect(lesson.cells.map((c) => c.clip!.fps)).toEqual([30, 30, 30, 30, 30, 30])
  expect(lesson.cells.map((c) => [c.slug, c.clip?.frames])).toEqual(
    built.cells.map((c) => [c.slug, c.frames])
  )
  expect(lesson.cells.map((c) => clipPath(c.clip!.url, [realpathSync(b)]))).toEqual(
    built.cells.map((c) => join(realpathSync(b), 'build', c.clip))
  )
  expect(lesson.cells[0].md.startsWith('## ')).toBe(false)
  expect(repoFiles).toEqual([join(ROOT, 'explainers/lesson.py')])
})

test('an edited lesson.py is stale', async ({}, info) => {
  const b = fixture(info.outputDir)
  appendFileSync(join(b, 'lesson.py'), '\n')
  expect(load(b).lesson.alerts).toEqual([{ t: 'stale', files: ['lesson.py'] }])
})

test('an edited bundle input is stale', async ({}, info) => {
  const b = fixture(info.outputDir)
  appendFileSync(join(b, 'helpers.py'), '\n')
  expect(load(b).lesson.alerts).toEqual([{ t: 'stale', files: ['helpers.py'] }])
})

test('an edited repo input is stale', async ({}, info) => {
  const b = fixture(info.outputDir)
  const repo = join(info.outputDir, 'repo')
  mkdirSync(repo)
  cpSync(join(ROOT, 'explainers'), join(repo, 'explainers'), { recursive: true })
  edit(index(b), (s) => JSON.stringify({ ...JSON.parse(s), repo_root: repo }))
  expect(load(b).lesson.alerts).toEqual([])
  appendFileSync(join(repo, 'explainers/lesson.py'), '\n')
  expect(load(b).lesson.alerts).toEqual([{ t: 'stale', files: ['repo/explainers/lesson.py'] }])
})

test('swapped headings raise the order alert', async ({}, info) => {
  const b = fixture(info.outputDir)
  edit(join(b, 'cells.md'), (s) =>
    s.replace('## sum', '## SWAP').replace('## exp', '## sum').replace('## SWAP', '## exp')
  )
  expect(load(b).lesson.alerts).toEqual([
    {
      t: 'order',
      prose: ['scores', 'sum', 'exp', 'divide', 'probs', 'top'],
      build: ['scores', 'exp', 'sum', 'divide', 'probs', 'top']
    }
  ])
})

test('a heading with no clip has a null clip', async ({}, info) => {
  const b = fixture(info.outputDir)
  appendFileSync(join(b, 'cells.md'), '\n## extra\nMore.\n')
  const { lesson } = load(b)
  expect(lesson.cells.at(-1)).toEqual({
    slug: 'extra',
    head: '## extra',
    md: 'More.\n',
    clip: null
  })
  expect(lesson.alerts.map((a) => a.t)).toEqual(['order'])
})

test('an unbuilt bundle has no build, no clips and no alerts', async ({}, info) => {
  const b = fixture(info.outputDir)
  rmSync(index(b))
  const { lesson } = load(b)
  expect([lesson.build, lesson.alerts, lesson.cells.map((c) => c.clip)]).toEqual([
    null,
    [],
    [null, null, null, null, null, null]
  ])
})

test('an index without fps is a load error', async ({}, info) => {
  const b = fixture(info.outputDir)
  edit(index(b), (s) => JSON.stringify({ ...JSON.parse(s), fps: undefined }))
  expect(() => load(b)).toThrow(LoadError)
  expect(() => load(b)).toThrow(`${index(b)}: / must have required property 'fps'`)
})

test('an empty cells.md is a load error', async ({}, info) => {
  const b = fixture(info.outputDir)
  writeFileSync(join(b, 'cells.md'), '')
  expect(() => load(b)).toThrow(new LoadError('cells.md has no cells'))
})

test("clipPath serves only open bundles' clips", async ({}, info) => {
  const odd = join(info.outputDir, 'a b#c?d%41e.explainer')
  execFileSync('cp', ['-c', '-R', fixture(info.outputDir), odd])
  const { lesson } = load(odd)
  const clip = lesson.cells[0].clip!
  const real = realpathSync(odd) // as the window holds it
  const built = JSON.parse(readFileSync(join(odd, 'build', 'index.json'), 'utf8'))
  expect(clipPath(clip.url, [real])).toBe(join(real, 'build', built.cells[0].clip))
  expect(clipPath(clip.url, [join(info.outputDir, 'other.explainer')])).toBeNull()
  // URLs built by hand: clipUrl would normalize these before clipPath ever saw them.
  const base = 'clip://local' + pathToFileURL(odd).pathname
  writeFileSync(join(odd, 'secret.mp4'), 'x')
  expect(clipPath(`${base}/build/clips/%2e%2e/%2e%2e/secret.mp4`, [real])).toBeNull()
  symlinkSync(join(odd, 'secret.mp4'), join(odd, 'build', 'clips', 'link.mp4'))
  expect(clipPath(`${base}/build/clips/link.mp4`, [real])).toBeNull()
  expect(clipPath(`${base}/build/clips/x%zz.mp4`, [real])).toBeNull()
  expect(clipPath(clipUrl(join(odd, 'build', 'clips', 'x.json')), [real])).toBeNull()
})

test('duplicate headings are a load error', async ({}, info) => {
  const b = fixture(info.outputDir)
  appendFileSync(join(b, 'cells.md'), '\n## sum\nAgain.\n')
  expect(() => load(b)).toThrow(new LoadError('cells.md has "## sum" twice; a slug names one cell'))
})

test('a vanished cells.md and a half-written index.json are load errors', async ({}, info) => {
  const b = fixture(info.outputDir)
  writeFileSync(index(b), '{"format": "expl')
  expect(() => load(b)).toThrow(LoadError)
  expect(() => load(b)).toThrow(`${index(b)}: `)
  rmSync(join(b, 'cells.md'))
  expect(() => load(b)).toThrow(LoadError)
  expect(() => load(b)).toThrow(`${join(b, 'cells.md')}: ENOENT`)
})

test('byteRange answers what a video asks for', () => {
  expect(byteRange(null, 100)).toBeNull()
  expect(byteRange('bytes=0-', 100)).toEqual({ start: 0, end: 99 })
  expect(byteRange('bytes=10-19', 100)).toEqual({ start: 10, end: 19 })
  expect(byteRange('bytes=90-200', 100)).toEqual({ start: 90, end: 99 })
  expect(byteRange('bytes=-30', 100)).toEqual({ start: 70, end: 99 })
  expect(byteRange('bytes=-0', 100)).toBe('unsatisfiable')
  expect(byteRange('bytes=-5', 0)).toBe('unsatisfiable')
  expect(byteRange('bytes=100-', 100)).toBe('unsatisfiable')
  expect(byteRange('bytes=20-10', 100)).toBeNull() // invalid: ignored, the whole file (RFC 9110)
  expect(byteRange('bytes=0-1, 5-6', 100)).toBeNull() // multiple ranges: not served as such
})

const cellsOf = (b: string) => readFileSync(join(b, 'cells.md'), 'utf8')
const section = (b: string, slug: string) => load(b).lesson.cells.find((c) => c.slug === slug)!.md

test('saveSection writes only its section', async ({}, info) => {
  const b = fixture(info.outputDir)
  const before = cellsOf(b)
  const base = section(b, 'sum')
  expect(saveSection(b, 'sum', base, 'Sum them up.   \n\n\n')).toEqual({ t: 'saved' })
  // one newline after the prose, then one blank line before the next heading
  expect(cellsOf(b)).toBe(before.replace('## sum\n' + base, '## sum\nSum them up.\n\n'))
  const last = section(b, 'top')
  expect(saveSection(b, 'top', last, 'The end.')).toEqual({ t: 'saved' })
  expect(cellsOf(b).endsWith('## top\nThe end.\n')).toBe(true) // the last cell: no blank line after it
})

test('saveSection answers conflict with the disk body', async ({}, info) => {
  const b = fixture(info.outputDir)
  const base = section(b, 'sum')
  writeFileSync(join(b, 'cells.md'), cellsOf(b).replace('Add them all', 'Add every one'))
  const disk = cellsOf(b)
  expect(saveSection(b, 'sum', base, 'Mine.')).toEqual({ t: 'conflict', disk: section(b, 'sum') })
  expect(cellsOf(b)).toBe(disk)
})

test('saveSection answers gone', async ({}, info) => {
  const b = fixture(info.outputDir)
  expect(saveSection(b, 'nope', '', 'x')).toEqual({ t: 'gone' })
})

test('saveSection refuses text that changes the cells', async ({}, info) => {
  const b = fixture(info.outputDir)
  const before = cellsOf(b)
  const r = saveSection(b, 'sum', section(b, 'sum'), 'Split.\n\n## extra\nNew.')
  expect(r.t).toBe('invalid')
  expect(cellsOf(b)).toBe(before)
})

test('saveSection reports an unreadable cells.md as invalid', async ({}, info) => {
  const b = fixture(info.outputDir)
  rmSync(join(b, 'cells.md'))
  expect(saveSection(b, 'sum', '', 'x')).toEqual({
    t: 'invalid',
    message: `${join(b, 'cells.md')}: ENOENT: no such file or directory, open '${join(b, 'cells.md')}'`
  })
})

test('saveSection reports a failed write as invalid and writes nothing', async ({}, info) => {
  const b = fixture(info.outputDir)
  const before = cellsOf(b)
  mkdirSync(join(b, 'cells.md.tmp')) // a directory in the way: the temporary file cannot be made
  let r: ReturnType<typeof saveSection> | undefined
  expect(() => (r = saveSection(b, 'sum', section(b, 'sum'), 'x'))).not.toThrow() // an answer, never a throw
  expect(r!.t).toBe('invalid')
  expect(cellsOf(b)).toBe(before)
})

// Comments, written as the app would; fingerprints computed here from the files, independently of bundle.ts.
const prose = (b: string, slug: string) => section(b, slug)
const framesSha = (b: string, slug: string) =>
  JSON.parse(readFileSync(index(b), 'utf8')).cells.find((c: { slug: string }) => c.slug === slug)
    .frames_sha
const comment = (b: string, id: string, cell: string, span: [number, number] | null = null) => ({
  id,
  cell,
  span,
  text: `about ${cell}`,
  created: '2026-10-27T00:00:00.000Z',
  fingerprint: {
    section_sha: createHash('sha256').update(prose(b, cell)).digest('hex'),
    frames_sha: framesSha(b, cell)
  }
})
const writeStored = (b: string, comments: object[]) =>
  writeFileSync(
    join(b, 'comments.json'),
    JSON.stringify({ format: 'explainer-comments', version: 1, comments })
  )
const storedIds = (b: string) =>
  (JSON.parse(readFileSync(join(b, 'comments.json'), 'utf8')).comments as { id: string }[]).map(
    (c) => c.id
  )

test('a changed section drops only its comments', async ({}, info) => {
  const b = fixture(info.outputDir)
  writeStored(b, [comment(b, 'aaaaaaa1', 'sum'), comment(b, 'aaaaaaa2', 'probs')])
  edit(join(b, 'cells.md'), (s) => s.replace('Add them all', 'Add every one'))
  const { comments, lesson } = load(b)
  expect(comments.kept.map((c) => c.id)).toEqual(['aaaaaaa2'])
  expect(comments.dropped).toBe(1)
  expect(lesson.comments.map((c) => [c.id, c.on])).toEqual([['aaaaaaa2', 'cell']])
})

test("a changed frames_sha drops only that cell's", async ({}, info) => {
  const b = fixture(info.outputDir)
  writeStored(b, [comment(b, 'aaaaaaa1', 'sum'), comment(b, 'aaaaaaa2', 'probs')])
  edit(index(b), (s) => {
    const ix = JSON.parse(s)
    ix.cells.find((c: { slug: string }) => c.slug === 'sum').frames_sha = 'f'.repeat(64)
    return JSON.stringify(ix)
  })
  expect(load(b).comments.kept.map((c) => c.id)).toEqual(['aaaaaaa2'])
})

test('a renamed heading keeps its comments as orphans', async ({}, info) => {
  const b = fixture(info.outputDir)
  writeStored(b, [comment(b, 'aaaaaaa1', 'sum', [0, 3])])
  edit(join(b, 'cells.md'), (s) => s.replace('## sum\n', '## total\n'))
  const { comments, lesson } = load(b)
  expect(comments.dropped).toBe(0)
  expect(lesson.comments).toEqual([
    { id: 'aaaaaaa1', cell: 'sum', text: 'about sum', on: 'orphan', span: [0, 3] }
  ])
})

test('an unbuilt bundle keeps comments whose prose is unchanged and drops those whose prose changed', async ({}, info) => {
  const b = fixture(info.outputDir)
  writeStored(b, [comment(b, 'aaaaaaa1', 'sum', [0, 3]), comment(b, 'aaaaaaa2', 'probs', [0, 3])])
  rmSync(index(b))
  edit(join(b, 'cells.md'), (s) => s.replace('Add them all', 'Add every one'))
  const { comments, lesson } = load(b)
  expect(comments.kept.map((c) => c.id)).toEqual(['aaaaaaa2'])
  expect(lesson.comments).toEqual([
    { id: 'aaaaaaa2', cell: 'probs', text: 'about probs', on: 'span', span: [0, 3], quote: 'Now' }
  ])
})

test('an invalid comments.json is a LoadError naming the schema path', async ({}, info) => {
  const b = fixture(info.outputDir)
  const valid = comment(b, 'aaaaaaa1', 'sum')
  writeStored(b, [{ ...valid, id: 'nothex!!' }])
  expect(() => load(b)).toThrow(`${join(b, 'comments.json')}: /comments/0/id must match pattern`)
  writeStored(b, [{ ...valid, created: 'yesterday' }])
  expect(() => load(b)).toThrow('/comments/0/created must match format "date-time"')
})

test('addComment writes a schema-valid comment with its fingerprint', async ({}, info) => {
  const b = fixture(info.outputDir)
  addComment(b, 'sum', prose(b, 'sum'), [0, 3], 'Why add?')
  const [c] = JSON.parse(readFileSync(join(b, 'comments.json'), 'utf8')).comments
  expect(c).toMatchObject({
    cell: 'sum',
    span: [0, 3],
    text: 'Why add?',
    fingerprint: comment(b, 'x', 'sum').fingerprint
  })
  expect(c.id).toMatch(/^[0-9a-f]{8}$/)
  expect(Number.isNaN(Date.parse(c.created))).toBe(false)
  expect(load(b).lesson.comments).toEqual([
    { id: c.id, cell: 'sum', text: 'Why add?', on: 'span', span: [0, 3], quote: 'Add' }
  ])
})

test('resolve removes exactly that comment', async ({}, info) => {
  const b = fixture(info.outputDir)
  writeStored(b, [comment(b, 'aaaaaaa1', 'sum'), comment(b, 'aaaaaaa2', 'probs')])
  resolveComment(b, 'aaaaaaa1')
  expect(storedIds(b)).toEqual(['aaaaaaa2'])
})

test('addComment refuses a span measured on older prose', async ({}, info) => {
  const b = fixture(info.outputDir)
  const old = prose(b, 'sum')
  edit(join(b, 'cells.md'), (s) => s.replace('Add them all', 'Add every one'))
  expect(() => addComment(b, 'sum', old, [0, 3], 'x')).toThrow(
    'This cell changed while you were commenting'
  )
  expect(existsSync(join(b, 'comments.json'))).toBe(false)
})
