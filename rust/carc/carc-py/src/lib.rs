//! `carc_rs` — PyO3 bindings for `carc-core`.
//!
//! P0 exposed the `compat` primitives. P1 adds [`MirrorState`] — the engine
//! mirror advanced by action ints, which is the wire format the reconcile
//! scripts drive. `FairAgentRs` / `choose_action` land with P3–P4.

use carc_core::compat;
use carc_core::game::{deck_from_descriptions, deck_from_seed, Game};
use carc_core::tiles;
use pyo3::prelude::*;
use pyo3::types::PyBytes;

// --------------------------------------------------------------------------
// P1: the engine mirror state
// --------------------------------------------------------------------------

/// A Rust-side Carcassonne game advanced by flat action indices.
///
/// The constructor mirrors the two replay entry points in the spec:
/// `MirrorState.from_seed(deck_seed)` (CPython-MT-compatible deck shuffle) and
/// `MirrorState.from_deck([...])` (explicit deck; no RNG dependence, the phone
/// path).  `advance(action)` is called for **every** applied action, both seats.
#[pyclass(name = "MirrorState")]
struct PyMirrorState {
    game: Game,
}

#[pymethods]
impl PyMirrorState {
    /// `random.seed(deck_seed); Game().get_init_board()`.
    ///
    /// `deck_seed` is a **decimal string** so arbitrary-precision CPython ints
    /// round-trip (see the G0 mt19937 gate).
    #[staticmethod]
    #[pyo3(signature = (deck_seed, window_size=25))]
    fn from_seed(deck_seed: &str, window_size: i32) -> PyResult<Self> {
        Ok(PyMirrorState {
            game: Game::from_deck_with_window(deck_from_seed(deck_seed), window_size),
        })
    }

    /// Build from an explicit deck of tile descriptions, in draw order.
    #[staticmethod]
    #[pyo3(signature = (descriptions, window_size=25))]
    fn from_deck(descriptions: Vec<String>, window_size: i32) -> PyResult<Self> {
        let deck = deck_from_descriptions(&descriptions)
            .map_err(pyo3::exceptions::PyValueError::new_err)?;
        Ok(PyMirrorState {
            game: Game::from_deck_with_window(deck, window_size),
        })
    }

    /// Apply one flat action index.
    fn advance(&mut self, action: i32) -> PyResult<()> {
        self.game
            .advance(action)
            .map_err(pyo3::exceptions::PyValueError::new_err)
    }

    /// The exact `Game.string_representation` bytes.
    fn string_repr(&self) -> String {
        self.game.string_repr()
    }

    /// `hashlib.sha256(get_valid_moves(board).tobytes()).hexdigest()`.
    fn legal_mask_sha256(&self) -> String {
        self.game.legal_mask_sha256()
    }

    /// The legal mask as raw bytes (one `0`/`1` per action index).
    fn legal_mask_bytes<'py>(&self, py: Python<'py>) -> Bound<'py, PyBytes> {
        PyBytes::new(py, &self.game.legal_mask().mask)
    }

    fn legal_actions(&self) -> Vec<i32> {
        self.game.legal_actions()
    }

    /// `(n_total, n_overflow)` from the mask build — the two counters
    /// `Game._compute_mask` uses for its `WindowOverflowError` conditions.
    fn mask_counts(&self) -> (usize, usize) {
        let m = self.game.legal_mask();
        (m.n_total, m.n_overflow)
    }

    fn scores(&self) -> (i64, i64) {
        let s = self.game.scores();
        (s[0], s[1])
    }

    fn meeples(&self) -> (i32, i32) {
        (self.game.state.meeples[0], self.game.state.meeples[1])
    }

    fn is_terminal(&self) -> bool {
        self.game.is_terminal()
    }

    fn current_player(&self) -> usize {
        self.game.state.current_player
    }

    fn phase(&self) -> &'static str {
        self.game.state.phase.value()
    }

    fn deck_len(&self) -> usize {
        self.game.state.deck_len()
    }

    /// `flat_leaf.flat_base_score(state, player)` — the exact terminal leaf.
    #[pyo3(signature = (player=0))]
    fn flat_base_score(&self, player: usize) -> i64 {
        self.game.flat_base_score(player)
    }

    /// `(origin_row, origin_col, size)` of the centered window.
    fn window_offset(&self) -> (i32, i32, i32) {
        let o = self.game.offset;
        (o.origin_row, o.origin_col, o.size)
    }

    /// A short content digest over repr + mask + scores + offset + terminal.
    fn state_digest(&self) -> String {
        self.game.state_digest()
    }
}

