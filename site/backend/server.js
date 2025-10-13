import express from 'express'
import cors from 'cors'
import fetch from 'node-fetch'

const PORT = process.env.PORT || 8080
const PY_SERVER = process.env.PY_SERVER || 'http://localhost:5000'

const app = express()
app.use(cors())
app.use(express.json())

// Health
app.get('/api/health', (req, res) => res.json({ ok: true }))

// Proxy decrypt to Python backend
app.post('/api/decrypt', async (req, res) => {
  try {
    const r = await fetch(`${PY_SERVER}/decrypt`, { method: 'POST' })
    const data = await r.json()
    res.status(r.status).json(data)
  } catch (e) {
    res.status(500).json({ error: 'proxy_failed', message: String(e) })
  }
})

// (Optional) proxy encrypt if needed later
app.post('/api/encrypt', async (req, res) => {
  try {
    const r = await fetch(`${PY_SERVER}/encrypt`, { method: 'POST' })
    const data = await r.json()
    res.status(r.status).json(data)
  } catch (e) {
    res.status(500).json({ error: 'proxy_failed', message: String(e) })
  }
})

app.listen(PORT, () => console.log(`Backend listening on :${PORT}`))
