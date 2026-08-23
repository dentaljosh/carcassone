//! ⛔ `#[ignore]`d BLAST-RADIUS PROBE for the 2026-08-23 board-bounds fix.
//!
//! `cargo test -p carc-core --release -- --ignored board_wall_probe --nocapture`
//!
//! The fix at [`super::GameState::board_direct`] removes a CRASH and deliberately
//! leaves the CPython `-1` wrap in place.  That split is only defensible if the
//! wrap is not silently corrupting anything, so this measures the two conditions
//! rather than arguing about them.
//!
//! Every index this engine can produce is ONE step off a placed tile
//! (`CityUtil.opposite_edge`, `FarmUtil.opposite_edge`, the cloister 3x3), so:
//!
//!   PANIC CONDITION (the pre-fix crash) — a tile on the LAST row or column.
//!   The step reaches index 35 and CPython's `IndexError` fired.  This killed
//!   three live b32v64 games on 2026-08-22.
//!
//!   WRAP CONDITION (a silent wrong-cell READ) — `-1` is the only negative index
//!   reachable, and `py_index` maps it to the OPPOSITE extreme.  So the wrap
//!   returns a real tile if and only if the board occupies row 0 AND row 34 (or
//!   column 0 and column 34) in the same game: a full 35-cell span of a 72-tile
//!   deck.  Nothing weaker will do it.
//!
//! MEASURED 2026-08-23.  This probe under the `fixed_v1` geometry: widest span
//! **19 rows / 19 columns of 35** at the committed `GAMES = 1,000`, and **20
//! rows / 22 columns** on a one-off 4,000-game run — zero wall contacts and zero
//! wrap conditions in both.  Against the RECORDED CHAMPION corpora, which are the
//! population that actually crashed:
//!
//!   `measurement/champ_action_logs` (449 games, `walled`, start row 6)
//!       row 0 occupied in **346 of 449 games (77%)** — the near wall is only six
//!       rows up, so `board_direct(-1, col)` is on the production hot path and
//!       always has been — yet row 34 occupied in **0**, widest span 17 rows /
//!       19 columns.  Every one of those wrapped reads landed on an empty cell
//!       and correctly answered "no tile".
//!   `measurement/e4_games` (39 phone games, `fixed_v1`, start row 18)
//!       widest span 16 rows / 17 columns, no wall contact.
//!
//! VERDICT: the wrap is exercised constantly and has never once been observable,
//! because it needs a span no game comes within 13 rows of.  It is a latent
//! defect, not a live one — and "latent" is a property of the corpus, not of the
//! code, which is why this probe exists to be re-run rather than cited.
//!
//! ⚠️ NOTE WHAT THIS PROBE DOES **NOT** SHOW.  Tier-1 self-play from ply 1 never
//! reaches a wall, so it cannot exercise the panic condition; the live crashes
//! came from tier-1 playouts CONTINUING a champion midgame, a different and
//! wider-spreading distribution.  The panic's reachability is established by the
//! three live seeds, not here.

use super::*;
use crate::game::{DrawRule, Game, GameConfig, StartRule};
use crate::tier1::RuleBasedPlayer;

const GAMES: usize = 1_000;
const MAX_PLIES: usize = 400;

fn fixed_v1() -> GameConfig {
    GameConfig {
        window_size: 25,
        start_rule: StartRule::Retail,
        start_row: 18,
        start_col: 15,
        cloister_scan_fix: true,
        draw_rule: DrawRule::Redraw,
    }
}

#[test]
#[ignore = "blast-radius probe: minutes, not seconds — run it deliberately"]
fn board_wall_probe() {
    let (mut touch_r0, mut touch_r34, mut touch_c0, mut touch_c34) = (0, 0, 0, 0);
    let (mut panic_cond, mut wrap_cond) = (0usize, 0usize);
    let (mut max_row_span, mut max_col_span) = (0i32, 0i32);

    for i in 0..GAMES {
        let seed = 140_000_000_000i64 + i as i64;
        let mut g = Game::from_seed_with_config(&seed.to_string(), fixed_v1())
            .expect("fixed_v1 is a valid config");
        let mut agent = RuleBasedPlayer::new(seed);
        let mut plies = 0;
        while !g.is_terminal() && plies < MAX_PLIES {
            let a = agent
                .choose_action(&g, None)
                .expect("tier1 always has a legal action");
            g.advance(a).expect("tier1 only picks legal actions");
            plies += 1;
        }

        let rows: Vec<i32> = g.state.placed_coords.iter().map(|&(r, _)| r).collect();
        let cols: Vec<i32> = g.state.placed_coords.iter().map(|&(_, c)| c).collect();
        let (r_lo, r_hi) = (*rows.iter().min().unwrap(), *rows.iter().max().unwrap());
        let (c_lo, c_hi) = (*cols.iter().min().unwrap(), *cols.iter().max().unwrap());

        max_row_span = max_row_span.max(r_hi - r_lo + 1);
        max_col_span = max_col_span.max(c_hi - c_lo + 1);

        let (first_row, last_row) = (r_lo == 0, r_hi == BOARD_ROWS - 1);
        let (first_col, last_col) = (c_lo == 0, c_hi == BOARD_COLS - 1);
        touch_r0 += first_row as usize;
        touch_r34 += last_row as usize;
        touch_c0 += first_col as usize;
        touch_c34 += last_col as usize;
        panic_cond += (last_row || last_col) as usize;
        wrap_cond += ((first_row && last_row) || (first_col && last_col)) as usize;
    }

    println!("\n=== board wall probe: {GAMES} tier1-vs-tier1 games, fixed_v1 geometry ===");
    println!("  touched row 0 / row 34 : {touch_r0} / {touch_r34}");
    println!("  touched col 0 / col 34 : {touch_c0} / {touch_c34}");
    println!("  PANIC condition        : {panic_cond}  (a tile on the last row/col)");
    println!("  WRAP  condition        : {wrap_cond}  (BOTH ends of one axis occupied)");
    println!(
        "  widest span seen       : {max_row_span} rows / {max_col_span} cols of {BOARD_ROWS}"
    );

    // THE CLAIM UNDER TEST.  The wrap can only return a real tile on a full-axis
    // span, so the honest assertion is the SPAN BOUND — it holds whether or not
    // this population happens to touch a wall, and it is what makes the wrap
    // unobservable.  (`wrap_cond` is implied by it; asserted too, cheaply.)
    assert!(
        max_row_span < BOARD_ROWS && max_col_span < BOARD_COLS,
        "a game spanned a FULL axis ({max_row_span} rows / {max_col_span} cols) — \
         the `-1` wrap is now observable and the silent-read path is LIVE.  This \
         is the trigger to fix the wrap itself, behind a GameConfig flag."
    );
    assert_eq!(
        wrap_cond, 0,
        "wrap condition reached: the `-1` read returns a real tile in {wrap_cond} game(s)"
    );
}
