#!/usr/bin/env python3
"""E-1b — ARMED (S1 scope=opp) CONTINUATION PRICING of the 91 banked plies.

⚠️ **NO JUDGE ANYWHERE**, exactly as in the instrument this adapts
(`../e4_continuation_20260828/continue_plies.py`). The price of a ply is a
REALIZED GAME OUTCOME: the final score differential of a game played to
termination. Nothing here scores a position.

⭐ **THE SINGLE VARIABLE IS THE CONTINUATION POLICY FAMILY.** E-1a played the
UNMODIFIED production champion from both arms; E-1b plays the **S1-ARMED**
champion — `jrules_prior_{dose=0.25, mask=31, scope="opp"}`, the arming G1
adjudicated (`G1-EXPRESSES`, d* = 0.25) and G3 witnessed — from both arms, at
the SAME target plies, the SAME CRN worlds, the SAME arm actions, the SAME
estimator, and the SAME budget E-1a ran (k_dets 8 x sims 1376 = 11008).

⛔ THE BUDGET IS **PINNED**, NOT INHERITED. `governance/PRODUCTION.yaml`'s
`fair_deploy` moved to k16 x 1376 = 22016 on 2026-08-30, AFTER E-1a ran. A
YAML-default champion today would therefore differ from E-1a in THREE ways at
once (budget, arming, and the 2026-08-30 tie-arbiter fold) and its number could
not be contrasted with the banked -1.87. `PINNED_K_DETS` / `PINNED_SIMS_PER_DET`
below are E-1a's budget, re-asserted from the RESOLVED rust config on every arm
(`G-BUDGET`), and the drift from today's YAML is recorded in the manifest rather
than papered over.

WHICH SIDE CARRIES THE ARMED POLICY: **both seats.** The instrument's
continuation policy is ONE agent that plays both seats to termination, so the
family swap is symmetric by construction — which is what keeps the estimand
parallel to E-1a's (*"the value of the target ply's move under subsequent
<family> play by both seats"*). A one-sided arming would grade a MATCH between
two different agents, not a continuation family, and would confound the price
with the strength difference between the seats. See PREREG.md §2.2.

⭐⭐ **THE SCOPE WITNESS.** A resolved `jrules_prior_scope` in a manifest is a
CONFIG ECHO: it proves the knob was requested, never that it BOUND. This program
has banked knob-never-bound cells twice (the FPU knob; the phasegate smoke), and
S1's R7 review is what added the play-derived census. Every arm here therefore
reads `FairAgentRs.stats()`'s `jr_expansions_{total,own_mover,boosted}` AFTER
the continuation and stores it on the unit row; `scope_witness()` below is the
gate, and a failing arm VOIDS its unit's pair (a skip, never a price).
"""
from __future__ import annotations

import argparse
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
ARCHIVES = REPO / "measurement" / "e4_games"

SCHEMA = "e1b-armed-continuation/v1"

# --- constants INHERITED from E-1a, unchanged (the CRN must reproduce) ------ #
WORLD_SEED = 20260828          # ⛔ identical to E-1a or the worlds differ
CONTINUATION_SEED = 0
M_WORLDS = 8
ARM_WALL_CAP_S = 600
CPU_HARD_GRACE_S = 30
WALL_GRACE_S = 60
ARMS = ("arm_owner", "arm_cf")

# --- constants NEW to E-1b (frozen; see PREREG.md §1.2) --------------------- #
ARM_DOSE = 0.25                # G1's adjudicated d*
ARM_MASK = 31                  # joshua_bot.PRESETS["current"], S1 G3's mask
ARM_SCOPE = "opp"              # the S1 arming: opponent-mover nodes
PINNED_K_DETS = 8              # ⛔ E-1a's budget, NOT today's YAML (k16)
PINNED_SIMS_PER_DET = 1376
PINNED_EXACT_K = 2
LEAF_HASH_OF_RECORD = "a36d2e15a3b3d71d"

CRN_WITNESS_KEYS = ("root_repr_sha", "world_deck_sha", "world_deck_len",
                    "n_drawn_prefix", "n_legal_root", "det_seed_base_at_root",
                    "move_idx_at_root")
