import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'

/* ------------------------------------------------------------------
   Real data only (evidence rules): timings and verdicts from this project's own eval runs.
   ------------------------------------------------------------------ */

// Check-time model: medians measured in this project's runs (seconds).
const STAGES = [
  { key: 'normalize', name: 'Prepare clip', s: 1.8 },
  { key: 'observe', name: 'Muse Spark observes', s: 8.1 },
  { key: 'judge', name: 'Muse Spark judges', s: 10.1 },
]
const TOTAL_S = STAGES.reduce((a, b) => a + b.s, 0)

// Evaluation run 5 (eval/results.csv): 12 judgements on 8 recorded clips, SOP of 4 steps.
const CASES = [
  ['Enclosure out of the sleeve', 1, 'pass', 'pass', 17.7],
  ['Enclosure out of the sleeve', 3, 'flag', 'flag', 18.5],
  ['Top cap off, USB-C end open', 2, 'pass', 'pass', 19.9],
  ['Top cap off, USB-C end open', 4, 'flag', 'flag', 16.4],
  ['Bottom cap off', 3, 'pass', 'pass', 20.8],
  ['Bottom cap off', 2, 'flag', 'flag', 21.8],
  ['PCB slid out of the housing', 4, 'pass', 'pass', 13.4],
  ['PCB slid out of the housing', 1, 'flag', 'flag', 16.9],
  ['Top screw loosened, cap still on', 2, 'flag', 'flag', 14.9],
  ['Bottom screw worked, cap still on', 3, 'flag', 'flag', 22.4],
  ['Screwdriver twisted, cap never off', 2, 'flag', 'flag', 15.6],
  ['Bottom cap removed, hands block the view', 3, 'flag', 'flag', 21.5],
]
const RUNS = [
  ['1', 'Baseline', '86%', '1'],
  ['2', 'Strict look-alike rule', '71%', '0'],
  ['3–4', 'Exact wording, step history', '86%', '0'],
  ['5', 'Every step ends in a visible state', '100%', '0'],
]
const REPO = 'https://github.com/Harshxox/shopfloor-copilot'

const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x))
const reduced = () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

function useReveal() {
  useEffect(() => {
    if (reduced()) return undefined
    document.documentElement.classList.add('motion')
    const blocks = Array.from(document.querySelectorAll('.rv-block'))
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (!e.isIntersecting) return
        const sibs = Array.from(e.target.parentElement?.querySelectorAll(':scope > .rv-block') || [])
        e.target.style.transitionDelay = `${Math.max(0, sibs.indexOf(e.target)) * 0.07}s`
        e.target.classList.add('in')
        io.unobserve(e.target)
      })
    }, { rootMargin: '0px 0px -8% 0px' })
    blocks.forEach((b) => io.observe(b))
    return () => { io.disconnect(); document.documentElement.classList.remove('motion') }
  }, [])
}

/* ---------------- hero: products travel a conveyor through the split wordmark ---------------- */
// Illustrations of products an expert could teach a procedure for. Only the enclosure was tested.
const PRODUCTS = [
  { src: 'ssd', name: 'M.2 SSD enclosure', w: 720, h: 296, size: 0.62, tested: true },
  { src: 'valve', name: 'Gate valve', w: 720, h: 622, size: 1.0 },
  { src: 'pcb', name: 'Controller board', w: 720, h: 359, size: 0.78 },
  { src: 'motor', name: 'Induction motor', w: 720, h: 459, size: 0.9 },
  { src: 'drill', name: 'Cordless drill', w: 720, h: 616, size: 1.0 },
  { src: 'gear', name: 'Spur gear', w: 720, h: 349, size: 0.7 },
  { src: 'battery', name: 'Battery pack', w: 720, h: 303, size: 0.72 },
]

