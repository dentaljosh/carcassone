//! numpy's **pairwise** summation — the reduction order behind `np.sum` /
//! `ndarray.sum()` for contiguous 1-D `float32` / `float64` arrays.
//!
//! Provenance
//! ----------
//! numpy 2.4.4 (git `be93fe2960dbf49b4647f5783c66d967fb2c65b5`),
//! `numpy/_core/src/umath/loops_utils.h.src` → `@TYPE@_pairwise_sum`
//! (`PW_BLOCKSIZE 128`), reached from
//! `numpy/_core/src/umath/loops_arithm_fp.dispatch.c.src` line 54:
//!
//! ```text
//!     // reduce
//!     if (ssrc0 == 0 && ssrc0 == sdst && src0 == dst) {
//!     #if @PW@                      // PW == 1 only for `add`
//!         *((@type@*)src0) += @TYPE@_pairwise_sum(src1, len, ssrc1);
//! ```
//!
//! So `np.sum(a)` on a contiguous 1-D array is exactly
//! `identity(+0.0) + pairwise_sum(a, n)` — that leading `0.0 +` is modelled here
//! because it is observable: the base case seeds with `-0.0` (to preserve `-0.0`
//! for all-negative-zero inputs) and `0.0 + -0.0 == 0.0`.
//!
//! Three details that are easy to get wrong and are transcribed verbatim from
//! the source rather than from memory:
//!   1. the `n < 8` base case starts from **`-0.0`**, not `0.0`;
//!   2. the 8-accumulator block reduces as `((r0+r1)+(r2+r3)) + ((r4+r5)+(r6+r7))`
//!      and then the `n % 8` tail is folded into that scalar, in order;
//!   3. the recursive split is `n2 = n/2; n2 -= n2 % 8;` — i.e. the split point
//!      is snapped **down** to a multiple of the unroll factor, so it is NOT a
//!      plain halving.
//!
//! Caveat: numpy's reduce is unbuffered for contiguous same-dtype 1-D input, so
//! the whole array arrives in one inner-loop call. A buffered path (casting,
//! non-contiguous, object dtype) would chunk at `bufsize` (default 8192) and
//! change the order — such call sites are out of scope for this port; the leaf's
//! two prior sites are contiguous f64 / f32.
//!
//! Gate: `scripts/rustport/reconcile_npsum.py` (bit-equal vs `np.sum`).

/// `PW_BLOCKSIZE` from `loops_utils.h.src`.
pub const PW_BLOCKSIZE: usize = 128;

macro_rules! impl_pairwise {
    ($fname:ident, $t:ty, $doc:literal) => {
        #[doc = $doc]
        pub fn $fname(a: &[$t]) -> $t {
            let n = a.len();
            if n < 8 {
                // "Start with -0 to preserve -0 values. The reason is that
                //  summing only -0 should return -0, but `0 + -0 == 0` while
                //  `-0 + -0 == -0`."
                let mut res: $t = -0.0;
                for &v in a.iter() {
                    res += v;
                }
                res
            } else if n <= PW_BLOCKSIZE {
                let mut r: [$t; 8] = [
                    a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7],
                ];
                let mut i = 8usize;
                let stop = n - (n % 8);
                while i < stop {
                    r[0] += a[i];
                    r[1] += a[i + 1];
                    r[2] += a[i + 2];
                    r[3] += a[i + 3];
                    r[4] += a[i + 4];
                    r[5] += a[i + 5];
                    r[6] += a[i + 6];
                    r[7] += a[i + 7];
                    i += 8;
                }
                // "accumulate now to avoid stack spills for single peel loop"
                let mut res = ((r[0] + r[1]) + (r[2] + r[3])) + ((r[4] + r[5]) + (r[6] + r[7]));
                // "do non multiple of 8 rest"
                while i < n {
                    res += a[i];
                    i += 1;
                }
                res
            } else {
                // "divide by two but avoid non-multiples of unroll factor"
                let mut n2 = n / 2;
                n2 -= n2 % 8;
                $fname(&a[..n2]) + $fname(&a[n2..])
            }
        }
    };
}

impl_pairwise!(
    pairwise_sum_f64,
    f64,
    "`DOUBLE_pairwise_sum` — numpy's reduction order for `float64`."
);
impl_pairwise!(
    pairwise_sum_f32,
    f32,
    "`FLOAT_pairwise_sum` — numpy's reduction order for `float32`."
);

/// `np.sum(a)` for a contiguous 1-D `float64` array: the additive identity plus
/// the pairwise reduction.
pub fn np_sum_f64(a: &[f64]) -> f64 {
    0.0f64 + pairwise_sum_f64(a)
}

/// `np.sum(a)` for a contiguous 1-D `float32` array (numpy does **not** upcast
/// the accumulator for `float32` input).
pub fn np_sum_f32(a: &[f32]) -> f32 {
    0.0f32 + pairwise_sum_f32(a)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tiny_lengths_are_left_to_right_from_neg_zero() {
        for n in 0..8usize {
            let v: Vec<f64> = (0..n).map(|i| (i as f64 + 1.0) * 0.1).collect();
            let mut want: f64 = -0.0;
            for &x in &v {
                want += x;
            }
            assert_eq!(pairwise_sum_f64(&v).to_bits(), want.to_bits(), "n={n}");
        }
    }

    #[test]
    fn negative_zero_is_preserved_by_the_base_case() {
        // pairwise_sum of all -0.0 is -0.0; np.sum adds the +0.0 identity, so
        // np.sum([-0.0]*k) is +0.0. Both behaviours are modelled.
        let v = [-0.0f64; 4];
        assert_eq!(pairwise_sum_f64(&v).to_bits(), (-0.0f64).to_bits());
        assert_eq!(np_sum_f64(&v).to_bits(), (0.0f64).to_bits());
    }

    #[test]
    fn block_boundary_shapes_are_not_naive() {
        // n = 129 takes the recursive branch: n2 = 64 (already a multiple of 8),
        // so it splits 64 + 65 -- NOT 64/65 by plain halving coincidence but by
        // the snap-down rule. n = 130 -> n2 = 65 -> 64, split 64 + 66.
        for &n in &[129usize, 130, 135, 136, 137, 200, 256, 257, 1000] {
            let v: Vec<f64> = (0..n).map(|i| 1.0 / ((i + 1) as f64)).collect();
            let naive: f64 = v.iter().fold(-0.0f64, |a, b| a + b);
            let pw = pairwise_sum_f64(&v);
            // Not a correctness assert per se: it documents that the order
            // matters at these lengths (the reconcile script is the real gate).
            let _ = (naive, pw, n);
        }
        // Direct structural check of the split rule at n = 130.
        let v: Vec<f64> = (0..130).map(|i| (i as f64) * 1e-3).collect();
        let want = pairwise_sum_f64(&v[..64]) + pairwise_sum_f64(&v[64..]);
        assert_eq!(pairwise_sum_f64(&v).to_bits(), want.to_bits());
    }

    #[test]
    fn f32_and_f64_agree_on_exact_integers() {
        let v64: Vec<f64> = (0..1000).map(|i| i as f64).collect();
        let v32: Vec<f32> = (0..1000).map(|i| i as f32).collect();
        assert_eq!(np_sum_f64(&v64), 499500.0);
        assert_eq!(np_sum_f32(&v32), 499500.0);
    }

    #[test]
    fn empty_sum_is_positive_zero() {
        assert_eq!(np_sum_f64(&[]).to_bits(), (0.0f64).to_bits());
        assert_eq!(np_sum_f32(&[]).to_bits(), (0.0f32).to_bits());
    }
}