JR_KEYS = ("total", "own_mover", "boosted")


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def sha256_file(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def world_rng(deck_seed: int, ply: int, world: int) -> random.Random:
    """The world's deck-completion generator — BYTE-IDENTICAL to E-1a's.

    ⚠️ NO ARM TERM (the CRN guarantee) and NO POLICY TERM (the cross-family
    guarantee): the same `(deck_seed, ply, world)` yields the same permutation
    under either continuation family, which is what makes `G-ROOT` checkable and
    the family-paired secondary a paired statistic."""
    return random.Random(WORLD_SEED ^ (int(deck_seed) * 1000003)
                         ^ (int(ply) * 7919) ^ (int(world) * 104729))


# --------------------------------------------------------------------------- #
# THE SCOPE WITNESS — play-derived, never a config echo                         #
# --------------------------------------------------------------------------- #
def scope_denominator(census: dict, scope: str) -> int:
    """The expansions THIS scope is allowed to boost.

    `own` -> own-mover expansions; `opp` -> the complement; `all` -> everything.
    (S1 READ_RULE_G3 §6.1 check 6 / DESIGN §9.2(c).)"""
    total, own = int(census["total"]), int(census["own_mover"])
    if scope == "own":
        return own
    if scope == "opp":
        return total - own
    if scope == "all":
        return total
    raise ValueError(f"unknown scope {scope!r}")


def scope_witness(census, scope: str) -> dict:
    """`G-WITNESS` for ONE arm. HARD checks (any failure voids the arm's pair):

      1. the mapping carries all three INTEGER keys — an absent key is a STALE
         `carc_rs` wheel (pre-R7), never "the arm did not boost";
      2. `total > 0`             — the census ran at all;
      3. `0 <= own_mover <= total`;
      4. `boosted > 0`           — ⭐ the knob EXPRESSED IN PLAY;
      5. `boosted <= denominator(scope)` — the boost never reached a node
         OUTSIDE its scope.

    ⚠️ Check 5 is an INEQUALITY on purpose. A probe at production knobs
    (measurement note in PREREG §5.2) measured EXACT equality
    (`boosted == total - own_mover` under `opp`), but terminal and
    no-legal-child expansions can legitimately boost nothing, and a gate written
    to the reader's expectation rather than the emitter's real output is the
    PG-A1 defect that voids healthy cells. `coverage` is reported and is
    ADVISORY ONLY — it never voids."""
    fail = []
    if not isinstance(census, dict):
        return {"ok": False, "failures": ["census_absent_stale_wheel"],
                "coverage": None, "denominator": None}
    missing = [k for k in JR_KEYS if k not in census]
    if missing:
        return {"ok": False, "failures": [f"census_missing_keys:{missing}"],
                "coverage": None, "denominator": None}
    try:
        total = int(census["total"])
        own = int(census["own_mover"])
        boosted = int(census["boosted"])
    except (TypeError, ValueError):
        return {"ok": False, "failures": ["census_not_integers"],
                "coverage": None, "denominator": None}
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


def root_identity(witness: dict, baseline: dict | None) -> dict:
    """`G-ROOT` for ONE unit: every CRN witness field must equal the E-1a
    sibling's. Those seven fields describe the ROOT and the WORLD and carry no
    continuation-policy term, so a mismatch means E-1b is not pricing the same
    thing E-1a priced — a BUG SIGNAL, not attrition."""
    if baseline is None:
        return {"ok": False, "reason": "baseline_absent", "fields": None}
    bad = [k for k in CRN_WITNESS_KEYS if witness.get(k) != baseline.get(k)]
    return {"ok": not bad, "fields": bad,
            "reason": None if not bad else "root_identity_mismatch"}


# --------------------------------------------------------------------------- #
# the armed champion                                                            #
# --------------------------------------------------------------------------- #
def armed_prior_cfg(dose=ARM_DOSE, mask=ARM_MASK, scope=ARM_SCOPE):
    """The production champion's `HeuristicPriorConfig` with the S1 arming.

    ⛔ Built by REPLACING three SEARCH fields on `champion_factory
    .production_prior_cfg()` — the champion's own leaf, curve, caps, c_puct,
    tau_p, value_norm and final_select are untouched, and NO leaf hash moves
    (surface B is a search knob, which is exactly why the play-derived census
    exists). `dose=0.0` returns the champion byte-for-byte, which is what the
    negative control uses."""
    import dataclasses as dc

    from carcassonne_ai import champion_factory as CF

    base = CF.production_prior_cfg()
    if float(dose) == 0.0:
        return base
    return dc.replace(base, jrules_prior_dose=float(dose),
                      jrules_prior_mask=int(mask),
                      jrules_prior_scope=str(scope))


def build_armed_champion(game, seed, threads, *, dose=ARM_DOSE, mask=ARM_MASK,
                         scope=ARM_SCOPE, k_dets=PINNED_K_DETS,
                         sims=PINNED_SIMS_PER_DET, exact_k=PINNED_EXACT_K):
    """The E-1b continuation policy. RUST-ONLY and FAIR-ONLY.

    ⚠️ `jrules_prior_*` is rust-only: a nonzero dose on the python search path
    hard-exits (`heuristic_prior_mcts`) and a pre-S1 `carc_rs` rejects `scope`
    at config construction. Both are fail-closed, which is the good direction —
    a silently unarmed 'armed' agent would play champion-vs-champion and grade a
    perfect null wearing this round's name."""
    from carcassonne_ai import champion_factory as CF

    return CF.build_fair_champion(
        game, cfg=armed_prior_cfg(dose, mask, scope),
        sims=int(sims), k_dets=int(k_dets), seed=int(seed),
        exact_endgame=True, exact_max_k=int(exact_k),
        backend="rust", rust_threads=int(threads or 1))


def jr_census(agent) -> dict | None:
    """The play-derived expansion census off `FairAgentRs.stats()`.

    Returns None when the counters are ABSENT — a stale (pre-R7) wheel. None is
    NOT zeros: `scope_witness` treats it as a hard failure, because "the arm did
    not boost" and "nobody looked" must never wear the same shape."""
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


# --------------------------------------------------------------------------- #
# one arm, inside its own capped child                                          #
# --------------------------------------------------------------------------- #
def _run_arm(p: dict) -> dict:
    from carcassonne_ai import rules_profile
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.mirror_protocol import advance, resolve_execution, seat

    t_arm = time.time()
    prof = rules_profile.resolve(p["profile"])
    ex = resolve_execution("rust", profile="desktop", rust_threads=p["threads"])
    if ex["backend"] != "rust":
        raise RuntimeError(f"E-1b is rust-only (surface B is): got {dict(ex)}")
    seed, actions, ply = int(p["deck_seed"]), p["actions"], int(p["ply"])

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

    # --- the world's deck completion (arm- AND family-independent) -----------
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

    champ = build_armed_champion(g2, CONTINUATION_SEED, p["threads"],
                                 dose=p["dose"], mask=p["mask"], scope=p["scope"],
                                 k_dets=p["k_dets"], sims=p["sims"],
                                 exact_k=p["exact_k"])
    arming = resolved_arming(champ)
    if p["dose"] != 0.0 and (abs(arming["dose"] - float(p["dose"])) > 1e-12
                             or arming["mask"] != int(p["mask"])
                             or arming["scope"] != str(p["scope"])):
        raise RuntimeError(f"the rust side resolved a different arming: {arming}")
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
    st = champ.stats() if hasattr(champ, "stats") else {}
    if hasattr(champ, "close"):
        champ.close()

    return {
        "status": "OK",
        "arm": p["arm"], "arm_action": act,
        "final_scores": [s0, s1],
        "margin_p0_minus_p1": s0 - s1,
        "n_continuation_decisions": n_dec,
        "n_plies_total": ply + 1 + n_dec,
        "first_followup_action": followup,
        "prefix_replay_s": round(prefix_s, 3),
        "continuation_s": round(play_s, 3),
        "arm_s": round(time.time() - t_arm, 3),
        "s_per_decision": round(play_s / max(1, n_dec), 4),
        # --- CRN witnesses: every one MUST match across the two arms AND the
        #     E-1a baseline (G-ROOT).
        "witness": {
            "root_repr_sha": sha(root_repr),
            "world_deck_sha": sha("|".join(world_order)),
            "world_deck_len": len(world_order),
            "n_drawn_prefix": n_drawn,
            "n_legal_root": n_legal_root,
            "det_seed_base_at_root": det_base,
            "move_idx_at_root": ply,
        },
        # ⭐⭐ the play-derived scope witness + the RESOLVED knobs beside it
        "jr_expansions": census,
        "arming_resolved": arming,
        "scope_witness": scope_witness(census, p["scope"]),
        "execution": dict(ex),
        "final_move_idx": int(getattr(champ, "move_idx", -1)) if st else None,
    }


def _arm_child(payload, mem_bytes, cpu_cap_s, conn):
    try:
        if mem_bytes > 0:
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        if cpu_cap_s > 0:
            # SIGXCPU left at its DEFAULT disposition on purpose: a Python-level
            # handler only runs at a bytecode boundary and would be ignored for
            # the whole duration of a long RUST decision.
            resource.setrlimit(resource.RLIMIT_CPU,
                               (cpu_cap_s, cpu_cap_s + CPU_HARD_GRACE_S))
        conn.send(("OK", _run_arm(payload)))
    except MemoryError:
        conn.send(("OOM", None))
    except BaseException as e:                              # noqa: BLE001
        conn.send(("EXC", f"{type(e).__name__}: {e}"))
    finally:
        conn.close()


def run_arm_isolated(payload, mem_cap_gb: float, cpu_cap_s: int) -> dict:
    mem_bytes = int(mem_cap_gb * (1 << 30)) if mem_cap_gb > 0 else 0
    if mem_bytes <= 0 and cpu_cap_s <= 0:
        return _run_arm(payload)
    ctx = mp.get_context("fork")
    parent, child = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_arm_child,
                       args=(payload, mem_bytes, int(cpu_cap_s), child))
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
    if status == "OOM" or status == "EOF" or (proc.exitcode or 0) < 0:
        return {"status": "OOM_SKIPPED", "exitcode": proc.exitcode,
                "elapsed_s": elapsed}
    return {"status": "ERROR", "detail": out, "elapsed_s": elapsed}


