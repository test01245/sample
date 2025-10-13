import { useEffect, useState } from 'react'
import './App.css'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000'

function App() {
  const [key, setKey] = useState('')
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(false)

  const fetchKey = async () => {
    try {
      setLoading(true)
      const res = await fetch(`${API_BASE}/key`)
      const data = await res.json()
      setKey(data.key || '')
      setStatus('Encryption key fetched')
    } catch (e) {
      setStatus(`Failed to fetch key: ${e}`)
    } finally {
      setLoading(false)
    }
  }

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

  useEffect(() => {
    fetchKey()
  }, [])

  return (
    <div className="container">
      <h1>Ransomware Simulator Control</h1>
      <div className="panel">
        <div>
          <strong>Encryption Key:</strong>
          <pre className="key-box">{key || '(not available)'}</pre>
        </div>
        <div className="actions">
          <button onClick={fetchKey} disabled={loading}>Refresh Key</button>
          <button onClick={triggerDecrypt} disabled={loading}>Decrypt Files</button>
        </div>
        {status && <p className="status">{status}</p>}
      </div>
    </div>
  )
}

export default App
