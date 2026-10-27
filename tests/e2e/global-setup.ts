import { execFileSync } from 'child_process'
import { cpSync, mkdirSync, rmSync, writeFileSync } from 'fs'
import { join } from 'path'
import { BUILT, FRAMES, ROOT } from './app'

// The fixture lesson is built once, for real, and its "probs" clip decoded for frame-exact player checks.
export default function globalSetup(): void {
  rmSync(BUILT, { recursive: true, force: true })
  mkdirSync(join(BUILT, '..'), { recursive: true })
  cpSync(join(ROOT, 'tests/fixtures/softmax.explainer'), BUILT, {
    recursive: true,
    filter: (src) => !src.includes('/build')
  })
  execFileSync(join(ROOT, 'bin/explain-build'), [BUILT], { stdio: 'inherit' })
  const out = execFileSync('uv', [
    'run',
    '-q',
    '--project',
    ROOT,
    'python',
    join(__dirname, 'frames.py'),
    BUILT,
    'probs'
  ])
  writeFileSync(FRAMES, out)
}
