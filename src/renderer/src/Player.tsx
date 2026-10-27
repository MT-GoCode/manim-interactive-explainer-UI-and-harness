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
  // What was playing before the src changed: the same cell (a rebuild) keeps its time and paused state.
  const last = useRef<{ slug: string; time: number; paused: boolean } | null>(null)

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
    const prev = last.current
    const resume = prev?.slug === slug ? prev : null
    const start = () => {
      v.currentTime = resume ? Math.min(resume.time, v.duration) : 0
      if (!resume?.paused) void play(v)
    }
    v.addEventListener('loadedmetadata', start, { once: true })
    return () => {
      v.removeEventListener('loadedmetadata', start)
      last.current = { slug, time: v.currentTime, paused: v.paused }
    }
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
        src={clip.url}
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
