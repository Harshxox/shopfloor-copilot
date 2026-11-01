import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import TeachUpload from '../components/TeachUpload.jsx'

const STATUS_CLASS = { ready: 'good', failed: 'bad' }

export default function Teach() {
  const nav = useNavigate()
  const [sops, setSops] = useState([])

  const load = useCallback(() => api('/sops').then(setSops).catch(() => setSops([])), [])
  useEffect(() => { load() }, [load])

  const onReady = useCallback((id) => { load(); nav(`/teach/${id}`) }, [load, nav])

  return (
    <section>
      <h1>Teach</h1>
      <p className="muted">An expert does the job once on camera, narrating each step. The SOP is written for you.</p>
      <TeachUpload onReady={onReady} />

      <h2>Saved SOPs</h2>
      {sops.length === 0 ? (
        <p className="muted">No SOPs yet.</p>
      ) : (
        <div className="soplist">
          {sops.map((s) => (
            <Link key={s.id} to={`/teach/${s.id}`} className="sopitem">
              <span>{s.name}</span>
              <span className={`badge ${STATUS_CLASS[s.status] || ''}`}>{s.status}</span>
            </Link>
          ))}
        </div>
      )}
    </section>
  )
}
