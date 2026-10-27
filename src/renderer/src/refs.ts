import type { Root } from 'mdast'
import type { VFile } from 'vfile'
import { refsIn } from '../../../tools/grammar.mjs'

// Value references become their built values; unknown ones stay literal. refsIn is the build's own finder, so the
// app and explain-build agree on what is a reference (escapes, code, math, autolinks).
export const refs = (values: Record<string, string>) => () => (tree: Root, file: VFile) => {
  const hits = refsIn(tree, String(file)).filter((h) => h.key in values)
  for (const h of hits.sort((a, b) => b.vstart - a.vstart))
    // right to left: earlier offsets stay valid
    h.node.value = h.node.value.slice(0, h.vstart) + values[h.key] + h.node.value.slice(h.vend)
}
