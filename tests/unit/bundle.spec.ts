import { execFileSync } from 'child_process'
import {
  appendFileSync,
  cpSync,
  mkdirSync,
  readFileSync,
  realpathSync,
  rmSync,
  symlinkSync,
  writeFileSync
} from 'fs'
import { join } from 'path'
import { pathToFileURL } from 'url'
import { expect, test } from '@playwright/test'
import { clipPath, clipUrl, load, LoadError } from '../../src/main/bundle'
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
  expect(lesson.cells.at(-1)).toEqual({ slug: 'extra', md: 'More.\n', clip: null })
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
  const file = clipPath(clip.url, [real])!
  expect(file.startsWith(join(real, 'build', 'clips') + '/')).toBe(true)
  expect(readFileSync(file).length).toBeGreaterThan(0)
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
