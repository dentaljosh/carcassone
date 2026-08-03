//! `carc-net` — an ONNX-Runtime implementation of [`carc_core::eval::PolicyEvaluator`].
//!
//! See `docs/RUST_NET_EVAL_DESIGN_20260802.md` for why ORT and not PyO3/tch/candle/
//! tract. The one-line version: ORT is the only candidate that has BOTH a
//! CUDA-graph-class batch-1 latency (the thing the whole design turns on) and an
//! Android/CPU story, and it takes a neutral interchange format the project already
//! exports three other flavours of.
//!
//! ## The CUDA-graph point
//!
//! A 6x96 ResNet at batch 1 is ~1.34 GFLOP — nothing for a modern GPU. What it costs
//! is ~30 kernel LAUNCHES. Measured on this box (RTX 5060 Ti), eager torch batch-1 is
//! 2.40 ms while the identical graph replayed as a CUDA Graph is 0.339 ms. That 7.1x
//! is pure launch overhead, and it is the difference between a rust net arm being
//! hopeless and being marginal. ORT exposes it through the CUDA EP's
//! `enable_cuda_graph`, which is why the ONNX files are exported at FIXED batch
//! sizes — a captured graph requires static shapes.
//!
//! ## What this crate does NOT do
//!
//! It does not encode boards. [`carc_core::eval::PolicyEvaluator`] takes pre-encoded
//! tensors, because `board_repr.encode_board` (81 planes) is still Python/Cython and
//! porting it is a separate work item sized in the memo (§6). Keeping the seam at
//! tensors also means the faithfulness harness feeds torch and ORT byte-identical
//! inputs, so the residual it reports is backend drift and nothing else.

use carc_core::eval::{masked_softmax, NetEvalError, NetRep, PolicyEvaluator};
use ort::ep::{CPU, CUDA};
use ort::memory::{AllocationDevice, Allocator, AllocatorType, MemoryInfo, MemoryType};
use ort::session::{IoBinding, Session};
use ort::value::{Tensor, TensorRef};

pub mod cudart;
pub mod positions;

/// Which device the evaluator runs on. Recorded on the evaluator and stamped into
/// bench output, because "a forward measured on the wrong device" is exactly the
/// failure `coreml_evaluator.resolve_net_backend` refuses to allow silently.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Backend {
    /// ORT CPU execution provider, `intra_threads` as configured.
    Cpu(usize),
    /// ORT CUDA execution provider, eager, inputs/outputs passed as HOST slices.
    /// Every `run` therefore pays an H2D of the board+scalars and a D2H of the
    /// logits inside ORT. This is the §6.1 row of the design memo.
    Cuda,
    /// ORT CUDA execution provider, eager, inputs/outputs bound **device-resident**
    /// via `IoBinding`. Same kernels as [`Backend::Cuda`]; the difference is purely
    /// where the tensors live. Exists to SEPARATE the two effects the graph row
    /// otherwise conflates — copy elimination vs. launch elimination.
    CudaBound,
    /// [`Backend::CudaBound`] plus `enable_cuda_graph`. ORT captures the CUDA graph
    /// on the first `run_binding` and replays it thereafter; capture is only
    /// possible because the bound tensors give it stable device addresses and the
    /// ONNX graph is exported at a fixed batch.
    CudaGraph,
}

impl Backend {
    pub fn label(&self) -> String {
        match self {
            Backend::Cpu(t) => format!("cpu(threads={t})"),
            Backend::Cuda => "cuda".to_string(),
            Backend::CudaBound => "cuda+bound".to_string(),
            Backend::CudaGraph => "cuda+graph".to_string(),
        }
    }

    /// Whether this backend routes through `IoBinding` with device-resident tensors.
    pub fn is_bound(&self) -> bool {
        matches!(self, Backend::CudaBound | Backend::CudaGraph)
    }
}

