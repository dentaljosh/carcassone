#!/usr/bin/env python3
"""SYNTHETIC MECHANISM-CORROBORATION of CL-083's policy-conditional pricing clause.

⛔ SCOPE, BEFORE ANYTHING ELSE. This instrument prices **the CLAUSE** — the claim
that a champion-continuation future prices defense/steering divergences ~0
*because the continuation estimand is policy-conditional*. It says NOTHING about
the owner's edge, no owner ply is in it, and it can never substitute for the
defense-primary standing read (`measurement/defense_primary_prep/` is that
instrument, and it does not exist yet). See PREREG.md §0 and §8.

WHAT ONE UNIT IS
----------------
One unit is one `(game, ply, world)` on a SYNTHETIC self-play game. It runs
**four** arms from the identical root state at the target ply — the cross of

    pick    in {pick_champ, pick_armed}   the champion's / the armed agent's
                                          own choice at that root, both at the
                                          PINNED 11008 budget
    family  in {champ, armed}             the continuation policy that then
                                          plays BOTH SEATS to termination
                                          (dose 0.0 / dose 0.25 mask 31 opp)

and prices, per family, `delta_pts_mover = (pick_armed - pick_champ)`,
mover-signed. The FAMILY DELTA of a ply is `price_armed_family -
price_champ_family`; the PRIMARY is that family delta's DEFENSE-minus-CONTROL
contrast (PREREG §3).

⚠️ WHY THE PRIMARY IS A STRATUM CONTRAST AND NOT A RAW FAMILY DELTA. Each
policy's pick is that policy's own argmax, so under its own continuation it wins
by roughly its own root top-2 gap — for reasons that have nothing to do with
defense. The raw family delta is therefore biased POSITIVE at every stratum by
construction. Only the defense-minus-control contrast (on a stratum matched for
ply fraction, legal-move count and root top-2 gap) estimates the clause. This is
E-1b FORBIDDEN READING 4 applied to a synthetic corpus.

Reuse, not reinvention: the world/CRN machinery, the capped-child isolation, the
`jr_expansions` scope witness and the sign convention are E-1b's
(`measurement/e1b_armed_continuation_20260901/continue_armed.py`), copied here
rather than imported so that a frozen round owns its own code. The armed agent
is built through the PUBLIC factory seam (`champion_factory.production_prior_cfg`
+ `dataclasses.replace` on the three `jrules_prior_*` SEARCH fields) — no `src/`
edit, no leaf hash moves.

Subcommands
-----------
    gen             play synthetic champion-vs-armed games from a seed range
    select          per candidate ply: the two policies' picks + the mechanical
                    defense-shape census (judge-free)
    freeze-targets  stratify + match + cap -> targets_synth.jsonl (the FROZEN set)
    emit-manifest   the negative control + manifest.json
    price           the unit runner (4 arms per unit, resumable, sharded)
"""
from __future__ import annotations

import argparse
import dataclasses as _dc
import hashlib
import json
import multiprocessing as mp
import os
import platform
import random
import resource
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

DIR = Path(__file__).resolve().parent

SCHEMA = "defense-mech-synth/v1"

# --------------------------------------------------------------------------- #
# FROZEN CONSTANTS (PREREG.md §1.2)                                             #
# --------------------------------------------------------------------------- #
# ⛔ A DIFFERENT world seed from E-1a/E-1b's 20260828, deliberately: these are
#    different games entirely and NO CRN relationship with E-1b exists or is
#    claimed. Sharing the constant would invite exactly that misreading.
WORLD_SEED = 20260902
CONTINUATION_SEED = 0          # the continuation agents' seed, both families
SELECT_SEED = 0                # the two selector agents' seed
MATCH_SEED = 20260902          # the control-stratum matching draw
M_WORLDS = 8

ARM_DOSE = 0.25                # S1 G1's adjudicated d*
ARM_MASK = 31                  # joshua_bot.PRESETS["current"], S1 G3's mask
ARM_SCOPE = "opp"              # JrPriorScope::Opp — opponent-mover nodes

# ⛔ PINNED, not inherited from PRODUCTION.yaml: the same 11008 E-1a/E-1b used,
#    so "the pricing instrument" this round corroborates is the SAME instrument.
PINNED_K_DETS = 8
PINNED_SIMS_PER_DET = 1376
PINNED_EXACT_K = 2
LEAF_HASH_OF_RECORD = "a36d2e15a3b3d71d"

# The GENERATION budget — modest on purpose (positions are a DISTRIBUTION, never
# a statistic). `sims_per_det` is held at 1376 because S1 DESIGN measured that
# `scope=opp` is unexpressed at shallow per-world depth; halving k instead keeps
# the arming expressed while halving the cost.
GEN_K_DETS = 4
GEN_SIMS_PER_DET = 1376
GEN_EXACT_K = 2

RULES_PROFILE = "fixed_v1"

# --- the ply selector (judge-free, pre-declared) ---------------------------- #
PLY_FRAC_MIN = 0.62
PLY_FRAC_MAX = 0.88
MIN_UNSEEN_TILES = 8           # >= 8! distinct completions, so M=8 worlds differ
SELECT_PHASE = "tiles"
MAX_PER_GAME_PER_STRATUM = 2   # keeps the game-clustering inflation near 1.05
N_TARGET_PER_STRATUM = 200
N_IDENTITY = 8                 # agreement plies, G-IDENTITY only, never priced
                               # into any stratum

# --- the bar (PREREG §4; derived from the decision, NOT from 2 sigma-hat) --- #
BAR_CLAUSE = 1.75

# --- caps / isolation (inherited from E-1a's D-1) --------------------------- #
CPU_HARD_GRACE_S = 30
WALL_GRACE_S = 60

FAMILIES = ("champ", "armed")
PICKS = ("pick_champ", "pick_armed")
ARMS = tuple(f"{p}__{f}" for f in FAMILIES for p in PICKS)

CRN_WITNESS_KEYS = ("root_repr_sha", "world_deck_sha", "world_deck_len",
                    "n_drawn_prefix", "n_legal_root", "move_idx_at_root")
# ⚠️ `det_seed_base_at_root` is deliberately NOT a CRN key here: it is a property
#    of the AGENT (seed x move_idx), and this round runs two differently-configured
#    agents on the same root. It is RECORDED per arm and checked by G-ROOT as a
#    WITHIN-FAMILY equality only (see `root_identity`).
DET_SEED_KEY = "det_seed_base_at_root"
JR_KEYS = ("total", "own_mover", "boosted")

# The Stage-A / S0v2 census vocabulary this round's predicate is drawn from.
S0V2_DIR = REPO / "measurement" / "s0v2_scripted_prep"


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def sha256_file(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def world_rng(deck_seed: int, ply: int, world: int) -> random.Random:
    """The world's deck-completion generator.

    ⚠️ NO ARM TERM (the CRN guarantee) and NO POLICY/FAMILY TERM (the
    cross-family guarantee): the same `(deck_seed, ply, world)` yields the same
    permutation under either continuation family AND either pick, which is what
    makes `G-ROOT` checkable and the family delta a genuinely paired statistic.
    Shape copied from E-1b's `world_rng`; the seed constant is this round's own."""
    return random.Random(WORLD_SEED ^ (int(deck_seed) * 1000003)
                         ^ (int(ply) * 7919) ^ (int(world) * 104729))


def atomic_write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, sort_keys=False))
    tmp.rename(path)


# --------------------------------------------------------------------------- #
# THE SCOPE WITNESS — play-derived, never a config echo (E-1b §2.4, verbatim    #
# shape; extended with the CHAMPION-FAMILY zero check that E-1b could not make) #
# --------------------------------------------------------------------------- #
def scope_denominator(census: dict, scope: str) -> int:
    """The expansions THIS scope is allowed to boost."""
    total, own = int(census["total"]), int(census["own_mover"])
    if scope == "own":
        return own
    if scope == "opp":
        return total - own
    if scope == "all":
        return total
    raise ValueError(f"unknown scope {scope!r}")


