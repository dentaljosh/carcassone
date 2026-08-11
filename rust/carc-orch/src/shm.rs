//! Zero-copy shared-memory frontend.
//!
//! Removes the ~24ms TCP+np.save round-trip of the TCP transport. Each worker
//! owns a fixed slot in a `/dev/shm` mmap; it writes obs/scalars/mask directly
//! into the slot (one memcpy, no serialization), posts its request semaphore,
//! and blocks on its response semaphore. The server runs one reader thread per
//! worker that wakes on the request semaphore, copies the request out, feeds the
//! shared batcher, writes the response back into the slot, and posts the
//! response semaphore. Cross-worker batching happens in the batcher exactly as
//! for TCP — but now the transport is fast enough not to throttle supply.
//!
//! LAYOUT CONTRACT — must stay byte-identical to scripts/shm_eval_handles.py.
//!   file = N_WORKERS slots, each SLOT_SIZE bytes.
//!   slot:
//!     [0..8)    req_seq   u64 LE  (worker writes, ++ per request)
//!     [8..16)   k         u64 LE  (worker writes, 1..=MAX_K)
//!     [16..24)  resp_seq  u64 LE  (server writes, = req_seq when done)
//!     [24..32)  request_id u64 LE (worker writes, echoed for debug)
//!     [64..)               obs    MAX_K*(n_ch*HW*HW) f32
//!                          scalars MAX_K*n_scalar f32
//!                          mask   MAX_K*A u8
//!                          priors MAX_K*A f32   (server writes)
//!                          values MAX_K  f32    (server writes)
//!   semaphores (POSIX named, created by the server):
//!     /carc_<name>_req_<i>   worker posts, reader i waits
//!     /carc_<name>_resp_<i>  reader i posts, worker waits
//!
//! CHANNELS/SCALARS ARE RUNTIME-CONFIGURABLE (2026-07-03, M2 sighted rep): the
//! obs/scalar region sizes and hence all offsets are computed from
//! `(n_ch, n_scalar)` — NOT compile-time constants. The server learns them from
//! `--n-ch`/`--n-scalar`; the Python client is told the same two numbers in
//! `connect_shm`. Both compute an identical `Layout`, so blind 78ch/12-scalar
//! nets get the byte-identical layout they had before (`Layout::new(78,12)` ==
//! the old N_CH=78 / N_SCALAR_MAX=12 constants) and sighted 81ch/42-scalar nets
//! get their own exact-fit layout. MAX_K/HW/A stay fixed (locked rule set).
use anyhow::{bail, Context, Result};
use crossbeam_channel::{bounded, Receiver, Sender};
use std::ffi::CString;

use crate::batcher::{Job, RespMsg};

pub mod layout {
    pub const MAX_K: usize = 8;
    pub const HW: usize = 25;
    pub const A: usize = 2511; // action space (locked rule set)
    pub const HDR: usize = 64;
    // Sanity caps: reject a garbage --n-ch/--n-scalar before it sizes a huge
    // mmap. 128 is far beyond anything the featurizer emits (blind 78/12,
    // sighted 81/42).
    pub const N_CH_CAP: usize = 128;
    pub const N_SCALAR_CAP: usize = 128;

    /// Runtime slot layout for a given (n_ch, n_scalar). Byte-identical to the
    /// Python `_ShmConn` offset computation (shm_eval_handles.py).
    #[derive(Clone, Copy)]
    pub struct Layout {
        pub n_ch: usize,
        pub n_scalar: usize,
        pub obs_per: usize, // n_ch*HW*HW floats per board
        pub off_obs: usize,
        pub off_scl: usize,
        pub off_msk: usize,
        pub off_pri: usize,
        pub off_val: usize,
        pub slot_size: usize,
    }

    impl Layout {
        pub fn new(n_ch: usize, n_scalar: usize) -> Self {
            let obs_per = n_ch * HW * HW;
            let off_obs = HDR;
            let off_scl = off_obs + MAX_K * obs_per * 4;
            let off_msk = off_scl + MAX_K * n_scalar * 4;
            let off_pri = off_msk + MAX_K * A;
            let off_val = off_pri + MAX_K * A * 4;
            let slot_size = off_val + MAX_K * 4;
            Layout {
                n_ch,
                n_scalar,
                obs_per,
                off_obs,
                off_scl,
                off_msk,
                off_pri,
                off_val,
                slot_size,
            }
        }
    }
}

// Raw-pointer newtypes so we can hand disjoint slot pointers + sem handles to
// per-worker threads. Safe because each reader touches only its own slot
// (disjoint memory) and its own two semaphores.
struct Slot(*mut u8);
unsafe impl Send for Slot {}
struct Sem(*mut libc::sem_t);
unsafe impl Send for Sem {}

