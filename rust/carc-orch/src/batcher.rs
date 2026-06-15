//! Transport-agnostic batching core, PIPELINED + MULTI-FORWARDER.
//!
//!   * collector — pulls jobs, accumulates a batch (up to max_batch or the
//!     timeout), validates dims, concatenates into contiguous CPU buffers, and
//!     hands the prepared batch to a forwarder pool.
//!   * forwarder pool (N threads, each its own CModule copy) — each pulls a
//!     prepared batch, does H2D + one forward + D2H, and scatters per-job slices
//!     back. They share the prep channel (MPMC).
//!
//! Why N forwarders: HWiNFO showed the single-threaded batcher left the GPU at
//! ~30% TDP — it spent half each batch on serial CPU prep (from_slice/copy_data)
//! while the GPU idled. With N forwarders, while one thread's kernel runs the
//! others do their CPU prep and queue the next transfer, so the GPU runs
//! back-to-back (even on the shared default stream the H2D/kernel/D2H of the
//! next batch are already queued). Drives throughput toward the GPU-compute
//! ceiling instead of the serial-prep ceiling.
//!
//! Hardening (code-review §2.1): a forward error or panic sends a shape-matched
//! zero stub to every waiting job (so no client hangs) then exit(1).
use anyhow::{bail, Context, Result};
use crossbeam_channel::{bounded, Receiver, RecvTimeoutError, Sender};
use std::panic::AssertUnwindSafe;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tch::{CModule, Device, IValue, Kind, Tensor};

// CUDA-stream shim (csrc/cuda_stream_shim.cpp, linked via build.rs). tch 0.24 has
// no stream API; these bind each forwarder thread to its own non-default CUDA
// stream so forwards overlap on the GPU instead of serializing on the default
// stream — the in-process equivalent of orch-off's per-process contexts.
extern "C" {
    fn carc_set_thread_stream(device: i32);
    fn carc_current_stream_id(device: i32) -> i64;
}

fn cuda_index(device: Device) -> i32 {
    match device {
        Device::Cuda(i) => i as i32,
        _ => 0,
    }
}

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

#[derive(Default)]
struct Stats {
    batches: AtomicU64,
    examples: AtomicU64,
    fwd_nanos: AtomicU64, // summed across forwarders (whole process())
    h2d_nanos: AtomicU64, // input prep + H2D (blocking to_device)
    cmp_nanos: AtomicU64, // forward_is (kernel launch; async, returns fast)
    d2h_nanos: AtomicU64, // D2H to_device(Cpu) + contiguous + copy_data (sync-wait)
    jobs_in: AtomicU64,   // jobs received by the collector (watchdog: in-but-no-out = wedge)
}

/// Spawn the collector + N forwarders. Loads `n_forwarders` module copies.
#[allow(clippy::too_many_arguments)]
pub fn start(
    job_rx: Receiver<Job>,
    model_path: &str,
    device: Device,
    max_batch: i64,
    timeout: Duration,
    n_scalar: i64,
    n_forwarders: usize,
    watchdog_secs: u64,
) -> Result<()> {
    let n = n_forwarders.max(1);
    let mut modules = Vec::with_capacity(n);
    for _ in 0..n {
        let mut m =
            CModule::load_on_device(model_path, device).with_context(|| format!("load {model_path}"))?;
        m.set_eval();
        modules.push(m);
    }
    warmup(&modules[0], device, n_scalar); // primes cuDNN autotune (process-wide cache)

    let (prep_tx, prep_rx) = bounded::<Prepared>(n + 1);
    let stats = Arc::new(Stats::default());
    for (i, m) in modules.into_iter().enumerate() {
        let rx = prep_rx.clone();
        let st = stats.clone();
        std::thread::Builder::new()
            .name(format!("forwarder-{i}"))
            .spawn(move || forwarder_loop(i, m, device, rx, st, i == 0, n))?;
    }
    drop(prep_rx);
    let coll_stats = stats.clone();
    std::thread::Builder::new()
        .name("collector".into())
        .spawn(move || collector_loop(job_rx, max_batch, timeout, prep_tx, coll_stats))?;

    // Watchdog: a CUDA/forwarder wedge (the intermittent "stall") shows up as
    // jobs flowing IN (collector receiving) but no batch completing OUT. Detect
    // that and exit LOUD so workers fail clean (BrokenServerError, no retry) and
    // the cluster launcher restarts — instead of every worker hanging to its 60s
    // timeout. A pure idle (no jobs in) does NOT trip it.
    if watchdog_secs > 0 {
        let wd_stats = stats.clone();
        std::thread::Builder::new()
            .name("watchdog".into())
            .spawn(move || watchdog_loop(wd_stats, watchdog_secs))?;
    }
    eprintln!("[carc-orch] batcher: {n} forwarder(s), watchdog={watchdog_secs}s");
    Ok(())
}