def scope_witness(census, scope: str) -> dict:
    """`G-WITNESS` for one ARMED-family arm. Five hard checks (E-1b §2.4):

      1. all three INTEGER keys present — an absent key is a STALE (pre-R7)
         `carc_rs` wheel, never "the arm did not boost";
      2. `total > 0`;
      3. `0 <= own_mover <= total`;
      4. `boosted > 0` — the knob EXPRESSED IN PLAY;
      5. `boosted <= denominator(scope)` — the boost stayed inside its scope.

    Check 5 is an INEQUALITY on purpose (terminal / no-legal-child expansions can
    legitimately boost nothing). `coverage` is ADVISORY and never voids."""
    fail = []
    if not isinstance(census, dict):
        return {"ok": False, "failures": ["census_absent_stale_wheel"],
                "coverage": None, "denominator": None, "exact_partition": None}
    missing = [k for k in JR_KEYS if k not in census]
    if missing:
        return {"ok": False, "failures": [f"census_missing_keys:{missing}"],
                "coverage": None, "denominator": None, "exact_partition": None}
    try:
        total, own = int(census["total"]), int(census["own_mover"])
        boosted = int(census["boosted"])
    except (TypeError, ValueError):
        return {"ok": False, "failures": ["census_not_integers"],
                "coverage": None, "denominator": None, "exact_partition": None}
    if total <= 0:
        fail.append("total_not_positive")
    if not (0 <= own <= max(total, 0)):
        fail.append("own_mover_out_of_range")
    if boosted <= 0:
        fail.append("boosted_not_positive__knob_never_expressed")
    den = scope_denominator({"total": total, "own_mover": own}, scope)
    if boosted > max(den, 0):
        fail.append(f"boosted_outside_scope:{boosted}>{den}")
    return {"ok": not fail, "failures": fail, "denominator": den,
            "coverage": (boosted / den) if den > 0 else None,
            "exact_partition": (boosted == den)}


def champ_witness(census) -> dict:
    """⭐ The CHAMPION-family arm's witness — the IN-ROUND dose gate.

    E-1b could only dose-gate its census ONCE, in a four-decision pre-flight,
    because every one of its arms was armed. This round plays BOTH doses on every
    single root, so the negative control runs on EVERY unit: a dose-0 arm's
    census must be EXACTLY all-zero (the wiring probe of E-1b PREREG §5.2
    measured `{0, 0, 0}` for the unmodified champion). A nonzero counter here
    means the census is NOT dose-gated and every `boosted > 0` in the round is
    uninterpretable — so this is a HARD check, not an advisory one."""
    if not isinstance(census, dict):
        return {"ok": False, "failures": ["census_absent_stale_wheel"]}
    missing = [k for k in JR_KEYS if k not in census]
    if missing:
        return {"ok": False, "failures": [f"census_missing_keys:{missing}"]}
    try:
        vals = {k: int(census[k]) for k in JR_KEYS}
    except (TypeError, ValueError):
        return {"ok": False, "failures": ["census_not_integers"]}
    bad = [k for k, v in vals.items() if v != 0]
    return {"ok": not bad, "failures": [f"dose0_census_nonzero:{bad}"] if bad else [],
            "census": vals}


def family_witness(census, family: str, scope: str = ARM_SCOPE) -> dict:
    return scope_witness(census, scope) if family == "armed" else champ_witness(census)


def root_identity(witnesses: dict) -> dict:
    """`G-ROOT` for ONE unit — the single-variable proof, ACROSS FAMILIES.

    Every one of `CRN_WITNESS_KEYS` is a property of the ROOT and the WORLD and
    carries no policy term, so all FOUR arms of a unit (2 picks x 2 continuation
    families) must agree on all six, bit for bit. A mismatch means the two family
    pricings did not price the same world — a BUG SIGNAL, never attrition.

    `det_seed_base_at_root` is checked WITHIN family only (it is an agent
    property; the two families are different agents)."""
    arms = {k: v for k, v in witnesses.items() if isinstance(v, dict)}
    if len(arms) != len(ARMS):
        return {"ok": False, "reason": "arms_missing",
                "fields": sorted(set(ARMS) - set(arms))}
    ref_name = ARMS[0]
    ref = arms[ref_name]
    bad = sorted({k for name, w in arms.items() for k in CRN_WITNESS_KEYS
                  if w.get(k) != ref.get(k)})
    det_bad = []
    for fam in FAMILIES:
        vals = {arms[f"{p}__{fam}"].get(DET_SEED_KEY) for p in PICKS}
        if len(vals) > 1:
            det_bad.append(fam)
    if bad or det_bad:
        return {"ok": False, "reason": "root_identity_mismatch",
                "fields": bad, "det_seed_families": det_bad}
    return {"ok": True, "reason": None, "fields": [],
            "witness": {k: ref.get(k) for k in CRN_WITNESS_KEYS}}


# --------------------------------------------------------------------------- #
# THE AGENTS — public factory seam only, no src/ edit                           #
# --------------------------------------------------------------------------- #
def armed_prior_cfg(dose=ARM_DOSE, mask=ARM_MASK, scope=ARM_SCOPE):
    """The production champion's `HeuristicPriorConfig` with the S1 arming.

    Built by REPLACING three SEARCH fields on `champion_factory
    .production_prior_cfg()`; leaf/curve/caps/c_puct/tau_p/value_norm/
    final_select are untouched and NO leaf hash moves. `dose == 0.0` returns the
    champion byte-for-byte — that is the champion family AND the negative
    control, from one code path."""
    from carcassonne_ai import champion_factory as CF

    base = CF.production_prior_cfg()
    if float(dose) == 0.0:
        return base
    return _dc.replace(base, jrules_prior_dose=float(dose),
                       jrules_prior_mask=int(mask),
                       jrules_prior_scope=str(scope))


def build_agent(game, seed, threads, *, dose, mask=ARM_MASK, scope=ARM_SCOPE,
                k_dets=PINNED_K_DETS, sims=PINNED_SIMS_PER_DET,
                exact_k=PINNED_EXACT_K):
    """RUST-ONLY and FAIR-ONLY, exactly as E-1b: a nonzero dose on the python
    search path hard-exits and a pre-S1 `carc_rs` rejects `scope` at config
    construction. Both are fail-closed — a silently unarmed 'armed' agent would
    play champion-vs-champion and grade a perfect null wearing this round's
    name."""
    from carcassonne_ai import champion_factory as CF

    return CF.build_fair_champion(
        game, cfg=armed_prior_cfg(dose, mask, scope),
        sims=int(sims), k_dets=int(k_dets), seed=int(seed),
        exact_endgame=True, exact_max_k=int(exact_k),
        backend="rust", rust_threads=int(threads or 1))


def family_dose(family: str) -> float:
    if family == "champ":
        return 0.0
    if family == "armed":
        return ARM_DOSE
    raise ValueError(f"unknown continuation family {family!r}")


def jr_census(agent) -> dict | None:
    """The play-derived expansion census off `FairAgentRs.stats()`.

    Returns None when the counters are ABSENT — a stale (pre-R7) wheel. None is
    NOT zeros: the witnesses treat it as a hard failure, because "the arm did not
    boost" and "nobody looked" must never wear the same shape."""
    rs = getattr(agent, "_rs", None)
    if rs is None:
        return None
    s = rs.stats()
    if "jr_expansions_total" not in s:
        return None
    return {"total": int(s["jr_expansions_total"]),
            "own_mover": int(s["jr_expansions_own_mover"]),
            "boosted": int(s["jr_expansions_boosted"])}


def resolved_arming(agent) -> dict:
    """The RESOLVED knobs off the rust side — never what we asked for."""
    s = agent._rs.stats()
    return {"dose": float(s["jrules_prior_dose"]),
            "mask": int(s["jrules_prior_mask"]),
            "scope": str(s["jrules_prior_scope"]),
            "k_dets": int(s["k_dets"]),
            "sims_per_det": int(s["sims_per_det"]),
            "exact_max_k": int(s["exact_max_k"]),
            "threads": int(s["threads"]), "seed": int(s["seed"])}


def top2_gap(agent) -> dict:
    """The root's normalised top-2 pooled-visit gap — the matching covariate.

    `(v1 - v2) / sum(v)`, from `FairAgentRs.last_pooled_visits`. A root with one
    visited action reads 1.0. Used ONLY to match the control stratum to the
    defense stratum (PREREG §2.3); it is never an outcome and never a price."""
    try:
        pv = agent.last_pooled_visits
    except Exception:                                       # noqa: BLE001
        return {"gap": None, "n_actions": 0, "reason": "unavailable"}
    vals = sorted((float(v) for v in pv.values()), reverse=True)
    tot = sum(vals)
    if not vals or tot <= 0:
        return {"gap": None, "n_actions": len(vals), "reason": "no_visits"}
    if len(vals) == 1:
        return {"gap": 1.0, "n_actions": 1, "reason": None}
    return {"gap": (vals[0] - vals[1]) / tot, "n_actions": len(vals),
            "reason": None}


