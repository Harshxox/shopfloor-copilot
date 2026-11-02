import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api.js'
import { hasVoice, listenForDone, speak, voiceDoneSupported } from '../speech.js'

const LANGS = [['kn', 'ಕನ್ನಡ Kannada'], ['hi', 'हिंदी Hindi'], ['en', 'English']]
const SHOW_RESULT = {
  en: 'Finish the step, then hold the result up to the camera for 2 seconds and tap Done.',
  kn: 'ಹಂತ ಮುಗಿಸಿ, ಫಲಿತಾಂಶವನ್ನು 2 ಸೆಕೆಂಡ್ ಕ್ಯಾಮರಾಗೆ ತೋರಿಸಿ, ನಂತರ Done ಒತ್ತಿ.',
  hi: 'कदम पूरा करें, नतीजा 2 सेकंड कैमरे को दिखाएँ, फिर Done दबाएँ।',
}

// ---------- start screen ----------
function StartRun({ initialSop, initialLang, onStarted }) {
  const [sops, setSops] = useState([])
  const [sopId, setSopId] = useState(initialSop || '')
  const [lang, setLang] = useState(initialLang || localStorage.getItem('workerLang') || 'kn')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api('/sops').then((all) => {
      const ready = all.filter((s) => s.status === 'ready')
      setSops(ready)
      if (!sopId && ready[0]) setSopId(String(ready[0].id))
    })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function start() {
    setBusy(true)
    setError('')
    try {
      localStorage.setItem('workerLang', lang)
      const res = await api('/runs', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sop_id: Number(sopId), worker_language: lang }),
      })
      onStarted(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card">
      <label className="small muted">Procedure</label>
      <select value={sopId} onChange={(e) => setSopId(e.target.value)}>
        {sops.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
      </select>
      <label className="small muted" style={{ marginTop: 14, display: 'block' }}>Worker's language</label>
      <div className="langs">
        {LANGS.map(([code, label]) => (
          <button key={code} className={lang === code ? 'on' : ''} onClick={() => setLang(code)}>{label}</button>
        ))}
      </div>
      {!hasVoice(lang) && (
        <p className="warn small">No {LANGS.find((l) => l[0] === lang)[1]} voice on this computer — instructions will
          show on screen. (Chrome on Android has Kannada and Hindi voices.)</p>
      )}
      <button className="primary big" disabled={!sopId || busy} onClick={start}>
        {busy ? 'Starting…' : 'Start shift'}
      </button>
      {error && <p className="error">{error}</p>}
    </div>
  )
}

// ---------- camera + recorder ----------
function useCamera() {
  const [stream, setStream] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let s
    navigator.mediaDevices?.getUserMedia({ video: { facingMode: 'environment', width: { ideal: 1280 } }, audio: false })
      .then((st) => { s = st; setStream(st) })
      .catch((e) => setError(e.message))
    return () => s?.getTracks().forEach((t) => t.stop())
  }, [])
  return { stream, error }
}

function useRecorder(stream) {
  const rec = useRef(null)
  const chunks = useRef([])
  const [recording, setRecording] = useState(false)
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    if (!recording) return
    const t = setInterval(() => setSeconds((x) => x + 1), 1000)
    return () => clearInterval(t)
  }, [recording])

  const start = useCallback(() => {
    if (!stream) return
    chunks.current = []
    const opts = MediaRecorder.isTypeSupported?.('video/webm') ? { mimeType: 'video/webm' } : {}
    const r = new MediaRecorder(stream, opts)
    r.ondataavailable = (e) => e.data.size && chunks.current.push(e.data)
    r.start(500)
    rec.current = r
    setSeconds(0)
    setRecording(true)
  }, [stream])

  const stop = useCallback(() => new Promise((resolve) => {
    const r = rec.current
    if (!r || r.state === 'inactive') return resolve(null)
    r.onstop = () => {
      setRecording(false)
      resolve(new File([new Blob(chunks.current, { type: 'video/webm' })], `step-${Date.now()}.webm`,
        { type: 'video/webm' }))
    }
    r.stop()
  }), [])

  return { start, stop, recording, seconds }
}

// ---------- evidence (SAM overlay arrives a few seconds after the verdict) ----------
function Evidence({ runId, event }) {
  const [path, setPath] = useState(event.clip_path)
  useEffect(() => {
    setPath(event.clip_path)
    if (event.clip_path.endsWith('_hands.mp4')) return
    let n = 0
    const t = setInterval(async () => {
      n += 1
      const { events } = await api(`/runs/${runId}`)
      const ev = events.find((e) => e.id === event.id)
      if (ev?.clip_path.endsWith('_hands.mp4') || n > 20) {
        if (ev) setPath(ev.clip_path)
        clearInterval(t)
      }
    }, 3000)
    return () => clearInterval(t)
  }, [runId, event])
  return (
    <div className="evidence">
      <video src={`/media/${path}`} controls muted playsInline />
      <span className="small muted">{path.endsWith('_hands.mp4') ? 'SAM 3.1 hand tracking' : 'Clip (hand tracking loading…)'}</span>
    </div>
  )
}

