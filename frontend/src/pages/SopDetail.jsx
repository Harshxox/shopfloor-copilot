import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api.js'
import StepCard from '../components/StepCard.jsx'

const LANGS = [['kn', 'ಕನ್ನಡ Kannada'], ['hi', 'हिंदी Hindi'], ['en', 'English']]

export default function SopDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const videoRef = useRef(null)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [lang, setLang] = useState(() => localStorage.getItem('workerLang') || 'kn')
  const [showTranscript, setShowTranscript] = useState(false)

  useEffect(() => {
    api(`/sops/${id}`).then(setData).catch((e) => setError(e.message))
  }, [id])

  function seek(sec) {
    const v = videoRef.current
    if (!v) return
    v.currentTime = sec
    v.play()
    v.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  function onSaved(updated) {
    setData((d) => ({ ...d, steps: d.steps.map((s) => (s.id === updated.id ? updated : s)) }))
  }

  async function remove() {
    if (!window.confirm('Delete this SOP?')) return
    await api(`/sops/${id}`, { method: 'DELETE' }).catch(() => {})
    nav('/teach')
  }

  function startCheck() {
    localStorage.setItem('workerLang', lang)
    nav(`/check?sop=${id}&lang=${lang}`)
  }

  if (error) return <p className="error">{error}</p>
  if (!data) return <p className="muted">Loading…</p>
  const { sop, steps } = data
  const critical = steps.filter((s) => s.critical).length

  return (
    <section>
      <Link to="/teach" className="muted small">← All SOPs</Link>
      <div className="titlebar">
        <div>
          <h1>{sop.name}</h1>
          <p className="muted">{steps.length} steps · {critical} critical · status {sop.status}</p>
        </div>
        <button className="danger ghost" onClick={remove}>Delete</button>
      </div>

      <div className="grid2">
        <div>
          {sop.video_path && <video ref={videoRef} src={`/media/${sop.video_path}`} controls className="player" />}
          {sop.transcript && (
            <div className="card small">
              <button className="link" onClick={() => setShowTranscript(!showTranscript)}>
                {showTranscript ? 'Hide' : 'Show'} expert narration
              </button>
              {showTranscript && <pre className="transcript">{sop.transcript}</pre>}
            </div>
          )}
        </div>
        <div className="card start">
          <h2>Train a worker on this</h2>
          <p className="muted small">The worker hears corrections in their language.</p>
          <div className="langs">
            {LANGS.map(([code, label]) => (
              <button key={code} className={lang === code ? 'on' : ''} onClick={() => setLang(code)}>{label}</button>
            ))}
          </div>
          <button className="primary big" onClick={startCheck} disabled={sop.status !== 'ready'}>
            Start Check mode →
          </button>
        </div>
      </div>

      <h2>Steps</h2>
      <div className="steps">
        {steps.map((s) => <StepCard key={s.id} step={s} sopId={sop.id} onSeek={seek} onSaved={onSaved} />)}
      </div>
    </section>
  )
}
