#!/usr/bin/env python3
"""E4 CONTINUATION PRICING — the CRN-paired counterfactual continuation.

⚠️ **NO JUDGE ANYWHERE.** The price of a ply here is a REALIZED GAME OUTCOME:
the final score differential of a game actually played to termination. Nothing
in this instrument scores a position. The production champion appears only as a
POLICY that plays moves — never as an evaluator.

THE UNIT OF WORK is one `(game, ply, world)`. It runs TWO arms:

  * `arm_owner` — the archive's own move at that ply is applied;
  * `arm_cf`    — the production champion's counterfactual move (banked by the
                  2026-08-27 ply-pricing run) is applied instead.

and from each, the production champion plays BOTH SEATS to termination. The
price is `delta_pts_mover = (final margin | owner) - (final margin | cf)`,
mover-signed.

⚠️ At `defense` plies the "owner" arm's move is the ON-DEVICE CHAMPION's own
archived move (`actor == 1`), not the human's — the stratum prices what the
champion's pre-invasion move was worth against the production champion's
alternative. The arm keeps the name for symmetry; the sign convention is the
mover's either way.

**THE PAIRING IS THE VARIANCE KILLER (CRN).** Held IDENTICAL across the two arms
of a unit, by construction:

  1. the ROOT STATE — both arms replay the same archive action prefix, so the
     board, scores, meeples and `next_tile` at the target ply are the same
     object-for-object (witness: `root_repr_sha`, asserted equal across arms);
  2. the WORLD's DECK COMPLETION — the unseen tail is permuted by a generator
     seeded ONLY on `(WORLD_SEED, deck_seed, ply, world)`, which contains no arm
     term, so the two arms draw the same tiles in the same order (witness:
     `world_deck_sha`, asserted equal across arms);
  3. the POLICY's RANDOMNESS — one champion instance per arm, both built with
     `seed = CONTINUATION_SEED` and both seated at `_move_idx = ply` before the
     arm move, so continuation decision *j* uses the same determinization seeds
     in both arms (witness: `det_seed_base_at_root`, asserted equal).

What necessarily DIFFERS is the board after the arm move — that is the treatment.

Per-arm isolation reuses `price_plies.solve_isolated`'s pattern verbatim in
shape: every arm runs in its own forked child under `RLIMIT_AS` + `RLIMIT_CPU`
with a parent wall backstop. A capped arm is recorded `TIME_SKIPPED` /
`OOM_SKIPPED` and **voids its unit's pair** (a skip, never a price) — a
half-priced pair would break the pairing that the whole estimator rests on.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import os
import random
import resource
import signal
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

ARCHIVES = REPO / "measurement" / "e4_games"

# --- pre-registered constants (frozen; see PREREG.md) ----------------------- #
WORLD_SEED = 20260828
CONTINUATION_SEED = 0
M_WORLDS = 8
ARM_WALL_CAP_S = 600
CPU_HARD_GRACE_S = 30
WALL_GRACE_S = 60
ARMS = ("arm_owner", "arm_cf")


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def world_rng(deck_seed: int, ply: int, world: int) -> random.Random:
    """The world's deck-completion generator.

    ⚠️ NO ARM TERM. That absence IS the common-random-numbers guarantee: both
    arms of a unit derive the identical permutation of the identical unseen
    bag. Same shape as the 2026-08-27 run's clairvoyant world seeding, with its
    own frozen `WORLD_SEED`.
    """
    return random.Random(WORLD_SEED ^ (int(deck_seed) * 1000003)
                         ^ (int(ply) * 7919) ^ (int(world) * 104729))


# --------------------------------------------------------------------------- #
# one arm, inside its own capped child                                          #
# --------------------------------------------------------------------------- #
def _run_arm(p: dict) -> dict:
    from carcassonne_ai import rules_profile
    from carcassonne_ai.champion_factory import make_production_champion
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.mirror_protocol import advance, resolve_execution, seat

    t_arm = time.time()
    prof = rules_profile.resolve(p["profile"])
    ex = resolve_execution("inherit", profile="desktop", rust_threads=p["threads"])
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

    # --- the world's deck completion (arm-independent by construction) -------
    perm = list(unseen)
    if int(p["world"]) >= 0:
        world_rng(seed, ply, int(p["world"])).shuffle(perm)
    world_order = [t.description for t in perm]

    # --- pass 2: rebuild from ply 0 with the permuted tail installed ---------
    # The mirror can only be REPLAYED, never constructed from a board, so the
    # world is installed on the INITIAL board (whose drawn prefix is untouched)
    # and the prefix is replayed on top of it. `seat` reads `[next_tile] + deck`
    # straight out of that board, so python and rust get the same world with no
    # new Rust surface and no deck-swap call.
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

    champ = make_production_champion("fair", game=g2, seed=CONTINUATION_SEED,
                                     verify=True, **ex.factory_kwargs())
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
        # --- CRN witnesses: every one of these MUST match across the two arms
        "witness": {
            "root_repr_sha": sha(root_repr),
            "world_deck_sha": sha("|".join(world_order)),
            "world_deck_len": len(world_order),
            "n_drawn_prefix": n_drawn,
            "n_legal_root": n_legal_root,
            "det_seed_base_at_root": det_base,
            "move_idx_at_root": ply,
        },
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
CRN_WITNESS_KEYS = ("root_repr_sha", "world_deck_sha", "world_deck_len",
                    "n_drawn_prefix", "n_legal_root", "det_seed_base_at_root",
                    "move_idx_at_root")


def pair_price(owner: dict, cf: dict, actor: int) -> dict:
    """Price ONE CRN world from its two arm results.

    `margin_p0_minus_p1` is the REALIZED final score differential (P0 - P1) of a
    game played to termination. The price is mover-signed, exactly as the
    2026-08-27 ply-pricing run's `delta_pts_mover` is:

      * for a seat-0 mover, `owner - cf`;
      * for a seat-1 mover, its negation,

    so `delta_pts_mover > 0` means the PLAYED move was worth more points TO THE
    MOVER than the champion's counterfactual, at either seat.

    Returns a `VOID` pair (never a price) unless BOTH arms landed AND every CRN
    witness matches. A witness mismatch is a BUG SIGNAL, not a finding: it means
    the two arms did not actually share a root or a world, so their difference
    is not a paired contrast.
    """
    if owner.get("status") != "OK" or cf.get("status") != "OK":
        return {"status": "VOID", "reason": "arm_not_ok",
                "arm_status": [owner.get("status"), cf.get("status")]}
    wo, wc = owner.get("witness") or {}, cf.get("witness") or {}
    bad = [k for k in CRN_WITNESS_KEYS if wo.get(k) != wc.get(k)]
    if bad:
        return {"status": "VOID", "reason": "crn_witness_mismatch", "fields": bad,
                "owner_witness": wo, "cf_witness": wc}
    d = owner["margin_p0_minus_p1"] - cf["margin_p0_minus_p1"]
    return {"status": "OK",
            "margin_owner": owner["margin_p0_minus_p1"],
            "margin_cf": cf["margin_p0_minus_p1"],
            "delta_pts_mover": d if int(actor) == 0 else -d,
            "crn_witness": {k: wo.get(k) for k in CRN_WITNESS_KEYS}}


# --------------------------------------------------------------------------- #
# driver                                                                        #
# --------------------------------------------------------------------------- #
def unit_path(outdir: Path, game: str, ply: int, world: int) -> Path:
    return outdir / f"unit_{game.replace('.json', '')}_p{ply:03d}_w{world}.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", required=True)
    ap.add_argument("--units", required=True,
                    help="text file, one '<game> <ply> <world>' per line")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--log", default=None)
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--job-mem-cap-gb", type=float, default=4.0)
    ap.add_argument("--arm-cap-secs", type=int, default=ARM_WALL_CAP_S)
    ap.add_argument("--done-sentinel", default=None)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    targets = {}
    for line in Path(args.targets).open():
        r = json.loads(line)
        targets[(r["game"], int(r["ply"]))] = r

    units = []
    for line in Path(args.units).open():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        g, p, w = line.split()
        units.append((g, int(p), int(w)))

    profiles = {targets[(g, p)]["profile"] for g, p, _ in units}
    if len(profiles) != 1:
        raise SystemExit(f"R9 is import-latched: one process per profile group, "
                         f"got {sorted(profiles)}")
    profile = profiles.pop()

    from analyzer.ev_loss import prepare_env, resolve_profile_name
    env = prepare_env(profile)
    os.environ.setdefault("OMP_NUM_THREADS", "1")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    logf = open(args.log, "a", buffering=1) if args.log else None

    def log(msg):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        if logf:
            logf.write(line + "\n")

    log(f"START profile={profile} units={len(units)} env={env} "
        f"threads={args.threads} arm_cap={args.arm_cap_secs}s")

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
        # Rules epoch is resolved FROM THE ARCHIVE, never from a flag, and the
        # frozen target's stamp must agree with it.
        resolved = resolve_profile_name(arc)
        if resolved != t["profile"]:
            raise SystemExit(f"profile drift on {g}: archive says {resolved!r}, "
                             f"target says {t['profile']!r}")
        base = {"profile": resolved, "deck_seed": int(arc["deck_seed"]),
                "actions": [int(x) for x in arc["actions"]], "ply": ply,
                "world": world, "threads": args.threads}
        res = {}
        for arm, action in (("arm_owner", t["played_action"]),
                            ("arm_cf", t["counterfactual_action"])):
            res[arm] = run_arm_isolated(
                {**base, "arm": arm, "arm_action": int(action)},
                args.job_mem_cap_gb, args.arm_cap_secs)
        pair = pair_price(res["arm_owner"], res["arm_cf"], int(t["actor"]))
        row = {
            "game": g, "ply": ply, "world": world, "stratum": t["stratum"],
            "profile": resolved, "actor": int(t["actor"]), "phase": t["phase"],
            "k": t["k"], "n_plies_archive": t["n_plies"], "ply_frac": t["ply_frac"],
            "played_action": int(t["played_action"]),
            "counterfactual_action": int(t["counterfactual_action"]),
            # Budget epoch, carried per row FROM THE ARCHIVE (the E4 anchor is
            # nonstationary — tallies must be conditioned on it).
            "budget_note": ((arc.get("result") or {}).get("budget_note")
                            or arc.get("budget_note")),
            "played_sims_effective": arc.get("played_sims_effective"),
            "played_k_dets_effective": arc.get("played_k_dets_effective"),
            "r9_env": env,
            "arms": res,
            "pair": pair,
            # Descriptive only: did the champion's own first follow-up in the
            # owner arm match what the archive actually played next? An invasion
            # is a TILE placement whose meeple follow-up is a separate ply, and
            # this instrument forces ONLY the target ply (see PREREG §2.3).
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
        log(f"  {g} ply {ply:3d} w{world} {t['stratum']:12s} "
            f"pair={pair['status']} delta={pair.get('delta_pts_mover')} "
            f"owner={res['arm_owner'].get('margin_p0_minus_p1')} "
            f"cf={res['arm_cf'].get('margin_p0_minus_p1')} "
            f"dec={res['arm_owner'].get('n_continuation_decisions')}/"
            f"{res['arm_cf'].get('n_continuation_decisions')} "
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