/// Trips when the collector keeps receiving jobs but no batch completes for
/// ~`secs` (a wedged forwarder/GPU). Exits the process so workers fail fast.
fn watchdog_loop(stats: Arc<Stats>, secs: u64) {
    let window = Duration::from_secs((secs / 3).max(2));
    let mut last_jobs = 0u64;
    let mut last_batches = 0u64;
    let mut stuck = 0u32;
    loop {
        std::thread::sleep(window);
        let jobs = stats.jobs_in.load(Ordering::Relaxed);
        let batches = stats.batches.load(Ordering::Relaxed);
        if jobs > last_jobs && batches == last_batches {
            stuck += 1;
            eprintln!(
                "[carc-orch] WATCHDOG: {jobs} jobs in, batches stuck at {batches} for {}s (window {stuck}/3)",
                window.as_secs() * stuck as u64
            );
            if stuck >= 3 {
                eprintln!("[carc-orch] WATCHDOG: forwarders WEDGED (~{secs}s, jobs in / no batches out) — exiting(2) for clean worker failure + launcher restart");
                std::process::exit(2);
            }
        } else {
            stuck = 0;
        }
        last_jobs = jobs;
        last_batches = batches;
    }
}

fn collector_loop(
    job_rx: Receiver<Job>,
    max_batch: i64,
    timeout: Duration,
    prep_tx: Sender<Prepared>,
    stats: Arc<Stats>,
) {
    loop {
        let first = match job_rx.recv() {
            Ok(j) => j,
            Err(_) => {
                eprintln!("[carc-orch] all producers gone; collector exiting");
                return;
            }
        };
        stats.jobs_in.fetch_add(1, Ordering::Relaxed);
        let mut total_k = first.k;
        let mut jobs = vec![first];
        let deadline = Instant::now() + timeout;
        while total_k < max_batch {
            match job_rx.recv_deadline(deadline) {
                Ok(j) => {
                    stats.jobs_in.fetch_add(1, Ordering::Relaxed);
                    total_k += j.k;
                    jobs.push(j);
                }
                Err(RecvTimeoutError::Timeout) | Err(RecvTimeoutError::Disconnected) => break,
            }
        }
        match build(jobs, total_k) {
            Ok(prep) => {
                if prep_tx.send(prep).is_err() {
                    return;
                }
            }
            Err((jobs, e)) => fatal(&jobs, &format!("batch validation: {e:?}")),
        }
    }
}

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

