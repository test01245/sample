import express from 'express'
import cors from 'cors'
import fetch from 'node-fetch'
import { randomBytes, createHash, generateKeyPairSync } from 'crypto'
import fs from 'fs'
import os from 'os'
import dns from 'dns'

const PORT = process.env.PORT || 8080
const PY_SERVER = process.env.PY_SERVER || 'http://localhost:5000'

const app = express()
// Trust proxy so req.ip / X-Forwarded-For are populated correctly on Render/behind proxies
app.set('trust proxy', true)
app.use(cors())
app.use(express.json())

// Health
app.get('/api/health', (req, res) => res.json({ ok: true }))

// --- Key generation (demo endpoints) ---
// AES-256 (symmetric): public demo returns redacted key + fingerprint
app.post('/api/keys/aes', (req, res) => {
  try {
    const key = randomBytes(32) // 256-bit
    const b64 = Buffer.from(key).toString('base64')
    const fingerprint = createHash('sha256').update(key).digest('hex')
    const redacted = `${b64.slice(0, 6)}...${b64.slice(-6)}`
    return res.status(200).json({ algorithm: 'AES-256-GCM', key_redacted: redacted, fingerprint_sha256: fingerprint })
  } catch (e) {
    return res.status(500).json({ error: 'aes_keygen_failed', message: String(e) })
  }
})

// AES-256 full key (admin-only)
app.post('/api/keys/aes/private', (req, res) => {
  const admin = process.env.ADMIN_TOKEN
  const provided = req.headers['x-admin-token'] || req.query?.token
  if (!admin || provided !== admin) {
    return res.status(403).json({ error: 'forbidden', message: 'Admin token required (X-ADMIN-TOKEN)' })
  }
  try {
    const key = randomBytes(32)
    const b64 = Buffer.from(key).toString('base64')
    return res.status(200).json({ algorithm: 'AES-256-GCM', key_base64: b64 })
  } catch (e) {
    return res.status(500).json({ error: 'aes_keygen_failed', message: String(e) })
  }
})

// RSA-2048 keypair: public returns public key + fingerprints
app.post('/api/keys/rsa', (req, res) => {
  try {
    const { publicKey, privateKey } = generateKeyPairSync('rsa', {
      modulusLength: 2048,
      publicKeyEncoding: { type: 'spki', format: 'pem' },
      privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
    })

    const pubHash = createHash('sha256').update(publicKey).digest('hex')
    const prvHash = createHash('sha256').update(privateKey).digest('hex')

    // Capture device info from request
    const forwarded = req.headers['x-forwarded-for']
    const requesterIp = Array.isArray(forwarded)
      ? forwarded[0]
      : (forwarded?.split(',')[0] || req.socket.remoteAddress || '')

    const providedHostname = (req.body && req.body.hostname) || null

    const record = {
      timestamp: Date.now(),
      requester_ip: requesterIp,
      requester_hostname: providedHostname,
    }

    // Persist last request info for the site to display
    try {
      const path = './last_key_request.json'
      fs.writeFileSync(path, JSON.stringify(record, null, 2))
    } catch {}

    return res.status(200).json({
      algorithm: 'RSA-2048',
      public_key_pem: publicKey,
      public_key_fingerprint_sha256: pubHash,
      private_key_fingerprint_sha256: prvHash,
      device: record,
    })
  } catch (e) {
    return res.status(500).json({ error: 'rsa_keygen_failed', message: String(e) })
  }
})

// Retrieve last device info recorded during RSA key generation
app.get('/api/keys/last-request', (req, res) => {
  try {
    const path = './last_key_request.json'
    if (!fs.existsSync(path)) return res.status(200).json({})
    const data = JSON.parse(fs.readFileSync(path, 'utf-8'))
    return res.status(200).json(data)
  } catch (e) {
    return res.status(500).json({ error: 'read_failed', message: String(e) })
  }
})

// RSA private key (admin-only)
app.post('/api/keys/rsa/private', (req, res) => {
  const admin = process.env.ADMIN_TOKEN
  const provided = req.headers['x-admin-token'] || req.query?.token
  if (!admin || provided !== admin) {
    return res.status(403).json({ error: 'forbidden', message: 'Admin token required (X-ADMIN-TOKEN)' })
  }
  try {
    const { privateKey } = generateKeyPairSync('rsa', {
      modulusLength: 2048,
      publicKeyEncoding: { type: 'spki', format: 'pem' },
      privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
    })
    return res.status(200).json({ algorithm: 'RSA-2048', private_key_pem: privateKey })
  } catch (e) {
    return res.status(500).json({ error: 'rsa_keygen_failed', message: String(e) })
  }
})

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
