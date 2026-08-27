# External-reference inventory — candidate third referee engine ("carcassonne-rust")

> **Status: COMPLETE 2026-08-27.**
> **VERDICT: one candidate survives — `kotatsuyaki/carcassonne-rust`, GO as a *rules referee*,
> NO-GO as an *opponent*. The two GitHub Rust candidates are NO-GO on structural grounds.**
>
> Day-1 deliverable per the house method (memory `feedback_external_reference_first`):
> **inventory + rules-divergence audit**, and *rules agreement gates the harness*. Fourth run
> of that method, after the JCZ oracle
> ([`jcz_match_20260809/CONFIRM_READOUT.md`](../jcz_match_20260809/CONFIRM_READOUT.md)),
> Carcasum ([`carcasum_audit_20260823/AUDIT_READOUT.md`](../carcasum_audit_20260823/AUDIT_READOUT.md)),
> and the round-2 web inventory
> ([`docs/research/EXTERNAL_INVENTORY_R2_2026-08-23.md`](../../docs/research/EXTERNAL_INVENTORY_R2_2026-08-23.md)).
> Shape mirrors [`carcasum_match_prep/AUDIT_PLAN.md`](../carcasum_match_prep/AUDIT_PLAN.md).
>
> All compute on the **laptop** (`ssh laptop-wsl`, 24T, `nice -n 19`). Clones at
> `/home/doctor/extref/`. Nothing ran on the 5900XT. **No match harness was built and no
> strength number is produced or authorised by this document.**

---

## 0. Correction up front — the menu item was already occupied

An initial GitHub-only sweep found no Rust engine matching our scope and was about to record
the "carcassonne-rust" menu item as *empty*. **That would have been wrong.**
[`docs/LEVER_INDEX.md`](../../docs/LEVER_INDEX.md) §9 already carries a row for
**`kotatsuyaki/carcassonne-rust`** — which lives on **GitLab, not GitHub**, and so is
invisible to `gh search`. It was triaged on 2026-08-23 (R3 addendum,
[`EXTERNAL_INVENTORY_R2` §7](../../docs/research/EXTERNAL_INVENTORY_R2_2026-08-23.md)) as a
near-exact scope match and candidate third referee, **disposition unfunded**.

That triage was explicitly *source-reading only* — the R2 doc's own status line reads
"nothing built, nothing run". **This audit closes that gap: first build, first run, and an
independent re-derivation of the rules claims from source.** Every §2 row below was read
fresh from a working copy rather than inherited from the prior triage; where they agree,
that is confirmation, and §2.4 records the two places the prior triage was incomplete.

**Lesson worth keeping:** `gh search` cannot see GitLab, SourceHut, or Codeberg. An external
inventory that runs on `gh` alone will silently under-report, and in this case would have
retired a live candidate as nonexistent.

---

## 1. Candidate menu (screened)

Searched GitHub by language, topic, and code (`gh search repos/code`) across `carcassonne`,
`carcassonne ai`, `carcassonne mcts`, `carcassonne bot`, `carcassonne agent`,
`carcassonne monte carlo`, `topic:carcassonne`, `meeple language:Rust`; plus the standing
LEVER_INDEX §9 row for the GitLab candidate.