# --------------------------------------------------------------------------- #
# THE DEFENSE-SHAPE PREDICATE — mechanical, prospective, judge-free             #
# --------------------------------------------------------------------------- #
def _s0v2():
    """The Stage-A / S0v2 census vocabulary, imported the way its own tests do.

    ⛔ Nothing is re-implemented: `Structure`, `PlanConfig`, `merge_plausible`
    and `Structure.victims_of` are the S0v2 agent's own symbols
    (`measurement/s0v2_scripted_prep/s0v2_agent.py`), which in turn re-derive
    `stage_a_census`'s `contested` / `mech == "merge"` definitions exactly."""
    if str(S0V2_DIR) not in sys.path:
        sys.path.insert(0, str(S0V2_DIR))
    import s0v2_agent as S
    return S


def defense_shape(game, board) -> dict:
    """⭐ THE SELECTOR'S SHAPE CONDITION — mechanical, prospective, judge-free.

    Three steps, every term a Stage-A / S0v2 symbol:

      1. THREAT PAIRS. `V` in `Structure.victims_of(mover, PlanConfig())` — a
         component held EXCLUSIVELY by the mover, unfinished, `n_tiles >= 5`,
         `potential_pts >= 4` ("worth invading"); crossed with `B` exclusively
         held by the OPPONENT, same feature class, with
         `merge_plausible(struct, V, B)` — a single empty cell touches both, so
         ONE tile could merge the opponent's part into the mover's feature.
      2. MERGE CELLS. `C = union over pairs of adj_empty(V) & adj_empty(B)` —
         exactly the cells where that one-tile steal could land.
      3. ⭐ PLUGS. The MOVER'S OWN LEGAL TILE PLACEMENTS this ply whose
         coordinate lies in `C` — i.e. the defensive options that physically
         exist RIGHT NOW, with the tile actually in hand.

        DEFENSE-SHAPED  iff  `n_plugs >= 1`
        CONTROL         iff  `n_plugs == 0`

    ⚠️ WHY STEP 3 EXISTS, measured not assumed. Steps 1-2 alone SATURATE: a
    pre-freeze census of 46 late-window tiles plies found a live threat pair at
    100 % of them (all farm-class — in the [0.62, 0.88] window no city or road
    survives `victim_min_tiles = 5` unfinished and exclusively held). A predicate
    true everywhere has no control stratum and cannot be a contrast. Adding the
    legality step made the rate 26 % (12/46) — discriminating, and semantically
    the sharper claim: the strata differ in whether a DEFENSIVE MOVE EXISTS,
    which is precisely what "defense/steering value" has to mean.

    Nothing is judged, nothing looks forward, and the game's played line is
    irrelevant — only the position and the tile in hand. Returns the whole census
    so the artefact carries the counts the adjudicator re-derives, never a bare
    boolean."""
    from wingedsheep.carcassonne.objects.actions.tile_action import TileAction

    S = _s0v2()
    cfg = S.PlanConfig()
    state = board.state
    me = int(state.current_player)
    opp = 1 - me
    struct = S.Structure(state)
    victims = struct.victims_of(me, cfg)
    opp_parts = [k for k in struct.counts if struct.exclusively(k, opp)]
    pairs, cells = [], set()
    for v in victims:
        for b in opp_parts:
            if v[0] != b[0]:
                continue
            inter = struct.adj_empty(v) & struct.adj_empty(b)
            if inter:
                pairs.append((v, b))
                cells |= inter
    valid = game.get_valid_moves(board)
    n_plugs, n_tile_actions = 0, 0
    plug_cells = set()
    for idx in range(len(valid)):
        if not valid[idx]:
            continue
        act = game._decode_for(state, board.offset, int(idx))
        if not isinstance(act, TileAction):
            continue
        n_tile_actions += 1
        coord = (act.coordinate.row, act.coordinate.column)
        if coord in cells:
            n_plugs += 1
            plug_cells.add(coord)
    pts = [float(struct.potential_pts(v)) for v, _ in pairs]
    return {
        "n_plugs": n_plugs,
        "n_distinct_plug_cells": len(plug_cells),
        "n_tile_actions": n_tile_actions,
        "plug_share": (n_plugs / n_tile_actions) if n_tile_actions else 0.0,
        "n_threat_pairs": len(pairs),
        "n_merge_cells": len(cells),
        "n_victims": len(victims),
        "n_opp_parts": len(opp_parts),
        "max_threat_pts": max(pts) if pts else 0.0,
        "threat_classes": sorted({str(v[0]) for v, _ in pairs}),
        "cfg": {"victim_min_tiles": cfg.victim_min_tiles,
                "victim_min_pts": cfg.victim_min_pts},
    }


def stratum_of(census: dict) -> str:
    """`defense` iff a defensive PLUG is legal at this root, else `control`."""
    return "defense" if int(census["n_plugs"]) >= 1 else "control"


# --------------------------------------------------------------------------- #
# CAPPED-CHILD ISOLATION (E-1b §2.5, verbatim shape)                            #
# --------------------------------------------------------------------------- #
def _child(fn, payload, mem_bytes, cpu_cap_s, conn):
    try:
        if mem_bytes > 0:
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        if cpu_cap_s > 0:
            # SIGXCPU left at its DEFAULT disposition on purpose: a Python-level
            # handler only runs at a bytecode boundary and would be ignored for
            # the whole duration of a long RUST decision.
            resource.setrlimit(resource.RLIMIT_CPU,
                               (cpu_cap_s, cpu_cap_s + CPU_HARD_GRACE_S))
        conn.send(("OK", fn(payload)))
    except MemoryError:
        conn.send(("OOM", None))
    except BaseException as e:                              # noqa: BLE001
        conn.send(("EXC", f"{type(e).__name__}: {e}"))
    finally:
        conn.close()


def run_isolated(fn, payload, mem_cap_gb: float, cpu_cap_s: int) -> dict:
    mem_bytes = int(mem_cap_gb * (1 << 30)) if mem_cap_gb > 0 else 0
    if mem_bytes <= 0 and cpu_cap_s <= 0:
        return fn(payload)
    ctx = mp.get_context("fork")
    parent, child = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_child, args=(fn, payload, mem_bytes,
                                            int(cpu_cap_s), child))
    t0 = time.time()
    proc.start()
    child.close()
    wall_cap = (cpu_cap_s + WALL_GRACE_S) if cpu_cap_s > 0 else None
    status, out, wall_timeout = None, None, False
    try:
        if parent.poll(timeout=wall_cap):
            try:
                status, out = parent.recv()
            except EOFError:
                status = "EOF"
        elif wall_cap is not None:
            wall_timeout = True
    finally:
        parent.close()
    if wall_timeout:
        try:
            proc.kill()
        except Exception:                                   # noqa: BLE001
            pass
    proc.join(timeout=60)
    elapsed = time.time() - t0
    if wall_timeout:
        return {"status": "TIME_SKIPPED", "kill_reason": "wall", "elapsed_s": elapsed}
    if status == "OK":
        out["elapsed_s"] = elapsed
        return out
    if proc.exitcode == -signal.SIGXCPU:
        return {"status": "TIME_SKIPPED", "kill_reason": "rlimit_cpu",
                "exitcode": proc.exitcode, "elapsed_s": elapsed}
    if status in ("OOM", "EOF") or (proc.exitcode or 0) < 0:
        return {"status": "OOM_SKIPPED", "exitcode": proc.exitcode,
                "elapsed_s": elapsed}
    return {"status": "ERROR", "detail": out, "elapsed_s": elapsed}


# --------------------------------------------------------------------------- #
# STAGE 1 — GENERATION: champion vs S1-armed self-play                          #
# --------------------------------------------------------------------------- #
def _gen_game(p: dict) -> dict:
    """One synthetic game. The champion sits at seat `seed % 2`, the armed agent
    at the other — seat-balanced across the band by construction.

    ⚠️ These games are a POSITION SOURCE, never a statistic. No margin, elo or
    win rate is read off them and none may be (PREREG §8.2)."""
    from carcassonne_ai import rules_profile
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.mirror_protocol import advance, resolve_execution, seat

    t0 = time.time()
    prof = rules_profile.resolve(p["profile"])
    ex = resolve_execution("rust", profile="desktop", rust_threads=p["threads"])
    if ex["backend"] != "rust":
        raise RuntimeError(f"this round is rust-only (surface B is): {dict(ex)}")
    seed = int(p["deck_seed"])

    random.seed(seed)
    g = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
    b = g.get_init_board()
    n_tiles_total = 1 + len(b.state.deck)

    champ_seat = seed % 2
    agents = {}
    for s in (0, 1):
        dose = 0.0 if s == champ_seat else ARM_DOSE
        agents[s] = build_agent(g, CONTINUATION_SEED, p["threads"], dose=dose,
                                k_dets=p["k_dets"], sims=p["sims"],
                                exact_k=p["exact_k"])
        seat(agents[s], b)

    actions, n = [], 0
    while g.get_game_ended(b, 0) == 0.0:
        mover = int(b.state.current_player)
        a = int(agents[mover].choose_action(b))
        actions.append(a)
        b, _ = g.get_next_state(b, a)
        for s in (0, 1):
            advance(agents[s], a)
        n += 1
        if n > 4 * n_tiles_total + 64:
            raise RuntimeError("generation did not terminate")
    s0, s1 = (int(x) for x in b.state.scores)
    censuses = {}
    for s in (0, 1):
        censuses[str(s)] = jr_census(agents[s])
        if hasattr(agents[s], "close"):
            agents[s].close()
    return {
        "status": "OK", "schema": SCHEMA + "/game",
        "deck_seed": seed, "profile": p["profile"],
        "champ_seat": champ_seat, "armed_seat": 1 - champ_seat,
        "actions": actions, "n_plies": len(actions),
        "n_tiles_total": n_tiles_total,
        "final_scores": [s0, s1], "margin_p0_minus_p1": s0 - s1,
        "gen_budget": {"k_dets": p["k_dets"], "sims_per_det": p["sims"],
                       "total_sims": p["k_dets"] * p["sims"],
                       "exact_max_k": p["exact_k"]},
        "gen_census": censuses, "execution": dict(ex),
        "gen_s": round(time.time() - t0, 3),
    }


