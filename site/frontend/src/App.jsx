import { useState } from 'react'
import './App.css'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8080/api'

function App() {
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(false)
  const [hostname, setHostname] = useState('')
  const [deviceInfo, setDeviceInfo] = useState(null)
  const [publicKey, setPublicKey] = useState('')

  const triggerDecrypt = async () => {
    try {
      setLoading(true)
  const res = await fetch(`${API_BASE}/decrypt`, { method: 'POST' })
      const data = await res.json()
      setStatus(data.status || 'Decryption request sent')
    } catch (e) {
      setStatus(`Failed to decrypt: ${e}`)
    } finally {
      setLoading(false)
    }
  }

  const requestPublicKey = async () => {
    try {
      setLoading(true)
      setStatus('')
      const res = await fetch(`${API_BASE}/keys/rsa`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hostname: hostname || null }),
      })
      const data = await res.json()
      if (res.ok) {
        setPublicKey(data.public_key_pem || '')
        setDeviceInfo(data.device || null)
        setStatus('Public key generated and device info recorded')
      } else {
        setStatus(`Public key request failed: ${data.error || res.status}`)
      }
    } catch (e) {
      setStatus(`Public key request error: ${e}`)
    } finally {
      setLoading(false)
    }
  }

  const refreshDeviceInfo = async () => {
    try {
      setLoading(true)
      const res = await fetch(`${API_BASE}/keys/last-request`)
      const data = await res.json()
      setDeviceInfo(Object.keys(data || {}).length ? data : null)
      setStatus('Device info refreshed')
    } catch (e) {
      setStatus(`Failed to load device info: ${e}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="container">
      <h1>Ransomware Simulator</h1>
      <div className="panel">
        <div className="actions">
          <button onClick={triggerDecrypt} disabled={loading}>Decrypt Files</button>
        </div>
        {status && <p className="status">{status}</p>}
      </div>

      <div className="panel" style={{ marginTop: '1rem' }}>
        <h2>Device Info + Public Key (Demo)</h2>
        <div className="field">
          <label>Device Hostname (optional)</label>
          <input
            type="text"
            placeholder="Enter VM hostname"
            value={hostname}
            onChange={(e) => setHostname(e.target.value)}
          />
        </div>
        <div className="actions">
          <button onClick={requestPublicKey} disabled={loading}>Get Public Key</button>
          <button onClick={refreshDeviceInfo} disabled={loading}>Refresh Device Info</button>
        </div>
        {publicKey && (
          <div className="field">
            <label>Public Key (PEM)</label>
            <pre className="key-box" style={{ maxHeight: 200, overflow: 'auto' }}>{publicKey}</pre>
          </div>
        )}
        {deviceInfo && (
          <div className="field">
            <label>Last Request</label>
            <pre className="key-box">{JSON.stringify(deviceInfo, null, 2)}</pre>
          </div>
        )}
      </div>
    </div>
  )
}

export default App
