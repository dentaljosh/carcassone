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
use ort::session::Session;
use ort::value::TensorRef;

pub mod positions;

/// Which device the evaluator runs on. Recorded on the evaluator and stamped into
/// bench output, because "a forward measured on the wrong device" is exactly the
/// failure `coreml_evaluator.resolve_net_backend` refuses to allow silently.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Backend {
    /// ORT CPU execution provider, `intra_threads` as configured.
    Cpu(usize),
    /// ORT CUDA execution provider, eager (kernel launches per forward).
    Cuda,
    /// ORT CUDA execution provider with CUDA-Graph capture (static shapes only).
    CudaGraph,
}

impl Backend {
    pub fn label(&self) -> String {
        match self {
            Backend::Cpu(t) => format!("cpu(threads={t})"),
            Backend::Cuda => "cuda".to_string(),
            Backend::CudaGraph => "cuda+graph".to_string(),
        }
    }
}

/// An ORT-backed policy evaluator over a fixed-batch ONNX policy graph.
pub struct OrtPolicyEvaluator {
    session: Session,
    rep: NetRep,
    batch: usize,
    backend: Backend,
    /// Scratch for the raw logits ORT hands back, so `policy_batch` allocates nothing.
    logits: Vec<f32>,
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
            Backend::Cuda => builder
                .with_execution_providers([CUDA::default()
                    .with_cuda_graph(false)
                    .build()
                    .error_on_failure()])
                .map_err(|e| NetEvalError::Load(format!("CUDA EP did not register: {e}")))?,
            Backend::CudaGraph => builder
                .with_execution_providers([CUDA::default()
                    .with_cuda_graph(true)
                    .build()
                    .error_on_failure()])
                .map_err(|e| NetEvalError::Load(format!("CUDA EP did not register: {e}")))?,
        };

        let session = builder
            .commit_from_file(model_path)
            .map_err(|e| NetEvalError::Load(format!("{model_path}: {e}")))?;

        let mut ev = OrtPolicyEvaluator {
            session,
            rep,
            batch,
            backend,
            logits: vec![0.0; batch * rep.action_size],
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

    pub fn backend(&self) -> Backend {
        self.backend
    }

    /// Raw logits for a full batch — the forward with NO host-side masking, which is
    /// what the r micro-bench should time (masking is O(A) memory traffic the
    /// classical path does not pay for and would smear the device comparison).
    pub fn logits_batch(
        &mut self,
        boards: &[f32],
        scalars: &[f32],
    ) -> Result<&[f32], NetEvalError> {
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