def cmd_gen(a) -> int:
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    seeds = [s for s in range(a.seed_start, a.seed_start + a.n_games)
             if (s - a.seed_start) % a.of == a.shard]
    done = 0
    for s in seeds:
        p = out / f"g_{s}.json"
        if p.exists() and not a.force:
            done += 1
            continue
        r = run_isolated(_gen_game,
                         {"deck_seed": s, "profile": a.profile,
                          "threads": a.threads, "k_dets": a.gen_k_dets,
                          "sims": a.gen_sims, "exact_k": a.gen_exact_k},
                         a.job_mem_cap_gb, a.arm_cap_secs)
        r.setdefault("deck_seed", s)
        atomic_write_json(p, r)
        done += 1
        print(f"[gen] {s} {r.get('status')} n_plies={r.get('n_plies')} "
              f"{r.get('gen_s')}s", flush=True)
    print(f"[gen] shard {a.shard}/{a.of}: {done} games in {out}", flush=True)
    return 0


# --------------------------------------------------------------------------- #
# STAGE 2 — SELECTION: the two policies' picks + the shape census               #
# --------------------------------------------------------------------------- #
def _select_ply(p: dict) -> dict:
    """Both policies' picks at ONE candidate root, at the PINNED budget.

    Two fresh agents replay the game prefix with `advance` (never a search — the
    census at the root is asserted all-zero, exactly as the pricing arms do) and
    take one decision each. One capped child per candidate ply: deterministic,
    no cross-ply tree-reuse hazard, and the prefix replay is `advance`-only so it
    costs nothing measurable."""
    from carcassonne_ai import rules_profile
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.mirror_protocol import advance, resolve_execution, seat

    t0 = time.time()
    prof = rules_profile.resolve(p["profile"])
    ex = resolve_execution("rust", profile="desktop", rust_threads=p["threads"])
    seed, actions, ply = int(p["deck_seed"]), p["actions"], int(p["ply"])

    random.seed(seed)
    g = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
    b = g.get_init_board()
    n_tiles_total = 1 + len(b.state.deck)

    picks, gaps, arming, censuses = {}, {}, {}, {}
    mover = phase = n_legal = unseen = shape = root_sha = None
    for fam in FAMILIES:
        random.seed(seed)
        g2 = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
        b2 = g2.get_init_board()
        ag = build_agent(g2, SELECT_SEED, p["threads"], dose=family_dose(fam),
                         k_dets=p["k_dets"], sims=p["sims"], exact_k=p["exact_k"])
        seat(ag, b2)
        for act in actions[:ply]:
            b2, _ = g2.get_next_state(b2, int(act))
            advance(ag, int(act))
        if hasattr(ag, "check_sync"):
            ag.check_sync(b2, "selector_root")
        c0 = jr_census(ag)
        if c0 is not None and c0["total"] != 0:
            raise RuntimeError(f"the prefix replay searched: census {c0}")
        ag._move_idx = ply
        picks[fam] = int(ag.choose_action(b2))
        gaps[fam] = top2_gap(ag)
        arming[fam] = resolved_arming(ag)
        censuses[fam] = jr_census(ag)
        if fam == "champ":
            state = b2.state
            mover = int(state.current_player)
            valid = g2.get_valid_moves(b2)
            n_legal = int(valid.sum())
            # `n_unseen_tiles` is EXACTLY the quantity the world permutation
            # shuffles (`_run_arm`'s `unseen = list(state.deck)`), so the
            # selector's MIN_UNSEEN_TILES rule and the arm's `world_deck_len`
            # witness are the same number by construction.
            unseen = len(state.deck)
            phase = str(getattr(state.phase, "name", state.phase)).lower()
            shape = defense_shape(g2, b2)
            root_sha = sha(g2.string_representation(b2))
        if hasattr(ag, "close"):
            ag.close()

    return {
        "status": "OK", "schema": SCHEMA + "/select",
        "deck_seed": seed, "ply": ply, "profile": p["profile"],
        "n_plies": len(actions), "ply_frac": ply / max(1, len(actions)),
        "mover": mover, "phase": phase, "n_legal": n_legal,
        "n_unseen_tiles": unseen, "n_tiles_total": n_tiles_total,
        "root_repr_sha": root_sha,
        "pick_champ": picks["champ"], "pick_armed": picks["armed"],
        "diverges": picks["champ"] != picks["armed"],
        "top2_gap_champ": gaps["champ"]["gap"],
        "top2_gap_armed": gaps["armed"]["gap"],
        "top2_gap_detail": gaps,
        "shape": shape, "stratum_raw": stratum_of(shape),
        "arming_resolved": arming, "jr_expansions": censuses,
        "select_s": round(time.time() - t0, 3), "execution": dict(ex),
    }


def candidate_plies(game: dict, profile: str = RULES_PROFILE) -> list[int]:
    """The pre-declared candidate window (PREREG §2.1), decided SEARCH-FREE.

    A single replay of the game (engine transitions only, no agent, no search)
    yields every ply's phase, unseen-tail length and ply fraction, so the two
    expensive pinned-budget searches are only ever spent on plies that are
    already eligible:

        `phase == tiles`  AND  `len(state.deck) >= MIN_UNSEEN_TILES`
        AND  `PLY_FRAC_MIN <= ply/n_plies <= PLY_FRAC_MAX`

    ⚠️ THIS IS A THROUGHPUT FILTER ONLY and it is bit-identical in effect to
    filtering inside `_select_ply` — `build_targets` re-applies all three
    conditions to whatever rows exist, so a plan that over- or under-emits
    changes cost, never the frozen selection. Measured on the pre-freeze probe:
    it halves the selection bill (37 -> 18.0 searched plies per game)."""
    from carcassonne_ai import rules_profile
    from carcassonne_ai.game_wrapper import Game

    prof = rules_profile.resolve(profile)
    n = int(game["n_plies"])
    lo, hi = int(PLY_FRAC_MIN * n), int(PLY_FRAC_MAX * n)
    random.seed(int(game["deck_seed"]))
    g = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
    b = g.get_init_board()
    out = []
    for ply, act in enumerate(game["actions"]):
        if lo <= ply <= hi:
            st = b.state
            phase = str(getattr(st.phase, "name", st.phase)).lower()
            if phase == SELECT_PHASE and len(st.deck) >= MIN_UNSEEN_TILES:
                out.append(ply)
        if ply > hi:
            break
        b, _ = g.get_next_state(b, int(act))
    return out


def cmd_select(a) -> int:
    gdir, out = Path(a.games), Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    todo = []
    for gp in sorted(gdir.glob("g_*.json")):
        game = json.loads(gp.read_text())
        if game.get("status") != "OK":
            continue
        for ply in candidate_plies(game, game.get("profile", RULES_PROFILE)):
            todo.append((game, ply))
    todo = [t for i, t in enumerate(todo) if i % a.of == a.shard]
    n_ok = 0
    for game, ply in todo:
        p = out / f"s_{game['deck_seed']}_p{ply:03d}.json"
        if p.exists() and not a.force:
            n_ok += 1
            continue
        r = run_isolated(_select_ply,
                         {"deck_seed": game["deck_seed"], "actions": game["actions"],
                          "ply": ply, "profile": game["profile"],
                          "threads": a.threads, "k_dets": PINNED_K_DETS,
                          "sims": PINNED_SIMS_PER_DET, "exact_k": PINNED_EXACT_K},
                         a.job_mem_cap_gb, a.arm_cap_secs)
        r.setdefault("deck_seed", game["deck_seed"])
        r.setdefault("ply", ply)
        atomic_write_json(p, r)
        n_ok += r.get("status") == "OK"
    print(f"[select] shard {a.shard}/{a.of}: {n_ok}/{len(todo)} ok", flush=True)
    return 0