# --------------------------------------------------------------------------- #
# the pairing arithmetic (isolated so it can be unit-tested on fixtures)        #
# --------------------------------------------------------------------------- #
def pair_price(owner: dict, cf: dict, actor: int, scope: str = ARM_SCOPE,
               baseline: dict | None = None) -> dict:
    """Price ONE CRN world from its two arm results.

    Sign convention, IDENTICAL to E-1a's: `margin_p0_minus_p1` is the REALIZED
    final `P0 - P1`; `delta_pts_mover` is `owner - cf` for a seat-0 mover and
    its negation for a seat-1 mover, so a positive value means the PLAYED move
    was worth more points TO THE MOVER than the champion's counterfactual.

    Returns a `VOID` pair (never a price) unless ALL of:
      * both arms landed;
      * every CRN witness matches ACROSS THE ARMS  (`crn_witness_mismatch`);
      * every CRN witness matches the E-1a BASELINE (`root_identity_mismatch`)
        — the single-variable proof;
      * both arms' scope witnesses pass          (`arm_witness_failed`).

    Each of those is a BUG SIGNAL, not a finding: they mean the two arms did not
    share a root/world, or E-1b is not on E-1a's roots, or the arming did not
    bind in play."""
    if owner.get("status") != "OK" or cf.get("status") != "OK":
        return {"status": "VOID", "reason": "arm_not_ok",
                "arm_status": [owner.get("status"), cf.get("status")]}
    wo, wc = owner.get("witness") or {}, cf.get("witness") or {}
    bad = [k for k in CRN_WITNESS_KEYS if wo.get(k) != wc.get(k)]
    if bad:
        return {"status": "VOID", "reason": "crn_witness_mismatch", "fields": bad,
                "owner_witness": wo, "cf_witness": wc}
    ident = root_identity(wo, baseline)
    if not ident["ok"]:
        return {"status": "VOID", "reason": ident["reason"],
                "fields": ident["fields"], "witness": wo, "baseline": baseline}
    sw = {"arm_owner": scope_witness(owner.get("jr_expansions"), scope),
          "arm_cf": scope_witness(cf.get("jr_expansions"), scope)}
    if not (sw["arm_owner"]["ok"] and sw["arm_cf"]["ok"]):
        return {"status": "VOID", "reason": "arm_witness_failed",
                "scope_witness": sw}
    d = owner["margin_p0_minus_p1"] - cf["margin_p0_minus_p1"]
    return {"status": "OK",
            "margin_owner": owner["margin_p0_minus_p1"],
            "margin_cf": cf["margin_p0_minus_p1"],
            "delta_pts_mover": d if int(actor) == 0 else -d,
            "crn_witness": {k: wo.get(k) for k in CRN_WITNESS_KEYS},
            "root_identity_ok": True,
            "scope_witness": sw}