/// The device-resident I/O of a bound evaluator.
///
/// ⚠️ **Every field here is load-bearing for CUDA-graph capture.** ORT captures a
/// graph only if it can record fixed device addresses for the whole run: the input
/// tensors are allocated ONCE on the CUDA device and bound ONCE (subsequent
/// forwards overwrite their contents in place, which the captured graph sees
/// because it captured the *pointer*), and the output is bound with
/// `bind_output_to_device` so ORT allocates and REUSES one device buffer rather
/// than a fresh one per run. Re-binding, re-allocating, or handing ORT a host slice
/// invalidates the capture — which is exactly what the memo's prototype did, and
/// why `Backend::CudaGraph` panicked in ORT's value layer (§6.2).
struct Bound {
    binding: IoBinding,
    /// Device-side inputs. Kept (not moved into the binding) so their contents can
    /// be refreshed in place between forwards.
    board_dev: Tensor<f32>,
    scalars_dev: Tensor<f32>,
    /// ⚠️ **MUST outlive every tensor above, and Rust's drop order is what enforces
    /// it — so this field MUST stay last.** `Allocator` owns an `OrtAllocator` and
    /// releases it on drop, while a tensor built by `Tensor::new(&alloc, ..)` keeps
    /// only a raw pointer to that allocator for its own deallocation: `ort` ties the
    /// two by no lifetime at all. Dropping the allocator first is a use-after-free,
    /// and it is not a quiet one — the first version of this spike let the allocator
    /// die at the end of `make_bound` and **segfaulted** on the very next forward.
    #[allow(dead_code)]
    dev_alloc: Allocator,
}

/// An ORT-backed policy evaluator over a fixed-batch ONNX policy graph.
pub struct OrtPolicyEvaluator {
    session: Session,
    rep: NetRep,
    batch: usize,
    backend: Backend,
    /// Scratch for the raw logits ORT hands back, so `policy_batch` allocates nothing.
    logits: Vec<f32>,
    /// `Some` iff `backend.is_bound()`.
    bound: Option<Bound>,
    /// Whether the CUDA EP was left with TF32 enabled (its default). Recorded, not
    /// gated — §5 tier T2. TF32's 10-bit mantissa is the identified cause of the
    /// ~5e-4 residual in the memo's §6.4 CUDA row.
    tf32: bool,
    /// `CARC_ORT_EXPLICIT_SYNC=1` — see [`OrtPolicyEvaluator::forward_bound`].
    explicit_sync: bool,
}

impl OrtPolicyEvaluator {
    /// Build an evaluator over `model_path`, which MUST be an ONNX graph exported at
    /// exactly `batch` (see `tools/export_onnx.py`).
    ///
    /// The declared input shapes are validated against `rep` before any forward: a
    /// silent representation mismatch produces plausible-looking garbage priors
    /// rather than an error, which is the failure mode
    /// `heuristic_prior_mcts._validate_fair_net_prior_dims` exists to prevent on the
    /// Python side.
    pub fn new(
        model_path: &str,
        rep: NetRep,
        batch: usize,
        backend: Backend,
    ) -> Result<Self, NetEvalError> {
        // TF32 ON is ORT's own CUDA default, and it is what the memo's §6.4 CUDA row
        // was measured under. Keep it as the default so new numbers stay comparable
        // to the recorded ones; `new_with_tf32` exists to price the alternative.
        let tf32 = std::env::var("CARC_ORT_TF32").as_deref() != Ok("0");
        Self::new_with_tf32(model_path, rep, batch, backend, tf32)
    }