/// The deck `random.seed(deck_seed)` produces, as tile descriptions in draw
/// order (index 0 is the tile immediately drawn into `next_tile`).
#[pyfunction]
fn deck_descriptions_from_seed(deck_seed: &str) -> Vec<String> {
    deck_from_seed(deck_seed)
        .into_iter()
        .map(|b| tiles::tile(tiles::tile_id(b, 0)).description.to_string())
        .collect()
}

/// `(source_sha256, semantic_digest)` compiled into `tiles/generated.rs` — the
/// drift guard against `engine/.../base_deck.py`.
#[pyfunction]
fn tile_data_digests() -> (String, String) {
    (
        tiles::generated::SOURCE_SHA256.to_string(),
        tiles::generated::SEMANTIC_DIGEST.to_string(),
    )
}

/// Every rotated tile as `(description, rot, edge_type_repr_signature)` — used
/// by the tile-rotation reconcile against `Tile.turn` + `get_type`.
#[pyfunction]
fn rotated_tile_table() -> Vec<(String, u8, String)> {
    tiles::registry()
        .iter()
        .map(|t| (t.description.to_string(), t.rot, t.rot_sig_repr.clone()))
        .collect()
}

// --------------------------------------------------------------------------
// mt19937
// --------------------------------------------------------------------------

/// `random.seed(seed); random.shuffle(list(range(n)))` — the resulting permutation.
///
/// `seed` is a **decimal string** so arbitrary-precision CPython int seeds
/// (>= 2^64) round-trip exactly. `mode` is `"global"` or `"random"`.
#[pyfunction]
#[pyo3(signature = (seed, n, mode="global"))]
fn shuffle_indices(seed: &str, n: usize, mode: &str) -> PyResult<Vec<u32>> {
    let m = match mode {
        "global" => compat::SeedMode::GlobalSeed,
        "random" => compat::SeedMode::RandomInstance,
        other => {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "mode must be 'global' or 'random', got {other:?}"
            )))
        }
    };
    Ok(compat::shuffle_indices(seed, m, n))
}

/// The little-endian 32-bit word vector CPython's `random_seed()` builds.
#[pyfunction]
fn seed_words(seed: &str) -> Vec<u32> {
    compat::mt19937::seed_words_from_decimal(seed)
}

/// `[genrand_uint32() for _ in range(count)]` after seeding with `seed`.
#[pyfunction]
fn genrand_uint32_stream(seed: &str, count: usize) -> Vec<u32> {
    let mut mt = compat::MT19937::from_py_int_seed_decimal(seed);
    (0..count).map(|_| mt.genrand_uint32()).collect()
}

/// `[getrandbits(k) for k in ks]` after seeding with `seed` (`k <= 64`).
#[pyfunction]
fn getrandbits_stream(seed: &str, ks: Vec<u32>) -> Vec<u64> {
    let mut mt = compat::MT19937::from_py_int_seed_decimal(seed);
    ks.into_iter().map(|k| mt.getrandbits(k)).collect()
}

/// `[_randbelow(n) for n in ns]` after seeding with `seed`.
#[pyfunction]
fn randbelow_stream(seed: &str, ns: Vec<u64>) -> Vec<u64> {
    let mut mt = compat::MT19937::from_py_int_seed_decimal(seed);
    ns.into_iter().map(|n| mt.randbelow(n)).collect()
}

// --------------------------------------------------------------------------
// fsum / npsum
// --------------------------------------------------------------------------

/// `math.fsum(xs)`.
#[pyfunction]
fn fsum(xs: Vec<f64>) -> f64 {
    compat::fsum(&xs)
}

