import type { Node } from 'unist'
import type { Text } from 'mdast'
export const REF: RegExp
export const LINK: RegExp
export function isAutolink(source: string, n: Node): boolean
export function textsIn(tree: Node, source: string): { node: Text; start: number; src: string }[]
export function refsIn(
  tree: Node,
  source: string
): { node: Text; key: string; start: number; end: number; vstart: number; vend: number }[]
