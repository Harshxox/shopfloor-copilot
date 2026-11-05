import { useEffect, useState } from 'react'
import { Link, NavLink, Route, Routes } from 'react-router-dom'
import { api } from './api.js'
import Teach from './pages/Teach.jsx'
import SopDetail from './pages/SopDetail.jsx'
import Check from './pages/Check.jsx'
import Report from './pages/Report.jsx'
import Home from './pages/Home.jsx'

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
        <Link to="/" className="brand">ShopFloor Copilot<span className="stop">.</span></Link>
        <nav>
          <NavLink to="/teach">Teach</NavLink>
          <NavLink to="/check">Check</NavLink>
          <NavLink to="/report">Report</NavLink>
        </nav>
        <HealthBadge />
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/teach" element={<Teach />} />
          <Route path="/teach/:id" element={<SopDetail />} />
          <Route path="/check" element={<Check />} />
          <Route path="/report" element={<Report />} />
        </Routes>
      </main>
    </div>
  )
}
