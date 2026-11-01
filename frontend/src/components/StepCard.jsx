import { useState } from 'react'
import { api } from '../api.js'

const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`

export default function StepCard({ step, sopId, onSeek, onSaved }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(step)
  const [saving, setSaving] = useState(false)

  async function save() {
    setSaving(true)
    try {
      const updated = await api(`/sops/${sopId}/steps/${step.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: draft.action,
          expected_end_state: draft.expected_end_state,
          critical: draft.critical,
        }),
      })
      onSaved(updated)
      setEditing(false)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className={`step ${step.critical ? 'critical' : ''}`}>
      <div className="thumb" onClick={() => onSeek(step.start_sec)} title="Play this step">
        {step.thumbnail_path ? <img src={`/media/${step.thumbnail_path}`} alt={step.action} />
          : <div className="nothumb">No image</div>}
        <span className="num">{step.idx}</span>
        <span className="time">{fmt(step.start_sec)}–{fmt(step.end_sec)}</span>
      </div>

      <div className="body">
        {editing ? (
          <>
            <label className="small muted">Action</label>
            <input value={draft.action} onChange={(e) => setDraft({ ...draft, action: e.target.value })} />
            <label className="small muted">Done when</label>
            <textarea rows={2} value={draft.expected_end_state}
                      onChange={(e) => setDraft({ ...draft, expected_end_state: e.target.value })} />
            <label className="check">
              <input type="checkbox" checked={draft.critical}
                     onChange={(e) => setDraft({ ...draft, critical: e.target.checked })} />
              Critical step (skipping it causes a defect or safety risk)
            </label>
            <div className="row">
              <button className="primary" onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Save'}</button>
              <button onClick={() => { setDraft(step); setEditing(false) }}>Cancel</button>
            </div>
          </>
        ) : (
          <>
            <div className="head">
              <h3>{step.action}</h3>
              {step.critical && <span className="tag crit">Critical</span>}
              <button className="link" onClick={() => setEditing(true)}>Edit</button>
            </div>
            <p className="done"><span className="muted">Done when: </span>{step.expected_end_state}</p>
            <div className="chips">
              {step.parts.map((p) => <span key={`p-${p}`} className="chip">{p}</span>)}
              {step.tools.map((t) => <span key={`t-${t}`} className="chip tool">🔧 {t}</span>)}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
