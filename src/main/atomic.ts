import { renameSync, writeFileSync } from 'fs'

// Write-then-rename, so a crash leaves either the old file or the new one, never half.
export function atomicWrite(path: string, text: string): void {
  writeFileSync(`${path}.tmp`, text)
  renameSync(`${path}.tmp`, path)
}
