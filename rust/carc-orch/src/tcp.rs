//! TCP frontend: byte-exact len-prefixed npy protocol (drop-in for the Python
//! remote_eval_bridge). One reader thread per connection, synchronous
//! one-in-flight, feeding the shared batcher.
use anyhow::{Context, Result};
use crossbeam_channel::{bounded, Receiver, RecvTimeoutError, Sender};
use std::net::{TcpListener, TcpStream};
use std::time::Duration;

use crate::batcher::{Job, RespMsg};
use crate::{npy, wire};

// Backstop so a wedged (alive-but-hung) batcher doesn't park a reader forever
// (code-review §3.3). Matches/exceeds the client's 60s response timeout.
const RESP_TIMEOUT: Duration = Duration::from_secs(75);

pub fn serve(host: &str, port: u16, job_tx: Sender<Job>) -> Result<()> {
    let listener = TcpListener::bind((host, port))
        .with_context(|| format!("bind {host}:{port}"))?;
    eprintln!("[carc-orch] TCP listening on {host}:{port} READY");
    for stream in listener.incoming() {
        match stream {
            Ok(s) => {
                let _ = s.set_nodelay(true);
                let tx = job_tx.clone();
                std::thread::spawn(move || {
                    let peer = s.peer_addr().map(|a| a.to_string()).unwrap_or_default();
                    if let Err(e) = conn_loop(s, tx) {
                        eprintln!("[carc-orch] conn {peer} error: {e}");
                    }
                });
            }
            Err(e) => eprintln!("[carc-orch] accept error: {e}"),
        }
    }
    Ok(())
}

fn conn_loop(mut stream: TcpStream, job_tx: Sender<Job>) -> Result<()> {
    let (resp_tx, resp_rx): (Sender<RespMsg>, Receiver<RespMsg>) = bounded(1);
    loop {
        let body = match wire::read_frame(&mut stream) {
            Ok(b) => b,
            Err(e) => {
                // Distinguish clean EOF from a mid-stream I/O error (§4).
                if is_clean_eof(&e) {
                    return Ok(());
                }
                return Err(e).context("read_frame");
            }
        };
        let req = wire::parse_request(&body).context("parse_request")?;
        let request_id = req.request_id;
        job_tx
            .send(Job {
                k: req.k,
                obs: req.obs,
                obs_inner: req.obs_inner,
                scalars: req.scalars,
                scalars_inner: req.scalars_inner,
                mask: req.mask,
                a_size: req.a_size,
                resp_tx: resp_tx.clone(),
            })
            .map_err(|_| anyhow::anyhow!("batcher gone"))?;
        let resp = match resp_rx.recv_timeout(RESP_TIMEOUT) {
            Ok(r) => r,
            Err(RecvTimeoutError::Timeout) => {
                anyhow::bail!("batcher wedged: no response in {RESP_TIMEOUT:?}")
            }
            Err(RecvTimeoutError::Disconnected) => anyhow::bail!("batcher dropped response"),
        };
        let priors_npy = npy::write_f32(&[resp.k, resp.a_size], &resp.priors);
        let values_npy = npy::write_f32(&[resp.k], &resp.values);
        let out = wire::build_response(request_id, &priors_npy, &values_npy);
        wire::write_frame(&mut stream, &out)?;
    }
}

fn is_clean_eof(e: &anyhow::Error) -> bool {
    // wire::read_frame surfaces a closed peer as an io::Error (UnexpectedEof)
    // or our own "peer closed" message; treat those as a clean disconnect.
    if let Some(io) = e.downcast_ref::<std::io::Error>() {
        return matches!(
            io.kind(),
            std::io::ErrorKind::UnexpectedEof | std::io::ErrorKind::ConnectionReset
        );
    }
    false
}