| Repo | Host | Lang | License | AI | Result |
|---|---|---|---|---|---|
| **[kotatsuyaki/carcassonne-rust](https://gitlab.com/kotatsuyaki/carcassonne-rust)** | GitLab | Rust | **none** | MCTS (chance nodes, UCT √2) + a GNN (no weights) | **Built + audited → GO as referee, NO-GO as opponent (§2)** |
| **[nr6000000/carcassonne-uct](https://github.com/nr6000000/carcassonne-uct)** | GitHub | Rust | **none** | UCT / UCT-RAVE / UCT-ECO, minimax, heuristic, greedy | **Built + audited → NO-GO (§3)** |
| **[human-0/carcassonne-bot](https://github.com/human-0/carcassonne-bot)** | GitHub | Rust | GPL-3.0 | 1-ply exhaustive eval + heuristics, SPRT-tuned | **Built + audited → NO-GO (§4)** |
| [tsaglam/Carcassonne](https://github.com/tsaglam/Carcassonne) | GitHub | Java | EPL-2.0 | `RuleBasedAI` — 1-ply rule-based, *does* handle fields | Noted, not built (§5) |
| [Maurdekye/carcassonne](https://github.com/Maurdekye/carcassonne) | GitHub | Rust | none | none (GUI + lobby only) | No AI — rejected |
| [Shedarshian/cacason-bot](https://github.com/Shedarshian/cacason-bot) | GitHub | Rust | MIT | none yet (`main.rs` 484 B) | Stub — rejected |
| [WilliamMoolman/rustassonne](https://github.com/WilliamMoolman/rustassonne), [wlyh514/carcassonne](https://github.com/wlyh514/carcassonne), [shypre/rustcassonne](https://github.com/shypre/rustcassonne), [specialjcg/carcassone](https://github.com/specialjcg/carcassone) | GitHub | Rust | mixed | none / trivial | Rejected |
| [quibbble/go-carcassonne](https://github.com/quibbble/go-carcassonne) | GitHub | Go | — | none (rules only) | No AI — rejected |

Previously-triaged-and-rejected candidates (`hanskrig/carcassonne-rl`, `drgtheneutrino`,
`abhg86`, Xbox360 Sierra, TheCodingMonkeys, BGA, BrettspielWelt, Carcassonne-SGE,
YetAnotherSpieskowcy, fancarpedia) are **not re-litigated here** — see
[`EXTERNAL_INVENTORY_R2`](../../docs/research/EXTERNAL_INVENTORY_R2_2026-08-23.md) §1 and §7.

---

## 2. `kotatsuyaki/carcassonne-rust` — the real candidate

| field | value |
|---|---|
| Repo | `https://gitlab.com/kotatsuyaki/carcassonne-rust` |
| HEAD audited | `d490fd1f314b11d2400c7d6016cc62fee51b1698` (2021-09-21, "Add readme") — dead since |
| License | **NONE** — no `LICENSE`, no SPDX. All rights reserved by default ⇒ **private benchmarking only, no redistribution/vendoring.** |
| Layout | Cargo workspace: `carcassonne` (1245 LOC engine), `carcassonne-mcts` (443), `carcassonne-gnn` (GATv2, ScalableAlphaZero-style), `server`, `testdrive`, `selfplay-train`, `profile-playground` |
| AI type | **Search-based.** Real chance-node MCTS — `legal_draws()` supplies weighted chance children (`carcassonne-mcts/src/lib.rs:282-285`) and selection is textbook UCT with `sqrt(2.0)` (`:212`), random playouts. GNN is training code only — no published weights. |
| Build on laptop | **PASS — `carcassonne` + `carcassonne-mcts` in 5.67 s** once the toolchain is pinned (§2.2). |
| Self-test | **None exists** — `cargo test` compiles and runs, reporting `0 passed` across all four targets. The repo has no test suite whatsoever. |
| Smoke | **PASS — it plays.** See §2.2b. |

### 2.1 Divergence table

| # | rule point | our engine | theirs | citation | verdict |
|---|---|---|---|---|---|
| 1 | **Tied-feature scoring** | ALL tied players score FULL points (engine patched) | Identical, and explicit: `Ordering::Equal if red_count != 0 => &[Red, Blue]`, then **each** scored player is credited the full `area_score`. (The `red_count != 0` guard correctly makes an unclaimed feature score nobody.) | `carcassonne/src/lib.rs:847-863`, esp. **`:851-860`** | ✅ **MATCH** |
| 2 | **Farm scoring variant** | modern 3 pts per completed adjacent city | Identical: `let area_score = (city_count * 3) as u8`. `city_count` comes from `field_floodfill`, whose `city_ids` map is populated **only for cities with `is_closed == true`** — so incomplete cities correctly score the field nothing. Per-field independent, size-independent. | `carcassonne/src/lib.rs:697` (the ×3), `:739-743` (closed-cities-only), `:586-630` (`field_floodfill`) | ✅ **MATCH** |
| 3 | **Cloister / road / city scoring** | road 1/tile; city 2/tile completed, 1 incomplete; pennant +2/+1; cloister 9 | Identical. `area_score = (tile_count + pennant_count) * score_multiplier` with `score_multiplier = 2` for cities and `1` for roads in-game, and `1` for **everything** at endgame — which yields city 2/1, pennant +2/+1, road 1/1 exactly. Cloister is a flat `+= 9` on completion. | `carcassonne/src/lib.rs:672` (formula), `:259` (in-game multiplier), `:758` (endgame multiplier 1), `:277` (cloister 9) | ✅ **MATCH** |
| 4 | **Farmer placement / adjacency semantics** | `find_farm` = full connected-component, start-independent (R9 fix, DECISIONS 2026-05-29) | Equivalent in kind: an explicit stack-based flood fill over `(Coord, FeatureId)` pairs with a `visited` set, crossing to `neighbor.tile.feature_id_of(seg.opposite())`. Start-independent by construction (full component traversal, dedup by `visited`). Feature granularity is per-tile-edge-segment, i.e. the same half-edge model whose convention produced the R9 bug class — **this is exactly what a differential audit exists to check**, and it is the one row that source reading cannot fully settle. | `carcassonne/src/lib.rs:586-630`, `:614-621` (neighbour crossing) | ✅ **MATCH in kind** — half-edge convention needs differential testing (R9 class) |
| 4b | **Farms never score mid-game / farmers never return** | invariant | **Upheld.** Fields are scored only inside `endgame_score_update`'s second pass, and `field_update_scores` reads meeples with `.get()` — it never removes them and never increments `meeples_remain`. Contrast `update_scores`, which recycles when `should_recycle_meeples`. | `carcassonne/src/lib.rs:774-810` (endgame-only), `:686-695` (`.get()`, no recycle) | ✅ **MATCH** |
| — | **Tile-set fidelity** | standard 72-tile base deck, no expansions | **72 exactly** — `NUM_TILES` (24 kinds) sums to 72, verified by summing the array. `Board::new()` builds the deck from all kinds **minus one `CastleWallRoad`**, which is placed at (0,0) as the start tile ⇒ **71 drawn**, our exact convention. No river or expansion kinds exist. | `carcassonne/src/tiles.rs:824-849` (sums to 72), `carcassonne/src/lib.rs:109-118` (deck minus start), `:135-141` (start tile placed) | ✅ **MATCH** |
| — | **Players** | 2 | **2, structurally** — `scores: [u8; 2]`, `meeples_remain: [u8; 2]`, `enum Player { Red, Blue }`. Not a configurable N. | `carcassonne/src/lib.rs:75-76`, `:847-856` | ✅ **MATCH** |
| — | **Meeple count** | 7 | **7** | `carcassonne/src/lib.rs:129` | ✅ **MATCH** |
| — | **Game end** | deck exhaustion | `is_ended()` ⇔ `deck.is_empty()`; `endgame_score_update()` fires when the deck empties. | `carcassonne/src/lib.rs:152-154`, `:282-283` | ✅ **MATCH** |
| — | **Tile draw** | draw 1, place it | Real draw: `do_action` pops the deck top (`:209`), and `draw()` randomly swaps a tile into the last slot (`:429-438`). A genuine stochastic single-tile draw. | `carcassonne/src/lib.rs:209`, `:429-438` | ✅ **MATCH** |
| — | **🔧 Deck seeding** | deck-seeded, paired | **`thread_rng()`, unseeded, at every site** — `draw()` (`:436`), `Rotation::choose()` for the **start-tile rotation** (`:1220`), and five sites in the MCTS. Deck-paired replay is impossible without a patch. | `carcassonne/src/lib.rs:436`, `:1220`; `carcassonne-mcts/src/lib.rs:188,216,233,247,318` | ⚠️ **patch required** (see §2.4) |

**Ten of eleven rule rows are a clean MATCH**, including all four critical points, on an
engine that was never written with our conventions in view. That is the strongest rules
agreement of any candidate found outside JCZ and Carcasum.

### 2.2 Build — solved, and cheaper than "medium effort"

The prior triage estimated "build-compat patch + a ~15-line seed hook, medium effort."
**The build-compat half needs no patch at all.** On modern stable (rustc 1.97.1) the build
dies in a *transitive dependency*:

```
error: `box_syntax` has been removed
error: could not compile `guard` (lib) due to 4 previous errors
```

`guard v0.5.1` uses the long-removed nightly `box_syntax` feature. Rather than vendor and
patch it, pin an era-matched nightly — **a one-line fix, no source changes**:

```bash
rustup toolchain install nightly-2021-10-01 --profile minimal   # rustc 1.57.0-nightly
cargo +nightly-2021-10-01 build --release -p carcassonne-testdrive
```

Only the seed hook remains real work, and §2.1's last row shows it is **two sites in the
engine** (`draw`, `Rotation::choose`), not one — plus the MCTS's own five if playouts must
be reproducible.

> ⚠️ **Do not build the whole workspace.** `carcassonne-gnn`, `server`, `selfplay-train` and
> `testdrive` pull a `pyo3`/torch chain that **still fails** on the era nightly —
> `error[E0425]: cannot find function ... PyUnicode_READY in module ffi`, i.e. `pyo3` 0.14
> against a modern system Python. Irrelevant to referee use. Build
> **`-p carcassonne -p carcassonne-mcts`** (5.67 s, clean) and leave the GNN path alone.
> A third trap for anyone chasing `testdrive`: a *standalone* crate path-depending on
> `carcassonne` also fails to resolve (`funty ~1.2` is yanked) — build **inside** the
> workspace so its committed `Cargo.lock` is used.

### 2.2b Smoke — it plays, and the ply count independently confirms the deck

A ~30-line random-self-play example (`carcassonne/examples/smoke.rs`, added to the working
copy as an untracked file — **no engine source was modified**) driving only the public
`Board` API:

```
game 0: plies=71 scores=[15, 13] deck_remain=0 meeples_remain=[0, 0]
game 1: plies=71 scores=[ 7, 24] deck_remain=0 meeples_remain=[0, 0]
game 2: plies=71 scores=[15, 27] deck_remain=0 meeples_remain=[0, 0]
--- 200 random self-play games (Board::new, full deck) ---
P0 wins 111  P1 wins 81  draws 8
mean plies 70.7   mean score  P0 18.5  P1 17.3
```

**`plies = 71`, every game.** That is the source claim of §2.1 (72-tile deck minus the
`CastleWallRoad` start tile) confirmed *behaviourally* rather than by reading — the one
row in this document that got a real empirical check. Mean scores of 18.5 / 17.3 under
uniformly random play are of the right order for base+farmers Carcassonne, and the
first-seat edge is expected: 71 is odd, so P0 places 36 tiles to P1's 35.

The whole loop is five lines, which is the drivability claim of §2.3 demonstrated:

```rust
let mut board = ccs::Board::new();
while board.is_ended() == false {
    board.draw();
    let action = *board.legal_actions().choose(&mut thread_rng()).unwrap();
    board.do_action(action);
}
```

⚠️ The crate's **lib name is `ccs`, not `carcassonne`** (`[lib] name = "ccs"`) — a fourth
small trap for a future driver author.

### 2.3 Drivability

- **Clean library API on `Board`**, which is what a referee needs and the best surface of any
  candidate: `tiles_iter`, `meeples_iter`, `deck_iter`, `turn`, `remain`, `scores`,
  `winner`, `meeples_remain`, `is_ended`, plus `do_action` / legal-action generation
  (`carcassonne/src/lib.rs:156-172`, `:866-888`, `:209`, `:321-386`).
- A **driver would be a small Rust bin linking `carcassonne`** — no IPC, no protocol,
  no parsing. Cheaper than the Carcasum driver was.
- **AI budget is iteration count** (`--mcts/-m`), so budgeting is deterministic and a
  budget ladder is definable — the property CL-070 says we need and RoDv2-as-anchor lacks.
- **`server/`** exposes an HTTP backend for the separate `carcassonne-ui` project — an
  alternative drive path, unexamined here.

### 2.4 Ops traps — the two known ones confirmed, four more found

The prior triage flagged the first two; both verified, and one is worse than recorded:

1. **`testdrive` defaults to the Small board.** `#[structopt(long = "size", default_value = "BoardSize::Small")]` (`testdrive/src/main.rs:65`), and `Board::new_small()` replaces the 72-tile deck with **one tile of each kind — 24 tiles** (`carcassonne/src/lib.rs:146-150`). Any benchmark that forgets `--size Normal` is measuring a different, tiny game. This is also the board the author's GNN self-play used, which is why the blog's AZ results say nothing about the real game.
2. **`testdrive` defaults to 500 MCTS iterations** (`testdrive/src/main.rs:52`) while the author's own "≈average human" claim was made at 4000. A default-config run under-reports their engine by 8×.

**Not in the prior triage, found here:**

3. **The seed hook is two engine sites, not one.** The **start-tile rotation** is also drawn from `thread_rng()` (`carcassonne/src/lib.rs:134` → `:1220`), so a naive `draw()`-only patch still yields non-reproducible games. (Plus five MCTS sites if playouts must also be reproducible.)
4. **The modern-toolchain problem needs no source patch** — it is entirely in the `guard` dependency, and toolchain pinning solves it (§2.2).
5. **There is no test suite.** `cargo test` reports `0 passed` on every target. Nothing in this repo self-verifies its own scoring — so a differential audit against our engine would be the *first* test this code has ever had, and there is no upstream golden set to lean on. This raises, not lowers, the value of the audit — but it also means **no rules row here may be trusted on the author's reputation for care.**
6. **`[lib] name = "ccs"`**, `carcassonne-mcts` → `ccs_mcts`, `testdrive` → binary `ccs-testdrive`. Package names and lib names differ throughout; `-p testdrive` fails, `-p carcassonne-testdrive` is correct.

### 2.5 Verdict

**GO as a rules referee** — 10/11 rule rows match including all four critical points, an
independent half-edge field implementation makes it a genuinely informative R9-class
differential target, and the build is now a two-line recipe.

**NO-GO as an opponent** — no calibrated strength evidence exists (the author's claim has no
n, no opponent, no clock), the prior triage's judgement of "likely sub-JCZ" is unchallenged
by anything found here, and JCZ is already sliding toward saturation. Adding a probably-weaker
reference does not address blocker #1.

**Gating, unchanged from house method:** the referee role requires the seed hook plus a
differential audit meeting the standing bar — *0 REAL divergences, final scores agree N/N*
([`AUDIT_PLAN.md`](../carcasum_match_prep/AUDIT_PLAN.md)). Row 4's half-edge convention is
precisely what that audit would be for. **This document does not authorise that work** —
disposition remains the owner's, and remains unfunded.

---

## 3. `nr6000000/carcassonne-uct` — Rust MCTS, **NO-GO**

| field | value |
|---|---|
| Repo | `https://github.com/nr6000000/carcassonne-uct` |
| HEAD audited | `293292984f41cb86fbfd2d898efc4a37be3985d9` (2026-06-14) |
| License | **NONE** — no `LICENSE`/`COPYING`, no SPDX field |
| Provenance | Polish MSc AI-methods project (`MSI_Carcassone___Konspekt_Projektu.pdf` in-repo) |
| AI type | **Search-based.** `UctEngine` with three presets (`uct_engine.rs:94/98/102`): `new_basic` (plain UCT, c=√2), `new_rave` (UCT-RAVE, β=√(k/(3n+k)), `uct_engine.rs:133-145`), `new_eco` (depth-capped). Plus `MinimaxEngine`, `HeuresticEngine`, `GreedyEngine`, `RandomEngine`. Tree reused across moves (`uct_engine.rs:327-332`); move chosen by max visits (`:340-344`). |
| Build on laptop | **PASS** — `cargo build --release`, **10.65 s**, rustc 1.97.1, 26 warnings, 0 errors |
| Self-test | **PASS 14/14** — `cargo test --release`: 9 unit + `score_city_split`, `score_city_nosplit`, `score_cloister`, `score_field`, `score_road` |

### 3.1 Divergence table

| # | rule point | our engine | theirs | citation | verdict |
|---|---|---|---|---|---|
| 1 | **Tied-feature scoring** | ALL tied players score FULL points | Identical. `max_set_by_key` returns **every** player tied at the max follower count; each is credited `structure.points` in full. | `src/game_logic/game.rs:547-555` | ✅ **MATCH** |
| 2 | **Farm scoring variant** | modern 3 pts per completed adjacent city | Identical. Field flood-fill collects adjacent city pixels; each distinct city component is completion-tested; `score += 3` per completed city, flat and size-independent. | `src/game_logic/structures.rs:120-171`, esp. **`:164-167`**; asserted by `tests/score_field.rs:119` (expects **6** = 2 completed cities × 3) | ✅ **MATCH** |
| 3 | **Cloister / road / city scoring** | road 1; city 2/1; pennant +2/+1; cloister 9 | Identical. `Road=>1/1`, `City=>2/1`, `PennantCity=>4/2`; cloister `neighbour_count(place)+1` ⇒ 9. **A completed 2-tile city scores 4, not 2** — no legacy tiny-city case, matching our patch. | `src/game_logic/tilepixel_ext.rs:58-68`; cloister `src/game_logic/structures.rs:183-186` | ✅ **MATCH** |
| 4 | **Farmer placement / adjacency** | full connected-component `find_farm` | Different representation, equivalent connectivity: tiles are **5×5 pixel rasters**, fields 4-neighbour scanline-flood-filled, `connects` joins Field↔Field only. Start-independent. | `src/game_logic/flood_fill.rs:15-101`, `src/game_logic/tilepixel_ext.rs:49-56` | ⚠️ **PARTIAL** |
| 4b | **Farms never score mid-game / farmers never return** | invariant | **VIOLATED.** Fields use the same `completed` path as roads/cities (`completed` falsified only when the fill touches a `Nothing` pixel). `play_move` scores *every* completed structure and returns its followers — so a field enclosed by cities/roads within placed tiles **scores mid-game and hands the farmer back**. | `src/game_logic/game.rs:585-589`; `src/game_logic/structures.rs:31-45`, `:73-83` | ❌ **REAL divergence** |
| — | **Tile-set fidelity** | 72-tile base deck | **72 exactly** (`[tile-numbers]` sums to 72 over 24 faces); start tile `CRFR` placed and removed from the bag ⇒ 71 drawn. No expansions. | `tilesets/standard/tileset.toml:30-54`, `src/game_logic/game.rs:236-239` | ✅ **MATCH** |
| — | **Meeple count** | 7 | **8** (`number_followers: 8`), configurable | `src/game_logic/game.rs:55` | ⚠️ patchable |
| — | **Farmers enabled** | always | **OFF by default**, and the shipped tournament disables them ⇒ the published UCT/RAVE tuning is a **farmers-off** tuning | `src/game_logic/game.rs:57`, `src/main.rs:33` | ⚠️ tuning does not transfer |
| — | **🛑 Tile draw** | draw 1, place it | **THERE IS NO DRAW.** `get_moves_placement` iterates `self.tiles_left.elements()` — *every* tile left in the bag — × every free place × 4 rotations; `play_move` then removes the chosen tile. All engines and the WASM layer route through this. | `src/game_logic/game.rs:306-308`, `:573-574`, `:370-372`; `src/js_binds/wasm_game.rs:233,419` | ❌ **IRRECONCILABLE** |

### 3.2 The demo plays — and that is itself disqualifying

`cargo run --release` (farmers off, 2 players, 3 games/pair) completed its first matchup:

```
  >> UCT-ECO(3400,d=10) vs RAVE(2000,k=300)
     [ 1/3] wynik:  31 -   0  (1 wygrywa)  czas: 26.0s vs 12.9s  [lacznie 39.2s]
     [ 2/3] wynik:  36 -   0  (1 wygrywa)  czas: 24.1s vs 17.1s  [lacznie 41.5s]
     [ 3/3] wynik:  34 -   0  (1 wygrywa)  czas: 23.3s vs 17.6s  [lacznie 41.0s]
  WYNIK: UCT-ECO(3400,d=10) W:3 D:0 L:0 | RAVE(2000,k=300) W:0 D:0 L:3   sr.pkt: 33.7 vs 0.0
```

**The loser scores exactly zero, three times out of three.** A 2000-iteration UCT-RAVE agent
completing *not one structure* across ~71 plies does not happen in Carcassonne — it happens
in a game where the mover picks its own tile from the whole bag (§3.1 row 🛑) and can starve
the opponent outright. Recorded as an observation corroborating the structural finding,
**not** diagnosed — diagnosis is not worth the hours given the NO-GO.

### 3.3 Drivability (recorded for completeness)

Genuinely good — `src/lib.rs` exposes the crate so a driver is a small Rust bin; a JSON
protocol already exists for the WASM front end (`get_starting_info`, `compute_human_moves`,
`get_meeple_options`, `play_human_move`, `bot_play`, `get_board_state`, `get_scores`,
`is_game_over`, `end_game` — `src/js_binds/wasm_game.rs:221-503`); budget is iteration count
(`uct_engine.rs:13,335`). Deck RNG is unseeded `rand::rng()` (`game.rs:232`). All moot.

### 3.4 Verdict

**NO-GO** — the engine has no tile draw (`game.rs:306-308`), so it is not the game we
measure and no deck-paired contrast is definable; farms also score mid-game, and the missing
license is an independent blocker.

---

## 4. `human-0/carcassonne-bot` — Rust competition bot, **NO-GO**

| field | value |
|---|---|
| Repo | `https://github.com/human-0/carcassonne-bot` |
| HEAD audited | `9258c126162167025195b20457a1d65f080c9cf3` (2025-07-24) |
| License | **GPL-3.0** |
| Provenance | Entry for **SYNCS Bot Battle 2025** ([`syncs-usyd/public-carcassonne-game-engine`](https://github.com/syncs-usyd/public-carcassonne-game-engine)); the Rust workspace reimplements that Python engine from scratch |
| AI type | **1-ply exhaustive**, not tree search: enumerate every legal (tile, meeple) pair, evaluate as if the game ended immediately, apply an unreturned-meeple penalty, maximise own-minus-others (`bot-algo.md`). Author states it cannot plan more than one move ahead. Tuned by **SPRT** over ~10⁵ games. |
| Build on laptop | **PASS** — `cargo build --release`, **9.49 s** (6 crates + deps), 0 errors |
| Self-test | **`cargo test` does not compile** — 6× `error[E0308]: mismatched types` in the inline `#[cfg(test)]` module at `carcassonne-engine/src/state.rs:270-343` (a `HashSet`/`foldhash` hasher-type mismatch — dependency bit-rot since 2025-07). Library and binaries unaffected. |
| Demo | **Plays, and fast.** The in-repo `sprt` binary ran bot-vs-bot to **6000 complete games in 90 s** (~67 games/s, single process) with a live SPRT readout. Best engineering of any candidate seen. |

### 4.1 Divergence table

| # | rule point | our engine | theirs | citation | verdict |
|---|---|---|---|---|---|
| 1 | **Tied-feature scoring** | ALL tied players score FULL points | Identical: max claim count computed, then `let reward = if meeples.len() == max { reward } else { 0 }` — every player at the max gets the full reward. | `carcassonne-engine/src/lib.rs:212-214` | ✅ **MATCH** |
| 2 | **Farm scoring variant** | modern 3 pts per completed adjacent city | **FARMS DO NOT EXIST.** `Structure::Grass` is a terrain, but `is_placeable` admits only `Road \| RoadStart \| City`, so no meeple can be a farmer; `Structure::points` returns `0` for Grass via the `_` arm. Zero occurrences of `farm`/`farmer`/`meadow` in the workspace. | `carcassonne-util/src/interact/structure.rs:37-39`, **`:41-48`**, `:9-16` | ❌ **IRRECONCILABLE** — our scope is base **+ farmers** |
| 3 | **Cloister / road / city scoring** | road 1; city 2/1; pennant +2/+1; cloister 9 | Identical: `ROAD_POINTS=1`, `CITY_POINTS=2`, `CITY_PARTIAL_POINTS=1`, `MONASTARY_POINTS=9`; `EMBLEM` adds `+2` complete / `+1` partial. | `carcassonne-util/src/interact/structure.rs:3-6`, `:41-48`, `:50-64` | ✅ **MATCH** |
| 4 | **Farmer placement / adjacency** | full connected-component `find_farm` | N/A — not implemented | — | ❌ **ABSENT** |
| — | **Tile-set fidelity** | 72-tile base deck, **no River** | Base deck **72, verified by their own test** (`assert_eq!(count, 72)`), plus a **12-tile River set** (`assert_eq!(count, 12)`) that is **on by default** (`river_phase: true`). | `carcassonne-util/src/interact/tile/properties.rs:421`, `:472`, `:484`; `carcassonne-engine/src/state.rs:27,42` | ⚠️ base ✅ / River out of scope |
| — | **Meeple count** | 7 | 7 | `carcassonne-util/src/interact/meeple.rs:5` | ✅ **MATCH** |
| — | **🛑 Game end** | deck exhaustion | **50-point sudden death**, checked on every scoring event | `carcassonne-engine/src/state.rs:19`; `state/mutate.rs:115,215,224,250` | ❌ **IRRECONCILABLE** |
| — | **🛑 Hand size** | draw 1, place it | **2 tiles in hand**, 1 drawn per round; mover chooses between them and may discard/replace | `carcassonne-engine/src/state.rs:17-18`; `carcassonne-engine/src/lib.rs:83,89,148` | ❌ **IRRECONCILABLE** |
| — | **🛑 Player count** | 2 | **4, hardcoded as a const** (array sizes depend on it) | `carcassonne-util/src/lib.rs:11` | ❌ **IRRECONCILABLE** |

### 4.2 Drivability

WASM/WASI, not a CLI — the bot compiles to `wasm32-wasip1` and is loaded by a Python stub
(`wasm_stub.py`, `build_bot.sh`) for the SYNCS simulator; `wasm-bot/src/lib.rs` is the
interface layer. Driving it means hosting the module (wasmtime) or linking `simple-bot` as a
crate. The in-repo `sprt` binary would have been the natural match driver. **No budget knob**
— 1-ply exhaustive, so strength is a fixed point and no ladder rung is definable.

### 4.3 Verdict

**NO-GO** — no farmers at all (`structure.rs:37-39`), which alone puts it outside our locked
scope, compounded by 50-point sudden death, a 2-tile hand, River-by-default, and a hardcoded
4 players.

---

## 5. `tsaglam/Carcassonne` — Java, noted and deferred (not built)

The only *other* engine found with a working AI that handles farmers. Recorded so the next
reader's grep cannot miss it; not recommended.

- **Repo / license:** `https://github.com/tsaglam/Carcassonne`, **EPL-2.0**, 129★, actively
  maintained (pushed 2026-08-26).
- **AI:** `RuleBasedAI` (`src/main/java/carcassonne/model/ai/RuleBasedAI.java`) — a 1-ply
  rule-based chooser: enumerate all `(tile, meeple)` moves, keep positive-value ones, avoid
  spending the last meeple on a field, avoid low-value early fields, maximise a combined
  score-plus-meeple value. It **does** model fields (`isFieldMove`, `REQUIRED_FIELD_VALUE`).
  `ZeroSumMove` supplies an opponent-aware move value.
- **Why deferred, one clause each:**
  1. **Not search-based** — a 1-ply heuristic in the same class as our own `tier1-greedy`,
     with no budget dial, so it cannot be a ladder; Tier-1 is already saturated.
  2. **Java, and we already have a Java external** (JCZ Carcasum) that passed a 50/50
     zero-REAL-divergence audit — marginal information is low.
  3. **Swing desktop GUI** with a `StateMachine`/`MainController` architecture and a debug
     `System.out.println` in the AI hot path; headless drivability is a project, not a day.
- **If revisited**, the day-1 questions are whether `MainController` can be driven without
  `view/`, and whether its field rule is 3-points-per-completed-city.

---

## 6. What this inventory does NOT establish

- **Nothing about strength.** No candidate played anything of ours. The `carcassonne-uct`
  tournament (§3.2) and the `sprt` run (§4) are *their* engines against *each other* —
  evidence only that the binaries play games to completion.
- **Nothing about timing.** Builds and demos ran `nice -n 19` on an idle laptop; no timing
  claim is made or needed.
- **§2 is source reading, not differential testing.** Every row is cited to a file and line
  that was read; only the deck size got a behavioural check (§2.2b, `plies=71`). A MATCH row
  says "the code says the same thing", **not** the N/N ply-level agreement the JCZ and
  Carcasum audits earned. **No row here licenses a strength number**, and §2.1 row 4 in
  particular (the half-edge field convention — the R9 bug class) is exactly the kind of
  agreement that has previously *looked* fine in source and failed differentially. The
  absence of any upstream test suite (§2.4 item 5) makes that caveat sharper, not softer.

---

## 7. Recommendation

1. **`kotatsuyaki/carcassonne-rust` stays the standing third-referee candidate, and its
   LEVER_INDEX §9 row should be updated from "medium effort, nothing built" to reflect this
   audit**: build solved by toolchain pin (no source patch), seed hook is two engine sites
   not one, 10/11 rule rows independently re-derived as MATCH. Disposition remains
   **unfunded and the owner's** — nothing here changes the priority argument, which the R2
   doc gates on the Carcasum rung-2 K-SATURATION verdict.
2. **The GitHub Rust menu is closed as empty** — searched and absent. No GitHub-hosted Rust
   Carcassonne engine carries a search AI over 2-player base+farmers with a real tile draw.
3. **Blocker #1 is untouched.** None of these is plausibly stronger than JCZ, so none
   addresses "no strong non-saturated reference". `carcassonne-rust` is a *rules* referee, a
   differential-testing asset — not a ruler.
4. **Process fix:** future external inventories must sweep beyond GitHub. This one nearly
   retired a live, indexed candidate because `gh search` cannot see GitLab.

---

## 8. Provenance — box, census, reproduction

**Box:** laptop (`ssh laptop-wsl`), 24 threads, 11 GB RAM, 907 GB free. Everything
`nice -n 19`. **Nothing ran on the 5900XT** (file edits only).

| | loadavg (1/5/15) | note |
|---|---|---|
| **Before** | `0.12 / 0.08 / 0.01` | idle, as expected — no python/cargo processes |
| **After** | `0.40 / 1.33 / 1.23` | **back to idle** — zero cargo/python processes; the 1/5-min figures are the decay tail of the last build. Nothing left running. |

Toolchains: **cargo/rustc 1.97.1** was already present; **nightly-2021-10-01**
(rustc 1.57.0-nightly, minimal profile) installed by this audit for `carcassonne-rust`.
Total laptop compute ≈ **30 minutes**, dominated by the `carcassonne-uct` demo tournament
(~7 min), the `sprt` run (90 s), and dependency compilation. Disk: **1.9 GB** under
`/home/doctor/extref` (1.4 G carcassonne-rust, 320 M uct, 160 M bot — nearly all `target/`),
on 904 GB free.

**Clones (kept, for any follow-up):**

```
/home/doctor/extref/carcassonne-rust   HEAD d490fd1f314b11d2400c7d6016cc62fee51b1698  (GitLab)
/home/doctor/extref/carcassonne-uct    HEAD 293292984f41cb86fbfd2d898efc4a37be3985d9
/home/doctor/extref/carcassonne-bot    HEAD 9258c126162167025195b20457a1d65f080c9cf3
```

The only file added to any clone is `carcassonne-rust/carcassonne/examples/smoke.rs`
(untracked, §2.2b). **No upstream source was modified in any of the three.**

**Reproduce:**

```bash
export PATH=/home/doctor/.cargo/bin:$PATH

# carcassonne-rust (GitLab) — era-pinned toolchain, no source patch
rustup toolchain install nightly-2021-10-01 --profile minimal
nice -n 19 cargo +nightly-2021-10-01 build --release \
  --manifest-path /home/doctor/extref/carcassonne-rust/Cargo.toml \
  -p carcassonne -p carcassonne-mcts                      # 5.67 s, clean
nice -n 19 cargo +nightly-2021-10-01 run --release \
  --manifest-path /home/doctor/extref/carcassonne-rust/Cargo.toml \
  -p carcassonne --example smoke                          # the §2.2b play smoke

# carcassonne-uct
nice -n 19 cargo build --release --manifest-path /home/doctor/extref/carcassonne-uct/Cargo.toml
nice -n 19 cargo test  --release --manifest-path /home/doctor/extref/carcassonne-uct/Cargo.toml
nice -n 19 timeout 420 cargo run --release --manifest-path /home/doctor/extref/carcassonne-uct/Cargo.toml

# carcassonne-bot
nice -n 19 cargo build --release --manifest-path /home/doctor/extref/carcassonne-bot/Cargo.toml
nice -n 19 timeout 90 /home/doctor/extref/carcassonne-bot/target/release/sprt
```

Every citation in §2, §3 and §4 was read from these working copies at the SHAs above.
