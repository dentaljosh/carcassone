//! CPython-compatible Mersenne Twister (`random.Random` / the `random` module).
//!
//! Provenance
//! ----------
//! Ported from CPython 3.12:
//!   * `Modules/_randommodule.c` — `init_genrand`, `init_by_array`,
//!     `genrand_uint32`, `random_seed`, `_random_Random_getrandbits_impl`
//!   * `Lib/random.py` — `Random._randbelow_with_getrandbits`, `Random.shuffle`
//!
//! Why this exists: every deck the project has ever shuffled is defined by
//! `random.seed(deck_seed); random.shuffle(tiles)` (and the determinization
//! draws by `random.Random(base + i)`). Reproducing the record therefore
//! requires bit-exact CPython MT, not "a" Mersenne Twister — the seeding path
//! (abs value split into little-endian 32-bit words fed to `init_by_array`) and
//! the descending Fisher-Yates in `shuffle` are both CPython-specific.
//!
//! Gate: `scripts/rustport/reconcile_mt19937.py` (0 mismatches, full stop).

const N: usize = 624;
const M: usize = 397;
const MATRIX_A: u32 = 0x9908_b0df;
const UPPER_MASK: u32 = 0x8000_0000;
const LOWER_MASK: u32 = 0x7fff_ffff;

/// CPython's `_random.Random` state.
#[derive(Clone)]
pub struct MT19937 {
    state: [u32; N],
    index: usize,
}

impl MT19937 {
    /// `init_genrand(s)` — CPython `_randommodule.c`.
    pub fn from_u32_seed(s: u32) -> Self {
        let mut mt = MT19937 {
            state: [0u32; N],
            index: N,
        };
        mt.init_genrand(s);
        mt
    }

    fn init_genrand(&mut self, s: u32) {
        self.state[0] = s;
        for i in 1..N {
            // mt[i] = 1812433253 * (mt[i-1] ^ (mt[i-1] >> 30)) + i
            let prev = self.state[i - 1];
            self.state[i] = 1812433253u32
                .wrapping_mul(prev ^ (prev >> 30))
                .wrapping_add(i as u32);
        }
        self.index = N;
    }

    /// `init_by_array(init_key, key_length)` — CPython `_randommodule.c`.
    ///
    /// `key` must be non-empty (CPython guarantees `keyused >= 1`).
    pub fn from_key(key: &[u32]) -> Self {
        assert!(!key.is_empty(), "init_by_array requires a non-empty key");
        let mut mt = MT19937 {
            state: [0u32; N],
            index: N,
        };
        mt.init_genrand(19650218);
        let key_length = key.len();
        let mut i: usize = 1;
        let mut j: usize = 0;
        let mut k = if N > key_length { N } else { key_length };
        while k > 0 {
            let prev = mt.state[i - 1];
            mt.state[i] = (mt.state[i] ^ (prev ^ (prev >> 30)).wrapping_mul(1664525))
                .wrapping_add(key[j])
                .wrapping_add(j as u32);
            i += 1;
            j += 1;
            if i >= N {
                mt.state[0] = mt.state[N - 1];
                i = 1;
            }
            if j >= key_length {
                j = 0;
            }
            k -= 1;
        }
        let mut k = N - 1;
        while k > 0 {
            let prev = mt.state[i - 1];
            mt.state[i] = (mt.state[i] ^ (prev ^ (prev >> 30)).wrapping_mul(1566083941))
                .wrapping_sub(i as u32);
            i += 1;
            if i >= N {
                mt.state[0] = mt.state[N - 1];
                i = 1;
            }
            k -= 1;
        }
        mt.state[0] = 0x8000_0000;
        mt.index = N;
        mt
    }

