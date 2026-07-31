//! The **per-simulation trace harness** — built in P3, *before* k-parallel
//! (P4), because it is the debugging instrument for everything after.
//!
//! Both sides (this, and `scripts/rustport/trace_search.py`) emit the SAME
//! JSONL schema, one record per line, in the SAME order, so
//! `scripts/rustport/trace_diff.py` can bisect to the first divergent
//! simulation instead of staring at an aggregate mismatch.
//!
//! Schema — two record kinds, distinguished by `"t"`:
//!
//! ```text
//! {"t":"exp","node":"<16 hex>","p":<player>,"term":<0|1>,"tv":"<bits>",
//!  "lv":"<bits>","va":[<action>,...],"pr":["<bits>",...]}
//! {"t":"sim","i":<sim>,"path":["<16 hex>",...],"acts":[<action>,...],
//!  "lv":"<bits>","nw":[[<N>,"<bits>"],...]}
//! ```
//!
//! Floats are the raw IEEE-754 bit pattern as 16 lowercase hex digits — the
//! only encoding with no rounding, no locale and no `-0.0` ambiguity.  Node
//! identity is `sha256(string_representation)[:16]`; the full keys are large
//! (~2–4 KB late game) and a digest keeps a 1376-sim trace in the low MB.
//!
//! `exp` records are emitted at expansion time, i.e. *interleaved* with the
//! `sim` records exactly where the expansion happens during the descent, so the
//! record ORDER is itself part of the comparison.

use std::io::Write;

pub struct ExpandRecord<'a> {
    pub digest: &'a str,
    pub player_to_move: usize,
    pub is_terminal: bool,
    pub terminal_value: f64,
    pub leaf_value: f64,
    pub valid_actions: &'a [i32],
    pub priors: &'a [f64],
}

pub struct SimRecord<'a> {
    pub sim: usize,
    pub path: &'a [&'a str],
    pub actions: &'a [i32],
    pub leaf_value: f64,
    pub nw: &'a [(i64, f64)],
}

pub trait TraceSink {
    fn expand(&mut self, rec: &ExpandRecord<'_>);
    fn sim(&mut self, rec: &SimRecord<'_>);
}

/// Raw IEEE-754 bits, 16 lowercase hex digits.
#[inline]
pub fn bits(x: f64) -> String {
    format!("{:016x}", x.to_bits())
}

/// A `TraceSink` writing the JSONL schema to any `Write`.
pub struct JsonlTrace<W: Write> {
    w: W,
    /// Skip `exp` records (they dominate the file on wide positions).
    pub expansions: bool,
}

impl<W: Write> JsonlTrace<W> {
    pub fn new(w: W) -> Self {
        JsonlTrace { w, expansions: true }
    }
    pub fn sims_only(w: W) -> Self {
        JsonlTrace { w, expansions: false }
    }
    pub fn into_inner(self) -> W {
        self.w
    }
}

fn join_i32(v: &[i32]) -> String {
    let mut s = String::with_capacity(v.len() * 5);
    for (i, x) in v.iter().enumerate() {
        if i > 0 {
            s.push(',');
        }
        s.push_str(&x.to_string());
    }
    s
}

impl<W: Write> TraceSink for JsonlTrace<W> {
    fn expand(&mut self, rec: &ExpandRecord<'_>) {
        if !self.expansions {
            return;
        }
        let mut pr = String::with_capacity(rec.priors.len() * 20);
        for (i, p) in rec.priors.iter().enumerate() {
            if i > 0 {
                pr.push(',');
            }
            pr.push('"');
            pr.push_str(&bits(*p));
            pr.push('"');
        }
        let _ = writeln!(
            self.w,
            "{{\"t\":\"exp\",\"node\":\"{}\",\"p\":{},\"term\":{},\"tv\":\"{}\",\"lv\":\"{}\",\"va\":[{}],\"pr\":[{}]}}",
            rec.digest,
            rec.player_to_move,
            rec.is_terminal as u8,
            bits(rec.terminal_value),
            bits(rec.leaf_value),
            join_i32(rec.valid_actions),
            pr
        );
    }

    fn sim(&mut self, rec: &SimRecord<'_>) {
        let mut path = String::with_capacity(rec.path.len() * 20);
        for (i, d) in rec.path.iter().enumerate() {
            if i > 0 {
                path.push(',');
            }
            path.push('"');
            path.push_str(d);
            path.push('"');
        }
        let mut nw = String::with_capacity(rec.nw.len() * 30);
        for (i, (n, w)) in rec.nw.iter().enumerate() {
            if i > 0 {
                nw.push(',');
            }
            nw.push('[');
            nw.push_str(&n.to_string());
            nw.push_str(",\"");
            nw.push_str(&bits(*w));
            nw.push_str("\"]");
        }
        let _ = writeln!(
            self.w,
            "{{\"t\":\"sim\",\"i\":{},\"path\":[{}],\"acts\":[{}],\"lv\":\"{}\",\"nw\":[{}]}}",
            rec.sim,
            path,
            join_i32(rec.actions),
            bits(rec.leaf_value),
            nw
        );
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bits_are_sign_exact() {
        assert_eq!(bits(0.0), "0000000000000000");
        assert_eq!(bits(-0.0), "8000000000000000");
        assert_eq!(bits(1.0), "3ff0000000000000");
    }

    #[test]
    fn writes_both_record_kinds() {
        let mut buf: Vec<u8> = Vec::new();
        {
            let mut t = JsonlTrace::new(&mut buf);
            t.expand(&ExpandRecord {
                digest: "abcd",
                player_to_move: 1,
                is_terminal: false,
                terminal_value: 0.0,
                leaf_value: 0.5,
                valid_actions: &[3, 7],
                priors: &[0.25, 0.75],
            });
            t.sim(&SimRecord {
                sim: 0,
                path: &["abcd", "ef01"],
                actions: &[3],
                leaf_value: -0.5,
                nw: &[(1, 1.0), (1, -1.0)],
            });
        }
        let s = String::from_utf8(buf).unwrap();
        let lines: Vec<&str> = s.trim().split('\n').collect();
        assert_eq!(lines.len(), 2);
        assert!(lines[0].starts_with("{\"t\":\"exp\""));
        assert!(lines[1].contains("\"acts\":[3]"));
    }
}
