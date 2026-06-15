//! Transport-agnostic batching core. Both the TCP and shared-memory frontends
//! produce `Job`s on a crossbeam channel; the single batcher thread owns the
//! CUDA module, accumulates a batch (up to max_batch or the timeout), runs one
//! forward, and scatters per-job slices back via each job's `resp_tx`.
//!
//! Hardening (code-review §2.1, the high-severity finding): a forward error or
//! panic must NOT silently zombify the server. We (a) validate per-job dims
//! before concatenating, (b) wrap the forward in `catch_unwind`, and (c) on any
//! error/panic send a shape-matched zero stub to EVERY waiting job (so no client
//! hangs to its 60s timeout) and THEN `exit(1)` loudly — mirroring the Python
//! eval_server `_process_batch` except/stub/re-raise path.
use anyhow::{bail, Context, Result};
use crossbeam_channel::{Receiver, RecvTimeoutError, Sender};
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

pub fn batcher_loop(
    module: CModule,
    job_rx: Receiver<Job>,
    device: Device,
    max_batch: i64,
    timeout: Duration,
) {
    let mut n_batches: u64 = 0;
    let mut n_examples: u64 = 0;
    let mut fwd_total = Duration::ZERO;
    let mut fwd_window = Duration::ZERO;
    let mut last_log = Instant::now();

    loop {
        let first = match job_rx.recv() {
            Ok(j) => j,
            Err(_) => {
                eprintln!("[carc-orch] all producers gone; batcher exiting");
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

        let t0 = Instant::now();
        process_batch(&module, jobs, device, total_k); // never returns on error: stubs + exit(1)
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

/// Run one batch. On ANY error or panic: stub every waiting job with shaped
/// zeros (so no client hangs) then exit(1) loudly. Mirrors Python's
/// stub-then-reraise.
fn process_batch(module: &CModule, jobs: Vec<Job>, device: Device, total_k: i64) {
    let result =
        std::panic::catch_unwind(AssertUnwindSafe(|| forward(module, &jobs, device, total_k)));
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
    // Shape-matched zero stub to every waiting job so no client blocks to its
    // 60s timeout, then crash loudly (the launcher sees a dead process).
    for j in jobs {
        let _ = j.resp_tx.send(RespMsg {
            priors: vec![0.0f32; (j.k * j.a_size) as usize],
            values: vec![0.0f32; j.k as usize],
            a_size: j.a_size,
            k: j.k,
        });
    }
    eprintln!("[carc-orch] FATAL batcher: {msg}");
    std::process::exit(1);
}

struct Forward {
    priors: Vec<f32>,
    values: Vec<f32>,
    a_size: i64,
}

fn forward(module: &CModule, jobs: &[Job], device: Device, total_k: i64) -> Result<Forward> {
    let obs_inner = &jobs[0].obs_inner;
    let scalars_inner = &jobs[0].scalars_inner;
    let a_size = jobs[0].a_size;
    let obs_per: usize = obs_inner.iter().product::<i64>() as usize;
    let scl_per: i64 = scalars_inner.iter().product();

    // §2.1 / §3.4: validate every job's dims BEFORE concat so a mismatched
    // worker (e.g. the 10-vs-12 scalar-width footgun) is a clean Err, not a
    // reshape panic that zombifies the server.
    for (i, j) in jobs.iter().enumerate() {
        if &j.obs_inner != obs_inner {
            bail!("job {i} obs_inner {:?} != {:?}", j.obs_inner, obs_inner);
        }
        if &j.scalars_inner != scalars_inner {
            bail!("job {i} scalars_inner {:?} != {:?}", j.scalars_inner, scalars_inner);
        }
        if j.a_size != a_size {
            bail!("job {i} a_size {} != {}", j.a_size, a_size);
        }
        if j.obs.len() != j.k as usize * obs_per {
            bail!("job {i} obs len {} != k*{}", j.obs.len(), obs_per);
        }
        if j.scalars.len() != j.k as usize * scl_per as usize {
            bail!("job {i} scalars len mismatch");
        }
        if j.mask.len() != j.k as usize * a_size as usize {
            bail!("job {i} mask len mismatch");
        }
    }

    let mut obs_buf = Vec::with_capacity(total_k as usize * obs_per);
    let mut scl_buf = Vec::with_capacity(total_k as usize * scl_per as usize);
    let mut msk_buf = Vec::with_capacity(total_k as usize * a_size as usize);
    for j in jobs {
        obs_buf.extend_from_slice(&j.obs);
        scl_buf.extend_from_slice(&j.scalars);
        msk_buf.extend_from_slice(&j.mask);
    }

    let mut obs_shape = vec![total_k];
    obs_shape.extend_from_slice(obs_inner);
    // Fallible reshape (f_*) so a residual size bug is an Err, not a panic.
    let obs_t = Tensor::f_from_slice(&obs_buf)?.f_reshape(&obs_shape[..])?.to_device(device);
    let scl_t = Tensor::f_from_slice(&scl_buf)?
        .f_reshape([total_k, scl_per])?
        .to_device(device);
    let msk_t = Tensor::f_from_slice(&msk_buf)?
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
