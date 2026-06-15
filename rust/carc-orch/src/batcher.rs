//! Transport-agnostic batching core, PIPELINED. Both the TCP and shared-memory
//! frontends produce `Job`s on a crossbeam channel. Two threads:
//!
//!   * collector — pulls jobs, accumulates a batch (up to max_batch or the
//!     timeout), validates dims, and concatenates the per-job buffers into one
//!     contiguous CPU buffer. Sends the prepared buffers to the forwarder.
//!   * forwarder — owns the CUDA module; for each prepared batch does the H2D,
//!     one forward, the D2H, and scatters per-job slices back.
//!
//! The split lets the collector concat batch N+1 *while* the forwarder runs
//! batch N on the GPU — HWiNFO showed the single-threaded version left the GPU
//! ~50% idle (GPU Power ~30% TDP) waiting on the serial CPU concat. The bounded
//! channel double-buffers so the GPU never waits on a concat between batches.
//!
//! Hardening (code-review §2.1): a forward error or panic must not silently
//! zombify the server. On any error/panic we send a shape-matched zero stub to
//! every waiting job (so no client hangs to its 60s timeout) then exit(1) —
//! mirroring the Python eval_server stub/reraise.
use anyhow::{bail, Context, Result};
use crossbeam_channel::{bounded, Receiver, RecvTimeoutError, Sender};
use std::panic::AssertUnwindSafe;
use std::time::{Duration, Instant};
use tch::{CModule, Device, IValue, Kind, Tensor};

pub struct Job {
    pub k: i64,
    pub obs: Vec<f32>,
    pub obs_inner: Vec<i64>,
    pub scalars: Vec<f32>,
    pub scalars_inner: Vec<i64>,
    pub mask: Vec<u8>,
    pub a_size: i64,
    pub resp_tx: Sender<RespMsg>,
}

pub struct RespMsg {
    pub priors: Vec<f32>,
    pub values: Vec<f32>,
    pub a_size: i64,
    pub k: i64,
}

/// One batch concatenated on the collector, ready for the forwarder's GPU work.
struct Prepared {
    obs_buf: Vec<f32>,
    obs_inner: Vec<i64>,
    scl_buf: Vec<f32>,
    scl_per: i64,
    msk_buf: Vec<u8>,
    a_size: i64,
    total_k: i64,
    jobs: Vec<Job>,
}

/// Spawn the collector + forwarder. The forwarder owns the module. Returns once
/// both threads are spawned; they run until their channels close.
pub fn start(
    module: CModule,
    job_rx: Receiver<Job>,
    device: Device,
    max_batch: i64,
    timeout: Duration,
) -> Result<()> {
    // depth-2 so the collector can stay one batch ahead of the GPU
    let (prep_tx, prep_rx) = bounded::<Prepared>(2);
    std::thread::Builder::new()
        .name("forwarder".into())
        .spawn(move || forwarder_loop(module, device, prep_rx))?;
    std::thread::Builder::new()
        .name("collector".into())
        .spawn(move || collector_loop(job_rx, max_batch, timeout, prep_tx))?;
    Ok(())
}

fn collector_loop(
    job_rx: Receiver<Job>,
    max_batch: i64,
    timeout: Duration,
    prep_tx: Sender<Prepared>,
) {
    loop {
        let first = match job_rx.recv() {
            Ok(j) => j,
            Err(_) => {
                eprintln!("[carc-orch] all producers gone; collector exiting");
                return;
            }
        };
        let mut total_k = first.k;
        let mut jobs = vec![first];
        let deadline = Instant::now() + timeout;
        while total_k < max_batch {
            match job_rx.recv_deadline(deadline) {
                Ok(j) => {
                    total_k += j.k;
                    jobs.push(j);
                }
                Err(RecvTimeoutError::Timeout) | Err(RecvTimeoutError::Disconnected) => break,
            }
        }
        match build(jobs, total_k) {
            Ok(prep) => {
                if prep_tx.send(prep).is_err() {
                    return; // forwarder gone
                }
            }
            Err((jobs, e)) => fatal(&jobs, &format!("batch validation: {e:?}")),
        }
    }
}