// ---------- the run ----------
function ActiveRun({ start }) {
  const run0 = start.run
  const lang = run0.worker_language
  const [run, setRun] = useState(run0)
  const [sop, setSop] = useState(null)
  const [texts] = useState(start.step_texts)
  const [phase, setPhase] = useState('recording') // recording | checking | result | done
  const [result, setResult] = useState(null)
  const [history, setHistory] = useState([])
  const [error, setError] = useState('')
  const [said, setSaid] = useState(start.say)
  const videoRef = useRef(null)
  const fileRef = useRef(null)
  const { stream, error: camError } = useCamera()
  const recorder = useRecorder(stream)

  useEffect(() => { api(`/sops/${run0.sop_id}`).then(setSop) }, [run0.sop_id])
  useEffect(() => { speak(start.say, lang) }, [start.say, lang])
  useEffect(() => {
    if (stream && videoRef.current) videoRef.current.srcObject = stream
  }, [stream])
  useEffect(() => {
    if (stream && phase === 'recording' && !recorder.recording) recorder.start()
  }, [stream, phase]) // eslint-disable-line react-hooks/exhaustive-deps

  const submit = useCallback(async (file) => {
    if (!file) return
    setPhase('checking')
    setError('')
    const form = new FormData()
    form.append('clip', file)
    form.append('step_idx', run.current_step)
    try {
      const res = await api(`/runs/${run.id}/check`, { method: 'POST', body: form })
      setResult(res)
      setRun(res.run)
      setHistory((h) => [...h, res.event])
      setSaid(res.say)
      speak(res.say, lang)
      setPhase(res.run.status === 'done' ? 'done' : 'result')
      if (res.event.kind === 'pass' && res.run.status !== 'done') {
        setTimeout(() => { setResult(null); setPhase('recording') }, 3500)
      }
    } catch (e) {
      setError(e.message)
      setPhase('recording')
    }
  }, [run, lang])

  const done = useCallback(async () => {
    if (phase !== 'recording') return
    submit(await recorder.stop())
  }, [phase, recorder, submit])

  useEffect(() => {
    const onKey = (e) => { if (e.code === 'Space' && e.target.tagName !== 'INPUT') { e.preventDefault(); done() } }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [done])

  // Hands-free: say "done" (or ಮುಗಿತು / हो गया) instead of tapping
  const [voiceDone, setVoiceDone] = useState(false)
  const [voiceStatus, setVoiceStatus] = useState({})
  const doneRef = useRef(done)
  doneRef.current = done
  useEffect(() => {
    if (!voiceDone) { setVoiceStatus({}); return undefined }
    return listenForDone(() => doneRef.current(), setVoiceStatus)
  }, [voiceDone])

  async function retry() {
    setResult(null)
    setPhase('recording')
    speak(texts[run.current_step], lang)
  }

  async function overrideFlag() {
    const res = await api(`/runs/${run.id}/override`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event_id: result.event.id }),
    })
    setHistory((h) => [...h, { id: `o${result.event.id}`, kind: 'override', step_idx: result.event.step_idx }])
    setRun(res.run)
    setSaid(res.say)
    speak(res.say, lang)
    setResult(null)
    setPhase(res.run.status === 'done' ? 'done' : 'recording')
  }

  async function uploadInstead(e) {
    const f = e.target.files[0]
    e.target.value = ''
    if (recorder.recording) await recorder.stop()
    submit(f)
  }

  const steps = sop?.steps || []
  const step = steps.find((s) => s.idx === run.current_step)
  const statusOf = (idx) => {
    const evs = history.filter((e) => e.step_idx === idx)
    if (evs.some((e) => e.kind === 'pass' || e.kind === 'override')) return 'done'
    if (evs.some((e) => e.kind === 'flag')) return idx === run.current_step ? 'flagged' : ''
    return idx === run.current_step ? 'active' : ''
  }

  if (phase === 'done') {
    const flags = history.filter((e) => e.kind === 'flag').length
    const overrides = history.filter((e) => e.kind === 'override').length
    return (
      <div className="card done-card">
        <span className="sign" aria-hidden="true">✓</span>
        <h2>All {steps.length} steps complete</h2>
        <p className="said">{said}</p>
        <p className="muted">{flags} correction{flags === 1 ? '' : 's'}, {overrides} supervisor override{overrides === 1 ? '' : 's'}</p>
        <div className="row">
          <Link to="/report"><button className="primary">View report</button></Link>
          <button onClick={() => window.location.reload()}>Start another shift</button>
        </div>
      </div>
    )
  }

  return (
    <div className="checkgrid">
      <div className="camcol">
        <div className={`cam ${phase}`}>
          {camError ? <div className="nocam">Camera unavailable ({camError}). Use “Upload clip”.</div>
            : <video ref={videoRef} autoPlay muted playsInline />}
          {phase === 'recording' && recorder.recording && <span className="rec">● Recording {recorder.seconds}s</span>}
          {phase === 'checking' && <div className="overlay"><div className="spinner" />Checking the step with Muse Spark</div>}
        </div>

        {result && (
          <div className={`verdict ${result.event.kind}`}>
            <span className="sign" aria-hidden="true">{result.event.kind === 'pass' ? '✓' : '✕'}</span>
            <div className="vhead">{result.event.kind === 'pass' ? 'Correct' : labelFor(result.event.deviation_type)}</div>
            <p className="said">{result.say}</p>
            {result.event.kind === 'flag' && (
              <>
                <details>
                  <summary className="small">Why (for supervisor)</summary>
                  <p className="small">{result.event.reason}</p>
                </details>
                <Evidence runId={run.id} event={result.event} />
                <div className="row">
                  <button className="primary" onClick={retry}>Try again</button>
                  <button onClick={overrideFlag}>Supervisor: false alarm</button>
                </div>
              </>
            )}
          </div>
        )}
        {error && <p className="error">{error}</p>}
      </div>

      <div className="stepcol">
        <div className="stepnow card">
          <div className="small muted">Step {run.current_step} of {steps.length}{step?.critical && <span className="tag crit" style={{ marginLeft: 8 }}>Critical</span>}</div>
          <h2 className="native">{texts[run.current_step]}</h2>
          {lang !== 'en' && step && <p className="muted small">{step.action}</p>}
          {step?.thumbnail_path && <img src={`/media/${step.thumbnail_path}`} alt="" className="ref" />}
          <p className="small"><span className="muted">Done when: </span>{step?.expected_end_state}</p>
          {phase === 'recording' && <p className="hint">{SHOW_RESULT[lang]}</p>}
          <div className="donebar">
            <button className="primary big" disabled={phase !== 'recording' || !recorder.recording} onClick={done}>
              Done <span className="small">(Space{voiceDone ? ' or say “done”' : ''})</span>
            </button>
            {voiceDoneSupported() && (
              <label className="check small voicetoggle">
                <input type="checkbox" checked={voiceDone} onChange={(e) => setVoiceDone(e.target.checked)} />
                Hands-free: say “done” / “ಮುಗಿತು” / “हो गया”
              </label>
            )}
            {voiceDone && (
              <p className={`small voicestatus ${voiceStatus.state || ''}`}>
                {voiceStatus.state === 'error' ? `⚠ ${voiceStatus.error}`
                  : voiceStatus.state === 'triggered' ? `✓ Heard “${voiceStatus.heard}”`
                  : voiceStatus.state === 'listening' ? `🎙 Listening… ${voiceStatus.heard ? `heard “${voiceStatus.heard}”` : ''}`
                  : 'Starting microphone…'}
              </p>
            )}
          </div>
          <button className="link small" onClick={() => fileRef.current.click()} disabled={phase === 'checking'}>
            Upload clip instead
          </button>
          <input ref={fileRef} type="file" accept="video/*" hidden onChange={uploadInstead} />
        </div>

        <ol className="stepbar">
          {steps.map((s) => (
            <li key={s.id} className={statusOf(s.idx)}>
              <span className="n">{s.idx}</span><span>{texts[s.idx] || s.action}</span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  )
}

function labelFor(type) {
  return { skip: 'Step skipped', wrong_order: 'Wrong step', wrong_part: 'Wrong part', missing: 'Not finished',
    unclear: 'Not visible' }[type] || 'Check again'
}

export default function Check() {
  const [params] = useSearchParams()
  const [start, setStart] = useState(null)
  return (
    <section className={start ? 'wide' : ''}>
      <h1>Check</h1>
      <p className="muted">The worker does the job. Each step is checked and corrected out loud.</p>
      {start ? <ActiveRun start={start} />
        : <StartRun initialSop={params.get('sop')} initialLang={params.get('lang')} onStarted={setStart} />}
    </section>
  )
}