    /// As [`OrtPolicyEvaluator::new`], with explicit control over the CUDA EP's TF32
    /// setting. `tf32 = false` trades slower convolutions for a tighter residual;
    /// §5 tier T2 wants that trade to be a deliberate, measured choice rather than a
    /// default nobody looked at.
    pub fn new_with_tf32(
        model_path: &str,
        rep: NetRep,
        batch: usize,
        backend: Backend,
        tf32: bool,
    ) -> Result<Self, NetEvalError> {
        // NOTE: `with_optimization_level` is deliberately NOT set. The `ort` rc.13
        // crate and the onnxruntime 1.22 shared library this box links against
        // disagree on the session-options ABI, and setting it fails the session with
        // "graph_optimization_level is not valid". ORT's own default is already
        // full optimization, so omitting it costs nothing — but the version
        // sensitivity is a maintenance fact worth keeping in view: an `ort` upgrade
        // and an onnxruntime upgrade are ONE change, not two.
        let mut builder = Session::builder().map_err(|e| NetEvalError::Load(e.to_string()))?;

        builder = match backend {
            Backend::Cpu(threads) => builder
                .with_intra_threads(threads)
                .map_err(|e| NetEvalError::Load(e.to_string()))?
                .with_execution_providers([CPU::default().build()])
                .map_err(|e| NetEvalError::Load(e.to_string()))?,
            // `.error_on_failure()` is LOAD-BEARING, not defensive. ORT's default is
            // to log a provider-registration failure and silently fall back to CPU.
            // That fail-open produced a bogus first reading of this very bench: the
            // rc.13 `download-binaries` onnxruntime is built against CUDA 13, this
            // box has CUDA 12, the provider failed to load, and the "cuda" and
            // "cuda+graph" rows both quietly measured the CPU — reading ~4.6 ms
            // batch-1 and being indistinguishable from each other, which is the
            // tell. A measurement that cannot fail loudly will eventually report the
            // wrong device, which is precisely what `coreml_evaluator.
            // resolve_net_backend` refuses to permit on the Python side.
            // Two CUDA-EP knobs are exposed by env var rather than hard-coded,
            // because both are plausible wins for a conv stack and neither should be
            // adopted on plausibility. Both DEFAULT OFF, matching ORT's own defaults.
            // (Conv ALGORITHM search is deliberately not exposed at all — `ort`'s
            // default is already `Exhaustive`.)
            //
            // ⚠️⚠️ `CARC_ORT_FUSE_CONV_BIAS=1` IS MEASURED WRONG ON THIS BOX — DO NOT
            // ENABLE IT. It looks like a free ~3% at batch 8, and it is the most
            // dangerous kind of result: the forward gets faster and the OUTPUT GOES
            // GARBAGE, silently. Measured 2026-08-03, all three CUDA backends, 1168
            // corpus positions: argmax agreement collapses 100.00% -> ~30%, max-abs
            // residual 4.9e-4 -> 1.0. Nothing raises; ORT reports success. It is left
            // wired up, default-off, precisely so the trap is discoverable and
            // re-testable after an onnxruntime upgrade instead of being rediscovered
            // by someone reading the option list and assuming it is free. The same
            // session first mis-attributed this to `use_tf32=0`, because the knob was
            // briefly defaulted ON and contaminated the TF32 control — which is why
            // every knob row in the readout is paired with a faithfulness row.
            // `prefer_nhwc` is merely SLOWER here (1.22 -> 1.53 ms/leaf-batch at 64),
            // not wrong.
            Backend::Cuda | Backend::CudaBound | Backend::CudaGraph => builder
                .with_execution_providers([CUDA::default()
                    .with_cuda_graph(backend == Backend::CudaGraph)
                    .with_tf32(tf32)
                    .with_prefer_nhwc(std::env::var("CARC_ORT_NHWC").as_deref() == Ok("1"))
                    .with_fuse_conv_bias(std::env::var("CARC_ORT_FUSE_CONV_BIAS").as_deref() == Ok("1"))
                    .build()
                    .error_on_failure()])
                .map_err(|e| NetEvalError::Load(format!("CUDA EP did not register: {e}")))?,
        };

        let mut session = builder
            .commit_from_file(model_path)
            .map_err(|e| NetEvalError::Load(format!("{model_path}: {e}")))?;

        let bound = if backend.is_bound() {
            Some(Self::make_bound(&mut session, rep, batch)?)
        } else {
            None
        };

        let mut ev = OrtPolicyEvaluator {
            session,
            rep,
            batch,
            backend,
            logits: vec![0.0; batch * rep.action_size],
            bound,
            tf32,
            explicit_sync: std::env::var("CARC_ORT_EXPLICIT_SYNC").as_deref() == Ok("1"),
        };

        // Validate by PROBE FORWARD rather than by reading the graph's declared
        // shapes. It is the stronger check — it proves the model actually accepts
        // this representation at this batch and returns the action width we will
        // index — and it is the check that catches the failure that matters: a
        // silent rep mismatch yields plausible-looking garbage priors, not an error
        // (the Rust twin of `_validate_fair_net_prior_dims`). It also warms the
        // CUDA-graph capture, which ORT performs on the first run.
        let zb = vec![0.0f32; batch * rep.board_stride()];
        let zs = vec![0.0f32; batch * rep.n_scalars];
        let got = ev.logits_batch(&zb, &zs)?.len();
        if got != batch * rep.action_size {
            return Err(NetEvalError::Shape(format!(
                "model returned {got} logits, expected {} ({batch} x {})",
                batch * rep.action_size,
                rep.action_size
            )));
        }
        Ok(ev)
    }

