// Speak instructions to the worker with the browser's built-in voices.
const LOCALES = { kn: ['kn-IN', 'kn'], hi: ['hi-IN', 'hi'], en: ['en-IN', 'en-GB', 'en-US', 'en'] }

let voicesCache = []
function loadVoices() {
  voicesCache = window.speechSynthesis?.getVoices() || []
  return voicesCache
}
if (typeof window !== 'undefined' && window.speechSynthesis) {
  loadVoices()
  window.speechSynthesis.onvoiceschanged = loadVoices
}

export function voiceFor(lang) {
  const voices = voicesCache.length ? voicesCache : loadVoices()
  for (const loc of LOCALES[lang] || LOCALES.en) {
    const v = voices.find((x) => x.lang?.toLowerCase().startsWith(loc.toLowerCase()))
    if (v) return v
  }
  return null
}

export function hasVoice(lang) {
  return !!voiceFor(lang)
}

// ---------- hands-free "done" by voice (Chrome / Android Chrome) ----------
// Indian-English recognition is the most reliable everywhere and writes Hindi/Kannada words in Latin
// letters ("ho gaya", "mugitu"), so we always listen in en-IN and match Latin + native spellings.
const DONE_WORDS = [
  'done', 'dun', 'next', 'finished', 'finish', 'complete',
  'ho gaya', 'ho gya', 'hogaya', 'ho gayi', 'हो गया', 'हो गई', 'डन',
  'mugitu', 'mugithu', 'mugidide', 'aaytu', 'aytu', 'ಮುಗಿತು', 'ಮುಗಿದಿದೆ', 'ಆಯ್ತು', 'ಡನ್',
]
const FATAL = { 'not-allowed': 'Microphone blocked — allow it in the address bar',
  'service-not-allowed': 'Speech service blocked in this browser — try Chrome',
  'language-not-supported': 'Language not supported', network: 'Speech service unreachable (network) — try Chrome' }

export function voiceDoneSupported() {
  return typeof window !== 'undefined' && !!(window.SpeechRecognition || window.webkitSpeechRecognition)
}

// Listens continuously; calls onDone() on a done-word. onStatus({state, heard, error}) drives the UI.
export function listenForDone(onDone, onStatus = () => {}) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SR) { onStatus({ state: 'error', error: 'Voice input not supported in this browser' }); return () => {} }
  let stopped = false
  let rec
  const startOne = () => {
    if (stopped) return
    rec = new SR()
    rec.lang = 'en-IN'
    rec.continuous = true
    rec.interimResults = true
    rec.onstart = () => onStatus({ state: 'listening' })
    rec.onresult = (e) => {
      const said = Array.from(e.results).slice(e.resultIndex).map((r) => r[0].transcript).join(' ').trim()
      const low = said.toLowerCase()
      onStatus({ state: 'listening', heard: said })
      if (DONE_WORDS.some((w) => low.includes(w))) {
        stopped = true
        rec.abort()
        onStatus({ state: 'triggered', heard: said })
        onDone()
        setTimeout(() => { stopped = false; startOne() }, 1500) // listen again for the next step
      }
    }
    rec.onerror = (e) => {
      if (FATAL[e.error]) {
        stopped = true
        onStatus({ state: 'error', error: FATAL[e.error] })
      }
    }
    rec.onend = () => { if (!stopped) setTimeout(startOne, 300) } // browsers stop after silence; restart
    try { rec.start() } catch { /* already started */ }
  }
  startOne()
  return () => { stopped = true; try { rec?.abort() } catch { /* ignore */ } }
}

export function speak(text, lang) {
  if (!text || !window.speechSynthesis) return
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(text)
  const v = voiceFor(lang)
  if (v) u.voice = v
  u.lang = v?.lang || (LOCALES[lang] || LOCALES.en)[0]
  u.rate = 0.95
  window.speechSynthesis.speak(u)
}