#[allow(clippy::too_many_arguments)]
fn forwarder_loop(
    idx: usize,
    module: CModule,
    device: Device,
    prep_rx: Receiver<Prepared>,
    stats: Arc<Stats>,
    is_logger: bool,
    n_forwarders: usize,
) {
    // Bind THIS forwarder thread to its own non-default CUDA stream so its forward
    // kernels overlap on the GPU with the other forwarders' (instead of all
    // serializing on the shared default stream). Thread-local in libtorch, so it
    // must run here, inside the thread. Logged per-forwarder so we can verify the
    // streams are distinct and non-zero (proof the overlap path is engaged).
    if device.is_cuda() {
        let dev_idx = cuda_index(device);
        unsafe { carc_set_thread_stream(dev_idx) };
        let sid = unsafe { carc_current_stream_id(dev_idx) };
        eprintln!("[carc-orch] forwarder-{idx} CUDA stream=0x{sid:x} (0x0=default)");
    }
    let mut last_log = Instant::now();
    let mut prev_ex = 0u64;
    let mut prev_b = 0u64;
    let mut prev_f = 0u64;
    let mut prev_h2d = 0u64;
    let mut prev_cmp = 0u64;
    let mut prev_d2h = 0u64;
    loop {
        let prep = match prep_rx.recv() {
            Ok(p) => p,
            Err(_) => {
                if is_logger {
                    eprintln!("[carc-orch] collector gone; forwarder exiting");
                }
                return;
            }
        };
        let total_k = prep.total_k;
        let t0 = Instant::now();
        process(&module, prep, device, &stats);
        let dt = t0.elapsed().as_nanos() as u64;
        stats.batches.fetch_add(1, Ordering::Relaxed);
        stats.examples.fetch_add(total_k as u64, Ordering::Relaxed);
        stats.fwd_nanos.fetch_add(dt, Ordering::Relaxed);

        if is_logger {
            let win = last_log.elapsed();
            if win >= Duration::from_secs(5) {
                let e = stats.examples.load(Ordering::Relaxed);
                let b = stats.batches.load(Ordering::Relaxed);
                let f = stats.fwd_nanos.load(Ordering::Relaxed);
                let h = stats.h2d_nanos.load(Ordering::Relaxed);
                let c = stats.cmp_nanos.load(Ordering::Relaxed);
                let d = stats.d2h_nanos.load(Ordering::Relaxed);
                let d_ex = e - prev_ex;
                let d_b = (b - prev_b).max(1);
                let d_f = (f - prev_f) as f64 / 1e9; // summed forwarder-busy seconds
                let wall = win.as_secs_f64();
                // per-batch section breakdown (ms): h2d/cmp/d2h are summed across
                // forwarders, as is d_b, so delta/d_b is avg per batch.
                let ms = |x: u64, p: u64| (x - p) as f64 / 1e6 / d_b as f64;
                eprintln!(
                    "[carc-orch] {} batches, {} examples, avg_batch={:.1}, fwd_busy={:.0}%, examples/s={:.0} | per-batch ms: h2d={:.2} cmp={:.2} d2h={:.2}",
                    b,
                    e,
                    d_ex as f64 / d_b as f64,
                    100.0 * d_f / (wall * n_forwarders as f64),
                    d_ex as f64 / wall, // WALL throughput (aggregate)
                    ms(h, prev_h2d),
                    ms(c, prev_cmp),
                    ms(d, prev_d2h),
                );
                prev_ex = e;
                prev_b = b;
                prev_f = f;
                prev_h2d = h;
                prev_cmp = c;
                prev_d2h = d;
                last_log = Instant::now();
            }
        }
    }
}

fn process(module: &CModule, prep: Prepared, device: Device, stats: &Stats) {
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
            stats,
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
    stats: &Stats,
) -> Result<Forward> {
    let t_h2d = Instant::now();
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
    stats.h2d_nanos.fetch_add(t_h2d.elapsed().as_nanos() as u64, Ordering::Relaxed);

    let t_cmp = Instant::now();
    let out = tch::no_grad(|| {
        module.forward_is(&[
            IValue::Tensor(obs_t),
            IValue::Tensor(scl_t),
            IValue::Tensor(msk_t),
        ])
    })
    .context("forward_is")?;
    stats.cmp_nanos.fetch_add(t_cmp.elapsed().as_nanos() as u64, Ordering::Relaxed);

    let t_d2h = Instant::now();
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
    stats.d2h_nanos.fetch_add(t_d2h.elapsed().as_nanos() as u64, Ordering::Relaxed);

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

fn warmup(module: &CModule, device: Device, n_scalar: i64) {
    let res = std::panic::catch_unwind(AssertUnwindSafe(|| {
        let obs = Tensor::zeros([1, 78, 25, 25], (Kind::Float, device));
        let scl = Tensor::zeros([1, n_scalar], (Kind::Float, device));
        let msk = Tensor::ones([1, 2511], (Kind::Bool, device));
        let _ = tch::no_grad(|| {
            module.forward_is(&[
                IValue::Tensor(obs),
                IValue::Tensor(scl),
                IValue::Tensor(msk),
            ])
        });
        if device.is_cuda() {
            tch::Cuda::synchronize(0);
        }
    }));
    if res.is_err() {
        eprintln!("[carc-orch] warmup failed (n_scalar={n_scalar}?) — continuing");
    }
}
