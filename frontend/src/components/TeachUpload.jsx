import { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'

const STAGES = [
  ['uploaded', 'Uploaded'],
  ['normalizing', 'Preparing video'],
  ['transcribing', 'Transcribing narration'],
  ['building', 'Muse Spark writing steps'],
  ['thumbnails', 'SAM 3.1 marking parts'],
  ['ready', 'Ready'],
]

function Progress({ status, error }) {
  const current = STAGES.findIndex(([s]) => s === status)
  return (
    <div className="progress">
      {STAGES.map(([key, label], i) => {
        const state = status === 'failed' ? (i <= Math.max(current, 0) ? 'bad' : '')
          : i < current || status === 'ready' ? 'done' : i === current ? 'active' : ''
        return (
          <div key={key} className={`stage ${state}`}>
            <span className="dot" />
            <span>{label}</span>
          </div>
        )
      })}
      {status === 'failed' && <p className="error">Failed: {error}</p>}
    </div>
  )
}

function Recorder({ onRecorded }) {
  const videoRef = useRef(null)
  const recRef = useRef(null)
  const chunks = useRef([])
  const [stream, setStream] = useState(null)
  const [recording, setRecording] = useState(false)
  const [seconds, setSeconds] = useState(0)
  const [error, setError] = useState('')

  useEffect(() => () => stream?.getTracks().forEach((t) => t.stop()), [stream])
  useEffect(() => {
    if (!recording) return
    const t = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(t)
  }, [recording])

  async function openCamera() {
    setError('')
    try {
      const s = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1280 } }, audio: true,
      })
      setStream(s)
      videoRef.current.srcObject = s
    } catch (e) {
      setError(`Camera not available: ${e.message}`)
    }
  }

  function start() {
    chunks.current = []
    const opts = MediaRecorder.isTypeSupported?.('video/webm') ? { mimeType: 'video/webm' } : {}
    const rec = new MediaRecorder(stream, opts)
    rec.ondataavailable = (e) => e.data.size && chunks.current.push(e.data)
    rec.onstop = () => {
      const blob = new Blob(chunks.current, { type: 'video/webm' })
      onRecorded(new File([blob], `expert-${Date.now()}.webm`, { type: 'video/webm' }))
      stream.getTracks().forEach((t) => t.stop())
      setStream(null)
    }
    rec.start(1000)
    recRef.current = rec
    setSeconds(0)
    setRecording(true)
  }

  function stop() {
    recRef.current?.stop()
    setRecording(false)
  }

  return (
    <div className="recorder">
      <video ref={videoRef} autoPlay muted playsInline className={stream ? '' : 'hidden'} />
      {!stream && <button onClick={openCamera}>Open camera</button>}
      {stream && !recording && <button className="primary" onClick={start}>● Start recording</button>}
      {recording && <button className="danger" onClick={stop}>■ Stop ({seconds}s)</button>}
      {error && <p className="error">{error}</p>}
      <p className="muted small">Narrate each step out loud as you do it.</p>
    </div>
  )
}

export default function TeachUpload({ onReady }) {
  const [file, setFile] = useState(null)
  const [name, setName] = useState('')
  const [mode, setMode] = useState('upload')
  const [job, setJob] = useState(null) // {id, status, error}
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!job || ['ready', 'failed'].includes(job.status)) return
    const t = setInterval(async () => {
      const { sop } = await api(`/sops/${job.id}`)
      setJob({ id: sop.id, status: sop.status, error: sop.error })
      if (sop.status === 'ready') onReady(sop.id)
    }, 2000)
    return () => clearInterval(t)
  }, [job, onReady])

  async function submit() {
    if (!file) return
    setBusy(true)
    const form = new FormData()
    form.append('video', file)
    form.append('name', name)
    try {
      const res = await api('/sops/teach', { method: 'POST', body: form })
      setJob({ id: res.id, status: res.status, error: '' })
    } catch (e) {
      setJob({ id: null, status: 'failed', error: e.message })
    } finally {
      setBusy(false)
    }
  }

  const running = job && !['ready', 'failed'].includes(job.status)

  return (
    <div className="card">
      <div className="tabs">
        <button className={mode === 'upload' ? 'on' : ''} onClick={() => setMode('upload')}>Upload video</button>
        <button className={mode === 'record' ? 'on' : ''} onClick={() => setMode('record')}>Record now</button>
      </div>

      {mode === 'upload' ? (
        <label className="drop">
          <input type="file" accept="video/*" onChange={(e) => setFile(e.target.files[0] || null)} />
          {file ? <strong>{file.name}</strong> : <span>Choose the expert's video (mp4, mov, webm)</span>}
        </label>
      ) : (
        <Recorder onRecorded={(f) => { setFile(f); setMode('upload') }} />
      )}

      <div className="row">
        <input placeholder="Procedure name (optional — AI will name it)" value={name}
               onChange={(e) => setName(e.target.value)} />
        <button className="primary" disabled={!file || busy || running} onClick={submit}>
          {running ? 'Working…' : 'Build SOP'}
        </button>
      </div>

      {job && <Progress status={job.status} error={job.error} />}
    </div>
  )
}
