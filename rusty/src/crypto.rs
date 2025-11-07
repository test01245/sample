use aead::{Aead, KeyInit, OsRng};
use aes_gcm::{Aes256Gcm, Nonce};

pub struct AesCtx {
    cipher: Aes256Gcm,
    key: [u8; 32],
}

impl AesCtx {
    pub fn new_random() -> Self {
        let key = Aes256Gcm::generate_key(&mut OsRng);
        Self { cipher: Aes256Gcm::new(&key), key: (*key).into() }
    }

    pub fn from_key_bytes(key: [u8;32]) -> Self {
        let cipher = Aes256Gcm::new((&key).into());
        Self { cipher, key }
    }

    pub fn key_b64(&self) -> String {
        base64::encode(self.key)
    }

    pub fn set_key_b64(&mut self, b64: &str) -> Result<(), String> {
        let bytes = base64::decode(b64).map_err(|e| e.to_string())?;
        if bytes.len() != 32 { return Err("invalid key length".into()); }
        let mut k = [0u8;32];
        k.copy_from_slice(&bytes);
        *self = Self::from_key_bytes(k);
        Ok(())
    }

    // Encrypt: return nonce || ciphertext
    pub fn enc(&self, data: &[u8]) -> Result<Vec<u8>, String> {
        let nonce_bytes: [u8;12] = rand::random();
        let nonce = Nonce::from_slice(&nonce_bytes);
        let ct = self.cipher.encrypt(nonce, data).map_err(|e| e.to_string())?;
        let mut out = Vec::with_capacity(12 + ct.len());
        out.extend_from_slice(&nonce_bytes);
        out.extend_from_slice(&ct);
        Ok(out)
    }

    pub fn dec(&self, data: &[u8]) -> Result<Vec<u8>, String> {
        if data.len() < 12 { return Err("invalid data".into()); }
        let (nonce_bytes, ct) = data.split_at(12);
        let nonce = Nonce::from_slice(nonce_bytes);
        let pt = self.cipher.decrypt(nonce, ct).map_err(|e| e.to_string())?;
        Ok(pt)
    }
}
