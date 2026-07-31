//! `carc-core` — pure-Rust Carcassonne engine + search core.
//!
//! **No pyo3 here.** The crate must stay buildable for WASM/iOS targets (spec
//! "Out of scope (v1)": the architecture must not preclude them). Python bindings
//! live in the sibling `carc-py` crate.
//!
//! P0 ships only [`compat`], the determinism substrate that every later phase is
//! measured against. Engine, leaf, search and the fair agent land in P1–P4.

#![forbid(unsafe_code)]

pub mod compat;

/// Crate version, surfaced through the Python module for provenance stamping.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