/// `math.fsum` applied to each row of a flat buffer of `n_rows * row_len` f64s.
/// Batched to keep the 10^6-case reconcile fuzz out of per-call FFI overhead.
#[pyfunction]
fn fsum_batch(flat: Vec<f64>, offsets: Vec<usize>) -> Vec<f64> {
    offsets
        .windows(2)
        .map(|w| compat::fsum(&flat[w[0]..w[1]]))
        .collect()
}

/// `np.sum(np.asarray(xs, dtype=np.float64))`.
#[pyfunction]
fn np_sum_f64(xs: Vec<f64>) -> f64 {
    compat::np_sum_f64(&xs)
}

/// `np.sum(np.asarray(xs, dtype=np.float32))`.
#[pyfunction]
fn np_sum_f32(xs: Vec<f32>) -> f32 {
    compat::np_sum_f32(&xs)
}

/// Batched `np.sum` over ragged f64 rows described by a prefix-offset array.
#[pyfunction]
fn np_sum_f64_batch(flat: Vec<f64>, offsets: Vec<usize>) -> Vec<f64> {
    offsets
        .windows(2)
        .map(|w| compat::np_sum_f64(&flat[w[0]..w[1]]))
        .collect()
}

/// Batched `np.sum` over ragged f32 rows described by a prefix-offset array.
#[pyfunction]
fn np_sum_f32_batch(flat: Vec<f32>, offsets: Vec<usize>) -> Vec<f32> {
    offsets
        .windows(2)
        .map(|w| compat::np_sum_f32(&flat[w[0]..w[1]]))
        .collect()
}

// --------------------------------------------------------------------------
// libm compat
// --------------------------------------------------------------------------

/// `exp(x)` — ARM optimized-routines port, no FMA contraction.
#[pyfunction]
fn exp64(x: f64) -> f64 {
    compat::exp64(x)
}

/// `exp(x)` — the same algorithm with FMA contraction (glibc `-mfma` variant).
#[pyfunction]
fn exp64_fma(x: f64) -> f64 {
    compat::exp64_fma(x)
}

/// `tanh(x)` — fdlibm port.
#[pyfunction]
fn tanh64(x: f64) -> f64 {
    compat::tanh64(x)
}

/// `expm1(x)` — fdlibm port (the kernel `tanh64` is built on).
#[pyfunction]
fn expm1_64(x: f64) -> f64 {
    compat::expm1_64(x)
}

fn parse_flavor(name: &str) -> PyResult<compat::LibmFlavor> {
    Ok(match name {
        "msun" => compat::LibmFlavor::Msun,
        "msun_fma" => compat::LibmFlavor::MsunFma,
        "glibc" => compat::LibmFlavor::Glibc,
        "glibc_fma" => compat::LibmFlavor::GlibcFma,
        other => {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "flavor must be one of msun|msun_fma|glibc|glibc_fma, got {other:?}"
            )))
        }
    })
}

/// `expm1(x)` under an explicit platform hypothesis.
#[pyfunction]
#[pyo3(signature = (x, flavor="msun"))]
fn expm1_64_flavor(x: f64, flavor: &str) -> PyResult<f64> {
    Ok(compat::expm1_64_flavor(x, parse_flavor(flavor)?))
}

/// `tanh(x)` under an explicit platform hypothesis.
#[pyfunction]
#[pyo3(signature = (x, flavor="msun"))]
fn tanh64_flavor(x: f64, flavor: &str) -> PyResult<f64> {
    Ok(compat::tanh64_flavor(x, parse_flavor(flavor)?))
}

/// The four platform hypotheses, in the order the harness reports them.
#[pyfunction]
fn libm_flavors() -> Vec<String> {
    ["msun", "msun_fma", "glibc", "glibc_fma"].iter().map(|s| s.to_string()).collect()
}

