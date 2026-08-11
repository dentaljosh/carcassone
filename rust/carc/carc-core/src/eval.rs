//! `eval` — the neural-evaluator seam for the search core.
//!
//! **This module deliberately adds ZERO dependencies.** `carc-core` must stay
//! WASM/iOS-buildable (see the crate docs), which is precisely why no inference
//! runtime — not `ort`, not `tch`, not `candle`, not `tract` — may ever appear in
//! this crate's `Cargo.toml`. What lives here is the *trait*; every implementation
//! lives in a sibling crate that `carc-core` does not depend on. The dependency
//! arrow points **into** `carc-core`, never out of it.
//!
//! ## What a net evaluator replaces
//!
//! The classical evaluator ([`crate::search::Searcher::evaluate`]) builds its PUCT
//! priors from a *child sweep*: it clones the game once per legal action, advances
//! it, and takes a leaf evaluation of each afterstate — `1 + |legal|` leaf calls
//! per expansion (**measured ~9.6 on average**, `examples/evalprobe.rs`). The
//! `fair-netprior` arm replaces that entire sweep with **one network forward** for
//! the priors, keeping the frozen champion leaf for the *value* only — so per
//! expansion it pays `1` leaf call plus one forward instead of `1 + |legal|` leaf
//! calls and `|legal|` game clones.
//!
//! This is the fact that makes the python-era cost model wrong for the port. The
//! CL-067 gate's reopen condition
//! (`measurement/classical_search/NETPRIOR_EQTIME_GATE_20260728.md` §6) is stated as
//!
//! > REOPEN … when the target device's measured `r = forward_ms / search_ms_per_sim`
//! > is <= ~1.5
//!
//! which models the forward as **purely additive** on top of an unchanged search.
//! In Python that was a fair approximation: at 4.2 ms the forward dwarfed everything
//! it displaced. In Rust the displaced child sweep is a large fraction of the
//! per-simulation cost, so the honest quantity is the **per-move cost ratio**, and
//! `r` is only its upper bound. See `docs/RUST_NET_EVAL_DESIGN_20260802.md` §3.
//!
//! ## Acceptance
//!
//! Implementations are NOT expected to be bit-identical to torch — cross-framework
//! float identity is not achievable, and the project has already priced that:
//! `src/carcassonne_ai/coreml_evaluator.py` accepts its ANE backend on
//! **argmax + top-5 agreement** with a reported max-abs residual, not on equality.
//! [`FaithfulnessReport`] is the shape of that acceptance evidence, so a backend
//! swap produces the same readout the CoreML path already produces.

use core::fmt;

/// The action-space width for `window_size = 25` (`25*25*4 + 11`). An evaluator
/// whose model disagrees with this must fail loudly at construction rather than
/// silently mis-index priors.
pub const ACTION_SIZE: usize = 2511;

/// Board-plane geometry of the sighted representation the current nets use.
pub const WINDOW: usize = 25;

/// What went wrong in a forward. Deliberately a `String` payload: `carc-core` must
/// not know the error types of runtimes it does not depend on.
#[derive(Debug, Clone)]
pub enum NetEvalError {
    /// The model's declared shapes disagree with the caller's representation.
    Shape(String),
    /// The backend failed at load time.
    Load(String),
    /// The backend failed during a forward.
    Forward(String),
}

impl fmt::Display for NetEvalError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            NetEvalError::Shape(s) => write!(f, "net eval shape error: {s}"),
            NetEvalError::Load(s) => write!(f, "net eval load error: {s}"),
            NetEvalError::Forward(s) => write!(f, "net eval forward error: {s}"),
        }
    }
}

/// The representation a net expects. Checked against the checkpoint's own
/// `n_input_channels` / `n_scalar_features` at construction — the Rust twin of
/// `heuristic_prior_mcts._validate_fair_net_prior_dims`, which exists because a
/// silent rep mismatch produces plausible-looking garbage priors rather than an
/// error.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct NetRep {
    pub n_channels: usize,
    pub n_scalars: usize,
    pub window: usize,
    pub action_size: usize,
}

