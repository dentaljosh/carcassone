//! `math.fsum` — exact port of CPython's `math_fsum_impl` (Shewchuk partials).
//!
//! Provenance
//! ----------
//! CPython 3.12 `Modules/mathmodule.c`, `math_fsum_impl`. Based on
//! Shewchuk, "Adaptive Precision Floating-Point Arithmetic and Fast Robust
//! Geometric Predicates", `msum` / `grow_expansion`.
//!
//! Why this exists: the v2.9 leaf reduces its score components with
//! `math.fsum`, and every golden leaf value on record is that reduction's exact
//! result. Any other summation order (naive, Kahan, pairwise) is a different
//! function of the same multiset.
//!
//! Non-finite inputs
//! -----------------
//! CPython raises `OverflowError` on intermediate overflow and returns the
//! `inf`/`nan` special sum otherwise. **The leaf never feeds non-finite values**
//! (it sums bounded integer-ish scores), so [`fsum`] *panics* on any non-finite
//! input or intermediate overflow rather than silently returning a value that
//! would diverge from CPython's exception. Use [`fsum_checked`] if you need the
//! full CPython semantics as a `Result`.
//!
//! Gate: `scripts/rustport/reconcile_fsum.py` (bit-equal vs `math.fsum`).

/// What CPython would have raised instead of returning a float.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FsumError {
    /// CPython: `OverflowError("intermediate overflow in fsum")`
    IntermediateOverflow,
    /// CPython: `ValueError("-inf + inf in fsum")`
    InfMinusInf,
}

/// `math.fsum(seq)`. Panics on non-finite input / intermediate overflow — see
/// the module docs.
pub fn fsum(seq: &[f64]) -> f64 {
    match fsum_checked(seq) {
        Ok(v) => v,
        Err(e) => panic!("compat::fsum: {e:?} (CPython would raise); input len {}", seq.len()),
    }
}

/// `math.fsum(seq)` with CPython's exceptional cases surfaced as `Err`.
pub fn fsum_checked(seq: &[f64]) -> Result<f64, FsumError> {
    // `ps` in CPython is a stack array of NUM_PARTIALS=32 that grows on demand;
    // a Vec is the same thing without the realloc dance.
    let mut p: Vec<f64> = Vec::with_capacity(32);
    let mut n: usize = 0;
    let mut special_sum = 0.0f64;
    let mut inf_sum = 0.0f64;

    for &item in seq {
        let mut x = item;
        let xsave = x;
        // for y in partials: two-sum, keeping the low words
        let mut i: usize = 0;
        for j in 0..n {
            let mut y = p[j];
            if x.abs() < y.abs() {
                core::mem::swap(&mut x, &mut y);
            }
            let hi = x + y;
            let yr = hi - x;
            let lo = y - yr;
            if lo != 0.0 {
                p[i] = lo;
                i += 1;
            }
            x = hi;
        }
        n = i; // ps[i:] = [x]
        if x != 0.0 {
            if !x.is_finite() {
                // a nonfinite x is either intermediate overflow, or an inf/nan
                // summand
                if xsave.is_finite() {
                    return Err(FsumError::IntermediateOverflow);
                }
                if xsave.is_infinite() {
                    inf_sum += xsave;
                }
                special_sum += xsave;
                n = 0; // reset partials
            } else {
                if n < p.len() {
                    p[n] = x;
                } else {
                    p.push(x);
                }
                n += 1;
            }
        }
    }

    if special_sum != 0.0 {
        if inf_sum.is_nan() {
            return Err(FsumError::InfMinusInf);
        }
        return Ok(special_sum);
    }

    let mut hi = 0.0f64;
    let mut lo = 0.0f64;
    if n > 0 {
        n -= 1;
        hi = p[n];
        // sum_exact(ps, hi) from the top, stop when the sum becomes inexact.
        while n > 0 {
            let x = hi;
            n -= 1;
            let y = p[n];
            debug_assert!(y.abs() < x.abs());
            hi = x + y;
            let yr = hi - x;
            lo = y - yr;
            if lo != 0.0 {
                break;
            }
        }
        // Make half-even rounding work across multiple partials. Needed so that
        // sum([1e-16, 1, 1e16]) rounds the last digit up to two instead of down
        // to zero. Guarantees commutativity of math.fsum().
        if n > 0 && ((lo < 0.0 && p[n - 1] < 0.0) || (lo > 0.0 && p[n - 1] > 0.0)) {
            let y = lo * 2.0;
            let x = hi + y;
            let yr = x - hi;
            if y == yr {
                hi = x;
            }
        }
    }
    Ok(hi)
}

/// Streaming form of [`fsum`] — same algorithm, usable without materialising the
/// input slice (the leaf builds its terms lazily).
#[derive(Clone, Debug, Default)]
pub struct FsumAccum {
    p: Vec<f64>,
    n: usize,
}

