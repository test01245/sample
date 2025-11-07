use std::io::Write;
use std::sync::{Arc, atomic::{AtomicBool, Ordering}};
use std::thread;
use std::time::{Duration, Instant};

#[derive(Clone)]
pub struct RansomNote {
    running: Arc<AtomicBool>,
}

impl RansomNote {
    pub fn start(hours: u64) -> Self {
        let running = Arc::new(AtomicBool::new(true));
        let r2 = running.clone();
        thread::spawn(move || {
            let total = Duration::from_secs(hours * 3600);
            let start = Instant::now();
            while r2.load(Ordering::SeqCst) {
                let elapsed = start.elapsed();
                if elapsed >= total { break; }
                let remaining = total - elapsed;
                let h = remaining.as_secs() / 3600;
                let m = (remaining.as_secs() % 3600) / 60;
                let s = remaining.as_secs() % 60;
                eprint!("\r[NOTE] YOUR FILES ARE ENCRYPTED · ⏰ {:02}:{:02}:{:02} ⏰        ", h, m, s);
                let _ = std::io::stderr().flush();
                thread::sleep(Duration::from_secs(1));
            }
            eprintln!("\n[NOTE] Countdown stopped.");
        });
        Self { running }
    }

    pub fn stop(&self) {
        self.running.store(false, Ordering::SeqCst);
    }
}