    /// CPython `random_seed()` for an **integer** argument.
    ///
    /// CPython takes `abs(seed)`, writes it as a little-endian byte string of
    /// `ceil(bit_length/32)` 32-bit words (at least one word) and feeds that to
    /// `init_by_array`. `seed_words` is exactly that word vector — see
    /// [`seed_words_from_decimal`].
    pub fn from_py_int_seed_words(words: &[u32]) -> Self {
        if words.is_empty() {
            Self::from_key(&[0])
        } else {
            Self::from_key(words)
        }
    }

    /// Convenience: seed from an `i64` the way `random.seed(n)` does.
    pub fn from_py_int_seed_i64(seed: i64) -> Self {
        Self::from_py_int_seed_words(&u64_to_words(seed.unsigned_abs()))
    }

    /// Convenience: seed from an arbitrary-precision decimal string (`"-123"`,
    /// `"340282366920938463463374607431768211457"`, ...).
    pub fn from_py_int_seed_decimal(seed: &str) -> Self {
        Self::from_py_int_seed_words(&seed_words_from_decimal(seed))
    }

    /// `genrand_uint32` — the tempered MT output.
    pub fn genrand_uint32(&mut self) -> u32 {
        if self.index >= N {
            self.generate_block();
        }
        let mut y = self.state[self.index];
        self.index += 1;
        y ^= y >> 11;
        y ^= (y << 7) & 0x9d2c_5680;
        y ^= (y << 15) & 0xefc6_0000;
        y ^= y >> 18;
        y
    }

    fn generate_block(&mut self) {
        // CPython twists the whole array in one pass when mti >= N.
        let mag01 = [0u32, MATRIX_A];
        for kk in 0..(N - M) {
            let y = (self.state[kk] & UPPER_MASK) | (self.state[kk + 1] & LOWER_MASK);
            self.state[kk] = self.state[kk + M] ^ (y >> 1) ^ mag01[(y & 0x1) as usize];
        }
        for kk in (N - M)..(N - 1) {
            let y = (self.state[kk] & UPPER_MASK) | (self.state[kk + 1] & LOWER_MASK);
            self.state[kk] =
                self.state[kk + M - N] ^ (y >> 1) ^ mag01[(y & 0x1) as usize];
        }
        let y = (self.state[N - 1] & UPPER_MASK) | (self.state[0] & LOWER_MASK);
        self.state[N - 1] = self.state[M - 1] ^ (y >> 1) ^ mag01[(y & 0x1) as usize];
        self.index = 0;
    }

    /// `getrandbits(k)` for `k <= 64` — returns the value as a `u64`.
    ///
    /// CPython builds the result from little-endian 32-bit words: the FIRST word
    /// drawn is the LEAST significant, and only the LAST word is right-shifted.
    pub fn getrandbits(&mut self, k: u32) -> u64 {
        assert!(k <= 64, "use getrandbits_words for k > 64");
        if k == 0 {
            return 0;
        }
        if k <= 32 {
            return (self.genrand_uint32() >> (32 - k)) as u64;
        }
        let words = ((k - 1) / 32 + 1) as usize;
        let mut out: u64 = 0;
        let mut kk = k;
        for i in 0..words {
            let mut r = self.genrand_uint32();
            if kk < 32 {
                r >>= 32 - kk;
            }
            out |= (r as u64) << (32 * i);
            kk = kk.saturating_sub(32);
        }
        out
    }

    /// `Random._randbelow_with_getrandbits(n)` for `n < 2^64`
    /// (`Lib/random.py`): `k = n.bit_length()`, redraw while `r >= n`.
    pub fn randbelow(&mut self, n: u64) -> u64 {
        if n == 0 {
            return 0;
        }
        let k = 64 - n.leading_zeros(); // == n.bit_length()
        loop {
            let r = self.getrandbits(k);
            if r < n {
                return r;
            }
        }
    }

    /// `Random.shuffle(x)` over `range(n)` — returns the resulting permutation.
    ///
    /// ```text
    /// for i in reversed(range(1, len(x))):
    ///     j = self._randbelow(i + 1)
    ///     x[i], x[j] = x[j], x[i]
    /// ```
    pub fn shuffle_range(&mut self, n: usize) -> Vec<u32> {
        let mut x: Vec<u32> = (0..n as u32).collect();
        self.shuffle(&mut x);
        x
    }