/// Validate per-job dims (§2.1: a mismatched worker must be a clean error, not a
/// reshape panic) and concatenate into contiguous buffers.
fn build(jobs: Vec<Job>, total_k: i64) -> std::result::Result<Prepared, (Vec<Job>, anyhow::Error)> {
    let obs_inner = jobs[0].obs_inner.clone();
    let scalars_inner = jobs[0].scalars_inner.clone();
    let a_size = jobs[0].a_size;
    let obs_per: usize = obs_inner.iter().product::<i64>() as usize;
    let scl_per: i64 = scalars_inner.iter().product();

    for (i, j) in jobs.iter().enumerate() {
        let bad = if j.obs_inner != obs_inner {
            Some(format!("obs_inner {:?} != {:?}", j.obs_inner, obs_inner))
        } else if j.scalars_inner != scalars_inner {
            Some(format!("scalars_inner {:?} != {:?}", j.scalars_inner, scalars_inner))
        } else if j.a_size != a_size {
            Some(format!("a_size {} != {}", j.a_size, a_size))
        } else if j.obs.len() != j.k as usize * obs_per {
            Some(format!("obs len {} != k*{}", j.obs.len(), obs_per))
        } else if j.scalars.len() != j.k as usize * scl_per as usize {
            Some("scalars len mismatch".into())
        } else if j.mask.len() != j.k as usize * a_size as usize {
            Some("mask len mismatch".into())
        } else {
            None
        };
        if let Some(msg) = bad {
            return Err((jobs, anyhow::anyhow!("job {i} {msg}")));
        }
    }

    let mut obs_buf = Vec::with_capacity(total_k as usize * obs_per);
    let mut scl_buf = Vec::with_capacity(total_k as usize * scl_per as usize);
    let mut msk_buf = Vec::with_capacity(total_k as usize * a_size as usize);
    for j in &jobs {
        obs_buf.extend_from_slice(&j.obs);
        scl_buf.extend_from_slice(&j.scalars);
        msk_buf.extend_from_slice(&j.mask);
    }
    Ok(Prepared {
        obs_buf,
        obs_inner,
        scl_buf,
        scl_per,
        msk_buf,
        a_size,
        total_k,
        jobs,
    })
}

fn forwarder_loop(module: CModule, device: Device, prep_rx: Receiver<Prepared>) {
    let mut n_batches: u64 = 0;
    let mut n_examples: u64 = 0;
    let mut fwd_total = Duration::ZERO;
    let mut fwd_window = Duration::ZERO;
    let mut last_log = Instant::now();

    loop {
        let prep = match prep_rx.recv() {
            Ok(p) => p,
            Err(_) => {
                eprintln!("[carc-orch] collector gone; forwarder exiting");
                return;
            }
        };
        let total_k = prep.total_k;
        let t0 = Instant::now();
        process(&module, prep, device); // never returns on error: stubs + exit(1)
        let dt = t0.elapsed();

        n_batches += 1;
        n_examples += total_k as u64;
        fwd_total += dt;
        fwd_window += dt;
        let win = last_log.elapsed();
        if win >= Duration::from_secs(5) {
            eprintln!(
                "[carc-orch] {} batches, {} examples, avg_batch={:.1}, gpu_busy={:.0}%, examples/s={:.0}",
                n_batches,
                n_examples,
                n_examples as f64 / n_batches as f64,
                100.0 * fwd_window.as_secs_f64() / win.as_secs_f64(),
                n_examples as f64 / fwd_total.as_secs_f64().max(1e-9),
            );
            fwd_window = Duration::ZERO;
            last_log = Instant::now();
        }
    }
}