# --------------------------------------------------------------------------- #
# the manifest (self-describing, house rule)                                    #
# --------------------------------------------------------------------------- #
FROZEN_FIELDS = ("schema", "world_seed", "continuation_seed", "m_worlds",
                 "arming", "budget_pin", "targets_sha256",
                 "crn_baseline_sha256", "leaf_hash_of_record")


def _git(*args) -> str:
    try:
        return subprocess.run(("git", "-C", str(REPO)) + args, text=True,
                              capture_output=True, timeout=20).stdout.strip()
    except Exception:                                       # noqa: BLE001
        return ""


def build_manifest(args, env, negative_control: dict | None,
                   leaf_manifest: dict | None) -> dict:
    from carcassonne_ai import champion_factory as CF

    spec = CF.load_production_spec()
    return {
        "schema": SCHEMA,
        "what": "E-1b — the 91 banked E-1a plies re-priced under the S1-armed "
                "(scope=opp, d*=0.25) continuation, both seats. Judge-free: "
                "every price is a difference of REALIZED final scores.",
        "written_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "host": socket.gethostname(), "platform": platform.platform(),
        "world_seed": WORLD_SEED,
        "continuation_seed": CONTINUATION_SEED,
        "m_worlds": M_WORLDS,
        "arming": {"dose": ARM_DOSE, "mask": ARM_MASK, "scope": ARM_SCOPE,
                   "surface": "jrules_prior (surface B), rust-only",
                   "provenance": "S1 G1 verdict G1-EXPRESSES d*=0.25; "
                                 "S1 G3 arms at dose 0.25 mask 31 with "
                                 "G-WITNESS passing"},
        "budget_pin": {"k_dets": PINNED_K_DETS,
                       "sims_per_det": PINNED_SIMS_PER_DET,
                       "total_sims": PINNED_K_DETS * PINNED_SIMS_PER_DET,
                       "exact_max_k": PINNED_EXACT_K,
                       "why": "E-1a's realized budget. PINNED, not inherited."},
        "production_yaml_observed": {
            "champion_id": spec.champion_id,
            "k_dets": spec.k_dets, "sims_per_det": spec.sims_per_det,
            "total_sims": spec.k_dets * spec.sims_per_det,
            "backend": spec.backend, "leaf_hash": spec.yaml_leaf_hash,
            "drift_vs_pin": (spec.k_dets != PINNED_K_DETS
                             or spec.sims_per_det != PINNED_SIMS_PER_DET),
            "note": "PRODUCTION.yaml's fair_deploy moved to k16x1376=22016 on "
                    "2026-08-30, AFTER E-1a. E-1b pins E-1a's budget so the "
                    "continuation FAMILY is the only variable; the drift is "
                    "recorded here, not silently inherited.",
        },
        "leaf_hash_of_record": LEAF_HASH_OF_RECORD,
        "leaf_manifest": leaf_manifest,
        "tiearb": None,
        "tiearb_note": "OFF, both seats — E-1a ran before the 2026-08-30 desktop "
                       "arbiter fold, and make_production_champion does not read "
                       "fair_deploy.tiearb, so an unmodified rebuild is arbiter-"
                       "free. Holding it OFF keeps the family the only variable.",
        "targets": str(Path(args.targets).resolve()),
        "targets_sha256": sha256_file(args.targets),
        "crn_baseline": str(Path(args.baseline).resolve()) if args.baseline else None,
        "crn_baseline_sha256": (sha256_file(args.baseline) if args.baseline
                                else None),
        "negative_control": negative_control,
        "r9_env": env,
        "execution": {"backend": "rust", "rust_threads": int(args.threads),
                      "job_mem_cap_gb": float(args.job_mem_cap_gb),
                      "arm_cap_secs": int(args.arm_cap_secs),
                      "arm_wall_cap_s_frozen": ARM_WALL_CAP_S},
        "code": {"rev": _git("rev-parse", "HEAD"),
                 "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
                 "dirty": bool(_git("status", "--porcelain", "--",
                                    "src", "engine", "scripts", "rust"))},
        "python": sys.version.split()[0],
        "band": "TBD-AT-LAUNCH — see BAND_CLAIMED.placeholder",
    }


