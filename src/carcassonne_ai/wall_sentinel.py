"""F9 W4 — the fail-loud wall sentinel (and the A2 cloister counters).

docs/F9_BUILD_SPEC_20260802.md §A1 W4: "converts every silent denial and every
fatal face into a named, counted, raised event". This module is the COUNTING half,
built first and deliberately built as a **pure observer**:

    it reads the state after a ply; it never touches the state, the legal-move
    set, the agent, or the RNG.

That is not a stylistic choice. The spec's own gate for this item is
*bit-identical actions with the sentinel on vs off*, and the cheapest way to make
that gate informative rather than ceremonial is to make the inertness structural —
no engine file is edited, so there is no code path on which play could differ.
(The RAISING half — `BoardWallError`, the guards in `count_final_scores` and the
farm path — is A1-b, gated separately, and lands only behind a chosen geometry.)

THE FIVE BORDER FACES (DECISIONS 2026-07-31 evening + night, the ledger the spec
names; counted DISTINCTLY here because they fail in three different ways):

  1. **silent wall denial** — `StateUpdater.play_tile` bounds-checks before adding
     to `open_positions`, so a rule-legal cell off the array never enters the
     candidate set. Observable exactly: at each placement, the neighbours that
     fall off the grid are the cells that were dropped. Counted BY FACE
     (row<0 / row>=rows / col<0 / col>=cols) because the row<0 face is the one
     that fires in production and the others are the recentring's new exposure.
  2. **negative-row wrap** — a tile on row 0 makes `board[-1]` read row 34
     (Python negative indexing). Executes in 68% of uniform games and stays
     benign, but it is a *silent wrong read*, so it is counted, not assumed.
  3. **col-34 FATAL** — `FarmUtil.farm_for_position` indexes `board[..][35]`;
     CPython raises IndexError, and 4/4 G1-fuzz games that reached col 34 died.
  4. **last-row FATAL** — `count_final_scores` reads `board[r+1]` unguarded, and
     at the last row the flat and object scorers additionally DISAGREE.
  5. **`action_space.WindowOverflowError`** — the 25x25 centroid window can no
     longer encode ANY legal move. Orthogonal to board size (a representation
     cap, not a rules cap); crashed 16/400 capoff games deterministically.

Faces 3 and 4 are *fatal*, so a game that reaches them does not survive to be
counted — which is why the sentinel also records **near-fatal proximity**: how
close champion play came, in rows/cols, to each fatal face. Exposure measured
before the crash is the whole point of building this before the probe.

RE-PRICING A DIFFERENT GRID. Every coordinate is recorded RELATIVE to the start
tile, so a recorded game prices any candidate `(start_row, board_rows)` exactly —
the `diagnose_grid_wall.py` trick, done from the record instead of from a second
oversized playthrough. Caveat, stated in the output: this is exact for the
trajectory OBSERVED; a grid that binds differently would have produced a
different trajectory. That is why the probe generates at `centered18` (where
nothing binds) and re-prices `engine6` from it, rather than the reverse.

A2 COUNTERS (audit R1/R2) ride the same pass, per the spec's "folds into the
Phase C-lite corpus for free":
  * **cloister completion-deferral** — a cloister that is fully surrounded and
    still carries a monk after the scoring pass ran. The engine's 3x3 scan
    rebinds its own loop bound (`coordinate`), so rows 2-3 drift; a completion
    that falls outside the drifted window is not scored and its monk is not
    returned. Points arrive at final scoring, the MONK does not.
  * **monk-pinned-at-terminal** — the same predicate at game end: the count of
    monks that spent the rest of the game pinned on a completed cloister. This
    is the number R2 is worth, on a supply of 7.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

# How near a fatal face counts as "near-fatal exposure". 2 rows/cols = one tile
# of slack plus the guard cell the farm path reads; the raw min-distance is
# recorded too, so a different threshold can be applied after the fact.
NEAR_FATAL_MARGIN = 2


@dataclass
class GameSentinel:
    """Per-game counters. `to_dict()` lands in the game record; the aggregate
    lands in `manifest.json`."""

    # geometry this game was played on (so a record is self-describing)
    board_rows: int = 35
    board_cols: int = 35
    start_row: int = 6
    start_col: int = 15
    profile: str = "walled"

    # --- face 1: silent wall denial, BY FACE ------------------------------- #
    drops_row_neg: int = 0        # neighbour above row 0 (the production face)
    drops_row_over: int = 0       # neighbour below the last row
    drops_col_neg: int = 0        # neighbour left of col 0
    drops_col_over: int = 0       # neighbour right of the last col
    drop_plies: int = 0           # plies with >=1 dropped neighbour
    drop_cells: int = 0           # DISTINCT off-grid cells ever dropped
    first_drop_ply: int | None = None

    # --- face 2: negative-row wrap ----------------------------------------- #
    row_wrap_plies: int = 0       # placements on row 0 -> board[-1] reads row 34

    # --- faces 3+4: the fatal edges ---------------------------------------- #
    col_last_plies: int = 0       # placements on the last column (col 34 = FATAL)
    row_last_plies: int = 0       # placements on the last row (FATAL at scoring)
    near_fatal_col_plies: int = 0
    near_fatal_row_plies: int = 0
    min_dist_col_last: int | None = None   # closest approach, in columns
    min_dist_row_last: int | None = None
    min_dist_row_zero: int | None = None   # closest approach to the row-0 face

    # --- face 5: the action window ----------------------------------------- #
    window_overflow: int = 0
    aborted: bool = False
    abort_reason: str = ""

    # --- span (absolute AND relative to the start tile) --------------------- #
    min_row: int | None = None
    max_row: int | None = None
    min_col: int | None = None
    max_col: int | None = None
    rel_min_row: int = 0
    rel_max_row: int = 0
    rel_min_col: int = 0
    rel_max_col: int = 0

    # --- A2 (audit R1/R2) --------------------------------------------------- #
    cloister_completions: int = 0          # fully-surrounded cloister tiles seen
    cloister_deferrals: int = 0            # ... completed, monk still on it after scoring
    monk_pins_terminal: int = 0            # monks pinned on a completed cloister at game end

    # --- bookkeeping -------------------------------------------------------- #
    tile_plies: int = 0
    # Relative (row, col) of every placed tile, for exact re-pricing of any
    # candidate geometry. 72 pairs/game — a couple of KB.
    rel_coords: list[tuple[int, int]] = field(default_factory=list)
    # Cloisters already counted, so a monk pinned for 30 plies is ONE event, not
    # thirty; and off-grid cells already counted, so `drop_cells` is DISTINCT
    # cells while `drops_*_*` are per-ply exposure events.
    _seen_deferred: set = field(default_factory=set, repr=False)
    _seen_dropped: set = field(default_factory=set, repr=False)
    # Placements whose cloister check has not run yet — see `_flush_cloisters`.
    _pending: list = field(default_factory=list, repr=False)

    # ---------------------------------------------------------------------- #
    @property
    def any_event(self) -> bool:
        """The A1-a decider: zero events ⇒ W2 is adopted (spec §A1)."""
        return bool(
            self.drops_row_neg or self.drops_row_over
            or self.drops_col_neg or self.drops_col_over
            or self.row_wrap_plies or self.col_last_plies or self.row_last_plies
            or self.window_overflow)

    def to_dict(self, *, with_coords: bool = True) -> dict:
        d = {k: v for k, v in asdict(self).items() if not k.startswith("_")}
        d["any_event"] = self.any_event
        if not with_coords:
            d.pop("rel_coords", None)
        else:
            d["rel_coords"] = [[int(r), int(c)] for r, c in self.rel_coords]
        return d

    # --- observation hooks (all pure reads) -------------------------------- #
    def note_placement(self, state, coord, ply: int) -> None:
        """Call AFTER a tile lands at `coord`. Reads `state.board` only."""
        # The PREVIOUS placement's scoring has resolved by now — flush its
        # cloister check before recording this one. See `_flush_cloisters`.
        self._flush_cloisters(state)
        r, c = int(coord.row), int(coord.column)
        rows, cols = self.board_rows, self.board_cols
        self.tile_plies += 1
        rr, rc = r - self.start_row, c - self.start_col
        self.rel_coords.append((rr, rc))

        # span
        self.min_row = r if self.min_row is None else min(self.min_row, r)
        self.max_row = r if self.max_row is None else max(self.max_row, r)
        self.min_col = c if self.min_col is None else min(self.min_col, c)
        self.max_col = c if self.max_col is None else max(self.max_col, c)
        self.rel_min_row = min(self.rel_min_row, rr)
        self.rel_max_row = max(self.rel_max_row, rr)
        self.rel_min_col = min(self.rel_min_col, rc)
        self.rel_max_col = max(self.rel_max_col, rc)

        # face 1 — the neighbours StateUpdater.play_tile silently declined to add.
        # Mirrors its bounds check exactly: `0 <= nr < n_rows and 0 <= nc < n_cols`.
        dropped = 0
        for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if 0 <= nr < rows and 0 <= nc < cols:
                continue
            dropped += 1
            if nr < 0:
                self.drops_row_neg += 1
            elif nr >= rows:
                self.drops_row_over += 1
            elif nc < 0:
                self.drops_col_neg += 1
            else:
                self.drops_col_over += 1
            self._seen_dropped.add((nr, nc))
        if dropped:
            self.drop_plies += 1
            self.drop_cells = len(self._seen_dropped)
            if self.first_drop_ply is None:
                self.first_drop_ply = int(ply)

        # face 2 — row 0 makes board[-1] read the LAST row instead of raising.
        if r == 0:
            self.row_wrap_plies += 1

        # faces 3 + 4 — the fatal edges, and how near we came to them.
        d_col = (cols - 1) - c
        d_row = (rows - 1) - r
        self.min_dist_col_last = d_col if self.min_dist_col_last is None else min(
            self.min_dist_col_last, d_col)
        self.min_dist_row_last = d_row if self.min_dist_row_last is None else min(
            self.min_dist_row_last, d_row)
        self.min_dist_row_zero = r if self.min_dist_row_zero is None else min(
            self.min_dist_row_zero, r)
        if d_col == 0:
            self.col_last_plies += 1
        elif d_col <= NEAR_FATAL_MARGIN:
            self.near_fatal_col_plies += 1
        if d_row == 0:
            self.row_last_plies += 1
        elif d_row <= NEAR_FATAL_MARGIN:
            self.near_fatal_row_plies += 1

        # A2 — queued, NOT checked now: scoring has not run yet (below).
        self._pending.append((r, c))

    def note_window_overflow(self, ply: int, detail: str = "") -> None:
        """Face 5. The game is ABORTED and MARKED — never silently dropped."""
        self.window_overflow += 1
        self.aborted = True
        self.abort_reason = f"WindowOverflowError@ply{ply}" + (f": {detail}" if detail else "")

    def note_abort(self, reason: str) -> None:
        self.aborted = True
        self.abort_reason = reason

    def note_terminal(self, state) -> None:
        """A2 — count the monks still pinned on a completed cloister at game end."""
        self._flush_cloisters(state)
        self.monk_pins_terminal = sum(
            1 for _ in _pinned_monks(state, self.board_rows, self.board_cols))

    # ---------------------------------------------------------------------- #
    def _flush_cloisters(self, state) -> None:
        """Run the queued cloister checks, now that scoring has run.

        ⚠️ TIMING, and it is load-bearing. A tile placement puts the state into the
        MEEPLE phase; `remove_meeples_and_collect_points` — the drifting scan — only
        fires at the END of that phase. So a check performed at placement time sees
        every completed cloister still carrying its monk and reports a 100% deferral
        rate, which is what the first version of this file did and what the n=4
        smoke caught (7 "deferrals" against 0 terminal pins). Deferring the check to
        the NEXT placement (or to the terminal) puts it after the scoring pass,
        where "monk still there" means the scan genuinely missed it.
        """
        if not self._pending:
            return
        pending, self._pending = self._pending, []
        for r, c in pending:
            self._note_cloisters(state, r, c)

    def _note_cloisters(self, state, r: int, c: int) -> None:
        """The CORRECT 3x3 around the placement, compared against what scoring did.

        `remove_meeples_and_collect_points` rebinds `coordinate` inside its own
        loop bounds, so its scan drifts. Rather than re-implement the drift, this
        reads the OUTCOME: a cloister in the correct window that is fully
        surrounded and STILL carries a monk is one the scan missed (the engine
        removes the monk whenever it does score one).
        """
        rows, cols = self.board_rows, self.board_cols
        for row in range(r - 1, r + 2):
            for col in range(c - 1, c + 2):
                if not (0 <= row < rows and 0 <= col < cols):
                    continue
                tile = state.board[row][col]
                if tile is None or not (tile.chapel or tile.flowers):
                    continue
                if _filled_3x3(state, row, col, rows, cols) != 9:
                    continue
                key = (row, col)
                if key in self._seen_deferred:
                    continue
                self.cloister_completions += 1
                if _monk_on(state, row, col) is not None:
                    self.cloister_deferrals += 1
                self._seen_deferred.add(key)


# --------------------------------------------------------------------------- #
# State readers. Deliberately local re-implementations (a few lines each) rather #
# than engine imports: the sentinel must not be able to perturb an engine cache, #
# and `chapel_or_flowers_points` is itself one of the unguarded readers (it does #
# the very `board[row][column]` wrap this module is here to count).             #
# --------------------------------------------------------------------------- #
def _filled_3x3(state, row: int, col: int, rows: int, cols: int) -> int:
    """Tiles present in the 3x3 centred on (row, col), bounds-GUARDED.

    The engine's `chapel_or_flowers_points` is NOT guarded — at row 0 or the last
    row it wraps or raises. Guarding here means an off-board neighbour counts as
    empty, i.e. a cloister on the border is never called complete. That is the
    conservative direction: it can only UNDER-count deferrals.
    """
    n = 0
    for rr in range(row - 1, row + 2):
        for cc in range(col - 1, col + 2):
            if 0 <= rr < rows and 0 <= cc < cols and state.board[rr][cc] is not None:
                n += 1
    return n


def _monk_on(state, row: int, col: int):
    """Player index of a meeple sitting on the CENTER of (row, col), or None."""
    for player, meeples in enumerate(state.placed_meeples):
        for mp in meeples:
            cws = mp.coordinate_with_side
            if (cws.coordinate.row == row and cws.coordinate.column == col
                    and getattr(cws.side, "name", str(cws.side)) == "CENTER"):
                return player
    return None


def _pinned_monks(state, rows: int, cols: int):
    """Yield (player, row, col) for every monk on a COMPLETED cloister."""
    for player, meeples in enumerate(state.placed_meeples):
        for mp in meeples:
            cws = mp.coordinate_with_side
            if getattr(cws.side, "name", str(cws.side)) != "CENTER":
                continue
            row, col = cws.coordinate.row, cws.coordinate.column
            if not (0 <= row < rows and 0 <= col < cols):
                continue
            tile = state.board[row][col]
            if tile is None or not (tile.chapel or tile.flowers):
                continue
            if _filled_3x3(state, row, col, rows, cols) == 9:
                yield (player, row, col)


# --------------------------------------------------------------------------- #
# Re-pricing + aggregation                                                      #
# --------------------------------------------------------------------------- #
def reprice(rel_coords, start_row: int, start_col: int,
            board_rows: int = 35, board_cols: int = 35) -> dict:
    """Price a DIFFERENT geometry from a recorded trajectory.

    Exact for the trajectory observed (the `diagnose_grid_wall.py` trick applied
    to the record). NOT a prediction of what would have been played on that grid:
    a binding wall changes the trajectory. Read it as "the same game, drawn on a
    different sheet of paper — does it fit?".
    """
    out = {"drops_row_neg": 0, "drops_row_over": 0,
           "drops_col_neg": 0, "drops_col_over": 0,
           "row_wrap_plies": 0, "col_last_plies": 0, "row_last_plies": 0,
           "fits": True}
    for rr, rc in rel_coords:
        r, c = start_row + int(rr), start_col + int(rc)
        if not (0 <= r < board_rows and 0 <= c < board_cols):
            out["fits"] = False
            continue
        for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if 0 <= nr < board_rows and 0 <= nc < board_cols:
                continue
            if nr < 0:
                out["drops_row_neg"] += 1
            elif nr >= board_rows:
                out["drops_row_over"] += 1
            elif nc < 0:
                out["drops_col_neg"] += 1
            else:
                out["drops_col_over"] += 1
        if r == 0:
            out["row_wrap_plies"] += 1
        if c == board_cols - 1:
            out["col_last_plies"] += 1
        if r == board_rows - 1:
            out["row_last_plies"] += 1
    out["any_event"] = out["fits"] is False or any(
        out[k] for k in ("drops_row_neg", "drops_row_over", "drops_col_neg",
                         "drops_col_over", "row_wrap_plies", "col_last_plies",
                         "row_last_plies"))
    return out


_SUM_KEYS = (
    "drops_row_neg", "drops_row_over", "drops_col_neg", "drops_col_over",
    "drop_plies", "drop_cells", "row_wrap_plies", "col_last_plies",
    "row_last_plies", "near_fatal_col_plies", "near_fatal_row_plies",
    "window_overflow", "tile_plies",
    "cloister_completions", "cloister_deferrals", "monk_pins_terminal",
)


def aggregate(records) -> dict:
    """Fold per-game sentinel dicts into the manifest block.

    Counts games-with-the-event as well as event totals, because the decision the
    probe feeds is per-GAME ("how often does champion play hit the wall"), while
    the exposure question is per-EVENT.
    """
    recs = [r for r in records if r]
    agg: dict = {"games": len(recs), "games_aborted": 0, "games_any_event": 0}
    for k in _SUM_KEYS:
        agg[k] = 0
    for k in ("drops_row_neg", "drops_row_over", "drops_col_neg", "drops_col_over",
              "row_wrap_plies", "col_last_plies", "row_last_plies",
              "window_overflow", "cloister_deferrals", "monk_pins_terminal"):
        agg[f"games_with_{k}"] = 0
    spans = {"rel_min_row": 0, "rel_max_row": 0, "rel_min_col": 0, "rel_max_col": 0}
    min_dists: dict[str, int | None] = {
        "min_dist_col_last": None, "min_dist_row_last": None, "min_dist_row_zero": None}
    for r in recs:
        for k in _SUM_KEYS:
            agg[k] += int(r.get(k) or 0)
        for k in list(agg):
            if k.startswith("games_with_") and int(r.get(k[len("games_with_"):]) or 0):
                agg[k] += 1
        if r.get("aborted"):
            agg["games_aborted"] += 1
        if r.get("any_event"):
            agg["games_any_event"] += 1
        spans["rel_min_row"] = min(spans["rel_min_row"], int(r.get("rel_min_row") or 0))
        spans["rel_max_row"] = max(spans["rel_max_row"], int(r.get("rel_max_row") or 0))
        spans["rel_min_col"] = min(spans["rel_min_col"], int(r.get("rel_min_col") or 0))
        spans["rel_max_col"] = max(spans["rel_max_col"], int(r.get("rel_max_col") or 0))
        for k in min_dists:
            v = r.get(k)
            if v is not None:
                min_dists[k] = int(v) if min_dists[k] is None else min(min_dists[k], int(v))
    agg.update(spans)
    agg.update(min_dists)
    return agg
