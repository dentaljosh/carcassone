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

/// `repr()` of a plain-ASCII identifier-ish str (every value we emit is one).
fn py_str(s: &str) -> String {
    debug_assert!(
        !s.contains('\'') && !s.contains('\\') && s.is_ascii(),
        "repr() of {s:?} needs the full CPython escaping rules"
    );
    format!("'{s}'")
}

pub fn string_representation(state: &GameState) -> String {
    let mut placed: Vec<String> = Vec::with_capacity(state.placed_coords.len());
    for &(row, col) in &state.placed_coords {
        let tid = match state.get_tile(row, col) {
            // defensive, exactly like the Python `continue`
            None => continue,
            Some(t) => t,
        };
        let tile = tiles::tile(tid);
        placed.push(py_tuple(&[
            row.to_string(),
            col.to_string(),
            py_str(tile.description),
            tile.rot_sig_repr.clone(),
        ]));
    }

    let meeples = py_tuple(
        &(0..state.players)
            .map(|p| {
                py_tuple(
                    &state.placed_meeples[p]
                        .iter()
                        .map(|mp| {
                            py_tuple(&[
                                py_str(mp.meeple_type.value()),
                                mp.coord.row.to_string(),
                                mp.coord.col.to_string(),
                                py_str(mp.side.value()),
                            ])
                        })
                        .collect::<Vec<_>>(),
                )
            })
            .collect::<Vec<_>>(),
    );

    let scores = py_tuple(
        &(0..state.players)
            .map(|p| state.scores[p].to_string())
            .collect::<Vec<_>>(),
    );
    let meeple_counts = py_tuple(
        &(0..state.players)
            .map(|p| state.meeples[p].to_string())
            .collect::<Vec<_>>(),
    );
    let next_tile = match state.next_tile {
        None => "None".to_string(),
        Some(base) => py_str(tiles::tile(tiles::tile_id(base, 0)).description),
    };
    let last_tile_coord = match state.last_tile_action {
        None => "None".to_string(),
        Some(lta) => py_tuple(&[lta.coord.row.to_string(), lta.coord.col.to_string()]),
    };

    py_tuple(&[
        py_tuple(&placed),
        meeples,
        scores,
        meeple_counts,
        state.current_player.to_string(),
        py_str(state.phase.value()),
        state.deck_len().to_string(),
        next_tile,
        last_tile_coord,
    ])
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
