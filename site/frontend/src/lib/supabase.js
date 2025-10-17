import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || 'https://mawhbwogynurfbacxnyh.supabase.co'
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1hd2hid29neW51cmZiYWN4bnloIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjA2NDY2MjEsImV4cCI6MjA3NjIyMjYyMX0.KX1MKm74NRMC9Nb1yg4FyDxWFChboD796hFyTz92q_k'

let supabase = null
try {
  if (SUPABASE_URL && SUPABASE_ANON_KEY) {
    supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, { auth: { persistSession: false } })
  }
} catch {
  supabase = null
}

export { supabase, SUPABASE_URL }