function Belt() {
  const track = useRef(null)
  const gate = useRef(null)
  const [current, setCurrent] = useState(PRODUCTS[0].name)
  useEffect(() => {
    let raf = 0
    let last = ''
    const tick = () => {
      raf = requestAnimationFrame(tick)
      const g = gate.current?.getBoundingClientRect()
      if (!g || !track.current) return
      const gx = g.left + g.width / 2
      let hit = null
      let best = Infinity
      const items = track.current.querySelectorAll('.item')
      items.forEach((el) => {
        const r = el.querySelector('img').getBoundingClientRect()
        const d = Math.abs(r.left + r.width / 2 - gx)
        if (d < r.width * 0.42 && d < best) { best = d; hit = el }
      })
      items.forEach((el) => el.classList.toggle('at-gate', el === hit))
      hit = hit?.dataset.name
      if (hit && hit !== last) { last = hit; setCurrent(hit) }
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [])
  const set = (k) => PRODUCTS.map((p, i) => (
    <figure className="item" key={`${k}-${p.src}`} data-name={p.name} style={{ '--s': p.size, '--ar': p.w / p.h }}>
      <img src={`/landing/${p.src}.webp`} alt={k === 'a' ? `Illustration of a ${p.name.toLowerCase()}` : ''}
           aria-hidden={k === 'a' ? undefined : true} width={p.w} height={p.h} loading="eager" decoding="async" />
      <figcaption>
        <span className="fig">Fig. {i + 1}</span> {p.name}{p.tested && <span className="tested"> · tested</span>}
      </figcaption>
    </figure>
  ))
  return (
    <div className="belt">
      <div className="track" ref={track}>{set('a')}{set('b')}</div>
      <div className="gate" ref={gate} aria-hidden="true">
        <span className="gate-label">Check <b>{current}</b></span>
      </div>
      <div className="rail" aria-hidden="true" />
    </div>
  )
}

/* fine-line drafting sheet behind the hero: a part drawn the way a procedure is written, view by view */
function Blueprint() {
  const bolts = Array.from({ length: 8 }, (_, i) => {
    const a = (i / 8) * Math.PI * 2 + Math.PI / 8
    return [200 + 118 * Math.cos(a), 200 + 118 * Math.sin(a)]
  })
  return (
    <svg className="blueprint" viewBox="0 0 640 470" aria-hidden="true">
      <g className="draw" fill="none" stroke="var(--ink)" strokeWidth="1">
        {/* front view: flange */}
        <circle cx="200" cy="200" r="160" pathLength="1" />
        <circle cx="200" cy="200" r="62" pathLength="1" />
        <circle cx="200" cy="200" r="40" pathLength="1" strokeWidth=".7" />
        {bolts.map(([x, y], i) => <circle key={i} cx={x} cy={y} r="13" pathLength="1" strokeWidth=".8" />)}
        {/* side section */}
        <path d="M430 40 H470 V150 H500 V250 H470 V360 H430 Z" pathLength="1" />
        <path d="M430 160 H500 M430 240 H500" pathLength="1" strokeWidth=".7" />
      </g>
      <g stroke="var(--ink)" strokeWidth=".5" fill="none" opacity=".55">
        <circle cx="200" cy="200" r="118" strokeDasharray="10 3 2 3" />
        <line x1="20" y1="200" x2="380" y2="200" strokeDasharray="10 3 2 3" />
        <line x1="200" y1="20" x2="200" y2="380" strokeDasharray="10 3 2 3" />
        <line x1="410" y1="200" x2="520" y2="200" strokeDasharray="10 3 2 3" />
        {/* hatching in the section */}
        {Array.from({ length: 14 }, (_, i) => <line key={i} x1="430" y1={60 + i * 22} x2="470" y2={30 + i * 22} />)}
        {/* dimensions */}
        <line x1="40" y1="400" x2="360" y2="400" /><line x1="40" y1="390" x2="40" y2="410" /><line x1="360" y1="390" x2="360" y2="410" />
        <line x1="545" y1="40" x2="545" y2="360" /><line x1="535" y1="40" x2="555" y2="40" /><line x1="535" y1="360" x2="555" y2="360" />
        <line x1="290" y1="90" x2="330" y2="40" /><line x1="330" y1="40" x2="400" y2="40" />
        <line x1={bolts[5][0]} y1={bolts[5][1]} x2="40" y2="20" stroke="var(--pigment)" opacity="1" /><line x1="40" y1="20" x2="-150" y2="20" stroke="var(--pigment)" opacity="1" />
      </g>
      <g fontFamily="var(--mono)" fontSize="9" letterSpacing="1.4" fill="var(--ink-2)">
        <text x="200" y="420" textAnchor="middle">Ø 320</text>
        <text x="562" y="204">320</text>
        <text x="334" y="34">8 × Ø 26 ON PCD 236</text>
        <text x="40" y="452">VIEW A</text><text x="430" y="452">SECTION B–B</text>
      </g>
      <g fill="var(--pigment)">
        <circle cx={bolts[5][0]} cy={bolts[5][1]} r="3" />
        <text x="-150" y="14" fontFamily="var(--mono)" fontSize="9" letterSpacing="1.4">STEP 3 · TORQUE IN STAR ORDER</text>
      </g>
    </svg>
  )
}

function Hero() {
  const ref = useRef(null)
  const upper = useRef(null)
  const lower = useRef(null)
  const belt = useRef(null)

  useEffect(() => {
    const els = [upper.current, lower.current, belt.current].filter(Boolean)
    // already on screen at load: reveal on the next frame, never via an observer
    els.forEach((el) => { el.style.opacity = '0' })
    const r0 = requestAnimationFrame(() => {
      els.forEach((el) => { el.style.transition = 'opacity .9s ease'; el.style.opacity = '1' })
    })
    if (reduced()) return () => cancelAnimationFrame(r0)
    let raf = 0
    const update = () => {
      raf = 0
      const h = ref.current?.offsetHeight || 1
      const p = clamp(window.scrollY / h)
      if (upper.current) upper.current.style.transform = `translate(${3 * p}vw, ${-20 * p}vh)`
      if (lower.current) lower.current.style.transform = `translate(${-3 * p}vw, ${20 * p}vh)`
      if (belt.current) belt.current.style.transform = `translateY(${-14 * p}vh)`
    }
    const onScroll = () => { if (!raf) raf = requestAnimationFrame(update) }
    update()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    return () => { cancelAnimationFrame(r0); window.removeEventListener('scroll', onScroll); window.removeEventListener('resize', onScroll) }
  }, [])

  return (
    <section className="hero" ref={ref}>
      <div className="sheet" aria-hidden="true"><span>Sheet 01</span><span>Any product, any procedure</span><span>Fig. 1 tested, Figs. 2–7 illustrative</span></div>
      <Blueprint />
      <div className="hero-copy">
        <span className="label">Meta Global AI Developer Hackathon, 2026</span>
        <h1>The expert, in every worker’s <em>ear.</em></h1>
        <p className="lede">
          Any product, any procedure. A skilled worker records the job once. ShopFloor Copilot turns it into a
          procedure, then checks every new worker on camera, step by step, and corrects them out loud in Kannada,
          Hindi or English.
        </p>
        <div className="hero-actions">
          <Link className="btn primary" to="/check">Start a check</Link>
          <Link className="btn" to="/teach">Teach a procedure</Link>
        </div>
      </div>
      <div className="wordline upper" ref={upper} aria-hidden="true">ShopFloor</div>
      <div className="beltwrap" ref={belt}><Belt /></div>
      <div className="wordline lower" ref={lower} aria-hidden="true">Copilot</div>
    </section>
  )
}

/* ---------------- flow: one expert video to a checked worker, drawn as a plate ---------------- */
function Flow() {
  const nodes = [
    { x: 20, y: 40, k: '01', t: 'Expert video', s: 'Narrated, recorded once' },
    { x: 250, y: 40, k: '02', t: 'Procedure', s: 'Muse Voice + Muse Spark' },
    { x: 250, y: 230, k: '03', t: 'Worker clip', s: 'Phone camera, per step' },
    { x: 20, y: 230, k: '04', t: 'Judge', s: 'Observe, then pass or flag' },
    { x: 135, y: 410, k: '05', t: 'Spoken correction', s: 'Kannada, Hindi, English' },
  ]
  return (
    <figure className="drawing flow">
      <svg viewBox="0 0 470 520" role="img" aria-label="Flow: expert video, procedure, worker clip, judge, spoken correction">
        <g fill="none" stroke="var(--ink)" strokeWidth=".6" opacity=".5">
          {Array.from({ length: 24 }, (_, i) => <line key={`v${i}`} x1={i * 20} y1="0" x2={i * 20} y2="520" opacity=".25" />)}
          {Array.from({ length: 27 }, (_, i) => <line key={`h${i}`} x1="0" y1={i * 20} x2="470" y2={i * 20} opacity=".25" />)}
        </g>
        <g fill="none" stroke="var(--pigment)" strokeWidth="1.2" className="flowline">
          <path d="M220 85 H250" /><path d="M335 130 V230" /><path d="M250 275 H220" /><path d="M120 320 V365 H235 V410" />
          <path d="M120 230 V185 H300 V230" strokeDasharray="3 4" />
        </g>
        {nodes.map((n) => (
          <g key={n.k} transform={`translate(${n.x} ${n.y})`}>
            <rect width="200" height="90" fill="var(--ground)" stroke="var(--ink)" strokeWidth="1" />
            <text x="12" y="22" fontFamily="var(--mono)" fontSize="9" letterSpacing="1.6" fill="var(--pigment)">{n.k}</text>
            <text x="12" y="54" fontFamily="var(--serif)" fontSize="24" fill="var(--ink)">{n.t}</text>
            <text x="12" y="76" fontFamily="var(--mono)" fontSize="8.5" letterSpacing=".8" fill="var(--muted)">{n.s.toUpperCase()}</text>
          </g>
        ))}
        <text x="130" y="178" fontFamily="var(--mono)" fontSize="8.5" letterSpacing="1.2" fill="var(--pigment)">PASS · NEXT STEP</text>
        <text x="128" y="358" fontFamily="var(--mono)" fontSize="8.5" letterSpacing="1.2" fill="var(--pigment)">FLAG</text>
      </svg>
      <figcaption>Every step: one clip in, one verdict out. A pass advances, a flag repeats the step.</figcaption>
    </figure>
  )
}

function Procedure() {
  const [steps, setSteps] = useState([])
  useEffect(() => {
    api('/sops').then((all) => {
      const ready = all.filter((s) => s.status === 'ready')
      if (ready[0]) api(`/sops/${ready[0].id}`).then((r) => setSteps(r.steps))
    }).catch(() => {})
  }, [])
  return (
    <section>
      <div className="split">
        <div>
          <span className="label rv-block">The procedure</span>
          <h2 className="rv-block">Every step ends in something the <em>camera can see.</em></h2>
          <p className="lede rv-block">
            Muse Spark writes the steps from one narrated video of the expert. These are the ones it wrote for the tested enclosure. A loosened screw looks exactly like an
            untouched one, so the procedure only checks results that are visible: a cap off, an end open, a board out.
          </p>
          <dl className="dl rv-block">
            {steps.map((s) => (
              <div key={s.id}>
                <dt>Step {s.idx}</dt>
                <dd>{s.action}</dd>
                <span className="val">{s.critical ? 'Critical' : 'Standard'}</span>
              </div>
            ))}
          </dl>
        </div>
        <div className="rv-block"><Flow /></div>
      </div>
    </section>
  )
}

/* ---------------- pinned study: one check, computed from the timing model ---------------- */
function Study() {
  const ref = useRef(null)
  const [p, setP] = useState(0)
  useEffect(() => {
    let raf = 0
    const update = () => {
      raf = 0
      const el = ref.current
      if (!el) return
      const r = el.getBoundingClientRect()
      const span = el.offsetHeight - window.innerHeight
      setP(clamp(-r.top / (span || 1)))
    }
    const onScroll = () => { if (!raf) raf = requestAnimationFrame(update) }
    update()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    return () => { window.removeEventListener('scroll', onScroll); window.removeEventListener('resize', onScroll) }
  }, [])

  // model: t = p · T; stage = first stage whose cumulative end exceeds t; angle = 270° · t / T
  const t = p * TOTAL_S
  let acc = 0
  const bounds = STAGES.map((s) => { const b = { ...s, from: acc, to: acc + s.s }; acc += s.s; return b })
  const stage = bounds.find((b) => t < b.to) || bounds[bounds.length - 1]
  const SWEEP = 270
  const angle = SWEEP * (t / TOTAL_S)
  // arc geometry in percentages of the container (viewBox 100 x 60, preserveAspectRatio meet)
  const cx = 50; const cy = 33; const R = 24
  const pt = (deg) => {
    const a = ((135 + deg) * Math.PI) / 180
    return [cx + R * Math.cos(a), cy + R * Math.sin(a)]
  }
  const arc = (d0, d1) => {
    const [x0, y0] = pt(d0); const [x1, y1] = pt(d1)
    return `M ${x0} ${y0} A ${R} ${R} 0 ${d1 - d0 > 180 ? 1 : 0} 1 ${x1} ${y1}`
  }
  const [mx, my] = pt(angle)

  return (
    <section className="study" ref={ref}>
      <div className="study-stage">
        <div>
          <span className="label">One check, timed</span>
          <h2>Twenty seconds from <em>“done”</em> to the next instruction.</h2>
        </div>
        <div className="study-canvas">
          <svg viewBox="0 0 100 60" preserveAspectRatio="xMidYMid meet" aria-label="Arc of one check, stage by stage">
            <path d={arc(0, SWEEP)} fill="none" stroke="rgba(26,25,23,.16)" strokeWidth="0.25" />
            <path d={arc(0, Math.max(0.01, angle))} fill="none" stroke="var(--ink)" strokeWidth="0.5" />
            {bounds.map((b) => {
              const [x, y] = pt(SWEEP * (b.from / TOTAL_S))
              const [lx, ly] = pt(SWEEP * ((b.from + b.s / 2) / TOTAL_S))
              const out = 1.22
              return (
                <g key={b.key}>
                  <circle cx={x} cy={y} r="0.45" fill="var(--ink)" />
                  <text x={cx + (lx - cx) * out} y={cy + (ly - cy) * out} fontSize="1.7" fontFamily="var(--mono)"
                        textAnchor={lx < cx - 2 ? 'end' : lx > cx + 2 ? 'start' : 'middle'}
                        fill={b.key === stage.key ? 'var(--pigment)' : 'var(--muted)'} letterSpacing=".2">
                    {b.name.toUpperCase()}, {b.s.toFixed(1)} S
                  </text>
                </g>
              )
            })}
            <circle cx={mx} cy={my} r="1.1" fill="var(--pigment)" />
            <text x={cx} y={cy + 1.5} textAnchor="middle" fontSize="6" fontFamily="var(--serif)" fill="var(--ink)">{t.toFixed(1)}s</text>
          </svg>
        </div>
        <div>
          <div className="readouts">
            <div><span className="rv">{t.toFixed(1)}</span><span className="label">Seconds elapsed</span></div>
            <div><span className="rv">{Math.round(100 * t / TOTAL_S)}%</span><span className="label">Of a median check</span></div>
            <div><span className="rv">{angle.toFixed(0)}°</span><span className="label">Of a {SWEEP}° arc</span></div>
            <div><span className="rv" style={{ fontSize: 'clamp(20px,2vw,28px)' }}>{stage.name}</span><span className="label">Current stage</span></div>
          </div>
          <p className="study-model">
            Model: one check = prepare clip {STAGES[0].s}s + observe {STAGES[1].s}s + judge {STAGES[2].s}s = {TOTAL_S.toFixed(1)}s,
            the medians measured in this project’s runs. Scroll position sets the elapsed time; the arc angle, the stage and the
            percentage are all computed from it.
          </p>
        </div>
      </div>
    </section>
  )
}

/* ---------------- material and practice ---------------- */
function Practice() {
  const rows = [
    ['Muse Spark 1.2', 'Watches the expert once and writes the procedure, every step ending in a visible state.', 'Video to procedure'],
    ['Muse Spark 1.2', 'Describes each worker clip without being told what to expect, then judges it and calls pass or flag.', 'Agent with tool calls'],
    ['SAM 3.1', 'Marks the part on each step’s reference frame and tracks the worker’s hands as evidence.', 'Segmentation, tracking'],
    ['Muse Voice Transcribe', 'Turns the expert’s narration into timed turns that line up with the video.', 'Speech to text'],
  ]
  return (
    <section>
      <div style={{ maxWidth: 1320, margin: '0 auto' }}>
        <span className="label rv-block">Material and practice</span>
        <h2 className="rv-block" style={{ fontSize: 'clamp(30px,3.4vw,48px)', maxWidth: '20ch' }}>Three Meta models, <em>four jobs.</em></h2>
      </div>
      <div className="rows">
        {rows.map(([k, d, c], i) => (
          <div key={i} className="rv-block"><span className="k">{k}</span><span className="d">{d}</span><span className="c">{c}</span></div>
        ))}
      </div>
      <div className="pair">
        <div className="rv-block">
          <h3 style={{ fontSize: 26, marginBottom: 12 }}>Judge the result, never the motion.</h3>
          <p>
            Told “the expected step is X”, the first agent invented evidence for X. Now Muse Spark first describes the clip blind,
            then a strict judge compares that description and the clip with the procedure, the steps already done and the step’s
            visible end state. Narration is never proof.
          </p>
        </div>
        <div className="rv-block">
          <table className="minitable">
            <thead><tr><th>Run</th><th>Change</th><th>Accuracy</th><th>Missed</th></tr></thead>
            <tbody>
              {RUNS.map((r, i) => (
                <tr key={r[0]} className={i === RUNS.length - 1 ? 'final' : ''}>
                  <td>{r[0]}</td><td>{r[1]}</td><td className="num">{r[2]}</td><td>{r[3]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}

/* ---------------- work table: every judgement in evaluation run 5 ---------------- */
function Work() {
  const passCount = useMemo(() => CASES.filter((c) => c[2] === c[3]).length, [])
  return (
    <section>
      <div style={{ maxWidth: 1320, margin: '0 auto' }}>
        <span className="label rv-block">The evidence</span>
        <h2 className="rv-block" style={{ fontSize: 'clamp(30px,3.4vw,48px)' }}>{passCount} of {CASES.length} judgements correct, <em>none missed.</em></h2>
      </div>
      <table className="worktable">
        <thead><tr><th>Recorded clip</th><th>Checked as step</th><th>Should</th><th>Verdict</th><th>Correct</th><th>Time</th></tr></thead>
        <tbody>
          {CASES.map(([name, step, want, got, s], i) => (
            <tr key={i}>
              <td className="name">{name}</td>
              <td>Step {step}</td>
              <td>{want === 'pass' ? 'Pass' : 'Flag'}</td>
              <td className={got === 'pass' ? 'ok' : 'flagged'}>{got === 'pass' ? 'Passed' : 'Flagged'}</td>
              <td className="ok">{want === got ? 'Yes' : 'No'}</td>
              <td>{s.toFixed(1)} s</td>
            </tr>
          ))}
        </tbody>
        <caption>Source: eval/results.csv, evaluation run 5, Muse Spark 1.2. 8 clips of one enclosure, one camera position, one person.</caption>
      </table>
    </section>
  )
}

function Close() {
  return (
    <section className="close">
      <div className="close-row">
        <div className="rv-block">
          <h2>Teach it once. <em>Check it every time.</em></h2>
          <p className="fine">Built during the Meta Global AI Developer Hackathon on Muse Spark, SAM 3.1 and Muse Voice Transcribe. Open source, MIT licence.</p>
        </div>
        <div className="hero-actions rv-block">
          <Link className="btn primary" to="/check">Start a check</Link>
          <a className="btn" href={REPO} target="_blank" rel="noreferrer">Read the code</a>
        </div>
      </div>
      <div className="foot">
        <span>ShopFloor Copilot</span>
        <Link to="/teach">Teach</Link>
        <Link to="/check">Check</Link>
        <Link to="/report">Report</Link>
        <a href={REPO} target="_blank" rel="noreferrer">GitHub</a>
      </div>
      <div className="bigword" aria-hidden="true">ShopFloor Copilot<span className="stop">.</span></div>
    </section>
  )
}

export default function Home() {
  useReveal()
  return (
    <div className="home">
      <Hero />
      <Procedure />
      <Study />
      <Practice />
      <Work />
      <Close />
    </div>
  )
}
