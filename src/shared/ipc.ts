import type { Lesson } from './lesson'

export const CH = {
  init: 'ex:init',
  at: 'ex:at',
  command: 'ex:command'
} as const

// main → renderer
export type Command = { t: 'lesson'; lesson: Lesson } | { t: 'find' } | { t: 'goto' }

// renderer → main; the only surface the renderer sees.
export interface Api {
  init(): Promise<{ lesson: Lesson; slug: string | null }>
  at(slug: string): void
  onCommand(fn: (c: Command) => void): void
}
