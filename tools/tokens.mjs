// node tools/tokens.mjs <limit> <cells.md>...: each cell of cells.md (the build's sections, cells.mjs) over <limit>
// tokens, each file the reader rejects, then a summary. A cell's tokens are its whole source, prose, math and code as
// written, minus its own `## slug` line, encoded with o200k_base: tokens track reading load better than words (a long
// jargon word costs more). Exit 0: every cell within the limit; 1: anything bad.
import { readFileSync } from 'node:fs'
import { basename } from 'node:path'
import { countTokens } from 'gpt-tokenizer/encoding/o200k_base'
import { readCells } from './cells.mjs'

const [limit, ...files] = [Number(process.argv[2]), ...process.argv.slice(3)]
let over = 0, cells = 0, unread = 0
for (const file of files) {
  let text
  try {
    text = readFileSync(file, 'utf8')
  } catch (e) {
    unread++
    console.log(`could not check  ${file}: ${e.message}`)
    continue
  }
  const { sections, errors } = readCells(text)
  if (errors.length) {
    unread++
    console.log(`could not check  ${file}: ${errors.join('; ')}`)
    continue
  }
  for (const s of sections) {
    cells++
    const body = text.slice(s.start, s.end).replace(/^.*\n?/, '') // the cell's own "## slug" line is not content
    const n = countTokens(body)
    if (n > limit) {
      over++
      console.log(`over  ${file} ## ${s.slug} (${basename(file)}:${s.line}): ${n} tokens`)
    }
  }
}
console.log(`${files.length - unread} of ${files.length} files checked · ${cells} cells · ${over} over ${limit} tokens`)
process.exit(unread || over ? 1 : 0)