def negative_control(threads: int) -> dict:
    """⭐ Prove the census is DOSE-GATED before trusting any nonzero census.

    Builds the UNARMED (dose 0) champion at the pinned budget, plays four real
    decisions and asserts its census is all-zero. Without this, a nonzero
    `boosted` in the armed cells could in principle be champion traffic the
    wheel counts unconditionally, and the witness would prove nothing. The
    armed half of the control (`boosted > 0` at dose 0.25 on the same board) is
    run beside it so a single artifact carries both directions."""
    from carcassonne_ai.game_wrapper import Game

    out = {}
    for name, dose in (("unarmed_dose0", 0.0), ("armed_dose_dstar", ARM_DOSE)):
        g = Game(enable_legal_moves_cache=True)
        a = build_armed_champion(g, CONTINUATION_SEED, threads, dose=dose)
        b = g.get_init_board()
        a.start_game(b)
        t0 = time.time()
        for _ in range(4):
            act = int(a.choose_action(b))
            b, _ = g.get_next_state(b, act)
            a.advance(act)
        out[name] = {"census": jr_census(a), "arming": resolved_arming(a),
                     "decisions": 4, "s": round(time.time() - t0, 3)}
        if hasattr(a, "close"):
            a.close()
    z = out["unarmed_dose0"]["census"]
    p = out["armed_dose_dstar"]["census"]
    out["ok"] = bool(z is not None and p is not None
                     and all(int(z[k]) == 0 for k in JR_KEYS)
                     and int(p["boosted"]) > 0)
    out["reads"] = ("dose 0 -> all-zero census AND dose d* -> boosted>0 on the "
                    "same opening: the counters are dose-gated and live")
    if not out["ok"]:
        raise RuntimeError(f"NEGATIVE CONTROL FAILED — the census is not "
                           f"dose-gated or the arming is inert: {out}")
    return out