impl FsumAccum {
    pub fn new() -> Self {
        Self {
            p: Vec::with_capacity(32),
            n: 0,
        }
    }

    /// Add one term. Panics on non-finite input / intermediate overflow.
    pub fn add(&mut self, item: f64) {
        let mut x = item;
        assert!(x.is_finite(), "compat::FsumAccum::add: non-finite input {x}");
        let mut i: usize = 0;
        for j in 0..self.n {
            let mut y = self.p[j];
            if x.abs() < y.abs() {
                core::mem::swap(&mut x, &mut y);
            }
            let hi = x + y;
            let yr = hi - x;
            let lo = y - yr;
            if lo != 0.0 {
                self.p[i] = lo;
                i += 1;
            }
            x = hi;
        }
        self.n = i;
        if x != 0.0 {
            assert!(x.is_finite(), "compat::FsumAccum::add: intermediate overflow");
            if self.n < self.p.len() {
                self.p[self.n] = x;
            } else {
                self.p.push(x);
            }
            self.n += 1;
        }
    }

    /// The exactly-rounded sum of everything added so far.
    pub fn finish(&self) -> f64 {
        let mut n = self.n;
        let mut hi = 0.0f64;
        let mut lo = 0.0f64;
        if n > 0 {
            n -= 1;
            hi = self.p[n];
            while n > 0 {
                let x = hi;
                n -= 1;
                let y = self.p[n];
                hi = x + y;
                let yr = hi - x;
                lo = y - yr;
                if lo != 0.0 {
                    break;
                }
            }
            if n > 0 && ((lo < 0.0 && self.p[n - 1] < 0.0) || (lo > 0.0 && self.p[n - 1] > 0.0))
            {
                let y = lo * 2.0;
                let x = hi + y;
                let yr = x - hi;
                if y == yr {
                    hi = x;
                }
            }
        }
        hi
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn bits(x: f64) -> u64 {
        x.to_bits()
    }

    #[test]
    fn empty_and_singleton() {
        assert_eq!(bits(fsum(&[])), bits(0.0));
        assert_eq!(bits(fsum(&[0.0])), bits(0.0));
        assert_eq!(bits(fsum(&[-0.0])), bits(0.0)); // CPython: math.fsum([-0.0]) == 0.0
        assert_eq!(bits(fsum(&[1.5])), bits(1.5));
    }

    #[test]
    fn cpython_docstring_cases() {
        // These are the canonical cases from CPython's Lib/test/test_math.py
        assert_eq!(fsum(&[1e100, 1.0, -1e100, 1e-100, 1e100, -1.0, -1e100]), 1e-100);
        assert_eq!(fsum(&[0.1; 10]), 1.0);
        assert_eq!(fsum(&[1e16, 1.0, -1e16]), 1.0);
        // half-even fixup case
        assert_eq!(fsum(&[1e-16, 1.0, 1e16]), 1e16 + 2.0);
    }

    #[test]
    fn beats_naive_summation() {
        let v = [1.0f64, 1e16, -1e16];
        let naive: f64 = v.iter().sum();
        assert_eq!(fsum(&v), 1.0);
        assert_ne!(naive, 1.0);
    }

    #[test]
    fn cancellation_ladder() {
        let mut v = Vec::new();
        for k in 0..100 {
            v.push(2f64.powi(k - 50));
            v.push(-2f64.powi(k - 50));
        }
        v.push(0.5);
        assert_eq!(fsum(&v), 0.5);
    }

    #[test]
    fn accum_matches_slice_form() {
        let cases: Vec<Vec<f64>> = vec![
            vec![],
            vec![1.0, 2.0, 3.0],
            vec![1e100, 1.0, -1e100, 1e-100, 1e100, -1.0, -1e100],
            vec![0.1; 17],
            vec![1e-16, 1.0, 1e16],
            (0..50).map(|i| (i as f64 - 25.0) * 1e-13).collect(),
        ];
        for c in cases {
            let mut a = FsumAccum::new();
            for &x in &c {
                a.add(x);
            }
            assert_eq!(bits(a.finish()), bits(fsum(&c)), "{c:?}");
        }
    }

    #[test]
    fn special_values_are_reported() {
        assert_eq!(
            fsum_checked(&[f64::INFINITY, f64::NEG_INFINITY]),
            Err(FsumError::InfMinusInf)
        );
        assert_eq!(fsum_checked(&[f64::INFINITY, 1.0]), Ok(f64::INFINITY));
        assert_eq!(
            fsum_checked(&[f64::MAX, f64::MAX]),
            Err(FsumError::IntermediateOverflow)
        );
        assert!(fsum_checked(&[f64::NAN, 1.0]).unwrap().is_nan());
    }

    #[test]
    fn subnormals() {
        let tiny = f64::from_bits(1); // 5e-324
        assert_eq!(fsum(&[tiny, tiny, tiny]), 3.0 * tiny);
        assert_eq!(fsum(&[1.0, tiny, -1.0]), tiny);
    }
}
