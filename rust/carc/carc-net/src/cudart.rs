//! A ~60-line `cudaMemcpy` shim, resolved at runtime with `dlopen`.
//!
//! ## Why this exists
//!
//! CUDA-Graph capture requires the session's inputs and outputs to be
//! **device-resident** and at **stable addresses** — that is the whole reason the
//! bound path exists. But once the input buffers live on the GPU, something has to
//! refresh their contents between forwards, and `ort` rc.13 offers no usable way to
//! do it on this box:
//!
//! * `Value::copy_into` / `Value::to` are implemented as *a whole extra ORT session
//!   run* over a one-node Identity graph (`ort`'s own comment: "ONNX Runtime doesn't
//!   (currently) expose an API for inter-device copies"). That helper session sets
//!   `GraphOptimizationLevel::Level3`, and this box's `ort` rc.13 / onnxruntime 1.22
//!   pairing **rejects that option** — the same `graph_optimization_level is not
//!   valid` ABI mismatch `lib.rs` already documents for our own session. So every
//!   `copy_into` fails at runtime, and the failure is in `ort`'s code where we
//!   cannot pass a different option.
//! * Binding a *host* tensor as the input instead makes ORT do the H2D itself, but
//!   then the input is no longer device-resident and graph capture is off the table.
//!
//! A raw `cudaMemcpy` onto the pointer `ort` already hands us (`Value::data_ptr`) is
//! the direct route, and it is what a shipping integration would use anyway — the
//! design memo's §7.4 encoder work item ends with the encoder writing into staging
//! that gets copied to the device, not with an ORT Identity graph.
//!
//! ## Why `dlopen` rather than `#[link(name = "cudart")]`
//!
//! The CUDA-12 runtime on this box comes from torch's `nvidia-cuda-runtime-cu12`
//! wheel, which ships `libcudart.so.12` with **no** `libcudart.so` development
//! symlink — so `-lcudart` cannot resolve at link time and adding a `build.rs` to
//! manufacture one would put a second, independent CUDA-version pin in the build.
//! Resolving the soname at runtime keeps the crate's link line unchanged (it already
//! finds `libcudart.so.12` through the `LD_LIBRARY_PATH` that
//! `tools/ort_cuda_env.sh` sets for onnxruntime itself) and keeps CUDA an optional,
//! late-bound capability rather than a hard build dependency.
//!
//! ## Ordering
//!
//! Only the **synchronous** `cudaMemcpy` is exposed, deliberately. It blocks until
//! the transfer is complete, so an upload is ordered before a subsequent
//! `run_binding` and a download is ordered after it without any stream reasoning —
//! and ORT's `Run` already synchronizes its own stream before returning. An async
//! variant would be faster and is the right call for a real integration, but it
//! would need the EP's stream handle and would make the bench's upload/forward split
//! meaningless.

use core::ffi::{c_char, c_int, c_void};
use core::sync::atomic::{AtomicPtr, Ordering};

unsafe extern "C" {
    fn dlopen(filename: *const c_char, flag: c_int) -> *mut c_void;
    fn dlsym(handle: *mut c_void, symbol: *const c_char) -> *mut c_void;
}

const RTLD_NOW: c_int = 2;
const RTLD_GLOBAL: c_int = 0x100;

/// `cudaMemcpyKind::cudaMemcpyHostToDevice`.
pub const H2D: c_int = 1;
/// `cudaMemcpyKind::cudaMemcpyDeviceToHost`.
pub const D2H: c_int = 2;

type MemcpyFn = unsafe extern "C" fn(*mut c_void, *const c_void, usize, c_int) -> c_int;

static MEMCPY: AtomicPtr<c_void> = AtomicPtr::new(core::ptr::null_mut());

/// Candidate sonames, most specific first. The CUDA-12 pin is deliberate and
/// matches the onnxruntime build `tools/ort_cuda_env.sh` selects: a `libcudart.so.13`
/// picked up here against a CUDA-12 onnxruntime is the mirror image of the fail-open
/// the whole T3 tier exists to prevent.
const SONAMES: [&[u8]; 2] = [b"libcudart.so.12\0", b"libcudart.so\0"];

fn resolve() -> Result<MemcpyFn, String> {
    let cached = MEMCPY.load(Ordering::Acquire);
    if !cached.is_null() {
        return Ok(unsafe { core::mem::transmute::<*mut c_void, MemcpyFn>(cached) });
    }
    for soname in SONAMES {
        let handle = unsafe { dlopen(soname.as_ptr().cast::<c_char>(), RTLD_NOW | RTLD_GLOBAL) };
        if handle.is_null() {
            continue;
        }
        let sym = unsafe { dlsym(handle, c"cudaMemcpy".as_ptr()) };
        if !sym.is_null() {
            MEMCPY.store(sym, Ordering::Release);
            return Ok(unsafe { core::mem::transmute::<*mut c_void, MemcpyFn>(sym) });
        }
    }
    Err("could not dlopen libcudart.so.12 (is LD_LIBRARY_PATH set? see tools/ort_cuda_env.sh)".into())
}

/// Copy `bytes` from `src` to `dst` in the given direction, blocking until done.
///
/// # Safety
/// `src` and `dst` must be valid for `bytes` in the address spaces implied by
/// `kind`, and the calling thread must have a current CUDA context (ORT's session
/// construction establishes one on device 0).
pub unsafe fn memcpy(dst: *mut c_void, src: *const c_void, bytes: usize, kind: c_int) -> Result<(), String> {
    let f = resolve()?;
    let rc = unsafe { f(dst, src, bytes, kind) };
    if rc != 0 {
        return Err(format!("cudaMemcpy returned cudaError_t {rc}"));
    }
    Ok(())
}
