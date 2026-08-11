//! Reader for the `CARCPOS1` position dump written by `tools/dump_positions.py`.
//!
//! The dump carries real corpus positions AND torch's own reference priors, so the
//! faithfulness harness compares a backend against torch on inputs neither side
//! re-derived. See the python tool's docstring for the layout.

use std::fs::File;
use std::io::{BufReader, Read};

pub const MAGIC: &[u8; 8] = b"CARCPOS1";

pub struct Positions {
    pub n: usize,
    pub n_channels: usize,
    pub window: usize,
    pub n_scalars: usize,
    pub action_size: usize,
    /// `n * n_channels * window * window`
    pub boards: Vec<f32>,
    /// `n * n_scalars`
    pub scalars: Vec<f32>,
    /// `n * action_size`
    pub masks: Vec<bool>,
    /// `n * action_size` — TORCH reference priors (masked softmax, illegal == 0).
    pub ref_priors: Vec<f32>,
}

impl Positions {
    pub fn board_stride(&self) -> usize {
        self.n_channels * self.window * self.window
    }

    pub fn load(path: &str) -> std::io::Result<Positions> {
        let mut r = BufReader::new(File::open(path)?);
        let mut magic = [0u8; 8];
        r.read_exact(&mut magic)?;
        if &magic != MAGIC {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                "bad magic — not a CARCPOS1 dump",
            ));
        }
        let mut hdr = [0u8; 20];
        r.read_exact(&mut hdr)?;
        let u = |i: usize| u32::from_le_bytes(hdr[i * 4..i * 4 + 4].try_into().unwrap()) as usize;
        let (n, n_channels, window, n_scalars, action_size) = (u(0), u(1), u(2), u(3), u(4));

        let bstride = n_channels * window * window;
        let mut p = Positions {
            n,
            n_channels,
            window,
            n_scalars,
            action_size,
            boards: vec![0.0; n * bstride],
            scalars: vec![0.0; n * n_scalars],
            masks: vec![false; n * action_size],
            ref_priors: vec![0.0; n * action_size],
        };

        let mut fbuf = vec![0u8; bstride.max(n_scalars).max(action_size) * 4];
        let mut mbuf = vec![0u8; action_size];
        for i in 0..n {
            r.read_exact(&mut fbuf[..bstride * 4])?;
            read_f32(&fbuf[..bstride * 4], &mut p.boards[i * bstride..(i + 1) * bstride]);

            r.read_exact(&mut fbuf[..n_scalars * 4])?;
            read_f32(
                &fbuf[..n_scalars * 4],
                &mut p.scalars[i * n_scalars..(i + 1) * n_scalars],
            );

            r.read_exact(&mut mbuf)?;
            for (j, &b) in mbuf.iter().enumerate() {
                p.masks[i * action_size + j] = b != 0;
            }

            r.read_exact(&mut fbuf[..action_size * 4])?;
            read_f32(
                &fbuf[..action_size * 4],
                &mut p.ref_priors[i * action_size..(i + 1) * action_size],
            );
        }
        Ok(p)
    }

    /// Indices of rows with at least one legal action. The corpus contains a few
    /// all-illegal rows (terminal/aux records); they carry no ordering information,
    /// so scoring them would dilute the agreement rate with rows that cannot
    /// disagree. Excluded explicitly rather than silently.
    pub fn scorable(&self) -> Vec<usize> {
        (0..self.n)
            .filter(|&i| {
                self.masks[i * self.action_size..(i + 1) * self.action_size]
                    .iter()
                    .any(|&m| m)
            })
            .collect()
    }
}

fn read_f32(src: &[u8], dst: &mut [f32]) {
    for (i, c) in src.chunks_exact(4).enumerate() {
        dst[i] = f32::from_le_bytes(c.try_into().unwrap());
    }
}