impl NetRep {
    /// The sighted 81ch / 42-scalar representation used by the CL-067 distilled
    /// nets and by every current `fair-netprior` checkpoint.
    pub const SIGHTED: NetRep = NetRep {
        n_channels: 81,
        n_scalars: 42,
        window: WINDOW,
        action_size: ACTION_SIZE,
    };

    /// Floats per board plane-stack, for buffer sizing.
    pub const fn board_stride(&self) -> usize {
        self.n_channels * self.window * self.window
    }
}

/// A batched policy-prior forward.
///
/// The contract mirrors `evaluators.make_single_evaluator_policy_only` /
/// `make_batch_evaluator_policy_only`: **masked** priors over the action space,
/// with illegal actions exactly `0.0`, summing to 1 over the legal set. The value
/// is NOT part of this trait — the `fair-netprior` arm takes its value from the
/// frozen champion leaf, and an evaluator that also returned a value would invite
/// exactly the severed-value confusion CL-067 was designed to avoid.
///
/// Inputs are **pre-encoded** rather than `&Game`. That is a deliberate scoping
/// choice for the prototype: the board encoder (`board_repr.encode_board`, 81
/// planes) is still Python/Cython and porting it is a separate, sizeable work item
/// (see the design memo §6). Taking tensors keeps this seam honest about what has
/// and has not been ported, and it is exactly the interface the faithfulness
/// harness needs to feed torch and the backend byte-identical inputs.
pub trait PolicyEvaluator {
    /// The representation this evaluator was built for.
    fn rep(&self) -> NetRep;

    /// The largest batch a single call may carry. The SHM transport's `MAX_K = 8`
    /// is the production analogue; batching beyond the natural k-determinization
    /// width buys throughput, not latency.
    fn max_batch(&self) -> usize;

    /// Run one forward over `n` boards.
    ///
    /// * `boards`   — `n * rep().board_stride()` floats, C-order `(n, C, W, W)`.
    /// * `scalars`  — `n * rep().n_scalars` floats.
    /// * `masks`    — `n * rep().action_size` legality flags.
    /// * `out`      — `n * rep().action_size` floats, overwritten with masked priors.
    fn policy_batch(
        &mut self,
        boards: &[f32],
        scalars: &[f32],
        masks: &[bool],
        n: usize,
        out: &mut [f32],
    ) -> Result<(), NetEvalError>;
}

/// Reference masked softmax — the float32 twin of `network.policy_softmax_with_mask`.
///
/// Same three steps as `F.softmax(logits.masked_fill(~mask, -inf))`: subtract the
/// max over the LEGAL entries, exponentiate, normalise. The normalising sum is
/// accumulated in `f64` before the `f32` divide, matching the deliberate choice in
/// `coreml_evaluator.masked_softmax_np` — reproducible across builds, where a
/// SIMD-width-dependent `f32` reduction is not. Illegal entries are written as
/// exactly `0.0`.
///
/// An all-illegal row is NOT special-cased; it yields zeros, and callers never
/// produce one because only non-terminal boards are evaluated.
pub fn masked_softmax(logits: &[f32], mask: &[bool], out: &mut [f32]) {
    debug_assert_eq!(logits.len(), mask.len());
    debug_assert_eq!(logits.len(), out.len());

    let mut mx = f32::NEG_INFINITY;
    for (i, &m) in mask.iter().enumerate() {
        if m && logits[i] > mx {
            mx = logits[i];
        }
    }
    if !mx.is_finite() {
        for o in out.iter_mut() {
            *o = 0.0;
        }
        return;
    }
    let mut sum = 0.0f64;
    for i in 0..logits.len() {
        if mask[i] {
            let e = (logits[i] - mx).exp();
            out[i] = e;
            sum += e as f64;
        } else {
            out[i] = 0.0;
        }
    }
    let s = sum as f32;
    for i in 0..out.len() {
        if mask[i] {
            out[i] /= s;
        }
    }
}