    /// `Random.shuffle(x)` in place, for any element type.
    pub fn shuffle<T>(&mut self, x: &mut [T]) {
        if x.len() < 2 {
            return;
        }
        for i in (1..x.len()).rev() {
            let j = self.randbelow(i as u64 + 1) as usize;
            x.swap(i, j);
        }
    }
}

/// How a seed was supplied. Both CPython entry points (`random.seed(n)` on the
/// hidden module-global instance, and `random.Random(n)`) route an `int` through
/// the exact same `random_seed()` code path, so these are behaviourally
/// identical — the distinction is kept because the spec names both and the
/// reconcile gate proves the equality rather than assuming it.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SeedMode {
    /// `random.seed(n); random.shuffle(...)`
    GlobalSeed,
    /// `random.Random(n).shuffle(...)`
    RandomInstance,
}

/// The permutation `random.<mode>(seed); shuffle(list(range(n)))` produces.
pub fn shuffle_indices(seed_decimal: &str, mode: SeedMode, n: usize) -> Vec<u32> {
    let _ = mode; // identical seeding path; see SeedMode docs
    let mut mt = MT19937::from_py_int_seed_decimal(seed_decimal);
    mt.shuffle_range(n)
}

/// Split a non-negative `u64` into CPython's little-endian 32-bit seed words.
fn u64_to_words(mut n: u64) -> Vec<u32> {
    if n == 0 {
        return vec![0];
    }
    let mut out = Vec::new();
    while n != 0 {
        out.push((n & 0xffff_ffff) as u32);
        n >>= 32;
    }
    out
}

/// CPython `random_seed()`'s word vector for an arbitrary-precision int given as
/// a decimal string. Sign is discarded (`PyNumber_Absolute`); the number of words
/// is `ceil(bit_length / 32)`, minimum 1.
pub fn seed_words_from_decimal(s: &str) -> Vec<u32> {
    let s = s.trim();
    let digits = s.strip_prefix('-').or_else(|| s.strip_prefix('+')).unwrap_or(s);
    // Accumulate base-2^32 limbs, little-endian: limbs = limbs * 10 + d.
    let mut limbs: Vec<u32> = Vec::new();
    for ch in digits.chars() {
        let d = ch.to_digit(10).expect("seed must be a decimal integer") as u64;
        let mut carry = d;
        for limb in limbs.iter_mut() {
            let v = (*limb as u64) * 10 + carry;
            *limb = (v & 0xffff_ffff) as u32;
            carry = v >> 32;
        }
        while carry != 0 {
            limbs.push((carry & 0xffff_ffff) as u32);
            carry >>= 32;
        }
    }
    while limbs.last() == Some(&0) {
        limbs.pop();
    }
    if limbs.is_empty() {
        limbs.push(0); // bits == 0 -> keyused == 1
    }
    limbs
}

#[cfg(test)]
mod tests {
    use super::*;

    // --- reference vectors, all generated with CPython 3.12 -------------------

    #[test]
    fn seed_words_matches_cpython_split() {
        assert_eq!(seed_words_from_decimal("0"), vec![0]);
        assert_eq!(seed_words_from_decimal("1"), vec![1]);
        assert_eq!(seed_words_from_decimal("-1"), vec![1]);
        assert_eq!(seed_words_from_decimal("4294967295"), vec![0xffff_ffff]);
        assert_eq!(seed_words_from_decimal("4294967296"), vec![0, 1]);
        // 2**63 - 1
        assert_eq!(
            seed_words_from_decimal("9223372036854775807"),
            vec![0xffff_ffff, 0x7fff_ffff]
        );
        // 2**64 + 1
        assert_eq!(seed_words_from_decimal("18446744073709551617"), vec![1, 0, 1]);
        // 2**128 - 1
        assert_eq!(
            seed_words_from_decimal("340282366920938463463374607431768211455"),
            vec![0xffff_ffff; 4]
        );
    }