# --------------------------------------------------------------------------- #
# STAGE 3 — FREEZE: stratify, cap, match                                        #
# --------------------------------------------------------------------------- #
def _decile(x, edges) -> int:
    for i, e in enumerate(edges):
        if x <= e:
            return i
    return len(edges)


def _quantile_edges(vals, k: int) -> list[float]:
    v = sorted(vals)
    if not v:
        return []
    return [v[min(len(v) - 1, int(round(i * len(v) / k)))] for i in range(1, k)]


def _smd(a_vals, b_vals) -> float:
    """Standardised mean difference — the matching-balance statistic."""
    import statistics as st
    if len(a_vals) < 2 or len(b_vals) < 2:
        return float("inf")
    ma, mb = st.mean(a_vals), st.mean(b_vals)
    va, vb = st.pvariance(a_vals), st.pvariance(b_vals)
    pooled = ((va + vb) / 2.0) ** 0.5
    return abs(ma - mb) / pooled if pooled > 0 else (0.0 if ma == mb else float("inf"))


def build_targets(rows: list[dict], n_per_stratum=N_TARGET_PER_STRATUM,
                  n_identity=N_IDENTITY, seed=MATCH_SEED,
                  max_per_game=MAX_PER_GAME_PER_STRATUM) -> dict:
    """⭐ THE FROZEN SELECTOR, end to end and outcome-blind.

    1. eligibility  — `status == OK`, `phase == tiles`, `n_unseen_tiles >=
                      MIN_UNSEEN_TILES`, ply fraction in window.
    2. divergence   — `pick_champ != pick_armed`. (Agreement plies feed the
                      G-IDENTITY set instead; they are never priced into a
                      stratum.)
    3. stratum      — `defense` iff the shape census has `n_threats >= 1`,
                      else `control`.
    4. cap          — at most `max_per_game` plies per GAME per stratum, taken in
                      a seeded random order (never "the first two", which would
                      bias toward the early end of the window).
    5. defense draw — up to `n_per_stratum`, seeded.
    6. control MATCH — the control stratum is drawn to REPRODUCE the defense
                      stratum's joint histogram over
                      (ply-fraction quintile, n_legal tercile, champion top-2-gap
                      quintile). Cells short of supply are filled from the
                      nearest cell by L1 distance in cell coordinates, and every
                      such fill is RECORDED (E-1a's decile match did the same and
                      disclosed its 3-of-30 nearest-decile fills; so does this).

    The matching is what makes the PRIMARY a mechanism estimate rather than a
    restatement of each policy's own root top-2 gap — see the module docstring."""
    rng = random.Random(seed)
    elig = [r for r in rows
            if r.get("status") == "OK"
            and r.get("phase") == SELECT_PHASE
            and int(r.get("n_unseen_tiles", 0)) >= MIN_UNSEEN_TILES
            and PLY_FRAC_MIN <= float(r["ply_frac"]) <= PLY_FRAC_MAX
            and r.get("top2_gap_champ") is not None]
    div = [r for r in elig if r["diverges"]]
    agree = [r for r in elig if not r["diverges"]]

    def cap(pool):
        by_game: dict = {}
        for r in pool:
            by_game.setdefault(r["deck_seed"], []).append(r)
        out = []
        for seed_, rs in sorted(by_game.items()):
            rs = sorted(rs, key=lambda r: r["ply"])
            rng.shuffle(rs)
            out.extend(rs[:max_per_game])
        return sorted(out, key=lambda r: (r["deck_seed"], r["ply"]))

    d_pool = cap([r for r in div if r["stratum_raw"] == "defense"])
    c_pool = cap([r for r in div if r["stratum_raw"] == "control"])

    # TERCILES on all three axes => 27 cells. Quintiles were tried on paper and
    # rejected: 75 cells against a ~200-ply target leaves ~2.7 targets per cell
    # and forces nearest-cell fills for a large share of the stratum.
    pf_edges = _quantile_edges([r["ply_frac"] for r in d_pool + c_pool], 3)
    nl_edges = _quantile_edges([r["n_legal"] for r in d_pool + c_pool], 3)
    gp_edges = _quantile_edges([r["top2_gap_champ"] for r in d_pool + c_pool], 3)

    def cell(r):
        return (_decile(r["ply_frac"], pf_edges), _decile(r["n_legal"], nl_edges),
                _decile(r["top2_gap_champ"], gp_edges))

    d_sel = sorted(d_pool, key=lambda r: (r["deck_seed"], r["ply"]))
    rng.shuffle(d_sel)
    d_sel = sorted(d_sel[:n_per_stratum], key=lambda r: (r["deck_seed"], r["ply"]))

    want: dict = {}
    for r in d_sel:
        want[cell(r)] = want.get(cell(r), 0) + 1
    supply: dict = {}
    for r in c_pool:
        supply.setdefault(cell(r), []).append(r)
    for v in supply.values():
        rng.shuffle(v)

    c_sel, fills = [], []
    for c, k in sorted(want.items()):
        have = supply.get(c, [])
        take = have[:k]
        supply[c] = have[k:]
        c_sel.extend(take)
        short = k - len(take)
        if short <= 0:
            continue
        others = sorted((cc for cc, v in supply.items() if v),
                        key=lambda cc: (abs(cc[0] - c[0]) + abs(cc[1] - c[1])
                                        + abs(cc[2] - c[2]), cc))
        for cc in others:
            if short <= 0:
                break
            grab = supply[cc][:short]
            supply[cc] = supply[cc][len(grab):]
            c_sel.extend(grab)
            fills.append({"want_cell": list(c), "filled_from": list(cc),
                          "n": len(grab)})
            short -= len(grab)
        if short > 0:
            fills.append({"want_cell": list(c), "filled_from": None,
                          "n_unfilled": short})
    c_sel = sorted(c_sel, key=lambda r: (r["deck_seed"], r["ply"]))

    id_pool = cap([r for r in agree if r["stratum_raw"] == "defense"])
    rng.shuffle(id_pool)
    id_sel = sorted(id_pool[:n_identity], key=lambda r: (r["deck_seed"], r["ply"]))

    # `matched` covariates are what G-MATCH gates; `reported` ones are disclosed
    # beside them but were deliberately NOT matched (matching on the threat
    # SURFACE would over-constrain a 27-cell design, and `n_merge_cells` is
    # nonzero on essentially every eligible ply anyway).
    MATCHED = ("ply_frac", "n_legal", "top2_gap_champ")
    REPORTED = ("n_merge_cells", "max_threat_pts", "n_threat_pairs")
    balance = {}

    def _get(r, key):
        return float(r[key]) if key in r else float(r["shape"][key])

    for name in MATCHED + REPORTED:
        balance[name] = {
            "matched": name in MATCHED,
            "defense_mean": (sum(_get(r, name) for r in d_sel) / len(d_sel)) if d_sel else None,
            "control_mean": (sum(_get(r, name) for r in c_sel) / len(c_sel)) if c_sel else None,
            "smd": _smd([_get(r, name) for r in d_sel], [_get(r, name) for r in c_sel]),
        }

    def row(r, stratum):
        return {"deck_seed": r["deck_seed"], "ply": r["ply"], "stratum": stratum,
                "profile": r["profile"], "mover": r["mover"], "phase": r["phase"],
                "n_plies": r["n_plies"], "ply_frac": r["ply_frac"],
                "n_legal": r["n_legal"], "n_unseen_tiles": r["n_unseen_tiles"],
                "root_repr_sha": r["root_repr_sha"],
                "pick_champ": r["pick_champ"], "pick_armed": r["pick_armed"],
                "diverges": r["diverges"],
                "top2_gap_champ": r["top2_gap_champ"],
                "top2_gap_armed": r["top2_gap_armed"],
                "shape": r["shape"], "cell": list(cell(r))}

    targets = ([row(r, "defense") for r in d_sel]
               + [row(r, "control") for r in c_sel]
               + [row(r, "identity") for r in id_sel])
    return {
        "targets": targets,
        "selection": {
            "n_eligible": len(elig), "n_divergent": len(div),
            "n_agreement": len(agree),
            "divergence_rate": (len(div) / len(elig)) if elig else None,
            "pool_defense": len(d_pool), "pool_control": len(c_pool),
            "n_defense": len(d_sel), "n_control": len(c_sel),
            "n_identity": len(id_sel),
            "n_games": len({r["deck_seed"] for r in d_sel + c_sel}),
            "cell_edges": {"ply_frac": pf_edges, "n_legal": nl_edges,
                           "top2_gap_champ": gp_edges},
            "match_fills": fills, "balance": balance,
            "frozen": {"n_per_stratum": n_per_stratum, "n_identity": n_identity,
                       "match_seed": seed, "max_per_game": max_per_game,
                       "ply_frac_window": [PLY_FRAC_MIN, PLY_FRAC_MAX],
                       "min_unseen_tiles": MIN_UNSEEN_TILES,
                       "phase": SELECT_PHASE},
        },
    }