    /// Allocate the device-resident I/O and bind it once.
    ///
    /// T3 (device provenance) is asserted HERE as well as by `.error_on_failure()`,
    /// and the two checks are not redundant: `error_on_failure` proves the CUDA EP
    /// *registered*, while `memory_info().allocation_device()` proves the tensors we
    /// are about to time actually landed in **device** memory. ORT's
    /// `bind_output_to_device` in particular "will silently fall back to binding to
    /// CPU if the target device doesn't have an EP registered" (its own words) — a
    /// second fail-open in the same family as the one that produced the memo's bogus
    /// first reading.
    fn make_bound(session: &mut Session, rep: NetRep, batch: usize) -> Result<Bound, NetEvalError> {
        let load = |e: ort::Error| NetEvalError::Load(e.to_string());

        let dev_info = MemoryInfo::new(AllocationDevice::CUDA, 0, AllocatorType::Device, MemoryType::Default)
            .map_err(load)?;
        let dev_alloc = Allocator::new(session, dev_info).map_err(load)?;

        let board_dev =
            Tensor::<f32>::new(&dev_alloc, [batch, rep.n_channels, rep.window, rep.window]).map_err(load)?;
        let scalars_dev = Tensor::<f32>::new(&dev_alloc, [batch, rep.n_scalars]).map_err(load)?;

        for (name, t) in [("board", &board_dev), ("scalars", &scalars_dev)] {
            let dev = t.memory_info().allocation_device();
            if dev != AllocationDevice::CUDA {
                return Err(NetEvalError::Load(format!(
                    "T3: input '{name}' allocated on {dev:?}, not CUDA — device-resident binding did not take"
                )));
            }
        }

        let mut binding = session.create_binding().map_err(load)?;
        // Bind ONCE. Because these values already live on the target device, ORT
        // records their pointers rather than copying — so in-place refreshes of
        // their contents are seen by later runs, and the captured graph stays valid.
        binding.bind_input("board", &board_dev).map_err(load)?;
        binding.bind_input("scalars", &scalars_dev).map_err(load)?;
        // Output to the device, so nothing in the captured region touches host
        // memory. ORT allocates one buffer and reuses it across runs.
        let out_info = MemoryInfo::new(AllocationDevice::CUDA, 0, AllocatorType::Device, MemoryType::Default)
            .map_err(load)?;
        binding
            .bind_output_to_device("policy_logits", &out_info)
            .map_err(load)?;

        Ok(Bound {
            binding,
            board_dev,
            scalars_dev,
            dev_alloc,
        })
    }

    pub fn backend(&self) -> Backend {
        self.backend
    }

    /// Whether the CUDA EP ran with TF32 enabled. Reported, not gated (§5 T2).
    pub fn tf32(&self) -> bool {
        self.tf32
    }