    #[test]
    fn genrand_matches_cpython_seed_0() {
        // >>> random.seed(0); [random.getrandbits(32) for _ in range(6)]
        let mut mt = MT19937::from_py_int_seed_i64(0);
        let want = [
            3626764237u32, 1654615998, 3255389356, 3823568514, 1806341205, 173879092,
        ];
        for (i, w) in want.iter().enumerate() {
            assert_eq!(mt.genrand_uint32(), *w, "word {i}");
        }
    }

    #[test]
    fn genrand_matches_cpython_seed_12345() {
        // >>> random.seed(12345); [random.getrandbits(32) for _ in range(4)]
        let mut mt = MT19937::from_py_int_seed_i64(12345);
        let want = [1789368711u32, 3146859322, 43676229, 3522623596];
        for (i, w) in want.iter().enumerate() {
            assert_eq!(mt.genrand_uint32(), *w, "word {i}");
        }
    }

    #[test]
    fn getrandbits_widths_match_cpython() {
        // >>> random.seed(7); [random.getrandbits(k) for k in (1,3,17,32,33,53,64)]
        let mut mt = MT19937::from_py_int_seed_i64(7);
        let want: [(u32, u64); 7] = [
            (1, 0),
            (3, 7),
            (17, 19772),
            (32, 1695753998),
            (33, 2795742288),
            (53, 7397381398802227),
            (64, 1736392818365009963),
        ];
        for (k, v) in want {
            assert_eq!(mt.getrandbits(k), v, "getrandbits({k})");
        }
    }

    #[test]
    fn shuffle_matches_cpython_deck_lengths() {
        // >>> random.seed(1234); l=list(range(72)); random.shuffle(l); l[:8], l[-4:]
        let p = shuffle_indices("1234", SeedMode::GlobalSeed, 72);
        assert_eq!(p.len(), 72);
        assert_eq!(&p[..8], &[28u32, 3, 13, 37, 24, 26, 40, 65]);
        assert_eq!(&p[68..], &[11u32, 0, 14, 56]);

        // >>> random.seed(0); l=list(range(71)); random.shuffle(l); l[:6]
        let p = shuffle_indices("0", SeedMode::GlobalSeed, 71);
        assert_eq!(&p[..6], &[31u32, 24, 68, 29, 69, 42]);
    }

    #[test]
    fn shuffle_degenerate_lengths() {
        assert_eq!(shuffle_indices("5", SeedMode::GlobalSeed, 0), Vec::<u32>::new());
        assert_eq!(shuffle_indices("5", SeedMode::GlobalSeed, 1), vec![0]);
    }

    #[test]
    fn big_seed_shuffles() {
        // >>> random.seed(2**70 + 12345); l=list(range(72)); random.shuffle(l); l[:5]
        let p = shuffle_indices("1180591620717411315769", SeedMode::GlobalSeed, 72);
        assert_eq!(&p[..5], &[11u32, 71, 57, 40, 67]);
    }

    #[test]
    fn randbelow_rejection_loop() {
        // >>> random.seed(99); r=random.Random(99); [r._randbelow(n) for n in (2,3,5,71,72,100)]
        let mut mt = MT19937::from_py_int_seed_i64(99);
        let want = [1u64, 1, 1, 22, 29, 31];
        for (i, w) in want.iter().enumerate() {
            let n = [2u64, 3, 5, 71, 72, 100][i];
            assert_eq!(mt.randbelow(n), *w, "_randbelow({n})");
        }
    }

    #[test]
    fn seed_modes_agree() {
        for n in [0usize, 1, 2, 71, 72] {
            assert_eq!(
                shuffle_indices("424242", SeedMode::GlobalSeed, n),
                shuffle_indices("424242", SeedMode::RandomInstance, n),
            );
        }
    }
}
