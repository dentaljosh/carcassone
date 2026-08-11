//! Byte-exact `game_wrapper.Game.string_representation`.
//!
//! The MCTS transposition table keys nodes by this string, so **byte equality
//! is itself a G1 gate** — not merely "carries the same information".  The
//! Python side is `repr()` of a nested tuple, which fixes every separator,
//! quote and `None`/`True`/`False` spelling:
//!
//! ```text
//! ((placed...), (meeples_p0, meeples_p1), (s0, s1), (m0, m1),
//!  current_player, 'tiles'|'meeples', len(deck), 'next_tile_desc'|None,
//!  (row, col)|None)
//! ```
//!
//! * `placed` iterates `placed_coords` sorted by `(row, column)`;
//! * each entry is `(row, col, description, ((e_top, e_right, e_bottom, e_left),
//!   shield, chapel, flowers))` — the rotation signature, precomputed per
//!   rotated tile in [`crate::tiles::RotTile::rot_sig_repr`];
//! * meeple tuples appear in `placed_meeples` **list insertion order** (NOT
//!   sorted) — the spec calls this out explicitly.

use std::fmt::Write;

use crate::engine::GameState;
use crate::tiles;

/// CPython `repr()` of a tuple: `()`, `(x,)`, `(x, y)`.
pub fn py_tuple(items: &[String]) -> String {
    match items.len() {
        0 => "()".to_string(),
        1 => format!("({},)", items[0]),
        _ => format!("({})", items.join(", ")),
    }
}

/// Push `repr()` of a plain-ASCII identifier-ish str (every value we emit is one).
#[inline]
fn push_py_str(out: &mut String, s: &str) {
    debug_assert!(
        !s.contains('\'') && !s.contains('\\') && s.is_ascii(),
        "repr() of {s:?} needs the full CPython escaping rules"
    );
    out.push('\'');
    out.push_str(s);
    out.push('\'');
}

/// The `(x,)` vs `(x, y)` vs `()` trailing-comma rule, applied to a tuple whose
/// elements were streamed straight into `out`: `n` is how many were written, and
/// the caller has already emitted `", "` between them.
#[inline]
fn close_py_tuple(out: &mut String, n: usize) {
    if n == 1 {
        out.push(',');
    }
    out.push(')');
}

/// Byte-for-byte [`string_representation`], appended to `out` in a single pass —
/// no `Vec<String>`, no per-field `format!`, no `rot_sig_repr` clone (the
/// 2026-08-02 review's finding #4: ~350 throwaway `String`s per call).
pub fn string_representation_into(state: &GameState, out: &mut String) {
    out.push('(');

    // 1. placed tiles, in `placed_coords` order.
    out.push('(');
    let mut n = 0usize;
    for &(row, col) in &state.placed_coords {
        let tid = match state.get_tile(row, col) {
            // defensive, exactly like the Python `continue`
            None => continue,
            Some(t) => t,
        };
        let tile = tiles::tile(tid);
        if n > 0 {
            out.push_str(", ");
        }
        let _ = write!(out, "({row}, {col}, ");
        push_py_str(out, tile.description);
        out.push_str(", ");
        // `'static` registry string — borrow it, never clone it.
        out.push_str(&tile.rot_sig_repr);
        out.push(')');
        n += 1;
    }
    close_py_tuple(out, n);
    out.push_str(", ");

    // 2. meeples, per player, in `placed_meeples` INSERTION order.
    out.push('(');
    for p in 0..state.players {
        if p > 0 {
            out.push_str(", ");
        }
        out.push('(');
        for (i, mp) in state.placed_meeples[p].iter().enumerate() {
            if i > 0 {
                out.push_str(", ");
            }
            out.push('(');
            push_py_str(out, mp.meeple_type.value());
            let _ = write!(out, ", {}, {}, ", mp.coord.row, mp.coord.col);
            push_py_str(out, mp.side.value());
            out.push(')');
        }
        close_py_tuple(out, state.placed_meeples[p].len());
    }
    close_py_tuple(out, state.players);
    out.push_str(", ");

    // 3. scores, 4. meeple counts.
    out.push('(');
    for p in 0..state.players {
        if p > 0 {
            out.push_str(", ");
        }
        let _ = write!(out, "{}", state.scores[p]);
    }
    close_py_tuple(out, state.players);
    out.push_str(", ");

    out.push('(');
    for p in 0..state.players {
        if p > 0 {
            out.push_str(", ");
        }
        let _ = write!(out, "{}", state.meeples[p]);
    }
    close_py_tuple(out, state.players);
    out.push_str(", ");

    // 5. current player, 6. phase, 7. deck length.
    let _ = write!(out, "{}, ", state.current_player);
    push_py_str(out, state.phase.value());
    let _ = write!(out, ", {}, ", state.deck_len());

    // 8. next tile description.
    match state.next_tile {
        None => out.push_str("None"),
        Some(base) => push_py_str(out, tiles::tile(tiles::tile_id(base, 0)).description),
    }
    out.push_str(", ");

    // 9. last tile coordinate.
    match state.last_tile_action {
        None => out.push_str("None"),
        Some(lta) => {
            let _ = write!(out, "({}, {})", lta.coord.row, lta.coord.col);
        }
    }

    out.push(')');
}

pub fn string_representation(state: &GameState) -> String {
    // One allocation, sized so the late-game key (~4–6 KB) does not realloc.
    let mut out = String::with_capacity(256 + state.placed_coords.len() * 96);
    string_representation_into(state, &mut out);
    out
}

#[cfg(test)]
mod tests {
    use super::py_tuple;

    #[test]
    fn tuple_repr_edge_cases() {
        assert_eq!(py_tuple(&[]), "()");
        assert_eq!(py_tuple(&["1".into()]), "(1,)");
        assert_eq!(py_tuple(&["1".into(), "2".into()]), "(1, 2)");
    }
}
