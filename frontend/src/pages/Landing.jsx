import { Link } from 'react-router-dom'

const workflow = [
  {
    number: '01',
    title: 'Capture the craft',
    description: 'An expert records the job once. Their narration becomes a clear, visual step-by-step SOP.',
    icon: '↗',
  },
  {
    number: '02',
    title: 'Guide every step',
    description: 'Workers follow along on a phone and get a helpful correction when a step needs another look.',
    icon: '◎',
  },
  {
    number: '03',
    title: 'Learn from the line',
    description: 'Supervisors see where work gets stuck and get practical suggestions to improve the procedure.',
    icon: '↗',
  },
]

function ArrowIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" fill="none">
      <path d="M4.25 10h11.5m-5-5 5 5-5 5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function ProductPreview() {
  return (
    <div className="landing-preview" aria-label="Illustration of a worker completing a guided assembly step">
      <div className="preview-topline">
        <span className="preview-live"><i /> LIVE CHECK</span>
        <span className="preview-menu" aria-hidden="true">•••</span>
      </div>
      <div className="preview-scene">
        <div className="scene-orbit scene-orbit-one" />
        <div className="scene-orbit scene-orbit-two" />
        <div className="scene-spark" aria-hidden="true">✳</div>
        <div className="scene-workpiece" aria-hidden="true">
          <span className="workpiece-cap" />
          <span className="workpiece-body" />
          <span className="workpiece-base" />
          <span className="workpiece-screw screw-one" />
          <span className="workpiece-screw screw-two" />
        </div>
        <div className="scene-scan" />
        <span className="scene-label">ASSEMBLY · STATION 04</span>
      </div>
      <div className="preview-task">
        <div className="task-step"><span>STEP 03</span><span>3 OF 6</span></div>
        <strong>Secure the top cap</strong>
        <p>Align the marked edge, then tighten both screws.</p>
        <div className="task-progress"><span /></div>
        <div className="task-status"><span className="task-check">✓</span> End state verified <span className="task-time">just now</span></div>
      </div>
      <div className="preview-float">
        <span className="float-icon">✦</span>
        <span><strong>Nice work.</strong><small>On to the next step</small></span>
      </div>
    </div>
  )
}

export default function Landing() {
  return (
    <div className="landing-page">
      <header className="landing-header">
        <Link className="landing-brand" to="/" aria-label="ShopFloor Copilot home">
          <span className="landing-brand-mark" aria-hidden="true"><i /><i /></span>
          <span>shopfloor<span className="brand-light"> copilot</span></span>
        </Link>
        <nav className="landing-nav" aria-label="Main navigation">
          <a href="#workflow">How it works</a>
          <a href="#built-for-the-floor">Built for the floor</a>
        </nav>
        <Link className="landing-nav-cta" to="/teach">Open workspace <ArrowIcon /></Link>
      </header>

      <main className="landing-main">
        <section className="landing-hero">
          <div className="hero-copy">
            <div className="hero-eyebrow"><span /> KNOW-HOW, KEPT IN MOTION</div>
            <h1>Great work<br />shouldn’t be a<br /><em>trade secret.</em></h1>
            <p className="hero-description">
              Turn an expert’s hands-on know-how into clear guidance every worker can follow—one step at a time.
            </p>
            <div className="hero-actions">
              <Link className="hero-primary" to="/teach">Bring a process to life <ArrowIcon /></Link>
              <a className="hero-secondary" href="#workflow"><span className="play-icon">↓</span> See how it works</a>
            </div>
            <div className="hero-note"><span className="note-avatars" aria-hidden="true"><i>工</i><i>✓</i></span> Built for the people who make things work.</div>
          </div>
          <ProductPreview />
          <div className="hero-index" aria-hidden="true"><span>01</span><i /> THE HUMAN SIDE OF INDUSTRY</div>
        </section>

        <section className="landing-workflow" id="workflow">
          <div className="section-heading">
            <div>
              <span className="section-kicker">FROM EXPERT TO EVERYONE</span>
              <h2>Make experience<br />easy to pass on.</h2>
            </div>
            <p>Good work is learned by doing. ShopFloor Copilot helps teams capture the right way, coach in the moment, and keep getting better.</p>
          </div>
          <div className="workflow-grid">
            {workflow.map((item) => (
              <article className="workflow-card" key={item.number}>
                <div className="workflow-card-top"><span>{item.number}</span><span className="workflow-icon" aria-hidden="true">{item.icon}</span></div>
                <h3>{item.title}</h3>
                <p>{item.description}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="landing-bottom" id="built-for-the-floor">
          <div className="bottom-mark" aria-hidden="true">✳</div>
          <div>
            <span className="section-kicker">LESS GUESSWORK. MORE GOOD WORK.</span>
            <h2>Every step, a little more certain.</h2>
          </div>
          <Link className="bottom-link" to="/teach">Explore the workspace <ArrowIcon /></Link>
        </section>
      </main>

      <footer className="landing-footer">
        <Link className="footer-brand" to="/">shopfloor copilot</Link>
        <span>Made for the people who make things.</span>
        <span className="footer-status"><i /> READY WHEN YOU ARE</span>
      </footer>
    </div>
  )
}
