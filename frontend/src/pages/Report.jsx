import { useEffect, useState } from 'react'
import { api } from '../api.js'

const pct = (x) => (x === null || x === undefined ? '—' : `${Math.round(x * 100)}%`)

function Tile({ label, value, sub }) {
  return (
    <div className="tile">
      <div className="tval">{value}</div>
      <div className="tlabel">{label}</div>
      {sub && <div className="tsub">{sub}</div>}
    </div>
  )
}

function StepTable({ rows }) {
  const max = Math.max(1, ...rows.map((r) => r.flags))
  return (
    <table className="steptable">
      <thead>
        <tr><th>#</th><th>Step</th><th>Checks</th><th>Corrections</th><th>First-try pass</th></tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.idx}>
            <td>{r.idx}</td>
            <td>{r.action}{r.critical && <span className="tag crit">Critical</span>}</td>
            <td>{r.attempts}</td>
            <td>
              <div className="barcell" title={`${r.flags} corrections${r.overrides ? `, ${r.overrides} overridden` : ''}`}>
                {r.flags > 0 && <div className="bar" style={{ width: `${(r.flags / max) * 100}%` }} />}
                <span>{r.flags}</span>
              </div>
            </td>
            <td>{pct(r.first_try_pass_rate)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function Report() {
  const [rep, setRep] = useState(null)
  const [sopId, setSopId] = useState('')
  const [sugg, setSugg] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setSugg(null)
    api(`/report${sopId ? `?sop_id=${sopId}` : ''}`).then((r) => {
      setRep(r)
      if (!sopId && r.sop) setSopId(String(r.sop.id))
    }).catch((e) => setError(e.message))
  }, [sopId])

  async function suggest() {
    setBusy(true)
    setError('')
    try {
      const r = await api('/report/suggestions', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sop_id: Number(sopId) }),
      })
      setSugg(r.suggestions)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function exportMd() {
    const res = await fetch('/api/report/export', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sop_id: Number(sopId), suggestions: sugg || [] }),
    })
    const blob = new Blob([await res.text()], { type: 'text/markdown' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `shift-report-sop${sopId}.md`
    a.click()
  }

  if (error && !rep) return <p className="error">{error}</p>
  if (!rep) return <p className="muted">Loading…</p>
  if (!rep.sop) return (<section><h1>Report</h1><p className="muted">No SOPs yet — teach one first.</p></section>)

  const k = rep.kpis
  return (
    <section className="wide">
      <div className="titlebar">
        <div>
          <h1>Shift report</h1>
          <p className="muted">What went wrong across worker runs, and how to fix the procedure.</p>
        </div>
        <button onClick={exportMd}>Download report</button>
      </div>
      <select value={sopId} onChange={(e) => setSopId(e.target.value)}>
        {rep.sops.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
      </select>

      {k.runs === 0 ? <p className="muted" style={{ marginTop: 20 }}>No worker runs on this SOP yet.</p> : (
        <>
          <div className="tiles">
            <Tile label="Worker runs" value={k.runs} sub={`${k.completed_runs} completed, ${k.clean_runs} without corrections`} />
            <Tile label="First-try pass rate" value={pct(k.first_try_pass_rate)} sub={`over ${k.checks} step checks`} />
            <Tile label="Corrections given" value={k.corrections} sub="mistakes caught before they shipped" />
            <Tile label="False alarms" value={k.false_alarms} sub={`supervisor overrides, ${pct(k.false_alarm_rate)} of corrections`} />
            <Tile label="Avg check time" value={k.avg_check_seconds ? `${k.avg_check_seconds}s` : '—'} sub="Muse Spark observe and judge" />
          </div>

          {rep.most_failed_step && (
            <div className="callout">
              <strong>Most-failed step:</strong> {rep.most_failed_step.idx}. {rep.most_failed_step.action}
              {' '}— {rep.most_failed_step.flags} correction{rep.most_failed_step.flags === 1 ? '' : 's'}
            </div>
          )}

          <div className="grid2 rgrid">
            <div className="card">
              <h2>Per step</h2>
              <StepTable rows={rep.per_step} />
            </div>
            <div className="card">
              <h2>Corrections by type</h2>
              {rep.deviation_types.length === 0 ? <p className="muted">None yet.</p> : (
                <ul className="typelist">
                  {rep.deviation_types.map((d) => (
                    <li key={d.type} title={`${d.count} ${d.label}`}>
                      <span>{d.label}</span>
                      <div className="barcell"><div className="bar"
                        style={{ width: `${(d.count / rep.deviation_types[0].count) * 100}%` }} /><span>{d.count}</span></div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <div className="card">
            <div className="titlebar" style={{ margin: 0 }}>
              <h2 style={{ margin: 0 }}>Improve the SOP</h2>
              <button className="primary" onClick={suggest} disabled={busy || !k.corrections}>
                {busy ? 'Muse Spark is analysing…' : 'Suggest SOP changes'}
              </button>
            </div>
            {!k.corrections && <p className="muted small">Suggestions appear once workers have been corrected.</p>}
            {sugg && sugg.length === 0 && <p className="muted">No changes suggested.</p>}
            {sugg && sugg.length > 0 && (
              <ol className="sugg">
                {sugg.map((x, i) => (
                  <li key={i}>
                    <strong>Step {x.step_idx}: {x.title}</strong>
                    <p>{x.change}</p>
                    <p className="small muted">Why: {x.why}</p>
                  </li>
                ))}
              </ol>
            )}
            {error && <p className="error">{error}</p>}
          </div>

          <h2>Recent corrections</h2>
          {rep.recent_flags.length === 0 ? <p className="muted">None.</p> : (
            <div className="flags">
              {rep.recent_flags.map((f) => (
                <div key={f.id} className="flagcard">
                  <video src={`/media/${f.clip_path}`} controls muted playsInline preload="metadata" />
                  <div>
                    <div className="small muted">Run {f.run_id}, step {f.step_idx}, {new Date(f.created_at).toLocaleString()}</div>
                    <strong>{f.label}</strong>{f.overridden && <span className="tag">False alarm</span>}
                    <p className="small">{f.reason}</p>
                    {f.instruction && <p className="small">Worker heard: “{f.instruction}”</p>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  )
}
