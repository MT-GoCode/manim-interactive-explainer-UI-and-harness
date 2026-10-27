// node tools/cells-cli.mjs <cells.md>: prints readCells' result as JSON (explain-build's way in).
import { readFileSync } from 'node:fs'
import { readCells } from './cells.mjs'

process.stdout.write(JSON.stringify(readCells(readFileSync(process.argv[2], 'utf8'))) + '\n')
