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
  // A media error is shown for the clip it happened to; a new clip has none until it fails itself.
  const [failed, setFailed] = useState<{ url: string; message: string } | null>(null)
  // Which cell's clip this <video> element holds, and the resume it is to apply. The effect below is the only writer
  // of src: it reads the old clip's time and paused state before assigning the new one (assigning src resets the
  // time to 0 at once). Before the old clip's metadata arrived the element holds no time of its own, so a resume
  // still waiting is carried over.
  type Resume = { time: number; paused: boolean } | null
  const loaded = useRef<{ el: HTMLVideoElement; slug: string; resume: Resume } | null>(null)

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
    const prev = loaded.current
    const same = prev?.el === v && prev.slug === slug
    const resume: Resume = !same
      ? null
      : v.readyState >= HTMLMediaElement.HAVE_METADATA
        ? { time: v.currentTime, paused: v.paused }
        : prev.resume
    loaded.current = { el: v, slug, resume }
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
        onLoadedMetadata={(e) => setT(e.currentTarget.currentTime)}
        onTimeUpdate={(e) => setT(e.currentTarget.currentTime)}
        onSeeked={(e) => setT(e.currentTarget.currentTime)}
        onError={(e) => {
          const err = e.currentTarget.error!
          setFailed({
            url: clip.url,
            message: `This clip cannot play (${err.code}): ${err.message}`
          })
        }}
      />
      {failed?.url === clip.url && <div className="failed">{failed.message}</div>}
      <input
        type="range"
        min={0}
        max={clip.frames / clip.fps}
        step={1 / clip.fps}
        value={t}
        onChange={(e) => {
          // The bar's steps are frame starts; a frame is named by its centre (see frameOf).
          const k = Math.min(clip.frames - 1, Math.round(Number(e.target.value) * clip.fps))
          video.current!.currentTime = (k + 0.5) / clip.fps
        }}
      />
    </div>
  )
}
