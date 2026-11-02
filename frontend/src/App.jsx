import { useEffect, useState } from 'react'
import { Link, NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { api } from './api.js'
import Landing from './pages/Landing.jsx'
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

function Workspace() {
  return (
    <div className="app">
      <header className="topbar">
        <Link className="brand" to="/" aria-label="ShopFloor Copilot home">
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-text">shopfloor <span>copilot</span></span>
        </Link>
        <nav aria-label="Workspace">
          <NavLink to="/teach">Teach</NavLink>
          <NavLink to="/check">Check</NavLink>
          <NavLink to="/report">Report</NavLink>
        </nav>
        <HealthBadge />
      </header>
      <main>
        <Routes>
          <Route path="/teach" element={<Teach />} />
          <Route path="/teach/:id" element={<SopDetail />} />
          <Route path="/check" element={<Check />} />
          <Route path="/report" element={<Report />} />
          <Route path="*" element={<Navigate to="/teach" replace />} />
        </Routes>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/*" element={<Workspace />} />
    </Routes>
  )
}
