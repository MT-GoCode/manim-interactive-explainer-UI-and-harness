import type { Lesson } from './lesson'

export const CH = {
  init: 'ex:init',
  at: 'ex:at',
  save: 'ex:save',
  openLink: 'ex:openLink',
  comment: 'ex:comment',
  resolve: 'ex:resolve',
  ping: 'ex:ping',
  command: 'ex:command'
} as const

// main → renderer
export type Command =
  | { t: 'lesson'; lesson: Lesson }
  | { t: 'find' }
  | { t: 'goto' } // open the ⌘G box
  | { t: 'show'; slug: string } // a link landed here: make this cell current

// What a save of one cell came to: written, or why not (nothing was written then).
export type Saved =
  | { t: 'saved' }
  | { t: 'conflict'; disk: string } // the cell changed on disk since the edit began
  | { t: 'gone' } // the cell is no longer in cells.md
  | { t: 'invalid'; message: string } // cells.md is unreadable, or the text would change the cells

// renderer → main; the only surface the renderer sees.
export interface Api {
  init(): Promise<{ lesson: Lesson; slug: string | null }>
  at(slug: string): void
  save(slug: string, base: string, text: string): Promise<Saved>
  openLink(slug: string, cell: string): void
  // base: the prose the span was measured on (main refuses if the cell changed since)
  comment(cell: string, base: string, span: [number, number] | null, text: string): void
  resolve(id: string): void
  ping(): void
  onCommand(fn: (c: Command) => void): void
}
