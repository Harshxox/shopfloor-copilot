import { useEffect, useState } from 'react'
import { api } from '../api.js'

// Phase 2: lists existing SOPs. Phase 4 adds recording/upload and step cards.
export default function Teach() {
  const [sops, setSops] = useState([])

  useEffect(() => {
    api('/sops').then(setSops).catch(() => setSops([]))
  }, [])

  return (
    <section>
      <h1>Teach</h1>
      <p className="muted">An expert does the job once on camera. The steps are written for you.</p>
      <div className="card placeholder">Record / upload expert video — coming in Phase 4</div>
      <h2>Saved SOPs</h2>
      {sops.length === 0 ? (
        <p className="muted">No SOPs yet.</p>
      ) : (
        <ul>{sops.map((s) => <li key={s.id}>{s.name} — {s.status}</li>)}</ul>
      )}
    </section>
  )
}