def cmd_freeze_targets(a) -> int:
    rows = [json.loads(p.read_text()) for p in sorted(Path(a.select).glob("s_*.json"))]
    built = build_targets(rows, n_per_stratum=a.n_per_stratum,
                          n_identity=a.n_identity)
    tp = Path(a.out)
    tp.parent.mkdir(parents=True, exist_ok=True)
    tmp = tp.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r, sort_keys=True) + "\n"
                           for r in built["targets"]))
    tmp.rename(tp)
    atomic_write_json(tp.with_name("SELECTION.json"),
                      {"schema": SCHEMA + "/selection",
                       "targets": str(tp.name),
                       "targets_sha256": sha256_file(tp), **built["selection"]})
    s = built["selection"]
    print(f"[freeze] defense={s['n_defense']} control={s['n_control']} "
          f"identity={s['n_identity']} games={s['n_games']} "
          f"div_rate={s['divergence_rate']} fills={len(s['match_fills'])}",
          flush=True)
    for k, v in s["balance"].items():
        print(f"[freeze]   balance {k}: SMD={v['smd']:.3f}", flush=True)
    return 0


# --------------------------------------------------------------------------- #
# STAGE 4 — PRICING: one unit = one (game, ply, world), FOUR arms                #
# --------------------------------------------------------------------------- #
def _run_arm(p: dict) -> dict:
    """One arm: apply `arm_action` at the target ply, then let ONE agent of the
    named continuation family play BOTH SEATS to termination.

    Both seats carry the family (E-1b §2.2's argument, unchanged): the estimand's
    conditioning variable is the continuation POLICY, and arming one seat only
    would confound the ply's value with a strength difference between two
    different agents."""
    from carcassonne_ai import rules_profile
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.mirror_protocol import advance, resolve_execution, seat

    t_arm = time.time()
    prof = rules_profile.resolve(p["profile"])
    ex = resolve_execution("rust", profile="desktop", rust_threads=p["threads"])
    if ex["backend"] != "rust":
        raise RuntimeError(f"this round is rust-only (surface B is): {dict(ex)}")
    seed, actions, ply = int(p["deck_seed"]), p["actions"], int(p["ply"])
    fam = str(p["family"])

    # --- pass 1: the TRUE draw order and the unseen tail at the target ply ---
    random.seed(seed)
    g = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
    b = g.get_init_board()
    full = [b.state.next_tile] + list(b.state.deck)
    for a in actions[:ply]:
        b, _ = g.get_next_state(b, int(a))
    unseen = list(b.state.deck)
    n_drawn = len(full) - len(unseen)
    if [t.description for t in full[n_drawn:]] != [t.description for t in unseen]:
        raise RuntimeError("deck_tail_mismatch: replay tail != initial draw-order tail")
    true_repr = g.string_representation(b)

    # --- the world's deck completion (arm-, pick- AND family-independent) ----
    perm = list(unseen)
    if int(p["world"]) >= 0:
        world_rng(seed, ply, int(p["world"])).shuffle(perm)
    world_order = [t.description for t in perm]

    # --- pass 2: rebuild from ply 0 with the permuted tail installed ---------
    random.seed(seed)
    g2 = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
    b2 = g2.get_init_board()
    new_full = list(full[:n_drawn]) + perm
    if [t.description for t in new_full[:n_drawn]] != [t.description for t in full[:n_drawn]]:
        raise RuntimeError("world_prefix_mutated: the drawn prefix must be untouched")
    if sorted(t.description for t in new_full) != sorted(t.description for t in full):
        raise RuntimeError("world_not_a_permutation of the true draw order")
    b2.state.next_tile = new_full[0]
    b2.state.deck = list(new_full[1:])

    dose = family_dose(fam)
    champ = build_agent(g2, CONTINUATION_SEED, p["threads"], dose=dose,
                        mask=p["mask"], scope=p["scope"], k_dets=p["k_dets"],
                        sims=p["sims"], exact_k=p["exact_k"])
    arming = resolved_arming(champ)
    if dose != 0.0 and (abs(arming["dose"] - dose) > 1e-12
                        or arming["mask"] != int(p["mask"])
                        or arming["scope"] != str(p["scope"])):
        raise RuntimeError(f"the rust side resolved a different arming: {arming}")
    if dose == 0.0 and abs(arming["dose"]) > 1e-12:
        raise RuntimeError(f"the CHAMPION family resolved a nonzero dose: {arming}")
    if (arming["k_dets"] != int(p["k_dets"])
            or arming["sims_per_det"] != int(p["sims"])
            or arming["exact_max_k"] != int(p["exact_k"])):
        raise RuntimeError(f"budget pin not honoured by the rust side: {arming}")

    seat(champ, b2)
    t0 = time.time()
    for a in actions[:ply]:
        b2, _ = g2.get_next_state(b2, int(a))
        advance(champ, int(a))
    prefix_s = time.time() - t0
    if hasattr(champ, "check_sync"):
        champ.check_sync(b2, "continuation_root")
    root_repr = g2.string_representation(b2)
    if root_repr != true_repr:
        raise RuntimeError("root_state_diverged: permuting the UNSEEN tail changed "
                           "the position at the target ply")

    act = int(p["arm_action"])
    valid = g2.get_valid_moves(b2)
    if not bool(valid[act]):
        raise RuntimeError(f"arm action {act} illegal at the target ply")
    n_legal_root = int(valid.sum())

    # ⭐ The prefix is REPLAYED, never searched, so the census below counts the
    # CONTINUATION's expansions only. Asserted, not assumed.
    census_at_root = jr_census(champ)
    if census_at_root is not None and census_at_root["total"] != 0:
        raise RuntimeError(f"the prefix replay searched: census at root "
                           f"{census_at_root} (expected all-zero)")

    champ._move_idx = ply
    det_base = (int(champ.det_seed_base(ply))
                if hasattr(champ, "det_seed_base") else None)

    b2, _ = g2.get_next_state(b2, act)
    advance(champ, act)

    n_dec, t0 = 0, time.time()
    followup = None
    while g2.get_game_ended(b2, 0) == 0.0:
        a = int(champ.choose_action(b2))
        if n_dec == 0:
            followup = a
        b2, _ = g2.get_next_state(b2, a)
        advance(champ, a)
        n_dec += 1
    play_s = time.time() - t0
    s0, s1 = (int(x) for x in b2.state.scores)
    census = jr_census(champ)
    if hasattr(champ, "close"):
        champ.close()

    return {
        "status": "OK", "arm": p["arm"], "pick": p["pick"], "family": fam,
        "arm_action": act, "final_scores": [s0, s1],
        "margin_p0_minus_p1": s0 - s1,
        "n_continuation_decisions": n_dec,
        "n_plies_total": ply + 1 + n_dec,
        "first_followup_action": followup,
        "prefix_replay_s": round(prefix_s, 3),
        "continuation_s": round(play_s, 3),
        "arm_s": round(time.time() - t_arm, 3),
        "s_per_decision": round(play_s / max(1, n_dec), 4),
        "witness": {
            "root_repr_sha": sha(root_repr),
            "world_deck_sha": sha("|".join(world_order)),
            "world_deck_len": len(world_order),
            "n_drawn_prefix": n_drawn,
            "n_legal_root": n_legal_root,
            DET_SEED_KEY: det_base,
            "move_idx_at_root": ply,
        },
        "jr_expansions": census,
        "arming_resolved": arming,
        "family_witness": family_witness(census, fam, p["scope"]),
        "execution": dict(ex),
    }


