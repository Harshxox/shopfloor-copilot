import { useEffect, useState } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { api } from './api.js'
import Teach from './pages/Teach.jsx'
import Check from './pages/Check.jsx'
import Report from './pages/Report.jsx'

function HealthBadge() {
  const [health, setHealth] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api('/health').then(setHealth).catch((e) => setError(e.message))
  }, [])

  if (error) return <span className="badge bad">Backend offline</span>
  if (!health) return <span className="badge">Checking…</span>
  const ok = health.meta_key_set && health.ffmpeg
  return (
    <span className={`badge ${ok ? 'good' : 'warn'}`} title={JSON.stringify(health.models)}>
      {ok ? 'Backend ready' : `Backend up — ${!health.meta_key_set ? 'API key missing' : 'ffmpeg missing'}`}
    </span>
  )
}

export default function App() {
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">ShopFloor Copilot</div>
        <nav>
          <NavLink to="/teach">Teach</NavLink>
          <NavLink to="/check">Check</NavLink>
          <NavLink to="/report">Report</NavLink>
        </nav>
        <HealthBadge />
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/teach" replace />} />
          <Route path="/teach" element={<Teach />} />
          <Route path="/check" element={<Check />} />
          <Route path="/report" element={<Report />} />
        </Routes>
      </main>
    </div>
  )
}
