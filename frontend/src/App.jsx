import { useEffect, useState } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { api } from './api.js'
import Teach from './pages/Teach.jsx'
import SopDetail from './pages/SopDetail.jsx'
import Check from './pages/Check.jsx'
import Report from './pages/Report.jsx'

function HealthBadge() {
  const [health, setHealth] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api('/health').then(setHealth).catch((e) => setError(e.message))
  }, [])

  if (error) return <span className="badge bad">Server offline</span>
  if (!health) return <span className="badge">Connecting</span>
  const ok = health.meta_key_set && health.ffmpeg
  return (
    <span className={`badge ${ok ? 'good' : 'warn'}`} title={JSON.stringify(health.models)}>
      {ok ? 'Ready' : (!health.meta_key_set ? 'API key missing' : 'ffmpeg missing')}
    </span>
  )
}

export default function App() {
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand"><span className="brand-mark" aria-hidden="true" /><span className="brand-text">ShopFloor Copilot</span></div>
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
          <Route path="/teach/:id" element={<SopDetail />} />
          <Route path="/check" element={<Check />} />
          <Route path="/report" element={<Report />} />
        </Routes>
      </main>
    </div>
  )
}