/// Vectorised `exp64` over a little-endian f64 byte buffer; returns the results
/// as a byte buffer. Buffer-in/buffer-out keeps the 10^8-sample harness from
/// paying Python list-boxing costs.
#[pyfunction]
fn exp64_buf<'py>(py: Python<'py>, xs: &[u8], fma: bool) -> PyResult<Bound<'py, PyBytes>> {
    map_f64_buf(py, xs, |v| if fma { compat::exp64_fma(v) } else { compat::exp64(v) })
}

/// Vectorised `tanh64` over a little-endian f64 byte buffer, under an explicit
/// platform hypothesis.
#[pyfunction]
#[pyo3(signature = (xs, flavor="msun"))]
fn tanh64_buf<'py>(py: Python<'py>, xs: &[u8], flavor: &str) -> PyResult<Bound<'py, PyBytes>> {
    let f = parse_flavor(flavor)?;
    map_f64_buf(py, xs, |v| compat::tanh64_flavor(v, f))
}

/// Vectorised `expm1` over a little-endian f64 byte buffer.
#[pyfunction]
#[pyo3(signature = (xs, flavor="msun"))]
fn expm1_64_buf<'py>(py: Python<'py>, xs: &[u8], flavor: &str) -> PyResult<Bound<'py, PyBytes>> {
    let f = parse_flavor(flavor)?;
    map_f64_buf(py, xs, |v| compat::expm1_64_flavor(v, f))
}

fn map_f64_buf<'py>(
    py: Python<'py>,
    xs: &[u8],
    f: impl Fn(f64) -> f64,
) -> PyResult<Bound<'py, PyBytes>> {
    if xs.len() % 8 != 0 {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "buffer length must be a multiple of 8",
        ));
    }
    let n = xs.len() / 8;
    let mut out = vec![0u8; xs.len()];
    for i in 0..n {
        let mut b = [0u8; 8];
        b.copy_from_slice(&xs[i * 8..i * 8 + 8]);
        let y = f(f64::from_le_bytes(b));
        out[i * 8..i * 8 + 8].copy_from_slice(&y.to_le_bytes());
    }
    Ok(PyBytes::new(py, &out))
}

#[pymodule]
fn carc_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", carc_core::VERSION)?;
    m.add_function(wrap_pyfunction!(shuffle_indices, m)?)?;
    m.add_function(wrap_pyfunction!(seed_words, m)?)?;
    m.add_function(wrap_pyfunction!(genrand_uint32_stream, m)?)?;
    m.add_function(wrap_pyfunction!(getrandbits_stream, m)?)?;
    m.add_function(wrap_pyfunction!(randbelow_stream, m)?)?;
    m.add_function(wrap_pyfunction!(fsum, m)?)?;
    m.add_function(wrap_pyfunction!(fsum_batch, m)?)?;
    m.add_function(wrap_pyfunction!(np_sum_f64, m)?)?;
    m.add_function(wrap_pyfunction!(np_sum_f32, m)?)?;
    m.add_function(wrap_pyfunction!(np_sum_f64_batch, m)?)?;
    m.add_function(wrap_pyfunction!(np_sum_f32_batch, m)?)?;
    m.add_function(wrap_pyfunction!(exp64, m)?)?;
    m.add_function(wrap_pyfunction!(exp64_fma, m)?)?;
    m.add_function(wrap_pyfunction!(tanh64, m)?)?;
    m.add_function(wrap_pyfunction!(expm1_64, m)?)?;
    m.add_function(wrap_pyfunction!(expm1_64_flavor, m)?)?;
    m.add_function(wrap_pyfunction!(tanh64_flavor, m)?)?;
    m.add_function(wrap_pyfunction!(libm_flavors, m)?)?;
    m.add_function(wrap_pyfunction!(expm1_64_buf, m)?)?;
    m.add_function(wrap_pyfunction!(exp64_buf, m)?)?;
    m.add_function(wrap_pyfunction!(tanh64_buf, m)?)?;
    // P1
    m.add_class::<PyMirrorState>()?;
    m.add_function(wrap_pyfunction!(deck_descriptions_from_seed, m)?)?;
    m.add_function(wrap_pyfunction!(tile_data_digests, m)?)?;
    m.add_function(wrap_pyfunction!(rotated_tile_table, m)?)?;
    Ok(())
}
