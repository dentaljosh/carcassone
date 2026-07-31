//! `compat` — the determinism substrate.
//!
//! The Rust port must reproduce the *Python program's* arithmetic, not merely
//! compute the same mathematical quantity. Four primitives carry that burden:
//!
//! | module | reproduces | gate |
//! |---|---|---|
//! | [`mt19937`] | CPython `random` (seeding, `getrandbits`, `_randbelow`, `shuffle`) | `reconcile_mt19937.py` |
//! | [`fsum`] | `math.fsum` (Shewchuk partials) | `reconcile_fsum.py` |
//! | [`npsum`] | `np.sum` (numpy pairwise, f32 + f64) | `reconcile_npsum.py` |
//! | [`libm_compat`] | `exp` / `tanh` (ARM optimized-routines / fdlibm) | `harness_transcendental.py` |
//!
//! The first three are **bit-exact by construction** — they are ports of a known
//! algorithm with no platform freedom. The fourth is a *hypothesis about the
//! platform*: the gate measures whether the local `np.exp` / `math.tanh` really
//! are these implementations, and the spec's pre-registered fallback covers the
//! case where they are not.

pub mod exp_data;
pub mod fsum;
pub mod libm_compat;
pub mod mt19937;
pub mod npsum;

pub use fsum::{fsum, FsumAccum};
pub use libm_compat::{exp64, exp64_fma, expm1_64, tanh64};
pub use mt19937::{shuffle_indices, SeedMode, MT19937};
pub use npsum::{np_sum_f32, np_sum_f64, pairwise_sum_f32, pairwise_sum_f64};
