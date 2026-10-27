// One immutable snapshot of a bundle, made by main (the only reader of the disk) and rendered by the renderer.
export type Alert =
  | { t: 'stale'; files: string[] } // "lesson.py", bundle relpaths, "repo/<relpath>": changed since the build
  | { t: 'order'; prose: string[]; build: string[] } // cells.md slugs ≠ the build's, in order
  | { t: 'invalid'; message: string } // a reload failed: the last good lesson stays on screen
export type Clip = { url: string; frames: number; fps: number }
// md: the section without its heading line; head: that line verbatim (the source between cells is head + "\n")
export type Cell = { slug: string; head: string; md: string; clip: Clip | null }
export type Build = { refs: Record<string, string> }
// build null: never built. A cell's number is its position + 1, never stored.
export type Lesson = {
  dir: string
  title: string
  cells: Cell[]
  alerts: Alert[]
  build: Build | null
}
