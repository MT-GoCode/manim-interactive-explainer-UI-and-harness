import { execFileSync } from 'child_process'
import { cpSync, mkdirSync, rmSync } from 'fs'
import { join } from 'path'
import { BUILT, ROOT } from './app'

// The fixture lesson is built once, for real; each test works on its own clone of it.
export default function globalSetup(): void {
  rmSync(BUILT, { recursive: true, force: true })
  mkdirSync(join(BUILT, '..'), { recursive: true })
  cpSync(join(ROOT, 'tests/fixtures/softmax.explainer'), BUILT, {
    recursive: true,
    filter: (src) => !src.includes('/build')
  })
  execFileSync(join(ROOT, 'bin/explain-build'), [BUILT], { stdio: 'inherit' })
}
