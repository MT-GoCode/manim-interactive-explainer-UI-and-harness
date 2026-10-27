import type { Lesson } from './lesson'

export const CH = {
  init: 'ex:init',
  at: 'ex:at',
  save: 'ex:save',
  command: 'ex:command'
} as const

// main → renderer
export type Command = { t: 'lesson'; lesson: Lesson } | { t: 'find' } | { t: 'goto' }

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
  onCommand(fn: (c: Command) => void): void
}