# --------------------------------------------------------------------------- #
# driver                                                                        #
# --------------------------------------------------------------------------- #
def unit_path(outdir: Path, game: str, ply: int, world: int) -> Path:
    return outdir / f"unit_{game.replace('.json', '')}_p{ply:03d}_w{world}.json"


def _frozen_view(m: dict) -> dict:
    return {k: m.get(k) for k in FROZEN_FIELDS}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", required=True)
    ap.add_argument("--baseline", default=str(DIR / "CRN_BASELINE.json"))
    ap.add_argument("--units", default=None,
                    help="text file, one '<game> <ply> <world>' per line")
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--manifest", default=None,
                    help="path to the run manifest; written by --emit-manifest, "
                         "asserted identical by every runner process")
    ap.add_argument("--emit-manifest", action="store_true",
                    help="write the manifest + run the negative control, then exit")
    ap.add_argument("--log", default=None)
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--job-mem-cap-gb", type=float, default=6.0)
    ap.add_argument("--arm-cap-secs", type=int, default=1800)
    ap.add_argument("--done-sentinel", default=None)
    ap.add_argument("--force", action="store_true")
    # The arming is FROZEN; these exist so the selftests and a licensed
    # follow-on arm can address them, and every value lands in the manifest.
    ap.add_argument("--dose", type=float, default=ARM_DOSE)
    ap.add_argument("--mask", type=int, default=ARM_MASK)
    ap.add_argument("--scope", default=ARM_SCOPE, choices=("opp", "own", "all"))
    ap.add_argument("--k-dets", type=int, default=PINNED_K_DETS)
    ap.add_argument("--sims", type=int, default=PINNED_SIMS_PER_DET)
    ap.add_argument("--exact-k", type=int, default=PINNED_EXACT_K)
    args = ap.parse_args()

    targets = {}
    for line in Path(args.targets).open():
        r = json.loads(line)
        targets[(r["game"], int(r["ply"]))] = r

    if args.emit_manifest:
        if not args.manifest:
            raise SystemExit("--emit-manifest needs --manifest PATH")
        from analyzer.ev_loss import prepare_env
        env = prepare_env("fixed_v1")
        os.environ.setdefault("OMP_NUM_THREADS", "1")
        from carcassonne_ai import champion_factory as CF
        from carcassonne_ai.game_wrapper import Game
        ref = CF.make_production_champion(
            "fair", game=Game(enable_legal_moves_cache=True),
            seed=CONTINUATION_SEED, sims=args.sims, k_dets=args.k_dets,
            verify=True, backend="rust", rust_threads=args.threads)
        leaf_manifest = {k: ref.manifest.get(k) for k in
                         ("leaf", "leaf_hashes", "leaf_value_panel",
                          "leaf_value_panel_rust", "champion_id", "backend",
                          "runtime_budget_override", "code_commit", "search")}
        if hasattr(ref, "close"):
            ref.close()
        hashes = (leaf_manifest.get("leaf_hashes") or {})
        if LEAF_HASH_OF_RECORD not in set(map(str, hashes.values())):
            raise SystemExit(f"G-LEAF: {LEAF_HASH_OF_RECORD} not among the "
                             f"verified leaf hashes {hashes}")
        m = build_manifest(args, env, negative_control(args.threads), leaf_manifest)
        m["arming"].update(dose=float(args.dose), mask=int(args.mask),
                           scope=str(args.scope))
        m["budget_pin"].update(k_dets=int(args.k_dets),
                               sims_per_det=int(args.sims),
                               total_sims=int(args.k_dets) * int(args.sims),
                               exact_max_k=int(args.exact_k))
        p = Path(args.manifest)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(m, indent=1))
        tmp.rename(p)
        print(json.dumps({k: m[k] for k in FROZEN_FIELDS}, indent=1))
        print(f"MANIFEST {p}")
        return

    if not args.units or not args.outdir:
        raise SystemExit("--units and --outdir are required (or --emit-manifest)")

    units = []
    for line in Path(args.units).open():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        g, p_, w = line.split()
        units.append((g, int(p_), int(w)))

    profiles = {targets[(g, p_)]["profile"] for g, p_, _ in units}
    if len(profiles) != 1:
        raise SystemExit(f"R9 is import-latched: one process per profile group, "
                         f"got {sorted(profiles)}")
    profile = profiles.pop()

    from analyzer.ev_loss import prepare_env, resolve_profile_name
    env = prepare_env(profile)
    os.environ.setdefault("OMP_NUM_THREADS", "1")

    baseline = None
    if args.baseline:
        baseline = json.loads(Path(args.baseline).read_text())["units"]

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    logf = open(args.log, "a", buffering=1) if args.log else None

    def log(msg):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        if logf:
            logf.write(line + "\n")

    # ⛔ Cross-process manifest agreement: every chunk asserts the SAME frozen
    # config. Without it a mis-typed launcher could run half the cell at a
    # different dose and the two halves would look like one round.
    man_frozen = None
    if args.manifest:
        m = json.loads(Path(args.manifest).read_text())
        man_frozen = _frozen_view(m)
        mine = _frozen_view(build_manifest(args, env, None, None))
        mine["arming"] = {**mine["arming"], "dose": float(args.dose),
                          "mask": int(args.mask), "scope": str(args.scope)}
        mine["budget_pin"] = {**mine["budget_pin"], "k_dets": int(args.k_dets),
                              "sims_per_det": int(args.sims),
                              "total_sims": int(args.k_dets) * int(args.sims),
                              "exact_max_k": int(args.exact_k)}
        for k in FROZEN_FIELDS:
            if json.dumps(mine[k], sort_keys=True) != json.dumps(man_frozen[k],
                                                                sort_keys=True):
                raise SystemExit(f"manifest disagreement on {k!r}: this process "
                                 f"{mine[k]!r} vs manifest {man_frozen[k]!r}")

    log(f"START profile={profile} units={len(units)} env={env} "
        f"threads={args.threads} arm_cap={args.arm_cap_secs}s "
        f"arming=dose{args.dose}/mask{args.mask}/{args.scope} "
        f"budget=k{args.k_dets}x{args.sims} baseline={'yes' if baseline else 'NO'}")

    arc_cache: dict[str, dict] = {}
    t_start, n_done, n_skipped = time.time(), 0, 0
    for g, ply, world in units:
        out_p = unit_path(outdir, g, ply, world)
        if out_p.exists() and not args.force:
            n_skipped += 1
            continue
        t = targets[(g, ply)]
        if g not in arc_cache:
            arc_cache[g] = json.loads((ARCHIVES / g).read_text())
        arc = arc_cache[g]
        resolved = resolve_profile_name(arc)
        if resolved != t["profile"]:
            raise SystemExit(f"profile drift on {g}: archive says {resolved!r}, "
                             f"target says {t['profile']!r}")
        base = {"profile": resolved, "deck_seed": int(arc["deck_seed"]),
                "actions": [int(x) for x in arc["actions"]], "ply": ply,
                "world": world, "threads": args.threads,
                "dose": float(args.dose), "mask": int(args.mask),
                "scope": str(args.scope), "k_dets": int(args.k_dets),
                "sims": int(args.sims), "exact_k": int(args.exact_k)}
        res = {}
        for arm, action in (("arm_owner", t["played_action"]),
                            ("arm_cf", t["counterfactual_action"])):
            res[arm] = run_arm_isolated(
                {**base, "arm": arm, "arm_action": int(action)},
                args.job_mem_cap_gb, args.arm_cap_secs)
        bl = (baseline or {}).get(f"{g}|{ply}|{world}")
        pair = pair_price(res["arm_owner"], res["arm_cf"], int(t["actor"]),
                          scope=str(args.scope),
                          baseline=(bl or {}).get("witness") if bl else None)
        row = {
            "game": g, "ply": ply, "world": world, "stratum": t["stratum"],
            "profile": resolved, "actor": int(t["actor"]), "phase": t["phase"],
            "k": t["k"], "n_plies_archive": t["n_plies"], "ply_frac": t["ply_frac"],
            "played_action": int(t["played_action"]),
            "counterfactual_action": int(t["counterfactual_action"]),
            "budget_note": ((arc.get("result") or {}).get("budget_note")
                            or arc.get("budget_note")),
            "played_sims_effective": arc.get("played_sims_effective"),
            "played_k_dets_effective": arc.get("played_k_dets_effective"),
            "r9_env": env,
            "continuation_family": {"name": "s1_armed",
                                    "dose": float(args.dose),
                                    "mask": int(args.mask),
                                    "scope": str(args.scope),
                                    "k_dets": int(args.k_dets),
                                    "sims_per_det": int(args.sims),
                                    "exact_max_k": int(args.exact_k),
                                    "seats": "both"},
            "arms": res,
            "pair": pair,
            # The E-1a comparator for this exact (game, ply, world), carried so
            # the family-paired secondary needs no join at read time.
            "baseline_e1a": ({"delta_pts_mover": bl["delta_pts_mover"],
                              "margin_owner": bl["margin_owner"],
                              "margin_cf": bl["margin_cf"]} if bl else None),
            "followup_agrees_with_archive": (
                None if res["arm_owner"].get("status") != "OK"
                else (res["arm_owner"].get("first_followup_action")
                      == (int(arc["actions"][ply + 1])
                          if ply + 1 < len(arc["actions"]) else None))),
        }
        tmp = out_p.with_suffix(".tmp")
        tmp.write_text(json.dumps(row))
        tmp.rename(out_p)
        n_done += 1
        _sw = ((res["arm_owner"].get("scope_witness") or {}).get("coverage"))
        log(f"  {g} ply {ply:3d} w{world} {t['stratum']:12s} "
            f"pair={pair['status']} delta={pair.get('delta_pts_mover')} "
            f"(e1a {(bl or {}).get('delta_pts_mover')}) "
            f"owner={res['arm_owner'].get('margin_p0_minus_p1')} "
            f"cf={res['arm_cf'].get('margin_p0_minus_p1')} "
            f"cov={None if _sw is None else round(_sw, 3)} "
            f"s={res['arm_owner'].get('arm_s')}/{res['arm_cf'].get('arm_s')}")

    dt = time.time() - t_start
    log(f"DONE units={n_done} (resumed-skipped {n_skipped}) in {dt:.1f}s "
        f"(mean {dt / max(1, n_done):.1f}s/unit)")
    if args.done_sentinel:
        Path(args.done_sentinel).write_text(json.dumps(
            {"profile": profile, "n_units": n_done, "n_pre_existing": n_skipped,
             "elapsed_s": dt, "finished_at": time.time(),
             "outdir": str(outdir)}, indent=1))


if __name__ == "__main__":
    main()
