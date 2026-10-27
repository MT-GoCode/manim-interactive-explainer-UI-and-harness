export type Section = { slug: string; start: number; line: number; end: number }
export function readCells(text: string): {
  sections: Section[]
  refs: { key: string; name: string; line: number }[]
  links: { slug: string; cell: string; line: number }[]
  errors: string[]
}
