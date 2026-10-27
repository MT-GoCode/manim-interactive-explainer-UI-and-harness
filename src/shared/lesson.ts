// One immutable snapshot of a bundle, made by main (the only reader of the disk) and rendered by the renderer.
export type Alert =
  | { t: 'stale'; files: string[] } // "lesson.py", bundle relpaths, "repo/<relpath>": changed since the build
  | { t: 'order'; prose: string[]; build: string[] } // cells.md slugs ≠ the build's, in order
  | { t: 'invalid'; message: string } // a reload failed: the last good lesson stays on screen
export type Clip = { url: string; frames: number; fps: number; frames_sha: string }
// md: the section without its heading line; head: that line verbatim (the source between cells is head + "\n")
export type Cell = { slug: string; head: string; md: string; clip: Clip | null }
export type Build = { refs: Record<string, string> }
// A comment as the reader sees it, marked once in main: on a span of its cell's prose (with that quote), on the
// whole cell, or on a cell that is gone (Minh's to resolve).
export type Comment = { id: string; cell: string; text: string } & (
  | { on: 'cell' }
  | { on: 'span'; span: [number, number]; quote: string }
  | { on: 'orphan'; span: [number, number] | null }
)
// build null: never built. A cell's number is its position + 1, never stored.
export type Lesson = {
  dir: string
  title: string
  cells: Cell[]
  alerts: Alert[]
  build: Build | null
  comments: Comment[]
  pinging: boolean // the `ping` file exists: the model has not fetched yet
}