fn process(module: &CModule, prep: Prepared, device: Device) {
    let jobs = prep.jobs;
    let result = std::panic::catch_unwind(AssertUnwindSafe(|| {
        forward(
            module,
            device,
            &prep.obs_buf,
            &prep.obs_inner,
            &prep.scl_buf,
            prep.scl_per,
            &prep.msk_buf,
            prep.a_size,
            prep.total_k,
        )
    }));
    match result {
        Ok(Ok(fwd)) => scatter(fwd, jobs),
        Ok(Err(e)) => fatal(&jobs, &format!("forward error: {e:?}")),
        Err(p) => {
            let msg = p
                .downcast_ref::<&str>()
                .map(|s| s.to_string())
                .or_else(|| p.downcast_ref::<String>().cloned())
                .unwrap_or_else(|| "<non-string panic>".into());
            fatal(&jobs, &format!("forward PANIC: {msg}"));
        }
    }
}

fn fatal(jobs: &[Job], msg: &str) -> ! {
    for j in jobs {
        let _ = j.resp_tx.send(RespMsg {
            priors: vec![0.0f32; (j.k * j.a_size) as usize],
            values: vec![0.0f32; j.k as usize],
            a_size: j.a_size,
            k: j.k,
        });
    }
    eprintln!("[carc-orch] FATAL: {msg}");
    std::process::exit(1);
}

struct Forward {
    priors: Vec<f32>,
    values: Vec<f32>,
    a_size: i64,
}

#[allow(clippy::too_many_arguments)]
fn forward(
    module: &CModule,
    device: Device,
    obs_buf: &[f32],
    obs_inner: &[i64],
    scl_buf: &[f32],
    scl_per: i64,
    msk_buf: &[u8],
    a_size: i64,
    total_k: i64,
) -> Result<Forward> {
    let mut obs_shape = vec![total_k];
    obs_shape.extend_from_slice(obs_inner);
    let obs_t = Tensor::f_from_slice(obs_buf)?.f_reshape(&obs_shape[..])?.to_device(device);
    let scl_t = Tensor::f_from_slice(scl_buf)?
        .f_reshape([total_k, scl_per])?
        .to_device(device);
    let msk_t = Tensor::f_from_slice(msk_buf)?
        .f_reshape([total_k, a_size])?
        .to_kind(Kind::Bool)
        .to_device(device);

    let out = tch::no_grad(|| {
        module.forward_is(&[
            IValue::Tensor(obs_t),
            IValue::Tensor(scl_t),
            IValue::Tensor(msk_t),
        ])
    })
    .context("forward_is")?;

    let (priors_t, values_t) = match out {
        IValue::Tuple(mut v) if v.len() == 2 => {
            let values = ivalue_tensor(v.pop().unwrap())?;
            let priors = ivalue_tensor(v.pop().unwrap())?;
            (priors, values)
        }
        other => bail!("expected 2-tuple of tensors, got {other:?}"),
    };

    let priors_cpu = priors_t.to_device(Device::Cpu).contiguous();
    let values_cpu = values_t.to_device(Device::Cpu).contiguous();
    let pa = priors_cpu.size()[1];

    let plen = (total_k * pa) as usize;
    let mut priors = vec![0f32; plen];
    priors_cpu.copy_data(&mut priors, plen);
    let vlen = total_k as usize;
    let mut values = vec![0f32; vlen];
    values_cpu.copy_data(&mut values, vlen);

    Ok(Forward { priors, values, a_size: pa })
}

fn scatter(fwd: Forward, jobs: Vec<Job>) {
    let pa = fwd.a_size as usize;
    let mut off = 0usize;
    for j in jobs {
        let k = j.k as usize;
        let priors = fwd.priors[off * pa..(off + k) * pa].to_vec();
        let values = fwd.values[off..off + k].to_vec();
        let _ = j.resp_tx.send(RespMsg {
            priors,
            values,
            a_size: fwd.a_size,
            k: j.k,
        });
        off += k;
    }
}

fn ivalue_tensor(v: IValue) -> Result<Tensor> {
    match v {
        IValue::Tensor(t) => Ok(t),
        other => bail!("expected Tensor, got {other:?}"),
    }
}

// Keep the bounded import used even if depth changes.
const _: fn(usize) -> (Sender<Prepared>, Receiver<Prepared>) = bounded::<Prepared>;
