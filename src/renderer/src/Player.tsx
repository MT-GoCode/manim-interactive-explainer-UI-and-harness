import { useEffect, useImperativeHandle, useRef, useState, type Ref } from 'react'
import type { Clip } from '../../shared/lesson'

export type PlayerHandle = { toggle(): void; replay(): void; step(d: number): void }

// A new src aborts a pending play(): that interruption is expected; any other failure is not.
const play = (v: HTMLVideoElement) =>
  v.play().catch((e: DOMException) => {
    if (e.name !== 'AbortError') throw e
  })

// Frame k is shown on [k/fps, (k+1)/fps); its centre (k + 0.5)/fps is the time that names it exactly.
const frameOf = (t: number, fps: number) => Math.round(t * fps - 0.5)

export function Player({
  slug,
  clip,
  ref
}: {
  slug: string
  clip: Clip | null
  ref: Ref<PlayerHandle>
}) {
  const video = useRef<HTMLVideoElement>(null)
  const [t, setT] = useState(0)
  // Which cell's clip this <video> element holds. The effect below is the only writer of src: it reads the old
  // clip's time and paused state before assigning the new one (assigning src resets the time to 0 at once).
  const loaded = useRef<{ el: HTMLVideoElement; slug: string } | null>(null)

  useImperativeHandle(ref, () => ({
    toggle: () => {
      const v = video.current
      if (v) void (v.paused ? play(v) : v.pause())
    },
    replay: () => {
      const v = video.current
      if (!v) return
      v.currentTime = 0
      void play(v)
    },
    step: (d) => {
      const v = video.current
      if (!v || !clip) return
      v.pause()
      const k = Math.min(clip.frames - 1, Math.max(0, frameOf(v.currentTime, clip.fps) + d))
      v.currentTime = (k + 0.5) / clip.fps
    }
  }))

  const url = clip?.url
  useEffect(() => {
    const v = video.current
    if (!v || !url) return
    // The same cell on the same element is a rebuild: it keeps its time and paused state.
    const same = loaded.current?.el === v && loaded.current.slug === slug
    const resume = same ? { time: v.currentTime, paused: v.paused } : null
    loaded.current = { el: v, slug }
    v.src = url
    const start = () => {
      if (resume) v.currentTime = Math.min(resume.time, v.duration) // a fresh clip already starts at 0
      if (!resume?.paused) void play(v)
    }
    v.addEventListener('loadedmetadata', start, { once: true })
    return () => v.removeEventListener('loadedmetadata', start)
  }, [slug, url])

  if (!clip)
    return (
      <div className="player">
        <div className="noclip">No clip for this cell — run explain-build</div>
      </div>
    )
  return (
    <div className="player">
      <video
        ref={video}
        crossOrigin="anonymous"
        muted
        onTimeUpdate={(e) => setT(e.currentTarget.currentTime)}
        onSeeked={(e) => setT(e.currentTarget.currentTime)}
      />
      <input
        type="range"
        min={0}
        max={clip.frames / clip.fps}
        step={1 / clip.fps}
        value={t}
        onChange={(e) => {
          video.current!.currentTime = Number(e.target.value)
        }}
      />
    </div>
  )
}