def price_unit(arms: dict, mover: int, scope: str = ARM_SCOPE) -> dict:
    """Price ONE CRN world from its FOUR arm results.

    Sign convention, PARALLEL to E-1a/E-1b's: `margin_p0_minus_p1` is the
    REALIZED final `P0 - P1`; within a family,

        delta_pts_mover = (pick_armed - pick_champ)   for a seat-0 mover
                        = -(pick_armed - pick_champ)  for a seat-1 mover

    i.e. POSITIVE iff the ARMED agent's own pick was worth more points TO THE
    MOVER than the CHAMPION's pick, under that family's continuation. The unit's
    FAMILY DELTA is `delta[armed] - delta[champ]` — the quantity the clause is
    about, and the reason both families are priced on the identical world."""
    if any(a.get("status") != "OK" for a in arms.values()):
        return {"status": "VOID", "reason": "arm_not_ok",
                "detail": {k: v.get("status") for k, v in arms.items()}}
    ident = root_identity({k: v.get("witness") or {} for k, v in arms.items()})
    if not ident["ok"]:
        return {"status": "VOID", "reason": ident["reason"], "detail": ident}
    bad_w = [k for k, v in arms.items()
             if not (v.get("family_witness") or {}).get("ok")]
    if bad_w:
        return {"status": "VOID", "reason": "arm_witness_failed",
                "detail": {k: arms[k]["family_witness"] for k in bad_w}}
    sgn = 1 if int(mover) == 0 else -1
    delta = {}
    for fam in FAMILIES:
        m_a = arms[f"pick_armed__{fam}"]["margin_p0_minus_p1"]
        m_c = arms[f"pick_champ__{fam}"]["margin_p0_minus_p1"]
        delta[fam] = sgn * (m_a - m_c)
    return {"status": "OK",
            "margins": {k: v["margin_p0_minus_p1"] for k, v in arms.items()},
            "delta_pts_mover": delta,
            "family_delta": delta["armed"] - delta["champ"],
            "crn_witness": ident["witness"],
            "root_identity_ok": True,
            "family_witness": {k: v["family_witness"] for k, v in arms.items()}}


def unit_path(outdir: Path, seed: int, ply: int, world: int) -> Path:
    return Path(outdir) / f"unit_{seed}_p{ply:03d}_w{world}.json"


def _frozen_view(man: dict) -> dict:
    return {k: man.get(k) for k in
            ("schema", "world_seed", "continuation_seed", "m_worlds", "arming",
             "budget_pin", "targets_sha256", "leaf_hash_of_record")}


def cmd_price(a) -> int:
    tgts = {(int(r["deck_seed"]), int(r["ply"])): r
            for r in (json.loads(l) for l in Path(a.targets).read_text().splitlines() if l.strip())}
    games = {}
    for p in sorted(Path(a.games).glob("g_*.json")):
        gjs = json.loads(p.read_text())
        games[int(gjs["deck_seed"])] = gjs
    man = json.loads(Path(a.manifest).read_text())
    want = _frozen_view(man)
    here = {"schema": SCHEMA, "world_seed": WORLD_SEED,
            "continuation_seed": CONTINUATION_SEED, "m_worlds": M_WORLDS,
            "arming": {"dose": a.dose, "mask": a.mask, "scope": a.scope},
            "budget_pin": {"k_dets": a.k_dets, "sims_per_det": a.sims,
                           "total_sims": a.k_dets * a.sims,
                           "exact_max_k": a.exact_k},
            "targets_sha256": sha256_file(a.targets),
            "leaf_hash_of_record": LEAF_HASH_OF_RECORD}
    for k in ("schema", "world_seed", "continuation_seed", "m_worlds",
              "targets_sha256", "leaf_hash_of_record"):
        if want[k] != here[k]:
            raise SystemExit(f"FROZEN FIELD MISMATCH {k}: manifest={want[k]!r} "
                             f"process={here[k]!r} — refusing to price.")
    for k in ("dose", "mask", "scope"):
        if want["arming"].get(k) != here["arming"][k]:
            raise SystemExit(f"FROZEN arming.{k} mismatch: {want['arming']} vs {here['arming']}")
    for k in ("k_dets", "sims_per_det", "exact_max_k"):
        if want["budget_pin"].get(k) != here["budget_pin"][k]:
            raise SystemExit(f"FROZEN budget_pin.{k} mismatch: {want['budget_pin']} vs {here['budget_pin']}")

    units = []
    for line in Path(a.units).read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        s, p, w = (int(x) for x in line.split())
        units.append((s, p, w))
    units = [u for i, u in enumerate(units) if i % a.of == a.shard]

    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    n_done = 0
    for (s, ply, w) in units:
        up = unit_path(outdir, s, ply, w)
        if up.exists() and not a.force:
            n_done += 1
            continue
        t = tgts.get((s, ply))
        if t is None:
            raise SystemExit(f"unit ({s},{ply}) is not in the frozen target set")
        game = games.get(s)
        if game is None:
            raise SystemExit(f"game {s} absent from {a.games}")
        arms = {}
        for fam in FAMILIES:
            for pick in PICKS:
                arm = f"{pick}__{fam}"
                arms[arm] = run_isolated(
                    _run_arm,
                    {"deck_seed": s, "actions": game["actions"], "ply": ply,
                     "world": w, "profile": t["profile"], "arm": arm,
                     "pick": pick, "family": fam,
                     "arm_action": int(t[pick]),
                     "threads": a.threads, "dose": family_dose(fam),
                     "mask": a.mask, "scope": a.scope, "k_dets": a.k_dets,
                     "sims": a.sims, "exact_k": a.exact_k},
                    a.job_mem_cap_gb, a.arm_cap_secs)
        pair = price_unit(arms, int(t["mover"]), a.scope)
        atomic_write_json(up, {
            "schema": SCHEMA + "/unit", "deck_seed": s, "ply": ply, "world": w,
            "stratum": t["stratum"], "profile": t["profile"],
            "mover": t["mover"], "phase": t["phase"], "n_plies": t["n_plies"],
            "ply_frac": t["ply_frac"], "n_legal": t["n_legal"],
            "n_unseen_tiles": t["n_unseen_tiles"], "cell": t["cell"],
            "top2_gap_champ": t["top2_gap_champ"],
            "top2_gap_armed": t["top2_gap_armed"], "shape": t["shape"],
            "pick_champ": t["pick_champ"], "pick_armed": t["pick_armed"],
            "continuation_families": {
                f: {"dose": family_dose(f), "mask": a.mask, "scope": a.scope,
                    "k_dets": a.k_dets, "sims_per_det": a.sims,
                    "exact_max_k": a.exact_k, "seats": "both"} for f in FAMILIES},
            "arms": arms, "pair": pair,
        })
        n_done += 1
        print(f"[price] {s} p{ply} w{w} {t['stratum']} {pair.get('status')} "
              f"fd={pair.get('family_delta')}", flush=True)
    if a.done_sentinel:
        Path(a.done_sentinel).write_text(json.dumps(
            {"done": n_done, "shard": a.shard, "of": a.of,
             "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S")}))
    print(f"[price] shard {a.shard}/{a.of}: {n_done} units", flush=True)
    return 0


# --------------------------------------------------------------------------- #
# MANIFEST + the pre-flight negative control                                    #
# --------------------------------------------------------------------------- #
def negative_control(threads: int, k_dets=PINNED_K_DETS,
                     sims=PINNED_SIMS_PER_DET, exact_k=PINNED_EXACT_K) -> dict:
    """`G-NEGCTRL` — the census is DOSE-GATED, proven before any unit runs.

    Builds the dose-0 champion and the dose-d* agent on the SAME opening, plays
    four real decisions with each, and requires all-zero / `boosted > 0`. (The
    round then re-proves it on EVERY unit through the champion-family arms — see
    `champ_witness` — but the pre-flight keeps the launcher fail-closed.)"""
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai import rules_profile
    from carcassonne_ai.mirror_protocol import seat, advance

    prof = rules_profile.resolve(RULES_PROFILE)
    out = {}
    for name, dose in (("unarmed_dose0", 0.0), ("armed_dose_dstar", ARM_DOSE)):
        random.seed(12345)
        g = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
        b = g.get_init_board()
        ag = build_agent(g, CONTINUATION_SEED, threads, dose=dose,
                         k_dets=k_dets, sims=sims, exact_k=exact_k)
        seat(ag, b)
        for _ in range(4):
            if g.get_game_ended(b, 0) != 0.0:
                break
            act = int(ag.choose_action(b))
            b, _ = g.get_next_state(b, act)
            advance(ag, act)
        out[name] = {"dose": dose, "census": jr_census(ag),
                     "arming_resolved": resolved_arming(ag)}
        if hasattr(ag, "close"):
            ag.close()
    z = out["unarmed_dose0"]["census"] or {}
    d = out["armed_dose_dstar"]["census"] or {}
    out["ok"] = (all(int(z.get(k, -1)) == 0 for k in JR_KEYS)
                 and int(d.get("boosted", 0)) > 0)
    if not out["ok"]:
        raise RuntimeError(f"G-NEGCTRL FAILED pre-flight: dose0={z} dose_dstar={d}")
    return out


