import { useEffect, useState } from 'react'
import Lab from './Lab'
import C2Browser from './C2Browser'

const DEFAULT_BACKEND = (import.meta.env.VITE_API_BASE || 'http://localhost:8080/api').replace(/\/$/, '')

export default function PySimplePage() {
  const [host, setHost] = useState(DEFAULT_BACKEND)
  const [who, setWho] = useState(null)
  const apiBase = `${host}/py_simple`

  useEffect(() => {
    const fetchWho = async () => {
      try {
        const res = await fetch(`${apiBase}/whoami`)
        const data = await res.json()
        setWho(data)
      } catch (_) {/* ignore */}
    }
    fetchWho()
  }, [apiBase])

  return (
    <main className="container">
      <section className="card">
        <h2>Backend Host</h2>
        <div className="field">
          <label>API Base</label>
          <input className="input" value={host} onChange={(e) => setHost(e.target.value.replace(/\/$/, ''))} placeholder="https://your-backend" />
        </div>
        {who && (
          <div className="kv" style={{marginTop: '.5rem'}}>
            <div><span className="k">Your IP</span><span className="v">{who.ip || '—'}</span></div>
            <div><span className="k">Forwarded-For</span><span className="v">{who.forwarded_for || '—'}</span></div>
            <div><span className="k">Server</span><span className="v">{who.server || '—'}</span></div>
          </div>
        )}
      </section>
      <Lab apiBase={apiBase} />
      <C2Browser apiBase={apiBase} />
    </main>
  )
}