pub fn serve(
    name: &str,
    n_workers: usize,
    n_ch: i64,
    n_scalar: i64,
    job_tx: Sender<Job>,
) -> Result<()> {
    use layout::*;
    if n_ch < 1 || n_ch as usize > N_CH_CAP {
        bail!("--n-ch {n_ch} out of range 1..={N_CH_CAP}");
    }
    if n_scalar < 1 || n_scalar as usize > N_SCALAR_CAP {
        bail!("--n-scalar {n_scalar} out of range 1..={N_SCALAR_CAP}");
    }
    let lay = Layout::new(n_ch as usize, n_scalar as usize);
    let slot_size = lay.slot_size;
    let path = format!("/dev/shm/carc_{name}");
    let total = n_workers * slot_size;

    let file = std::fs::OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .open(&path)
        .with_context(|| format!("open shm {path}"))?;
    file.set_len(total as u64).context("set_len shm")?;
    let mut mmap = unsafe { memmap2::MmapMut::map_mut(&file)? };
    // zero it so a stale file from a prior run can't feed garbage
    for b in mmap.iter_mut() {
        *b = 0;
    }
    let base = mmap.as_mut_ptr();
    std::mem::forget(mmap); // keep mapped for the process lifetime (daemon)

    // Create the 2N semaphores fresh (unlink any stale ones first).
    let mut req_sems = Vec::with_capacity(n_workers);
    let mut resp_sems = Vec::with_capacity(n_workers);
    for i in 0..n_workers {
        req_sems.push(open_sem(name, "req", i)?);
        resp_sems.push(open_sem(name, "resp", i)?);
    }

    eprintln!(
        "[carc-orch] SHM {path} ({n_workers} slots x {slot_size}B = {total}B), n_ch={n_ch} n_scalar={n_scalar} READY"
    );

    let mut handles = Vec::new();
    for i in 0..n_workers {
        let slot = Slot(unsafe { base.add(i * slot_size) });
        let req = Sem(req_sems[i]);
        let resp = Sem(resp_sems[i]);
        let tx = job_tx.clone();
        let h = std::thread::Builder::new()
            .name(format!("shm-reader-{i}"))
            .spawn(move || reader_loop(i, slot, req, resp, lay, tx))?;
        handles.push(h);
    }
    drop(job_tx); // only the readers hold senders now
    for h in handles {
        let _ = h.join();
    }
    Ok(())
}

fn reader_loop(i: usize, slot: Slot, req: Sem, resp: Sem, lay: layout::Layout, job_tx: Sender<Job>) {
    use layout::*;
    let base = slot.0;
    let (resp_tx, resp_rx): (Sender<RespMsg>, Receiver<RespMsg>) = bounded(1);
    loop {
        if !sem_wait(req.0) {
            eprintln!("[carc-orch] shm reader {i}: req sem wait failed, exiting");
            return;
        }
        // Request is now fully visible (sem is a full barrier). Copy it out.
        let k = unsafe { read_u64(base, 8) } as usize;
        if k == 0 || k > MAX_K {
            eprintln!("[carc-orch] shm reader {i}: bad k={k}, skipping");
            // still must release the worker or it hangs forever
            unsafe { write_u64(base, 16, read_u64(base, 0)) };
            sem_post(resp.0);
            continue;
        }
        let request_id = unsafe { read_u64(base, 24) } as i64;
        let req_seq = unsafe { read_u64(base, 0) };
        let obs = unsafe { read_f32(base, lay.off_obs, k * lay.obs_per) };
        let scalars = unsafe { read_f32(base, lay.off_scl, k * lay.n_scalar) };
        let mask = unsafe { read_u8(base, lay.off_msk, k * A) };
        let _ = request_id;

        if job_tx
            .send(Job {
                k: k as i64,
                obs,
                obs_inner: vec![lay.n_ch as i64, HW as i64, HW as i64],
                scalars,
                scalars_inner: vec![lay.n_scalar as i64],
                mask,
                a_size: A as i64,
                resp_tx: resp_tx.clone(),
            })
            .is_err()
        {
            return; // batcher gone
        }
        let r = match resp_rx.recv() {
            Ok(r) => r,
            Err(_) => return,
        };
        // Write response back into the slot, then release the worker.
        unsafe {
            write_f32(base, lay.off_pri, &r.priors);
            write_f32(base, lay.off_val, &r.values);
            write_u64(base, 16, req_seq); // resp_seq = req_seq: response ready
        }
        if !sem_post(resp.0) {
            eprintln!("[carc-orch] shm reader {i}: resp sem post failed");
            return;
        }
    }
}

fn open_sem(name: &str, kind: &str, i: usize) -> Result<*mut libc::sem_t> {
    let sname = CString::new(format!("/carc_{name}_{kind}_{i}")).unwrap();
    unsafe {
        libc::sem_unlink(sname.as_ptr()); // clear any stale sem from a prior run
        let s = libc::sem_open(sname.as_ptr(), libc::O_CREAT, 0o600 as libc::c_uint, 0 as libc::c_uint);
        if s.is_null() || s as isize == -1 {
            let e = std::io::Error::last_os_error();
            bail!("sem_open {:?}: {e}", sname);
        }
        Ok(s)
    }
}

fn sem_wait(s: *mut libc::sem_t) -> bool {
    loop {
        let r = unsafe { libc::sem_wait(s) };
        if r == 0 {
            return true;
        }
        let e = std::io::Error::last_os_error();
        if e.raw_os_error() == Some(libc::EINTR) {
            continue;
        }
        return false;
    }
}

fn sem_post(s: *mut libc::sem_t) -> bool {
    unsafe { libc::sem_post(s) == 0 }
}

unsafe fn read_u64(base: *const u8, off: usize) -> u64 {
    (base.add(off) as *const u64).read_unaligned()
}
unsafe fn write_u64(base: *mut u8, off: usize, v: u64) {
    (base.add(off) as *mut u64).write_unaligned(v);
}
unsafe fn read_f32(base: *const u8, off: usize, n: usize) -> Vec<f32> {
    std::slice::from_raw_parts(base.add(off) as *const f32, n).to_vec()
}
unsafe fn read_u8(base: *const u8, off: usize, n: usize) -> Vec<u8> {
    std::slice::from_raw_parts(base.add(off), n).to_vec()
}
unsafe fn write_f32(base: *mut u8, off: usize, data: &[f32]) {
    std::ptr::copy_nonoverlapping(
        data.as_ptr(),
        base.add(off) as *mut f32,
        data.len(),
    );
}
