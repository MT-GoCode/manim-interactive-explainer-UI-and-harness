import { useMemo } from 'react'
import CodeMirror, { EditorView, keymap, type BasicSetupOptions } from '@uiw/react-codemirror'
import { markdown } from '@codemirror/lang-markdown'
import { EditorState, Prec } from '@codemirror/state'
import { vscodeDark } from '@uiw/codemirror-theme-vscode'

export type Problem = { t: 'conflict'; disk: string } | { t: 'invalid'; message: string }

// A plain text editor that only highlights: no gutters, completion, bracket pairing or active line.
const setup: BasicSetupOptions = {
  lineNumbers: false,
  foldGutter: false,
  highlightActiveLineGutter: false,
  highlightActiveLine: false,
  autocompletion: false,
  closeBrackets: false
}
const metrics = EditorView.theme({
  '.cm-content': { padding: '0', fontFamily: 'Menlo, monospace', fontSize: '14px' },
  '.cm-line': { padding: '0 4px' },
  '.cm-scroller': { lineHeight: '1.5' },
  '&.cm-focused': { outline: 'none' }
})

// One cell's raw markdown. ⌘↩ saves, Esc discards; leaving it for elsewhere in the app saves (App decides).
// Read-only while a save is in flight, so nothing typed then is lost.
export function Editor(props: {
  buf: string
  saving: boolean
  problem: Problem | null
  gone: boolean
  onChange: (buf: string) => void
  onSave: () => void
  onCancel: () => void
  onKeepMine: () => void
  onBlurOut: () => void
}) {
  const { buf, saving, problem, gone, onChange, onSave, onCancel, onKeepMine, onBlurOut } = props
  const extensions = useMemo(
    () => [
      markdown(),
      EditorView.lineWrapping,
      metrics,
      EditorState.readOnly.of(saving), // read-only, not uneditable: it keeps focus and its keys
      Prec.high(
        keymap.of([
          { key: 'Mod-Enter', run: () => (onSave(), true) },
          { key: 'Escape', run: () => (onCancel(), true) }
        ])
      )
    ],
    [saving, onSave, onCancel]
  )
  // Buttons never take focus, so pressing one is not leaving the editor.
  const keep = (e: React.MouseEvent) => e.preventDefault()
  return (
    <div
      className="editor"
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null) && document.hasFocus())
          onBlurOut()
      }}
    >
      <CodeMirror
        autoFocus
        value={buf}
        theme={vscodeDark}
        basicSetup={setup}
        extensions={extensions}
        onChange={onChange}
      />
      {gone && (
        <div className="problem">
          This cell is no longer in cells.md.{' '}
          <button onMouseDown={keep} onClick={onCancel}>
            Close
          </button>
        </div>
      )}
      {problem?.t === 'conflict' && (
        <div className="problem">
          This cell changed on disk while you edited it. On disk now:
          <pre>{problem.disk}</pre>
          <button onMouseDown={keep} onClick={onKeepMine}>
            Keep mine
          </button>{' '}
          <button onMouseDown={keep} onClick={onCancel}>
            Take the file&apos;s
          </button>
        </div>
      )}
      {problem?.t === 'invalid' && <div className="problem">{problem.message}</div>}
    </div>
  )
}