    /// Refresh the device-resident inputs from host slices, in place. Bound backends
    /// only.
    ///
    /// In place is the point: the graph captured on the first forward holds these
    /// exact device addresses, so overwriting the contents is what makes a replay
    /// see new data. Re-allocating or re-binding would invalidate the capture.
    ///
    /// This is a real, blocking H2D of ~1.6 MB at batch 8, and the bench reports it
    /// **separately** from the forward — both because a shipping integration would
    /// make it async out of pinned staging, and because the memo's torch reference
    /// (`graph.replay()` between two `cuda.synchronize()` calls, inputs already
    /// resident) does not include it either. Folding it in would compare two
    /// different quantities.
    pub fn upload(&mut self, boards: &[f32], scalars: &[f32]) -> Result<(), NetEvalError> {
        let rep = self.rep;
        let batch = self.batch;
        let b = self
            .bound
            .as_mut()
            .ok_or_else(|| NetEvalError::Forward("upload() requires a bound backend".into()))?;
        if boards.len() != batch * rep.board_stride() || scalars.len() != batch * rep.n_scalars {
            return Err(NetEvalError::Shape("upload(): input slice length mismatch".into()));
        }
        let err = |e: String| NetEvalError::Forward(e);
        unsafe {
            cudart::memcpy(
                b.board_dev.data_ptr_mut(),
                boards.as_ptr().cast(),
                core::mem::size_of_val(boards),
                cudart::H2D,
            )
            .map_err(err)?;
            cudart::memcpy(
                b.scalars_dev.data_ptr_mut(),
                scalars.as_ptr().cast(),
                core::mem::size_of_val(scalars),
                cudart::H2D,
            )
            .map_err(err)?;
        }
        Ok(())
    }

    /// Run the bound graph over whatever is already in the device input buffers, and
    /// leave the logits on the device. Bound backends only.
    ///
    /// **This is the number that answers the spike's pre-registered bar**, because it
    /// is the same quantity the torch reference measured: `graph.replay()` between
    /// two `cuda.synchronize()` calls, inputs already device-resident, no copies
    /// (`scratchpad/bench_torch_fwd.py`). ORT's `Run` synchronizes the EP's stream
    /// before returning unless `disable_device_sync` is set, which it is not here, so
    /// the two timings bracket the same work.
    /// ⚠️ **A latency number is only honest if the clock brackets GPU *completion*,
    /// not just kernel *launch*.** ORT's `Run` synchronizes the EP stream before
    /// returning, so it should — but "should" is how the memo's first CUDA reading
    /// got written, so set `CARC_ORT_EXPLICIT_SYNC=1` to append an explicit
    /// `SynchronizeBoundOutputs` and confirm the number does not move. (Measured
    /// 2026-08-03: it does not — see the spike's control row.)
    pub fn forward_bound(&mut self) -> Result<(), NetEvalError> {
        let explicit_sync = self.explicit_sync;
        let b = self
            .bound
            .as_ref()
            .ok_or_else(|| NetEvalError::Forward("forward_bound() requires a bound backend".into()))?;
        let _outputs = self
            .session
            .run_binding(&b.binding)
            .map_err(|e| NetEvalError::Forward(e.to_string()))?;
        drop(_outputs);
        if explicit_sync {
            let b = self.bound.as_ref().expect("checked above");
            b.binding
                .synchronize_outputs()
                .map_err(|e| NetEvalError::Forward(e.to_string()))?;
        }
        Ok(())
    }