def _flat(obj, prefix=""):
    """(key, scalar) pairs from a nested manifest — used to find the leaf hash
    wherever the factory files it, rather than guessing one key name."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _flat(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield from _flat(v, f"{prefix}[{i}]")
    else:
        yield prefix, obj


def _git(*args) -> str:
    try:
        return subprocess.run(["git", "-C", str(REPO), *args],
                              capture_output=True, text=True,
                              timeout=20).stdout.strip()
    except Exception:                                       # noqa: BLE001
        return ""


def build_manifest(a, env, nc, leaf_manifest) -> dict:
    from carcassonne_ai import champion_factory as CF
    spec = CF.load_production_spec()
    return {
        "schema": SCHEMA,
        "what": ("SYNTHETIC mechanism-corroboration of CL-083's policy-conditional "
                 "pricing clause. Prices the CLAUSE, never the owner's edge."),
        "written_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "host": socket.gethostname(), "platform": platform.platform(),
        "world_seed": WORLD_SEED, "continuation_seed": CONTINUATION_SEED,
        "select_seed": SELECT_SEED, "match_seed": MATCH_SEED,
        "m_worlds": M_WORLDS,
        "arming": {"dose": a.dose, "mask": a.mask, "scope": a.scope,
                   "surface": "B (search knob; moves NO leaf hash)",
                   "provenance": "S1 G1 adjudicated d*=0.25; G3 mask 31; scope=opp"},
        "families": {f: {"dose": family_dose(f), "seats": "both"} for f in FAMILIES},
        "budget_pin": {"k_dets": a.k_dets, "sims_per_det": a.sims,
                       "total_sims": a.k_dets * a.sims, "exact_max_k": a.exact_k,
                       "why": ("E-1a/E-1b's 11008. PINNED, not read from "
                               "PRODUCTION.yaml, so this round corroborates the "
                               "SAME pricing instrument.")},
        "gen_budget": {"k_dets": a.gen_k_dets, "sims_per_det": a.gen_sims,
                       "total_sims": a.gen_k_dets * a.gen_sims,
                       "exact_max_k": a.gen_exact_k,
                       "why": "position source only; never a statistic"},
        "selector": {"ply_frac_window": [PLY_FRAC_MIN, PLY_FRAC_MAX],
                     "min_unseen_tiles": MIN_UNSEEN_TILES, "phase": SELECT_PHASE,
                     "max_per_game_per_stratum": MAX_PER_GAME_PER_STRATUM,
                     "n_target_per_stratum": N_TARGET_PER_STRATUM,
                     "n_identity": N_IDENTITY,
                     "shape": ("victims_of(mover) x opponent-exclusive part with "
                               "merge_plausible — s0v2_agent.py symbols")},
        "bar_clause": BAR_CLAUSE,
        "production_yaml_observed": {
            "champion_id": getattr(spec, "champion_id", None),
            "k_dets": getattr(spec, "k_dets", None),
            "sims_per_det": getattr(spec, "sims_per_det", None),
            "note": ("recorded, never used: the budget above is PINNED. A YAML "
                     "drift is a disclosure, not a config source."),
        },
        "leaf_hash_of_record": LEAF_HASH_OF_RECORD,
        "leaf_manifest": leaf_manifest,
        "tiearb": None,
        "tiearb_note": ("OFF on every seat and every family: E-1a/E-1b were "
                        "arbiter-free and `make_production_champion` does not "
                        "read fair_deploy.tiearb — recorded, not engineered."),
        "targets": str(a.targets) if a.targets else None,
        "targets_sha256": sha256_file(a.targets) if a.targets else None,
        "rules_profile": RULES_PROFILE, "r9_env": env,
        "negative_control": nc,
        "execution": {"backend": "rust", "rust_threads": a.threads,
                      "job_mem_cap_gb": a.job_mem_cap_gb,
                      "arm_cap_secs": a.arm_cap_secs},
        "code": {"rev": _git("rev-parse", "HEAD"),
                 "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
                 "dirty": bool(_git("status", "--porcelain"))},
        "python": sys.version.split()[0],
        "band": "TBD-AT-LAUNCH — see BAND_CLAIMED.placeholder",
    }


def cmd_emit_manifest(a) -> int:
    from analyzer.ev_loss import prepare_env
    env = prepare_env(RULES_PROFILE)
    from carcassonne_ai import champion_factory as CF
    from carcassonne_ai.game_wrapper import Game

    # ⭐ G-LEAF is INVERTED for this round, exactly as E-1b's is: surface B moves
    # NO leaf hash, so the runtime-verified hash must EQUAL the hash of record.
    # `verify=True` proves the leaf on real boards at construction and raises on
    # any mismatch, so this is a runtime proof, never a config echo.
    g = Game(enable_legal_moves_cache=True)
    ref = CF.make_production_champion("fair", game=g, seed=0, verify=True)
    lm = dict(getattr(ref, "manifest", None) or {})
    hashes = sorted({str(v) for k, v in _flat(lm) if "hash" in str(k).lower()})
    if LEAF_HASH_OF_RECORD not in hashes:
        raise SystemExit(f"G-LEAF precondition FAILED: {LEAF_HASH_OF_RECORD} not among "
                         f"the runtime-verified hashes {hashes}")
    if hasattr(ref, "close"):
        ref.close()
    nc = negative_control(a.threads, a.k_dets, a.sims, a.exact_k)
    atomic_write_json(Path(a.manifest), build_manifest(a, env, nc, lm))
    print(f"[manifest] {a.manifest} — G-NEGCTRL ok={nc['ok']}", flush=True)
    return 0


# --------------------------------------------------------------------------- #
def _common(sp):
    sp.add_argument("--threads", type=int, default=1)
    sp.add_argument("--job-mem-cap-gb", type=float, default=6.0)
    sp.add_argument("--arm-cap-secs", type=int, default=1800)
    sp.add_argument("--shard", type=int, default=0)
    sp.add_argument("--of", type=int, default=1)
    sp.add_argument("--force", action="store_true")


def _budget(sp):
    sp.add_argument("--dose", type=float, default=ARM_DOSE)
    sp.add_argument("--mask", type=int, default=ARM_MASK)
    sp.add_argument("--scope", default=ARM_SCOPE, choices=("opp", "own", "all"))
    sp.add_argument("--k-dets", type=int, default=PINNED_K_DETS)
    sp.add_argument("--sims", type=int, default=PINNED_SIMS_PER_DET)
    sp.add_argument("--exact-k", type=int, default=PINNED_EXACT_K)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gen")
    g.add_argument("--seed-start", type=int, required=True)
    g.add_argument("--n-games", type=int, required=True)
    g.add_argument("--outdir", required=True)
    g.add_argument("--profile", default=RULES_PROFILE)
    g.add_argument("--gen-k-dets", type=int, default=GEN_K_DETS)
    g.add_argument("--gen-sims", type=int, default=GEN_SIMS_PER_DET)
    g.add_argument("--gen-exact-k", type=int, default=GEN_EXACT_K)
    _common(g)
    g.set_defaults(fn=cmd_gen)

    s = sub.add_parser("select")
    s.add_argument("--games", required=True)
    s.add_argument("--outdir", required=True)
    _common(s)
    s.set_defaults(fn=cmd_select)

    f = sub.add_parser("freeze-targets")
    f.add_argument("--select", required=True)
    f.add_argument("--out", required=True)
    f.add_argument("--n-per-stratum", type=int, default=N_TARGET_PER_STRATUM)
    f.add_argument("--n-identity", type=int, default=N_IDENTITY)
    f.set_defaults(fn=cmd_freeze_targets)

    m = sub.add_parser("emit-manifest")
    m.add_argument("--manifest", required=True)
    m.add_argument("--targets", default=None)
    m.add_argument("--gen-k-dets", type=int, default=GEN_K_DETS)
    m.add_argument("--gen-sims", type=int, default=GEN_SIMS_PER_DET)
    m.add_argument("--gen-exact-k", type=int, default=GEN_EXACT_K)
    _budget(m)
    _common(m)
    m.set_defaults(fn=cmd_emit_manifest)

    p = sub.add_parser("price")
    p.add_argument("--targets", required=True)
    p.add_argument("--games", required=True)
    p.add_argument("--units", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--outdir", required=True)
    p.add_argument("--done-sentinel", default=None)
    _budget(p)
    _common(p)
    p.set_defaults(fn=cmd_price)

    a = ap.parse_args(argv)
    if a.cmd != "freeze-targets":
        from analyzer.ev_loss import prepare_env
        prepare_env(RULES_PROFILE)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
