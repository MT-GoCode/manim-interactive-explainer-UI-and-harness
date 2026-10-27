// One immutable snapshot of a bundle, made by main (the only reader of the disk) and rendered by the renderer.
export type Alert =
  | { t: 'stale'; files: string[] } // "lesson.py", bundle relpaths, "repo/<relpath>": changed since the build
  | { t: 'order'; prose: string[]; build: string[] } // cells.md slugs ≠ the build's, in order
  | { t: 'invalid'; message: string } // a reload failed: the last good lesson stays on screen
export type Clip = { url: string; frames: number; fps: number }
export type Cell = { slug: string; md: string; clip: Clip | null } // md: the section without its heading line
export type Build = { refs: Record<string, string> }
// build null: never built. A cell's number is its position + 1, never stored.
export type Lesson = {
  dir: string
  title: string
  cells: Cell[]
  alerts: Alert[]
  build: Build | null
}