    /// Run the bound graph and bring the logits back to the host.
    fn logits_bound(&mut self, boards: &[f32], scalars: &[f32]) -> Result<&[f32], NetEvalError> {
        self.upload(boards, scalars)?;
        // Disjoint field borrows: `run_binding` holds `self.session` mutably and
        // `self.bound` shared for the lifetime of `outputs`; `self.logits` is a
        // different field, so the D2H below does not fight the borrow checker.
        let bound = self.bound.as_ref().expect("checked by upload()");
        let outputs = self
            .session
            .run_binding(&bound.binding)
            .map_err(|e| NetEvalError::Forward(e.to_string()))?;
        let dev_out = &outputs["policy_logits"];
        // T3 again, on the output this time: `bind_output_to_device` silently falls
        // back to CPU if the target device has no EP registered (ORT's own words),
        // and a host-resident output would mean the captured region touched host
        // memory. Check rather than assume.
        let where_ = dev_out.memory_info().allocation_device();
        if where_ != AllocationDevice::CUDA {
            return Err(NetEvalError::Forward(format!(
                "T3: bound output landed on {where_:?}, not CUDA"
            )));
        }
        unsafe {
            cudart::memcpy(
                self.logits.as_mut_ptr().cast(),
                dev_out.data_ptr(),
                core::mem::size_of_val(&self.logits[..]),
                cudart::D2H,
            )
            .map_err(NetEvalError::Forward)?;
        }
        Ok(&self.logits)
    }

    /// Raw logits for a full batch — the forward with NO host-side masking, which is
    /// what the r micro-bench should time (masking is O(A) memory traffic the
    /// classical path does not pay for and would smear the device comparison).
    pub fn logits_batch(
        &mut self,
        boards: &[f32],
        scalars: &[f32],
    ) -> Result<&[f32], NetEvalError> {
        if self.backend.is_bound() {
            return self.logits_bound(boards, scalars);
        }
        let n = self.batch;
        let bshape = [n as i64, self.rep.n_channels as i64, self.rep.window as i64, self.rep.window as i64];
        let sshape = [n as i64, self.rep.n_scalars as i64];

        let bt = TensorRef::from_array_view((bshape, boards))
            .map_err(|e| NetEvalError::Forward(e.to_string()))?;
        let st = TensorRef::from_array_view((sshape, scalars))
            .map_err(|e| NetEvalError::Forward(e.to_string()))?;

        let outputs = self
            .session
            .run(ort::inputs!["board" => bt, "scalars" => st])
            .map_err(|e| NetEvalError::Forward(e.to_string()))?;

        let (_shape, data) = outputs["policy_logits"]
            .try_extract_tensor::<f32>()
            .map_err(|e| NetEvalError::Forward(e.to_string()))?;
        self.logits.copy_from_slice(data);
        Ok(&self.logits)
    }
}

impl PolicyEvaluator for OrtPolicyEvaluator {
    fn rep(&self) -> NetRep {
        self.rep
    }

    fn max_batch(&self) -> usize {
        self.batch
    }

    fn policy_batch(
        &mut self,
        boards: &[f32],
        scalars: &[f32],
        masks: &[bool],
        n: usize,
        out: &mut [f32],
    ) -> Result<(), NetEvalError> {
        if n != self.batch {
            return Err(NetEvalError::Shape(format!(
                "this evaluator is pinned to batch {} (fixed-shape ONNX); got {n}",
                self.batch
            )));
        }
        let a = self.rep.action_size;
        if boards.len() != n * self.rep.board_stride()
            || scalars.len() != n * self.rep.n_scalars
            || masks.len() != n * a
            || out.len() != n * a
        {
            return Err(NetEvalError::Shape("input/output slice length mismatch".into()));
        }

        self.logits_batch(boards, scalars)?;
        // Mask on the HOST, in f32 — `coreml_evaluator`'s DESIGN DECISION 1, for the
        // same reasons: it keeps the graph a pure conv+FC stack (op coverage, and on
        // an accelerator, on-device residency), and it keeps the only numerical
        // difference vs torch the rounding of the logits themselves.
        for i in 0..n {
            let lo = i * a;
            let hi = lo + a;
            // Split the borrow: `self.logits` is read while `out` is written.
            let row = &self.logits[lo..hi];
            masked_softmax(row, &masks[lo..hi], &mut out[lo..hi]);
        }
        Ok(())
    }
}
