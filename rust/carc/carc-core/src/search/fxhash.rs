//! A tiny FxHash (rustc's hasher) so the node table can key on the ~2–4 KB
//! `string_representation` bytes without paying SipHash on every lookup.
//!
//! Vendored rather than depended on: `carc-core` is deliberately
//! dependency-free (it must stay WASM/iOS-buildable — spec "Out of scope (v1)").
//! Hash quality is not a correctness surface here — the map is keyed by exact
//! byte strings and collisions only cost a comparison.

use std::hash::{BuildHasherDefault, Hasher};

const SEED64: u64 = 0x51_7c_c1_b7_27_22_0a_95;
const ROTATE: u32 = 5;

#[derive(Default, Clone, Copy)]
pub struct FxHasher {
    hash: u64,
}

impl FxHasher {
    #[inline]
    fn add_to_hash(&mut self, i: u64) {
        self.hash = (self.hash.rotate_left(ROTATE) ^ i).wrapping_mul(SEED64);
    }
}

impl Hasher for FxHasher {
    #[inline]
    fn write(&mut self, bytes: &[u8]) {
        let mut b = bytes;
        while b.len() >= 8 {
            let mut buf = [0u8; 8];
            buf.copy_from_slice(&b[..8]);
            self.add_to_hash(u64::from_le_bytes(buf));
            b = &b[8..];
        }
        if b.len() >= 4 {
            let mut buf = [0u8; 4];
            buf.copy_from_slice(&b[..4]);
            self.add_to_hash(u32::from_le_bytes(buf) as u64);
            b = &b[4..];
        }
        for &byte in b {
            self.add_to_hash(byte as u64);
        }
    }

    #[inline]
    fn write_u8(&mut self, i: u8) {
        self.add_to_hash(i as u64);
    }
    #[inline]
    fn write_u32(&mut self, i: u32) {
        self.add_to_hash(i as u64);
    }
    #[inline]
    fn write_u64(&mut self, i: u64) {
        self.add_to_hash(i);
    }
    #[inline]
    fn write_usize(&mut self, i: usize) {
        self.add_to_hash(i as u64);
    }
    #[inline]
    fn write_i32(&mut self, i: i32) {
        self.add_to_hash(i as u32 as u64);
    }
    #[inline]
    fn finish(&self) -> u64 {
        self.hash
    }
}

pub type FxBuildHasher = BuildHasherDefault<FxHasher>;

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    #[test]
    fn map_round_trips() {
        let mut m: HashMap<Box<str>, u32, FxBuildHasher> = HashMap::default();
        for i in 0..1000u32 {
            m.insert(format!("key-{i}-{}", "x".repeat(i as usize % 97)).into_boxed_str(), i);
        }
        assert_eq!(m.len(), 1000);
        for i in 0..1000u32 {
            let k = format!("key-{i}-{}", "x".repeat(i as usize % 97));
            assert_eq!(m[k.as_str()], i);
        }
    }
}
