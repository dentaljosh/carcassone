//! carc-orch — Rust GPU inference orchestrator for Carcassonne self-play.
//!
//! A single batcher thread owns the CUDA module and aggregates forward requests
//! across all workers; a transport frontend feeds it. Two transports:
//!   * `tcp`  — byte-exact len-prefixed npy protocol, drop-in for the Python
//!     remote_eval_bridge (workers use `--remote-eval-server HOST:PORT`).
//!   * `shm`  — zero-copy shared memory + POSIX semaphores. Removes the ~24ms
//!     TCP+np.save round-trip that throttled the TCP transport below the GPU's
//!     batched rate; this is the transport that lets cross-worker batching
//!     actually beat per-worker local forwards.
mod batcher;
mod npy;
mod shm;
mod tcp;
mod wire;

use anyhow::{bail, Context, Result};
use crossbeam_channel::unbounded;
use std::time::Duration;
use tch::Device;

use batcher::Job;

#[derive(Clone, Copy, PartialEq)]
enum Transport {
    Tcp,
    Shm,
}

struct Config {
    model: String,
    host: String,
    port: u16,
    max_batch: i64,
    batch_timeout: Duration,
    device: Device,
    transport: Transport,
    shm_name: String,
    workers: usize,
    n_scalar: i64,
    require_cuda: bool,
    forwarders: usize,
    watchdog_secs: u64,
}

fn parse_args() -> Result<Config> {
    let mut model = None;
    let mut host = "0.0.0.0".to_string();
    let mut port = 0u16;
    let mut max_batch = 256i64;
    let mut batch_timeout_ms = 2.0f64;
    let mut device = Device::cuda_if_available();
    let mut device_explicit_cuda = false;
    let mut transport = Transport::Tcp;
    let mut shm_name = "carc_orch".to_string();
    let mut workers = 0usize;
    let mut n_scalar = 12i64;
    let mut require_cuda = true;
    let mut forwarders = 2usize;
    let mut watchdog_secs = 30u64;

    let args: Vec<String> = std::env::args().skip(1).collect();
    let mut i = 0;
    while i < args.len() {
        let a = &args[i];
        let mut next = || {
            i += 1;
            args.get(i).cloned().context("missing flag value")
        };
        match a.as_str() {
            "--model" => model = Some(next()?),
            "--host" => host = next()?,
            "--port" => port = next()?.parse()?,
            "--max-batch" => max_batch = next()?.parse()?,
            "--batch-timeout-ms" => batch_timeout_ms = next()?.parse()?,
            "--transport" => {
                transport = match next()?.as_str() {
                    "tcp" => Transport::Tcp,
                    "shm" => Transport::Shm,
                    other => bail!("unknown --transport {other}"),
                }
            }
            "--shm-name" => shm_name = next()?,
            "--workers" => workers = next()?.parse()?,
            "--n-scalar" => n_scalar = next()?.parse()?,
            "--forwarders" => forwarders = next()?.parse()?,
            "--watchdog-secs" => watchdog_secs = next()?.parse()?,
            "--allow-cpu" => require_cuda = false,
            "--device" => {
                device = match next()?.as_str() {
                    "cpu" => {
                        require_cuda = false;
                        Device::Cpu
                    }
                    "cuda" => {
                        device_explicit_cuda = true;
                        Device::Cuda(0)
                    }
                    other => bail!("unknown --device {other}"),
                }
            }
            other => bail!("unknown arg {other}"),
        }
        i += 1;
    }
    let _ = device_explicit_cuda;
    Ok(Config {
        model: model.context("--model required")?,
        host,
        port,
        max_batch,
        batch_timeout: Duration::from_secs_f64(batch_timeout_ms / 1000.0),
        device,
        transport,
        shm_name,
        workers,
        n_scalar,
        require_cuda,
        forwarders,
        watchdog_secs,
    })
}

fn main() -> Result<()> {
    let cfg = parse_args()?;

    // §2.2: fail LOUD if CUDA was intended but libtorch didn't register it
    // (the --as-needed / clobbered-LD_PRELOAD silent-CPU footgun). Default on;
    // pass --allow-cpu / --device cpu to opt into CPU explicitly.
    let cuda_ok = tch::Cuda::is_available();
    eprintln!(
        "[carc-orch] device={:?} cuda_available={} transport={}",
        cfg.device,
        cuda_ok,
        if cfg.transport == Transport::Tcp { "tcp" } else { "shm" }
    );
    if cfg.require_cuda && cfg.device.is_cuda() && !cuda_ok {
        bail!(
            "CUDA requested but tch::Cuda::is_available()==false — libtorch_cuda \
             not registered (LD_PRELOAD it, see run_server.sh). Refusing to run on \
             CPU silently; pass --allow-cpu to override."
        );
    }

    let (job_tx, job_rx) = unbounded::<Job>();
    // Spawns the collector + N forwarders (each its own module copy). Loads the
    // module(s) and warms cuDNN internally.
    batcher::start(
        job_rx,
        &cfg.model,
        cfg.device,
        cfg.max_batch,
        cfg.batch_timeout,
        cfg.n_scalar,
        cfg.forwarders,
        cfg.watchdog_secs,
    )?;

    eprintln!(
        "[carc-orch] max_batch={} timeout={:?} forwarders={}",
        cfg.max_batch, cfg.batch_timeout, cfg.forwarders
    );
    match cfg.transport {
        Transport::Tcp => tcp::serve(&cfg.host, cfg.port, job_tx)?,
        Transport::Shm => {
            if cfg.workers == 0 {
                bail!("--transport shm requires --workers N");
            }
            shm::serve(&cfg.shm_name, cfg.workers, cfg.n_scalar, job_tx)?
        }
    }
    Ok(())
}

