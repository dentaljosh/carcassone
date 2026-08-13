#!/usr/bin/env python3
"""TILE-TIE PRICING — position builder (DESIGN.md §2.1, §2.2, §2.3, §3, §7.3, §7.4).

Turns `measurement/tiletie_pricing_20260812/census/rows.jsonl` (the concurrent
census task's output — one row per TILE ply, `scripts/tiletie/chain_census.py`'s
`ROW_SCHEMA_KEYS`) into the per-leg `--positions-jsonl` files
`scripts/measurement_infra/oracle_score_pilot.py` consumes UNMODIFIED.

PLAIN SCRIPT, not a package import. This directory may or may not yet carry a
built `scripts/tiletie/__init__.py` (a concurrent task owns it) — this module
never assumes it exists; it works either way by putting its own directory on
`sys.path` and importing sibling modules by plain name, the pattern
`scripts/analyzer/run_farmwar.py` / `scripts/jcz_mining/*.py` use.

WHY A SEPARATE POSITION PER LEG, SAME `rid` (DESIGN §2.1)
-----------------------------------------------------------
`oracle_score_pilot`'s world/playout seeds are `sha256(tag|rid|j|salt)` — keyed
on `rid` and the run-wide salt, NEVER on the arms. So decomposing a K-way tie
into `A_p - 1` two-arm legs against one fixed reference arm (`arms[0]`), each
leg its own `--positions-jsonl` file, but EVERY leg of one position carrying the
SAME `rid`, makes every arm at that position see the identical M CRN worlds —
no instrument change, no wrapper. This is the whole mechanism; it costs
`2*(A_p-1)` arm-playouts per world instead of the minimal `A_p`, and it is what
lets the analyser treat every arm at a position as fully cross-arm CRN-paired.

AFTERSTATE DEDUPE (DESIGN §6 threat 3, adopted into §2.2 -- ARMED 2026-08-12)
------------------------------------------------------------------------------
Two tied tile placements can reach the SAME board (rotationally symmetric tiles
etc.). Measured over the whole tied population by
`scripts/tiletie/transposition_census.py`: ~24% (E4) / ~28% (self-play) of exact
tie sets collapse to ONE board, and ~37-41% carry at least one duplicate arm. A
duplicate arm's oracle delta is exactly 0 *by identity*, not by equivalence of
value -- it buys nothing and costs a full leg. So, before the cap `J`:

  * arms are DEDUPLICATED by successor board key (the lowest action of each
    transposition group survives, so `arms[0]` -- the leaf's tie-break of record
    -- can never move), and
  * positions whose ENTIRE tied set is one board are NOT BUILT at all. Their
    headroom contribution is analytically 0 with zero variance, so they belong
    in the population average as exact zeros, not in the compute budget. They
    are written to `DROPPED_ALL_TRANSPOSITION.json` so the analyser can add them
    back as the exact zeros they are (`headroom_all` vs
    `headroom_discriminable`, DESIGN §6).

The grouping is a JOIN, computed by `transposition_census.py --out` (which emits
`bp_rid` = this module's own `rid_for`, plus `action_groups` / `repr_actions`)
and passed here as `--afterstate-map`. It is REQUIRED: building without it needs
an explicit `--no-dedupe`, and `run_tiletie.py`'s preflight refuses to launch a
plan whose `afterstate_dedupe.applied` is not True.

ARM CONSTRUCTION (DESIGN §2.2), per qualifying position, in this exact order
------------------------------------------------------------------------------
  1. `arms[0]` = the leaf's own tie-break of record = `min(tie_actions_exact)`.
     Asserted equal to the row's `argmax_action` — a design invariant, not a
     soft check. A mismatch means the census and this module's tie-break
     convention disagree, and scoring on top of that would silently
     mis-attribute the reference arm, so it FAILS LOUDLY.
  1b. the tie set is DEDUPED by successor board key (above) -- BEFORE the cap,
     so the cap spends its `J` slots on distinct boards only.
  2. the remaining exact-tie members, ascending, capped at `--cap-j` (keeping
     `arms[0]` plus up to `J-1` more). Beyond the cap, members are dropped by a
     SEEDED uniform draw — never index truncation, which would correlate the
     drop with the tie-break convention itself. The draw is deterministic per
     `rid` via a sha256-derived seed (NEVER `hash()`, which is
     PYTHONHASHSEED-salted and would make two processes disagree — the same
     discipline `oracle_score_pilot._sha_int` uses). This is a literal
     implementation of DESIGN §2.2's "``random.Random((...))``-style
     deterministic seeding" clause: the *shape* (tag, rid, date) is exactly
     what DESIGN prescribes, expressed through a stable non-`hash()` seed
     rather than the literal (and non-reproducible-across-processes)
     `random.Random(<tuple>)` spelling.
  3. the champion's actual pick (E4: free, `action_played` from the archive;
     selfplay: from `--champ-picks`, the `champ_picks.py` output — see
     DESIGN §2.3). If it is already in the (possibly capped) arms list, its
     index is recorded (`champ_arm_index`); otherwise it is APPENDED as one
     more arm and `champ_outside_tieset` is set.

SELECTION (DESIGN §4.5): only exact ties whose `tie_actions_exact` was NOT
truncated by the census's own on-disk cap (`tie_exact == True and
tie_actions_exact_truncated == False`) are scored — the K-way problem this
module solves is already bounded before `--cap-j` ever applies.

OUTPUTS
-------
  positions_{profile}_leg{r}.jsonl   one line per position that HAS an arm at
                                     leg index r (r = 1 .. max_arms-1), for
                                     each `rules_profile` present in the
                                     sampled set.
  ARMS.json                          {rid: {arms, root_id, stratum, source,
                                     ..., champ_action, champ_arm_index,
                                     champ_outside_tieset, archive_path}} — the
                                     side index. `oracle_score_pilot._process`
                                     only rides a FIXED whitelist of extra keys
                                     into its output records (stratum,
                                     rules_profile, game_label, bucket, phase,
                                     delta_q, abs_delta_q, action_played,
                                     action_best, stratifier_rule) — everything
                                     else this module knows about a position is
                                     dropped on the way through the pilot, so
                                     the analyser joins back to THIS file on
                                     `rid`.
  POSITIONS_PLAN.json                counts per (profile, leg) and per
                                     stratum, max/mean arms, the cap J and how
                                     many positions it bit, the sampling seed,
                                     total arm-playouts implied, and the
                                     DESIGN §7.1 cost/ETA arithmetic at W=14
                                     and W=22.

IDENTIFIERS (must be stable and unique — DESIGN §2.1/§3)
----------------------------------------------------------
  rid      = f"tt_e4_{game_label}_p{ply}"   (e4)
             f"tt_sp_{deck_seed}_p{ply}"    (selfplay)
  root_id  = f"e4_{game_label}"             (e4)   -- the CLUSTER unit; e4 keys
             f"sp_{deck_seed}"              (selfplay)  on game_label, NOT
                                             deck_seed, because deck_seed is
                                             NOT unique across E4 archives (two
                                             games in measurement/e4_games/
                                             share 523563).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

for _p in (str(HERE),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SCHEMA = "carcassonne-tiletie-positions/v1"
DESIGN_DOC = "measurement/tiletie_pricing_20260812/DESIGN.md"

# --------------------------------------------------------------------------- #
# defaults                                                                      #
# --------------------------------------------------------------------------- #
DEFAULT_CENSUS_ROWS = REPO / "measurement/tiletie_pricing_20260812/census/rows.jsonl"
DEFAULT_OUT_DIR = REPO / "measurement/tiletie_pricing_20260812/positions"
DEFAULT_E4_DIR = REPO / "measurement/e4_games"
#: where `transposition_census.py --out` drops its per-profile afterstate maps
DEFAULT_AFTERSTATE_MAP_DIR = REPO / "measurement/tiletie_pricing_20260812/census"
DEFAULT_CHAMP_GAMES = REPO / "measurement/champ_action_logs/champ_games.jsonl"


def _share(rel: str) -> str:
    """House pattern (`gate_oracle_pilot_backend._share`): the share mount path
    differs by box (`/mnt/c/carc-shared` locally, `/mnt/carc-shared` remote)."""
    for root in ("/mnt/c/carc-shared", "/mnt/carc-shared"):
        if Path(root).is_dir():
            return f"{root}/{rel}"
    return f"/mnt/carc-shared/{rel}"


DEFAULT_BANK_ROOTS = _share("classical_search/move_agreement_k4_b28e9/roots.jsonl")

#: DESIGN §7.1: "the deploy budget promotion" — k8x1376 sequential, quiet 5900XT.
DEFAULT_T_CHAMP_SECS = 13.7552
#: DESIGN §2 / §7.1: the oracle's own M (deck completions per position) — fixed,
#: not a build_positions knob (it belongs to the scoring launcher / instrument).
M_WORLDS = 32

# --------------------------------------------------------------------------- #
# census loading — read defensively (task brief): a schema drift must fail      #
# loudly at BUILD time, naming the missing field, not mis-score silently.       #
# --------------------------------------------------------------------------- #
#: The subset of `chain_census.ROW_SCHEMA_KEYS` this module actually consumes.
#: (Full schema per the concurrent task's `scripts/tiletie/chain_census.py`:
#: n_cand, top1, top2, gap, tie_exact, tie_size_exact, tie_actions_exact,
#: tie_actions_exact_truncated, by_eps, argmax_action, stratum, source,
#: rules_profile, game_label, root_id, deck_seed, ply, seat, k_remaining,
#: phase_bucket, tercile, n_legal, checksum, action_played,
#: played_in_tieset_exact, played_is_argmax, secs, h200_top2_q_gap,
#: bank_phase_bucket. `root_id` is read from the row but NOT relied upon — this
#: module computes its own, see module docstring.)
REQUIRED_ROW_FIELDS = (
    "stratum", "source", "rules_profile", "game_label", "deck_seed", "ply", "seat",
    "k_remaining", "phase_bucket", "tercile", "n_legal", "n_cand", "checksum",
    "action_played", "tie_exact", "tie_size_exact", "tie_actions_exact",
    "tie_actions_exact_truncated", "argmax_action", "top1", "top2", "gap",
)


def _require(row: dict, keys, where: str) -> None:
    missing = [k for k in keys if k not in row]
    if missing:
        raise KeyError(
            f"{where}: census row is missing field(s) {missing} -- schema drift "
            f"between build_positions.REQUIRED_ROW_FIELDS and the census output? "
            f"row keys present: {sorted(row)}")


def load_census_rows(path) -> list:
    """Load + defensively validate every row of the census `rows.jsonl`."""
    out = []
    p = Path(path)
    for ln, line in enumerate(p.read_text().splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        _require(row, REQUIRED_ROW_FIELDS, f"{path}:{ln}")
        out.append(row)
    return out


def cross_check_schema(rows: list) -> dict | None:
    """Best-effort cross-check against `chain_census.ROW_SCHEMA_KEYS`, if that
    module is importable (it may not be, per the module docstring's "works
    either way" contract). Informational only — `REQUIRED_ROW_FIELDS` above is
    the load-bearing gate; this just surfaces upstream schema drift early."""
    if not rows:
        return None
    try:
        sys.path.insert(0, str(REPO / "scripts" / "tiletie"))
        import chain_census as _CC  # noqa: PLC0415
    except ImportError:
        return None
    keys = set(rows[0])
    return {"extra": sorted(keys - set(_CC.ROW_SCHEMA_KEYS)),
            "missing": sorted(set(_CC.ROW_SCHEMA_KEYS) - keys)}


def select_positions(rows: list) -> list:
    """DESIGN §4.5: only exact ties whose `tie_actions_exact` was not itself
    truncated by the census's own on-disk cap are scored."""
    return [r for r in rows
            if bool(r["tie_exact"]) and not bool(r["tie_actions_exact_truncated"])]


# --------------------------------------------------------------------------- #
# identifiers                                                                   #
# --------------------------------------------------------------------------- #
def rid_for(row: dict) -> str:
    if row["stratum"] == "e4":
        return f"tt_e4_{row['game_label']}_p{int(row['ply'])}"
    if row["stratum"] == "selfplay":
        return f"tt_sp_{int(row['deck_seed'])}_p{int(row['ply'])}"
    raise ValueError(f"unknown stratum {row['stratum']!r} (row game_label="
                     f"{row.get('game_label')!r} deck_seed={row.get('deck_seed')!r})")


def root_id_for(row: dict) -> str:
    if row["stratum"] == "e4":
        return f"e4_{row['game_label']}"
    if row["stratum"] == "selfplay":
        return f"sp_{int(row['deck_seed'])}"
    raise ValueError(f"unknown stratum {row['stratum']!r}")


def _stable_seed(*parts) -> int:
    """A deterministic, PYTHONHASHSEED-independent integer seed from `parts`.
    NEVER `random.Random(<tuple>)` directly (CPython hashes a non-int/str/bytes
    seed via `hash()`, which is salted per-process) — same discipline as
    `oracle_score_pilot._sha_int`, and the concrete implementation of DESIGN
    §2.2's "``random.Random((...))``-style deterministic seeding" clause."""
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(h[:8], "big") & 0x7FFFFFFF


CAP_SEED_TAG = "tiletie-cap"
CAP_SEED_DATE = 20260812


# --------------------------------------------------------------------------- #
# afterstate dedupe — DESIGN §6 threat 3 (the JOIN input)                       #
# --------------------------------------------------------------------------- #
def load_afterstate_maps(paths) -> dict:
    """`bp_rid` -> {"action_groups", "repr_actions", "n_distinct_afterstates",
    "all_transposition"}, merged over one or more `transposition_census.py --out`
    files (one per rules profile -- R9 is import-latched, so a profile cannot
    share a process and the map is necessarily written in pieces).

    A rid appearing twice with DIFFERENT groupings is a hard error: the two
    profiles would disagree about the same board, which can only mean a stale
    file."""
    out: dict = {}
    for path in ([paths] if isinstance(paths, (str, Path)) else list(paths)):
        data = json.loads(Path(path).read_text())
        for r in data["rows"]:
            rid = r["bp_rid"]
            groups = [sorted(int(a) for a in g) for g in r["action_groups"]]
            groups.sort(key=lambda g: g[0])
            entry = {"action_groups": groups,
                     "repr_actions": [g[0] for g in groups],
                     "n_distinct_afterstates": int(r["n_distinct_afterstates"]),
                     "all_transposition": bool(r["all_transposition"]),
                     "source_path": str(path)}
            prev = out.get(rid)
            if prev is not None and prev["action_groups"] != entry["action_groups"]:
                raise ValueError(
                    f"afterstate map conflict for rid={rid!r}: {prev['source_path']} "
                    f"says {prev['action_groups']} but {path} says "
                    f"{entry['action_groups']} -- one of them is stale")
            out[rid] = entry
    return out


def dedupe_tie_actions(tie_actions: list, entry: dict) -> dict:
    """Collapse a tie set to one action per distinct successor board.

    Returns {"kept": [...ascending...], "dropped": [...], "repr_of": {action:
    representative}, "n_distinct": int, "all_transposition": bool}.

    The map is VALIDATED against the row: its grouped actions must be exactly
    the row's `tie_actions_exact`. A mismatch means the map was built from a
    different census (or a different cap), and silently deduping against it
    would mis-attribute arms -- so it FAILS LOUDLY, in the house style of
    `build_tie_arms`'s own arm[0] assertion."""
    groups = [sorted(int(a) for a in g) for g in entry["action_groups"]]
    groups.sort(key=lambda g: g[0])
    flat = sorted(a for g in groups for a in g)
    want = sorted(int(a) for a in tie_actions)
    if flat != want:
        raise ValueError(
            f"stale afterstate map: it groups {flat} but the census row's "
            f"tie_actions_exact is {want} -- rebuild the map with "
            "scripts/tiletie/transposition_census.py against THIS rows.jsonl")
    kept = [g[0] for g in groups]
    repr_of = {a: g[0] for g in groups for a in g}
    return {"kept": kept, "dropped": sorted(set(want) - set(kept)),
            "repr_of": repr_of, "n_distinct": len(kept),
            "all_transposition": len(kept) == 1}


# --------------------------------------------------------------------------- #
# arm construction — DESIGN §2.2 steps 1-2 (reference + capped candidates)      #
# --------------------------------------------------------------------------- #
def build_tie_arms(row: dict, cap_j: int, afterstate: dict | None = None) -> dict:
    """Steps 1(+1b)-2. Returns {"arms": [...], "capped": bool,
    "dropped_actions": [...], "dedupe_dropped_actions": [...],
    "n_distinct_afterstates": int|None, "all_transposition": bool,
    "repr_of": {action: representative}}.

    `arms[0]` is asserted == `row["argmax_action"]` -- FAILS LOUDLY on
    disagreement (see module docstring). With `afterstate` given (DESIGN §6
    threat 3) the tie set is deduped by successor board key BEFORE the cap;
    the lowest action of each transposition group survives, so `arms[0]` is
    invariant under dedupe by construction."""
    tie_actions = sorted(int(a) for a in row["tie_actions_exact"])
    if len(tie_actions) < 2:
        raise ValueError(
            f"row (stratum={row.get('stratum')}, deck_seed={row.get('deck_seed')}, "
            f"ply={row.get('ply')}): tie_exact is True but tie_actions_exact has "
            f"{len(tie_actions)} member(s) -- not a real tie")
    ref = tie_actions[0]
    if ref != int(row["argmax_action"]):
        raise AssertionError(
            f"arm[0] (min(tie_actions_exact)={ref}) != row['argmax_action']="
            f"{row['argmax_action']} (stratum={row.get('stratum')}, "
            f"deck_seed={row.get('deck_seed')}, ply={row.get('ply')}) -- the "
            "leaf's own tie-break convention disagrees with the census; refusing "
            "to build arms on top of that.")

    dedupe_dropped: list = []
    n_distinct = None
    all_transposition = False
    repr_of: dict = {}
    if afterstate is not None:
        ded = dedupe_tie_actions(tie_actions, afterstate)
        tie_actions = ded["kept"]
        dedupe_dropped = ded["dropped"]
        n_distinct = ded["n_distinct"]
        all_transposition = ded["all_transposition"]
        repr_of = ded["repr_of"]
        assert tie_actions[0] == ref, "dedupe moved arm[0] -- impossible by min()"

    rid = rid_for(row)
    candidates = list(tie_actions[1:])       # already ascending, ref excluded
    capped, dropped = False, []
    j = max(1, int(cap_j))
    if len(candidates) > j - 1:
        rng = random.Random(_stable_seed(CAP_SEED_TAG, rid, CAP_SEED_DATE))
        keep_idx = sorted(rng.sample(range(len(candidates)), j - 1))
        kept = sorted(candidates[i] for i in keep_idx)
        dropped = sorted(set(candidates) - set(kept))
        candidates = kept
        capped = True
    return {"arms": [ref] + candidates, "capped": capped, "dropped_actions": dropped,
            "dedupe_dropped_actions": dedupe_dropped,
            "n_distinct_afterstates": n_distinct,
            "all_transposition": all_transposition, "repr_of": repr_of}


# --------------------------------------------------------------------------- #
# arm construction — DESIGN §2.2 step 3 (the champion's actual pick)            #
# --------------------------------------------------------------------------- #
def load_champ_picks(path) -> dict:
    """rid -> the champ_picks.py output record for that rid."""
    out = {}
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        out[o["rid"]] = o
    return out


def resolve_champion_arm(row: dict, arms: list, champ_picks: dict, *,
                         allow_missing: bool, repr_of: dict | None = None) -> dict:
    """Step 3. Returns {"arms": [...] (possibly +1), "champ_action",
    "champ_arm_index", "champ_outside_tieset", "champ_pick_missing",
    "champ_arm_action"}.

    E4: `action_played` is free (from the archive). Selfplay: looked up in
    `champ_picks` (champ_picks.py's output, keyed by rid) -- REQUIRED unless
    `allow_missing=True`, in which case a position with no resolved pick is
    still built (its tie-set legs are still scoreable) but carries no champion
    arm at all (`champ_pick_missing=True`), per DESIGN §2.3.

    `repr_of` (the dedupe grouping, DESIGN §6 threat 3) maps a tied action to
    its transposition representative. When the champion's pick is a duplicate of
    an arm already present it must NOT be appended as a second arm: the two
    reach the same board, so the extra leg would be a known-zero row. The played
    action is still recorded verbatim as `champ_action` (provenance);
    `champ_arm_action` is the arm actually scored."""
    stratum = row["stratum"]
    rid = rid_for(row)
    if stratum == "e4":
        champ_action = row.get("action_played")
        if champ_action is None:
            raise KeyError(
                f"e4 row rid={rid!r} has no action_played -- the e4 champion "
                "pick is supposed to be FREE from the archive (DESIGN §2.3); "
                "this is a census/schema problem, not a missing-champ-picks "
                "problem")
        champ_action = int(champ_action)
    elif stratum == "selfplay":
        rec = champ_picks.get(rid)
        missing = rec is None or rec.get("champ_action") is None
        if missing:
            if allow_missing:
                return {"arms": list(arms), "champ_action": None,
                       "champ_arm_action": None,
                       "champ_arm_index": None, "champ_outside_tieset": False,
                       "champ_pick_missing": True,
                       "champ_pick_error": (rec or {}).get("error")}
            raise KeyError(
                f"selfplay row rid={rid!r} has no resolved champion pick in "
                "--champ-picks (pass --allow-missing-champ-picks to build "
                "without one, or run champ_picks.py first)")
        champ_action = int(rec["champ_action"])
    else:
        raise ValueError(f"unknown stratum {stratum!r}")

    out_arms = list(arms)
    arm_action = (repr_of or {}).get(champ_action, champ_action)
    if arm_action in out_arms:
        idx = out_arms.index(arm_action)
        outside = False
    else:
        out_arms.append(arm_action)
        idx = len(out_arms) - 1
        # "outside the tie set" is a statement about the TIE SET, not about the
        # capped arm list: a champion pick that IS a tied member but was dropped
        # by the cap is still inside the set.
        outside = champ_action not in (repr_of or {})
    return {"arms": out_arms, "champ_action": champ_action,
           "champ_arm_action": arm_action, "champ_arm_index": idx,
           "champ_outside_tieset": outside, "champ_pick_missing": False}


# --------------------------------------------------------------------------- #
# move-sequence resolution (archive_path for e4, actions for selfplay)          #
# --------------------------------------------------------------------------- #
def resolve_archive_path(row: dict, e4_dir: Path) -> str:
    label = str(row["game_label"])
    for c in (Path(e4_dir) / f"{label}.json", Path(e4_dir) / label):
        if c.is_file():
            return str(c)
    raise FileNotFoundError(
        f"e4 archive not found for game_label={label!r} under {e4_dir} "
        f"(tried {label}.json and {label})")


def load_bank_roots(path) -> dict:
    """(deck_seed, ply) -> {"actions": [...], "checksum": ...} from the CL-070
    root bank's roots.jsonl."""
    out = {}
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        out[(int(o["deck_seed"]), int(o["ply"]))] = {
            "actions": [int(a) for a in o["actions"]],
            "checksum": o.get("checksum"),
        }
    return out


def load_champ_games(path) -> dict:
    """deck_seed -> the full action list, from champ_action_logs/champ_games.jsonl."""
    out = {}
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        out[int(o["deck_seed"])] = [int(a) for a in o["actions"]]
    return out


def resolve_selfplay_actions(row: dict, bank_roots: dict, champ_games: dict) -> list:
    """The full move sequence for a selfplay row, resolved from its `source`
    ("bank" -> the CL-070 roots.jsonl, keyed on (deck_seed, ply); "champ_games"
    -> champ_action_logs/champ_games.jsonl, keyed on deck_seed). If the census
    row ALREADY carries `actions` (not part of today's schema, but tolerated
    for forward compatibility), it is used and verified against the resolved
    sequence rather than trusted blind."""
    src = row.get("source")
    deck_seed, ply = int(row["deck_seed"]), int(row["ply"])
    if src == "bank":
        entry = bank_roots.get((deck_seed, ply))
        if entry is None:
            raise KeyError(f"selfplay/bank row (deck_seed={deck_seed}, ply={ply}) "
                            "not found in the CL-070 roots.jsonl bank")
        resolved = entry["actions"]
    elif src == "champ_games":
        acts = champ_games.get(deck_seed)
        if acts is None:
            raise KeyError(f"selfplay/champ_games row deck_seed={deck_seed} not "
                            "found in champ_action_logs/champ_games.jsonl")
        resolved = acts
    else:
        raise ValueError(f"selfplay row has unknown source {src!r} (expected "
                         "'bank' or 'champ_games')")
    given = row.get("actions")
    if given:
        given = [int(a) for a in given]
        if given != resolved:
            raise ValueError(
                f"census row for deck_seed={deck_seed} ply={ply} carries its own "
                "`actions` and it does NOT match the resolved bank/champ_games "
                "sequence")
        return given
    return resolved


# --------------------------------------------------------------------------- #
# sampling — DESIGN §7.3: e4 gets every available position first, selfplay      #
# fills the remainder                                                          #
# --------------------------------------------------------------------------- #
def stratified_sample(rows: list, n: int, seed: int, *, n_e4=None,
                      n_selfplay=None) -> list:
    """`n<=0` and no per-stratum counts => all. Otherwise: e4 takes every
    available position up to its own census ceiling (a seeded subsample of e4
    ONLY if `n` is smaller than the e4 supply itself); the remainder is filled
    from a seeded selfplay subsample. Deterministic: rows are sorted by `rid`
    before sampling so the result never depends on file/listing order.

    `n_e4` / `n_selfplay` override that e4-first split with an EXPLICIT
    per-stratum allocation, which is what DESIGN §7.3's Stage A needs: the
    backend constraint (§2.0) reversed the allocation to
    "280 selfplay/RUST (power) + 60 e4/PYTHON (relevance)", and the e4-first
    default would hand a 340-position budget entirely to e4."""
    explicit = n_e4 is not None or n_selfplay is not None
    if not explicit and (n is None or int(n) <= 0):
        return list(rows)
    e4 = sorted((r for r in rows if r["stratum"] == "e4"), key=rid_for)
    sp = sorted((r for r in rows if r["stratum"] == "selfplay"), key=rid_for)
    rng = random.Random(int(seed))

    def _take(pool, k):
        if k >= len(pool):
            return list(pool)
        idx = sorted(rng.sample(range(len(pool)), k))
        return [pool[i] for i in idx]

    if explicit:
        e4_take = _take(e4, len(e4) if n_e4 is None else max(0, int(n_e4)))
        sp_take = _take(sp, len(sp) if n_selfplay is None else max(0, int(n_selfplay)))
        return e4_take + sp_take
    n = int(n)
    e4_take = _take(e4, n)
    sp_take = _take(sp, max(0, n - len(e4_take)))
    return e4_take + sp_take


# --------------------------------------------------------------------------- #
# per-leg jsonl + ARMS.json                                                     #
# --------------------------------------------------------------------------- #
def write_leg_files(positions: list, out_dir: Path) -> dict:
    """One jsonl per (rules_profile, leg r), r=1..len(arms)-1 for each position
    that has an arm there. Returns {"max_arms": int, "files": {"profile/legR":
    {"path": str, "n": int}}}."""
    by_key: dict = {}
    max_arms = 0
    for p in positions:
        max_arms = max(max_arms, len(p["arms"]))
        profile = p["rules_profile"]
        for r in range(1, len(p["arms"])):
            line = {
                "rid": p["rid"], "root_id": p["root_id"],
                "deck_seed": p["deck_seed"], "ply": p["ply"],
                "root_player": p["seat"], "pick_a": p["arms"][0],
                "pick_b": p["arms"][r], "checksum": p["checksum"],
                "rules_profile": profile, "stratum": p["stratum"],
                "game_label": p["game_label"], "action_played": p["champ_action"],
                "action_best": p["arms"][r],
            }
            if p["stratum"] == "e4":
                line["archive_path"] = p["archive_path"]
            else:
                line["actions"] = p["actions"]
            by_key.setdefault((profile, r), []).append(line)

    files = {}
    for (profile, r), lines in sorted(by_key.items()):
        path = out_dir / f"positions_{profile}_leg{r}.jsonl"
        lines_sorted = sorted(lines, key=lambda x: x["rid"])
        path.write_text("".join(json.dumps(x) + "\n" for x in lines_sorted))
        files[f"{profile}/leg{r}"] = {"path": str(path), "n": len(lines_sorted)}
    return {"max_arms": max_arms, "files": files}


def build_arms_index(positions: list) -> dict:
    idx = {}
    for p in positions:
        idx[p["rid"]] = {
            "arms": p["arms"], "root_id": p["root_id"], "stratum": p["stratum"],
            "source": p["source"], "rules_profile": p["rules_profile"],
            "game_label": p["game_label"], "deck_seed": p["deck_seed"],
            "ply": p["ply"], "seat": p["seat"], "k_remaining": p["k_remaining"],
            "phase_bucket": p["phase_bucket"], "tercile": p["tercile"],
            "n_legal": p["n_legal"], "n_cand": p["n_cand"],
            "tie_size_exact": p["tie_size_exact"], "gap": p["gap"],
            "capped": p["capped"], "dropped_actions": p["dropped_actions"],
            "dedupe_dropped_actions": p.get("dedupe_dropped_actions", []),
            "n_distinct_afterstates": p.get("n_distinct_afterstates"),
            "champ_action": p["champ_action"], "champ_arm_index": p["champ_arm_index"],
            "champ_arm_action": p.get("champ_arm_action"),
            "champ_outside_tieset": p["champ_outside_tieset"],
            "champ_pick_missing": p.get("champ_pick_missing", False),
            "archive_path": p.get("archive_path"),
        }
    return idx


# --------------------------------------------------------------------------- #
# POSITIONS_PLAN.json — DESIGN §7.1 cost/ETA arithmetic                         #
# --------------------------------------------------------------------------- #
def cost_plan(positions: list, *, cap_j: int, sample_seed: int, playout_secs: float,
             m_worlds: int = M_WORLDS, t_champ_secs: float = DEFAULT_T_CHAMP_SECS,
             workers=(14, 22)) -> dict:
    """DESIGN §7.1:
        oracle_worker_secs = n_positions * (A_bar - 1) * 2 * M * c
        champ_pick_secs    = n_selfplay * t_champ
        wall_hours         = (oracle_worker_secs + champ_pick_secs) / (3600 * W)

    Computed per-position and summed (`sum(A_p - 1) == n_positions*(A_bar-1)`
    algebraically, so this is exact even with uneven arm counts across
    positions, not merely an approximation of the mean-based formula)."""
    n = len(positions)
    arm_counts = [len(p["arms"]) for p in positions]
    mean_arms = (sum(arm_counts) / n) if n else 0.0
    max_arms = max(arm_counts, default=0)
    n_capped = sum(1 for p in positions if p["capped"])
    n_selfplay = sum(1 for p in positions if p["stratum"] == "selfplay")
    n_e4 = n - n_selfplay

    total_arm_playouts = sum((c - 1) * 2 * m_worlds for c in arm_counts)
    oracle_worker_secs = total_arm_playouts * float(playout_secs)
    champ_pick_secs = n_selfplay * float(t_champ_secs)
    total_secs = oracle_worker_secs + champ_pick_secs

    counts_by_profile_leg: dict = {}
    for p in positions:
        for r in range(1, len(p["arms"])):
            key = f"{p['rules_profile']}/leg{r}"
            counts_by_profile_leg[key] = counts_by_profile_leg.get(key, 0) + 1

    return {
        "schema": SCHEMA, "design_doc": DESIGN_DOC,
        "n_positions": n, "n_e4": n_e4, "n_selfplay": n_selfplay,
        "counts_by_stratum": {"e4": n_e4, "selfplay": n_selfplay},
        "counts_by_profile_leg": counts_by_profile_leg,
        "max_arms": max_arms, "mean_arms": mean_arms,
        "cap_j": int(cap_j), "n_positions_capped": n_capped,
        "sample_seed": int(sample_seed),
        "m_worlds": int(m_worlds), "playout_secs": float(playout_secs),
        "t_champ_secs": float(t_champ_secs),
        "total_arm_playouts": total_arm_playouts,
        "oracle_worker_secs": oracle_worker_secs,
        "champ_pick_secs": champ_pick_secs,
        "total_worker_secs": total_secs,
        "eta_by_workers": {
            f"W={w}": {"wall_secs": total_secs / w, "wall_hours": total_secs / (3600.0 * w)}
            for w in workers
        },
        "formula": "DESIGN.md #7.1: oracle_worker_secs = n_positions*(A_bar-1)*2*M*c "
                   "(summed per-position here, algebraically identical); "
                   "champ_pick_secs = n_selfplay*t_champ; "
                   "wall_hours = (oracle_worker_secs+champ_pick_secs)/(3600*W)",
    }


def full_run_eta_secs(plan: dict, playout_secs: float, workers: int) -> dict:
    """Re-derive the plan's ETA at a DIFFERENT `c` (e.g. a smoke-measured
    worker-seconds/playout) without rebuilding positions."""
    total = plan["total_arm_playouts"] * float(playout_secs) + plan["champ_pick_secs"]
    return {"wall_secs": total / workers, "wall_hours": total / (3600.0 * workers)}


# --------------------------------------------------------------------------- #
# driver                                                                        #
# --------------------------------------------------------------------------- #
def _tieset_playouts(rows: list, cap_j: int, amap: dict | None,
                     m_worlds: int = M_WORLDS) -> int:
    """Arm-playouts implied by the TIE-SET arms alone (champion arm excluded --
    it is not what dedupe acts on), over `rows`, with `amap=None` meaning "as the
    pre-dedupe builder would have done it". The honest before/after denominator
    for the DESIGN §6 threat-3 saving."""
    total = 0
    for row in rows:
        entry = None if amap is None else amap.get(rid_for(row))
        tie = build_tie_arms(row, cap_j, afterstate=entry)
        if tie["all_transposition"]:
            continue                      # not built at all -- an analytic zero
        total += (len(tie["arms"]) - 1) * 2 * m_worlds
    return total


def build(rows: list, *, out_dir: Path, champ_picks: dict, cap_j: int, n: int,
         sample_seed: int, playout_secs: float, e4_dir: Path, bank_roots_path,
         champ_games_path, allow_missing_champ_picks: bool,
         afterstate_map: dict | None = None, require_afterstate_map: bool = True,
         n_e4=None, n_selfplay=None) -> dict:
    """The whole pipeline, factored out of `main()` so tests can call it without
    going through argparse/stdout. Returns the written `POSITIONS_PLAN.json` dict
    (also has the side effect of writing the leg files + ARMS.json + the plan +
    `DROPPED_ALL_TRANSPOSITION.json`)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    amap = afterstate_map or None
    if amap is None and require_afterstate_map:
        raise ValueError(
            "no afterstate map: DESIGN §6 threat 3 requires arms to be deduped "
            "by successor board key and all-transposition positions to be "
            "dropped before the run is launched. Pass --afterstate-map "
            "(scripts/tiletie/transposition_census.py --out ...), or "
            "--no-dedupe to build the pre-dedupe plan deliberately.")

    selected = select_positions(rows)

    # --- DESIGN §6 threat 3: drop the known-zero rows BEFORE sampling, so a
    # staged `n` buys n SCOREABLE positions and not n-minus-the-transpositions.
    dropped_rows: list = []
    kept = selected
    if amap is not None:
        missing = [rid_for(r) for r in selected if rid_for(r) not in amap]
        if missing:
            raise KeyError(
                f"afterstate map does not cover {len(missing)} qualifying "
                f"position(s), e.g. {missing[:5]} -- rebuild the map for every "
                "rules profile present (transposition_census.py is one process "
                "per profile; R9 is import-latched)")
        kept, dropped_rows = [], []
        for r in selected:
            (dropped_rows if amap[rid_for(r)]["all_transposition"] else kept).append(r)

    sampled = stratified_sample(kept, n, sample_seed, n_e4=n_e4,
                                n_selfplay=n_selfplay)

    e4_dir = Path(e4_dir)
    bank_roots = champ_games = None
    positions = []
    n_missing_champ = 0
    n_arm_deduped = 0
    for row in sampled:
        entry = None if amap is None else amap[rid_for(row)]
        tie = build_tie_arms(row, cap_j, afterstate=entry)
        if tie["dedupe_dropped_actions"]:
            n_arm_deduped += 1
        champ = resolve_champion_arm(row, tie["arms"], champ_picks,
                                     allow_missing=allow_missing_champ_picks,
                                     repr_of=tie["repr_of"] or None)
        if champ.get("champ_pick_missing"):
            n_missing_champ += 1
        pos = {
            "rid": rid_for(row), "root_id": root_id_for(row),
            "stratum": row["stratum"], "source": row["source"],
            "rules_profile": row["rules_profile"], "game_label": row["game_label"],
            "deck_seed": int(row["deck_seed"]), "ply": int(row["ply"]),
            "seat": int(row["seat"]), "k_remaining": row["k_remaining"],
            "phase_bucket": row["phase_bucket"], "tercile": row["tercile"],
            "n_legal": row["n_legal"], "n_cand": row["n_cand"],
            "tie_size_exact": row["tie_size_exact"], "gap": row["gap"],
            "checksum": row["checksum"],
            "arms": champ["arms"], "capped": tie["capped"],
            "dropped_actions": tie["dropped_actions"],
            "champ_action": champ["champ_action"],
            "champ_arm_index": champ["champ_arm_index"],
            "champ_outside_tieset": champ["champ_outside_tieset"],
            "champ_pick_missing": champ.get("champ_pick_missing", False),
            "champ_arm_action": champ.get("champ_arm_action"),
            "dedupe_dropped_actions": tie["dedupe_dropped_actions"],
            "n_distinct_afterstates": tie["n_distinct_afterstates"],
        }
        if row["stratum"] == "e4":
            pos["archive_path"] = resolve_archive_path(row, e4_dir)
        else:
            if bank_roots is None:
                bank_roots = load_bank_roots(bank_roots_path)
                champ_games = load_champ_games(champ_games_path)
            pos["actions"] = resolve_selfplay_actions(row, bank_roots, champ_games)
        positions.append(pos)

    leg_info = write_leg_files(positions, out_dir)
    arms_index = build_arms_index(positions)
    (out_dir / "ARMS.json").write_text(json.dumps(arms_index, indent=2, sort_keys=True))

    # DESIGN §6 threat 3: the dropped positions are NOT lost -- their headroom
    # contribution is analytically 0, so the analyser adds them back as exact
    # zeros (`headroom_all`) instead of paying to score them.
    dropped_index = [{
        "rid": rid_for(r), "root_id": root_id_for(r), "stratum": r["stratum"],
        "source": r["source"], "rules_profile": r["rules_profile"],
        "game_label": r["game_label"], "deck_seed": int(r["deck_seed"]),
        "ply": int(r["ply"]), "phase_bucket": r["phase_bucket"],
        "tercile": r["tercile"], "tie_size_exact": r["tie_size_exact"],
        "n_distinct_afterstates": 1,
        # An action played OUTSIDE the tie set has a different chain value,
        # hence -- chain value being a function of the tile afterstate -- a
        # different board. For those rows the "analytic zero" holds for the TIE
        # SET arms only, so the analyser needs the count to run that
        # sensitivity. (On `e4` the played action IS the champion's own pick,
        # from the archive; on `selfplay` it is the logged self-play move, and
        # the champion arm would have come from champ_picks.py.)
        "action_played": r.get("action_played"),
        "action_played_outside_tieset": (
            None if r.get("action_played") is None else
            int(r["action_played"]) not in [int(a) for a in r["tie_actions_exact"]]),
    } for r in dropped_rows]
    (out_dir / "DROPPED_ALL_TRANSPOSITION.json").write_text(json.dumps(
        {"schema": SCHEMA, "design_doc": DESIGN_DOC,
         "note": "exact-tie tile plies whose ENTIRE tie set reaches ONE board "
                 "(DESIGN §6 threat 3). NOT scored: headroom is analytically 0 "
                 "with zero variance. The analyser MUST include them as exact "
                 "zeros in headroom_all (and exclude them from "
                 "headroom_discriminable).",
         "n": len(dropped_index), "rows": dropped_index}, indent=2, sort_keys=True))

    plan = cost_plan(positions, cap_j=cap_j, sample_seed=sample_seed,
                     playout_secs=playout_secs)
    plan["files"] = leg_info["files"]
    plan["census_rows_n"] = len(rows)
    plan["census_qualifying_n"] = len(selected)
    plan["allow_missing_champ_picks"] = bool(allow_missing_champ_picks)
    plan["n_positions_champ_pick_missing"] = n_missing_champ

    n_drop = len(dropped_rows)
    dedupe: dict = {
        "applied": amap is not None,
        "design_ref": "DESIGN.md §6 threat 3 (arms deduped by successor board "
                      "key; all-transposition positions dropped as analytic zeros)",
        "n_qualifying_before_drop": len(selected),
        "n_dropped_all_transposition": n_drop,
        "dropped_pct": (100.0 * n_drop / len(selected)) if selected else 0.0,
        "n_dropped_by_stratum": {
            s: sum(1 for r in dropped_rows if r["stratum"] == s)
            for s in sorted({r["stratum"] for r in dropped_rows})},
        "n_dropped_with_action_played_outside_tieset": sum(
            1 for d in dropped_index if d["action_played_outside_tieset"]),
        "n_positions_with_arm_dedupe": n_arm_deduped,
        "dropped_index_path": str(out_dir / "DROPPED_ALL_TRANSPOSITION.json"),
    }
    if amap is not None:
        # honest before/after: TIE-SET arms only, over the FULL qualifying
        # supply (the champion arm is not what dedupe acts on, and including it
        # would mix a §2.3 cost into a §6 saving).
        before = _tieset_playouts(selected, cap_j, None)
        after = _tieset_playouts(selected, cap_j, amap)
        dedupe.update({
            "tieset_arm_playouts_full_supply_before": before,
            "tieset_arm_playouts_full_supply_after": after,
            "savings_pct_full_supply": (100.0 * (1 - after / before)) if before else 0.0,
        })
    plan["afterstate_dedupe"] = dedupe
    plan["out_dir"] = str(out_dir)
    plan["generated_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (out_dir / "POSITIONS_PLAN.json").write_text(json.dumps(plan, indent=2, sort_keys=True))
    return plan


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--census-rows", default=str(DEFAULT_CENSUS_ROWS))
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    ap.add_argument("--champ-picks", default=None,
                    help="path to the champ_picks.py output jsonl. Required for "
                         "selfplay-stratum positions unless "
                         "--allow-missing-champ-picks is given; e4 rows never "
                         "need it (their champion pick is free from the archive).")
    ap.add_argument("--allow-missing-champ-picks", action="store_true",
                    help="build selfplay positions even where no champion pick "
                         "is resolved yet -- they get no champion arm at all "
                         "(champ_pick_missing=True), but their tie-set legs are "
                         "still scoreable.")
    ap.add_argument("--cap-j", type=int, default=4)
    ap.add_argument("--n", type=int, default=0,
                    help="0 = all qualifying positions; else a seeded subsample "
                         "(--sample-seed), e4-first per DESIGN #7.3")
    ap.add_argument("--n-e4", type=int, default=None,
                    help="explicit e4 allocation (overrides the e4-first --n "
                         "split). DESIGN #7.3 Stage A = --n-selfplay 280 "
                         "--n-e4 60.")
    ap.add_argument("--n-selfplay", type=int, default=None,
                    help="explicit selfplay allocation -- see --n-e4.")
    ap.add_argument("--afterstate-map", nargs="+", default=None,
                    help="transposition_census.py --out file(s) carrying "
                         "bp_rid/action_groups. Default: every "
                         "census/afterstate_map_*.json. REQUIRED (DESIGN #6 "
                         "threat 3) unless --no-dedupe.")
    ap.add_argument("--no-dedupe", action="store_true",
                    help="deliberately build the PRE-dedupe plan (known-zero "
                         "transposition rows included). run_tiletie.py's "
                         "preflight REFUSES to launch such a plan.")
    ap.add_argument("--sample-seed", type=int, default=20260812)
    ap.add_argument("--playout-secs", type=float, default=1.65)
    ap.add_argument("--e4-dir", default=str(DEFAULT_E4_DIR))
    ap.add_argument("--bank-roots", default=DEFAULT_BANK_ROOTS)
    ap.add_argument("--champ-games", default=str(DEFAULT_CHAMP_GAMES))
    args = ap.parse_args(argv)

    rows = load_census_rows(args.census_rows)
    drift = cross_check_schema(rows)
    if drift and (drift["extra"] or drift["missing"]):
        print(f"[build_positions] WARNING: schema drift vs chain_census."
              f"ROW_SCHEMA_KEYS: {drift}", file=sys.stderr)

    champ_picks = load_champ_picks(args.champ_picks) if args.champ_picks else {}

    amap = None
    if not args.no_dedupe:
        paths = args.afterstate_map or sorted(
            str(p) for p in DEFAULT_AFTERSTATE_MAP_DIR.glob("afterstate_map_*.json"))
        if not paths:
            raise SystemExit(
                f"[build_positions] no afterstate map found under "
                f"{DEFAULT_AFTERSTATE_MAP_DIR} -- build one per rules profile "
                "with scripts/tiletie/transposition_census.py --profile <p> "
                "--out <dir>/afterstate_map_<p>.json (DESIGN #6 threat 3), or "
                "pass --no-dedupe deliberately.")
        amap = load_afterstate_maps(paths)
        print(f"[build_positions] afterstate map: {len(amap)} rid(s) from "
              f"{len(paths)} file(s): {paths}")

    plan = build(rows, out_dir=Path(args.out_dir), champ_picks=champ_picks,
                cap_j=args.cap_j, n=args.n, sample_seed=args.sample_seed,
                playout_secs=args.playout_secs, e4_dir=Path(args.e4_dir),
                bank_roots_path=args.bank_roots, champ_games_path=args.champ_games,
                allow_missing_champ_picks=args.allow_missing_champ_picks,
                afterstate_map=amap, require_afterstate_map=not args.no_dedupe,
                n_e4=args.n_e4, n_selfplay=args.n_selfplay)

    ded = plan["afterstate_dedupe"]
    print(f"[build_positions] afterstate dedupe: applied={ded['applied']} | "
          f"dropped {ded['n_dropped_all_transposition']}/"
          f"{ded['n_qualifying_before_drop']} all-transposition positions "
          f"({ded['dropped_pct']:.1f}%) | arm-deduped "
          f"{ded['n_positions_with_arm_dedupe']} | tie-set arm-playouts "
          f"{ded.get('tieset_arm_playouts_full_supply_before')} -> "
          f"{ded.get('tieset_arm_playouts_full_supply_after')} "
          f"({ded.get('savings_pct_full_supply', 0.0):.1f}% saved)")
    print(f"[build_positions] {len(rows)} census rows -> {plan['census_qualifying_n']} "
          f"qualifying -> {plan['n_positions']} sampled | e4={plan['n_e4']} "
          f"selfplay={plan['n_selfplay']} | max_arms={plan['max_arms']} "
          f"mean_arms={plan['mean_arms']:.2f} | capped={plan['n_positions_capped']} "
          f"| champ_pick_missing={plan['n_positions_champ_pick_missing']}")
    print(f"[build_positions] {len(plan['files'])} leg files -> {args.out_dir}")
    print(json.dumps(plan, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
