//! `carc-core` — pure-Rust Carcassonne engine + search core.
//!
//! **No pyo3 here.** The crate must stay buildable for WASM/iOS targets (spec
//! "Out of scope (v1)": the architecture must not preclude them). Python bindings
//! live in the sibling `carc-py` crate.
//!
//! P0 ships [`compat`], the determinism substrate that every later phase is
//! measured against. P1 adds the engine vertical slice — [`tiles`], [`engine`],
//! [`action_space`], [`repr_key`] and the [`game`] mirror state. Leaf, search
//! and the fair agent land in P2–P4.

#![forbid(unsafe_code)]

pub mod action_space;
pub mod compat;
pub mod endgame;
pub mod engine;
pub mod eval;
pub mod fair;
pub mod game;
pub mod leaf;
pub mod repr_key;
pub mod search;
pub mod sha256;
/// The `tier1-greedy` continuation playout — the tiearb2 arbiter's cost core.
/// Purely additive (Stage 2 Phase A); nothing pre-existing routes through it.
pub mod tier1;
pub mod tiles;

/// Crate version, surfaced through the Python module for provenance stamping.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