/// Argmax over the LEGAL entries of a prior row. `None` if nothing is legal.
///
/// Ties resolve to the lowest index, which is what `np.argmax` does, so the
/// faithfulness harness compares like with like.
pub fn legal_argmax(priors: &[f32], mask: &[bool]) -> Option<usize> {
    let mut best: Option<(usize, f32)> = None;
    for i in 0..priors.len() {
        if !mask[i] {
            continue;
        }
        match best {
            Some((_, bv)) if priors[i] <= bv => {}
            _ => best = Some((i, priors[i])),
        }
    }
    best.map(|(i, _)| i)
}

/// The acceptance evidence a backend must produce before it may be believed.
///
/// Modelled on `scripts/m5_bench/verify_coreml_evaluator.py`'s readout: report
/// agreement rates and a residual magnitude, never assert equality. See the design
/// memo §5 for the tier definitions these fields feed.
#[derive(Debug, Clone, Default)]
pub struct FaithfulnessReport {
    pub n: usize,
    /// Rows whose legal-argmax matches the reference exactly.
    pub argmax_agree: usize,
    /// Rows whose top-5 legal actions match the reference as an ordered list.
    pub top5_agree: usize,
    /// Rows byte-identical to the reference (expected to be ~0; recorded, not required).
    pub bitexact: usize,
    /// Largest absolute prior difference seen over all rows.
    pub max_abs_diff: f64,
    /// Largest total-variation distance (0.5 * L1) over all rows.
    pub max_tv: f64,
}

impl FaithfulnessReport {
    pub fn argmax_rate(&self) -> f64 {
        if self.n == 0 {
            0.0
        } else {
            self.argmax_agree as f64 / self.n as f64
        }
    }
    pub fn top5_rate(&self) -> f64 {
        if self.n == 0 {
            0.0
        } else {
            self.top5_agree as f64 / self.n as f64
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn masked_softmax_zeroes_illegal_and_normalises_legal() {
        let logits = [1.0f32, 5.0, 2.0, 9.0];
        let mask = [true, false, true, false];
        let mut out = [0.0f32; 4];
        masked_softmax(&logits, &mask, &mut out);
        assert_eq!(out[1], 0.0);
        assert_eq!(out[3], 0.0);
        let s: f32 = out.iter().sum();
        assert!((s - 1.0).abs() < 1e-6, "sum was {s}");
        // The big logits are illegal, so the legal argmax is index 2, not 3.
        assert_eq!(legal_argmax(&out, &mask), Some(2));
    }

    #[test]
    fn masked_softmax_is_shift_invariant() {
        let a = [0.5f32, -3.0, 7.25, 0.0];
        let mask = [true, true, true, true];
        let mut oa = [0.0f32; 4];
        let mut ob = [0.0f32; 4];
        masked_softmax(&a, &mask, &mut oa);
        let b: Vec<f32> = a.iter().map(|v| v + 100.0).collect();
        masked_softmax(&b, &mask, &mut ob);
        for i in 0..4 {
            assert!((oa[i] - ob[i]).abs() < 1e-6);
        }
    }

    #[test]
    fn all_illegal_row_is_zeros_not_nan() {
        let logits = [1.0f32, 2.0];
        let mask = [false, false];
        let mut out = [0.0f32; 2];
        masked_softmax(&logits, &mask, &mut out);
        assert_eq!(out, [0.0, 0.0]);
        assert_eq!(legal_argmax(&out, &mask), None);
    }

    #[test]
    fn legal_argmax_breaks_ties_low() {
        let p = [0.25f32, 0.25, 0.25, 0.25];
        let mask = [false, true, true, true];
        assert_eq!(legal_argmax(&p, &mask), Some(1));
    }

    #[test]
    fn sighted_rep_matches_the_checkpoints_of_record() {
        assert_eq!(NetRep::SIGHTED.board_stride(), 81 * 25 * 25);
        assert_eq!(NetRep::SIGHTED.action_size, ACTION_SIZE);
    }
}
