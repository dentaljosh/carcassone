"""4.2 — Logged human-vs-agent play harness (production FAIR agent).

A minimal, fully-logged interface for a human (or another agent) to play the
DEPLOYABLE fair-play champion — the audited-honest, non-clairvoyant PIMC + K<=2
marginalized-exact-endgame agent (Phase 0.1/0.4 are green, so the fair agent is
audited honest: it never peeks at the real deck).

⚠️ REWIRED 2026-07-19 (F1): the champion is now built by
``carcassonne_ai.champion_factory.make_production_champion("fair")`` — the CURRENT
champion, ``FairHeuristicPriorAgent`` (PUCT heuristic priors + curve125 leaf,
c_puct=1.5/tau_p=5/float/visits) at whatever budget PRODUCTION.yaml names — since the
2026-07-29 promotion that is k8x1376 = 11008 sims/move, resolved automatically below.
✅ FOLLOW-UP LANDED 2026-07-29: this harness now DOES read the deploy execution profile
``fair_deploy.deploy_profiles.desktop.parallel_workers`` (=8) via
``champion_factory.deploy_profile()``, so human-facing play runs the k-parallel split at
~2.2 s/move instead of the sequential k-loop's ~13.8 s/move. **Same player either way** —
the split is behavior-identical by construction (the k determinization worlds are
independent until the pooled-Q argmax; tests/test_kparallel.py asserts identical action
AND identical pooled root (N, W) at every move of full games), so this is a LATENCY change
and NOT a strength change; no re-eval is owed. Resolution is FAIL-SAFE: an unreadable /
absent / ``parallel_workers: null`` profile falls back to the sequential path, and
``--no-parallel`` forces it. The resolved worker count is recorded in the game log's
``config.parallel_workers`` (and, when non-None, in the factory's own agent manifest).
It previously wired the PRE-FLIP
``FairHeuristicMCTSAgent`` (random-expansion UCT + the old curve100 leaf), which the
2026-07-07 champion flip and the 2026-07-13 curve125 adopt never propagated here — so
this harness did NOT run the current champion (PRODUCTION.yaml stale_path_flag). The
factory PROVES the leaf on real boards at construction and records a runtime manifest
into every game log. E4 (the human exam) itself stays PARKED (Joshua).

✅ F-3 LANDED 2026-08-02: this harness now speaks the RUST MIRROR PROTOCOL. ``--backend
rust|auto`` builds the champion on ``carc_rs`` (~9.8x faster per move at the champion
budget — the felt difference is ~13.8 s/move sequential vs ~1.3 s/move), and ``play_game``
seats that agent's mirror on the dealt deck and ``advance()``s it for every applied
action of BOTH seats. The wiring is DUCK-TYPED and unconditional, so it is already
correct if ``champion_factory``'s default ever flips off ``python``; the flag DEFAULT is
still ``python``, i.e. a bare invocation is byte-identical to before. The engine is
provenance, never strength: it is gated behaviour-identical (G4 bit-exact, G6 100%
action agreement), and this harness's own gate is
``measurement/rustport_p6/F3_CALLER_GATES_20260802.json``. ⚠️ ``backend=rust`` and
``parallel_workers`` are mutually exclusive — Rust folds the same k worlds across
``--rust-threads`` OS threads instead of spawn processes — and ``resolve_execution()``
resolves the pair so a caller can never hand the factory the illegal combination.

🔌 TIE-ARBITER PLUMBING (2026-08-19, measurement/tiearb2_stage2_20260817): the
``--tiearb-*`` flags can arm the rust-only tie arbiter on the champion built here.
**OFF BY DEFAULT and it stays off** — arming it in production is an OWNER decision (a
``governance/PRODUCTION.yaml`` change), not this harness's default. Disarmed, NO
``tiearb`` keyword reaches ``make_production_champion`` at all, so the champion is
bit-for-bit the pre-plumbing one; the only change to a disarmed run is a manifest that
now says ``tiearb: {"enabled": false}`` OUT LOUD instead of saying nothing.
``--backend python`` + armed is refused AT LAUNCH (the arbiter is rust-only).
Contract tests: ``tests/test_play_harness_tiearb.py``.

Enforces the locked 2p Base+Farmers ruleset (the wingedsheep engine already
constrains this; we assert `state.players == 2`). No ELO math lives here — this
just produces trustworthy game records for the human-anchor program to score.

Records per game:
  * every action (seat, phase, k_remaining, action id + description),
  * per-move agent telemetry: which path (pimc / exact / forced), latch_k,
    solver secs & nodes for that move, wall-clock ms, wall timestamp,
  * a signed MANIFEST: agent version = git rev, resolved leaf env, config hash,
    leaf hash, deck seed + deck hash, final result, and a content signature
    (sha256 over the canonical manifest+moves — tamper-evident, NOT a keyed sig).

Paired-deck rematch: `play_paired(seed, ...)` plays the SAME shuffled deck twice
with seats swapped (A in seat0 / B in seat1, then B in seat0 / A in seat1). The
deck is reproduced by `random.seed(deck_seed)` before `get_init_board` (the
root_replay contract); both games carry an identical `deck_hash` proving it.

Usage:
  # prove the pipeline (RUNS one full fair-vs-fair game + a paired rematch, low sims):
  .venv/bin/python scripts/human_anchor/play_harness.py --self-test

  # a human (seat 0) vs the fair champion (seat 1), production sims:
  .venv/bin/python scripts/human_anchor/play_harness.py --human 0 --sims 400 --k-dets 4 \
      --seed 12345 --out measurement/human_anchor/games
"""
from __future__ import annotations

import env_preamble  # noqa: F401  MUST precede carcassonne_ai import
import argparse
import hashlib
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import _common as C

# telemetry counters snapshotted per move on the fair agent
_COUNTERS = ("heur_moves", "exact_moves", "n_timeouts", "solver_secs",
             "solver_nodes", "neural_moves")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def deck_hash(state) -> str:
    """Order-sensitive digest of the initial deck ([next_tile]+deck). Identical
    across a paired rematch iff the same shuffle was reproduced."""
    tiles = ([state.next_tile] if state.next_tile is not None else []) + list(state.deck)
    h = hashlib.sha256()
    h.update("\x1f".join(t.description for t in tiles).encode())
    return h.hexdigest()[:16]


def _snapshot(agent) -> dict:
    return {k: getattr(agent, k, 0) for k in _COUNTERS} | {"latch_k": agent.latch_k}


def resolve_parallel_workers(no_parallel: bool = False,
                             profile: str = "desktop") -> int | None:
    """The deploy EXECUTION profile's ``parallel_workers``, or None for the sequential
    k-loop. FAIL-SAFE by design (the champion_factory contract): an unknown/absent profile
    or a ``parallel_workers: null`` (the mobile/Chaquopy case) resolves to None, and any
    exception reading PRODUCTION.yaml also resolves to None rather than exploding a game.

    None is never a WEAKER player — the k-parallel split is behavior-identical
    (tests/test_kparallel.py) — it is only ~6.37x slower per move at the champion budget."""
    if no_parallel:
        return None
    try:
        from carcassonne_ai.champion_factory import deploy_profile
        return deploy_profile(profile)["parallel_workers"]
    except Exception as exc:                                    # noqa: BLE001
        print(f"[warn] could not resolve deploy profile {profile!r} "
              f"({type(exc).__name__}: {exc}); running the SEQUENTIAL k-loop")
        return None


def resolve_execution(backend="inherit", profile="desktop", rust_threads=None,
                      no_parallel=False):
    """The ENGINE + split for this run, resolved from ``--backend`` / the deploy profile.

    Superset of resolve_parallel_workers() (kept above for its callers): it also answers
    WHICH ENGINE runs the search, because the two are coupled — ``backend="rust"`` and
    ``parallel_workers`` are mutually exclusive in the factory (Rust folds the same k
    worlds across OS threads inside one GIL-released call). Same fail-safe posture.
    ``--backend auto`` reads the profile's ``backend`` from PRODUCTION.yaml; the DEFAULT
    is ``inherit`` = champion_factory's own default (today python), so a bare invocation
    is byte-identical to before this flag AND a flip of that default reaches here."""
    from carcassonne_ai.mirror_protocol import resolve_execution as _resolve
    return _resolve(backend, profile=profile, rust_threads=rust_threads,
                    no_parallel=no_parallel)


# --------------------------------------------------------------------------- #
# THE TIE ARBITER (measurement/tiearb2_stage2_20260817) — PLUMBING ONLY.        #
#                                                                              #
# ⚠️ OFF BY DEFAULT and it stays off: arming it in production is an OWNER       #
# decision (a PRODUCTION.yaml change), NOT something this harness's default     #
# does. Disarmed, `_resolve_tiearb` returns None and `_make_fair_agent` passes  #
# NO `tiearb` keyword to the factory at all, so the champion — its config hash, #
# its leaf hash, its manifest — is bit-for-bit what it was before this file     #
# grew the flags (tests/test_play_harness_tiearb.py asserts exactly that).      #
# --------------------------------------------------------------------------- #
def _resolve_tiearb(args) -> dict | None:
    """The ``--tiearb-*`` flags -> the dict ``make_production_champion`` takes, or
    ``None`` when the arbiter was not armed.

    ``None`` (not a dict with ``enabled=False``) on the unarmed leg, deliberately —
    the caller uses ``is None`` to decide whether to pass the keyword AT ALL, which is
    what makes a disarmed run byte-identical to a pre-arbiter one. The explicit
    off-RECORD lives in the game log instead (see ``_game_tiearb_block``), where an
    absent field would be unreadable rather than merely off.

    Ported from ``scripts/jcz_match/match.py::_resolve_tiearb`` (the ``--champ-tiearb-*``
    surface); the knobs and defaults are that harness's verbatim, so a game played here
    is comparable to a graded cell without a translation table.
    """
    if not bool(getattr(args, "tiearb_enabled", False)):
        return None
    return {"enabled": True,
            "B": int(args.tiearb_b), "J": int(args.tiearb_j),
            "mode": str(args.tiearb_mode), "salt": str(args.tiearb_salt),
            "eps": float(args.tiearb_eps)}


def _champ_tiearb_telemetry(champ, tiearb) -> dict | None:
    """TIE-ARBITER per-agent liveness read. ``None`` unless armed with an ENABLED
    ``tiearb``; an armed agent that is NOT a Rust-backed champion RAISES rather than
    stamping ``None`` (the arbiter is rust-only, and a silent ``None`` would let an
    armed game that never actually arbitrated a single ply be read as one that did —
    the J13 lesson).

    Field-for-field the same read as ``match.py::_champ_tiearb_telemetry`` and
    ``eval_fair_puct._cand_tiearb_telemetry``, so the three harnesses are comparable.
    """
    if not tiearb or not bool(tiearb.get("enabled")):
        return None
    rs = getattr(champ, "_rs", None)
    if rs is None:
        raise RuntimeError(
            "tiearb is armed but the champion has no FairAgentRs (the tie arbiter is "
            "rust-only) — it cannot have run")
    s = rs.stats()
    if not bool(s.get("tiearb_enabled")):
        raise RuntimeError(
            "tiearb is armed but FairAgentRs.stats() reports tiearb_enabled=False — "
            "the knob was dropped between main() and the rust config (a STALE carc_rs "
            "wheel is the usual cause)")
    return {
        "tile_plies": int(s["tiearb_tile_plies"]),
        # `fires` and `fired_plies` are THE SAME NUMBER under two names, on purpose:
        # the adjudicator's `G-FIRE` reads `fires` fail-closed while `fired_plies` is
        # what the summary blocks aggregate. Emitting one and not the other would void
        # a perfectly good record on a key spelling.
        "fires": int(s["tiearb_fired_plies"]),
        "fired_plies": int(s["tiearb_fired_plies"]),
        "pickchanges": int(s["tiearb_pickchanges"]),
        "arms_total": int(s["tiearb_arms_total"]),
        "playouts_total": int(s["tiearb_playouts_total"]),
        "secs": float(s["tiearb_secs"]),
        # FAIL-SOFT counter: a tier1 continuation can hit the engine's window refusal
        # or the ply ceiling deep in a determinized world, which falls back to the
        # champion's own pick rather than killing the GAME. Nonzero is REPORTABLE, not
        # fatal, and it must never be invisible.
        "errors": int(s.get("tiearb_errors") or 0),
        "first_error": s.get("tiearb_first_error"),
        # READ_RULE §0.F `G-PLY`: plies that took an argmax over FEWER than B completed
        # worlds. 0 by construction. ⚠️ Non-zero OR ABSENT => U-UNREADABLE.
        "partial_argmax": int(s.get("tiearb_partial_argmax") or 0),
        "max_plies": int(s.get("tiearb_max_plies") or 0),
        "mode": str(s["tiearb_mode"]),
        "B": int(s["tiearb_b"]), "J": int(s["tiearb_j"]),
    }


def _game_tiearb_block(agents: dict, tiearb: dict | None) -> dict:
    """The per-GAME arbiter record stamped into every manifest — ALWAYS present.

    ⚠️ UNLIKE ``match.py`` (whose frozen per-game jsonl schema forbids a new key on an
    unarmed record) this harness stamps ``{"enabled": false}`` EXPLICITLY when
    disarmed. The U-UNREADABLE rule: absent is unknown-not-zero, so a reader of a
    human-anchor game log must never have to infer from silence whether the arbiter
    was off, armed-but-dead, or armed-and-firing. The three states are now three
    distinguishable records:

      * ``{"enabled": false}``                       — never armed
      * ``enabled: true`` + a seat with ``fires: 0`` — armed, no tie ever qualified
      * ``enabled: true`` + a seat with ``fires > 0``— armed AND it arbitrated

    Only factory-built champions are read (the same ``.manifest`` test the
    ``champion_manifests`` block uses) — ``HumanCLIAgent`` carries no arbiter. An
    armed game with NO champion seat raises: that is a wiring bug, not a null cell.
    """
    if not tiearb or not bool(tiearb.get("enabled")):
        return {"enabled": False}
    block = {"enabled": True, "config": dict(tiearb), "seats": {}}
    for seat, a in sorted(agents.items()):
        if getattr(a, "manifest", None) is None:
            continue                 # not a factory champion (e.g. HumanCLIAgent)
        block["seats"][str(seat)] = _champ_tiearb_telemetry(a, tiearb)
    if not block["seats"]:
        raise RuntimeError(
            "tiearb is armed but no seat in this game is a factory-built champion — "
            "the arbiter cannot have run on anything")
    return block


def _make_fair_agent(game, sims, k_dets, seed, exact_endgame=True,
                     parallel_workers=None, execution=None, tiearb=None):
    """The PRODUCTION fair champion, built + runtime-verified by the champion factory
    (F1, 2026-07-19). Rewired from the PRE-FLIP FairHeuristicMCTSAgent (random-expansion
    UCT + old leaf) to the current champion: FairHeuristicPriorAgent (PUCT heuristic
    priors, curve125 leaf, c_puct=1.5/tau_p=5/float/visits) via
    champion_factory.make_production_champion, which reads governance/PRODUCTION.yaml and
    PROVES the leaf on real boards at construction (raises on mismatch). The returned
    agent carries a runtime manifest (`agent.manifest`) recorded into every game log.
    c_puct is no longer a knob here — the champion's c_puct=1.5 is factory-owned.

    ``parallel_workers`` (None = the sequential k-loop, byte-identical to before this
    kwarg existed) splits the k determinization worlds across spawn processes. LATENCY
    ONLY — same player, same chosen action; see resolve_parallel_workers().

    ``execution`` (F-3, 2026-08-02) is the resolved ENGINE+split from
    resolve_execution(); when it names ``backend="rust"`` the returned agent is a
    ``rust_agent.RustFairAgent``, whose mirror play_game() below drives. It supersedes
    ``parallel_workers`` when both are given (the pair is illegal on Rust).

    ``tiearb`` (plumbing added 2026-08-19) arms THE TIE ARBITER. ⚠️ ``None`` — the
    DEFAULT, and what ``_resolve_tiearb`` returns for every unarmed invocation — passes
    NO ``tiearb`` keyword to the factory whatsoever, so the constructed champion is
    bit-for-bit the pre-plumbing one. This is a keyword-PRESENCE contract, not a
    keyword-value one; do not "simplify" it to always passing ``tiearb=tiearb``."""
    from carcassonne_ai.champion_factory import make_production_champion
    from carcassonne_ai.mirror_protocol import Execution

    if execution is None:
        execution = Execution(backend="python", rust_threads=None,
                              parallel_workers=parallel_workers)
    # DISARMED => the keyword is ABSENT, not False. See the docstring.
    arb_kw = {"tiearb": tiearb} if tiearb is not None else {}
    return make_production_champion("fair", game=game, seed=seed, sims=sims,
                                    k_dets=k_dets, exact_endgame=exact_endgame,
                                    **execution.factory_kwargs(), **arb_kw)


class HumanCLIAgent:
    """A keyboard player: prints the board + enumerated legal moves, reads a pick.
    Same interface (`choose_action(board) -> int`) as the fair agent, so the play
    loop is agent-agnostic. Carries the fair-agent telemetry attrs (all 0) so the
    logger treats it uniformly."""

    def __init__(self, game):
        self._game = game
        self.latch_k = None
        for k in _COUNTERS:
            setattr(self, k, 0)

    def choose_action(self, board) -> int:
        legal = C.legal_action_ids(self._game, board)
        print(C.render_board(board.state))
        s = board.state
        tile_desc = getattr(s.next_tile, "description", None)
        print(f"  you are player {s.current_player}   scores(p0,p1)={list(s.scores)}"
              f"   phase={s.phase.value}   K={C.k_remaining(s)}")
        # Without this the move list is bare coordinates and the human cannot tell WHICH
        # tile they are placing / which tile they just placed a meeple on.
        print(f"  tile in hand: {tile_desc}   meeples left(p0,p1)={list(s.meeples)}")
        for i, a in enumerate(legal):
            print(f"    [{i:>3}] a={a:<5} {C.describe_action(board, a)}")
        while True:
            raw = input("  pick move # : ").strip()
            try:
                idx = int(raw)
                if 0 <= idx < len(legal):
                    return legal[idx]
            except ValueError:
                pass
            print("  invalid; try again.")


def play_game(game, deck_seed: int, agents: dict, agent_labels: dict,
              config: dict, tiearb: dict | None = None) -> dict:
    """Play one full 2p game. `agents` = {seat: agent} (seat -> object with
    choose_action(board)->int + the telemetry attrs). Returns a game record
    {manifest, moves, result}. Never records a peek at the true deck.

    ``tiearb`` is the RESOLVED arbiter dict the seats were BUILT with (or None). It is
    read-only here — it changes nothing about the play, it only tells the manifest
    which arbiter record to stamp (`_game_tiearb_block`)."""
    from carcassonne_ai import mirror_protocol as MP
    from carcassonne_ai import window_truncation as _WT

    random.seed(int(deck_seed))          # fixes the engine shuffle (root_replay contract)
    board = game.get_init_board()
    assert board.state.players == 2, "locked scope: 2-player only"
    # THE MIRROR PROTOCOL (F-3). A Rust-backed champion owns a game state that moves
    # only on advance(); seat it on the deck THIS board was dealt, then advance it for
    # every applied action of BOTH seats at the choke point below. No-op (duck-typed)
    # for the Python champion and for HumanCLIAgent, so this file is correct on either
    # backend — including if the factory default ever flips.
    MP.seat(agents, board)
    dh = deck_hash(board.state)
    moves = []
    t_start = time.time()
    move_idx = 0
    while game.get_game_ended(board, 0) == 0.0:
        seat = board.state.current_player
        agent = agents[seat]
        legal = C.legal_action_ids(game, board)
        before = _snapshot(agent)
        t0 = time.perf_counter()
        # F-c (`measurement/window_truncation_20260813/DESIGN.md` §7). This loop is
        # the ONLY place that holds everything an action-window crash needs to be
        # reconstructed — the deck seed, the applied-action prefix and the GLOBAL
        # ply — and it used to throw all three away on the way up to
        # `h2h._play_cell`, which is why the 2026-08-13 crash needed a full replay
        # (`reconstruct_crash_root.py`) to recover its root. The context manager
        # is inert unless the search raises an empty-mask error, and it ALWAYS
        # re-raises. `move_idx` is read off the AGENT (its own decision counter),
        # never from `move_idx` below — that one is the global ply.
        with _WT.capture(deck_seed=deck_seed, ply=len(moves),
                         actions=[m["action"] for m in moves],
                         player_to_move=seat, agent=agent,
                         raiser_is_champion=MP.is_mirrored(agent),
                         rules_profile=(config.get("rules_profile")
                                        or config.get("profile")),
                         champion_seed=getattr(agent, "_seed", None),
                         checksum=game.string_representation(board),
                         seats=dict(agent_labels),
                         extra={"agent_label": agent_labels.get(seat)}):
            a = int(agent.choose_action(board))
        ms = (time.perf_counter() - t0) * 1000.0
        after = _snapshot(agent)
        if len(legal) == 1:
            path = "forced"
        elif after["exact_moves"] > before["exact_moves"]:
            path = "exact"
        else:
            path = "pimc"
        moves.append({
            "move_idx": move_idx,
            "seat": seat,
            "agent": agent_labels[seat],
            "phase": board.state.phase.value,
            "k_remaining": C.k_remaining(board.state),
            "n_legal": len(legal),
            "action": a,
            "desc": C.describe_action(board, a),
            "path": path,
            "latch_k": after["latch_k"],
            "solver_secs_move": round(after["solver_secs"] - before["solver_secs"], 6),
            "solver_nodes_move": after["solver_nodes"] - before["solver_nodes"],
            "timeout": after["n_timeouts"] > before["n_timeouts"],
            "ms": round(ms, 2),
            "ts": time.time(),
        })
        board, _ = game.get_next_state(board, a)
        MP.advance(agents, a)            # EVERY applied action, BOTH seats
        move_idx += 1

    scores = list(board.state.scores)
    winner = 0 if scores[0] > scores[1] else 1 if scores[1] > scores[0] else -1
    result = {"scores": scores, "winner_seat": winner,
              "margin_seat0_minus_seat1": scores[0] - scores[1], "n_moves": move_idx,
              "wall_secs": round(time.time() - t_start, 2)}

    manifest = {
        "kind": "human_anchor_game",
        "agent_version": C.git_rev(),
        "leaf_hash": C.leaf_hash(),
        "leaf_env": env_preamble.RESOLVED,
        "deck_seed": int(deck_seed),
        "deck_hash": dh,
        "agent_labels": agent_labels,
        # F1: the runtime-verified champion factory manifest for every factory-built
        # agent seat (curve125 leaf proven on real boards at construction).
        "champion_manifests": {
            str(seat): m for seat, a in agents.items()
            if (m := getattr(a, "manifest", None)) is not None
        },
        # THE TIE ARBITER's per-game liveness witness. ALWAYS present, including the
        # disarmed `{"enabled": false}` — an armed arbiter that never fired must be
        # distinguishable from one that did AND from one that was never armed
        # (U-UNREADABLE: absent is unknown-not-zero). This is a RECORD field only; the
        # champion that produced the moves above is untouched when disarmed.
        "tiearb": _game_tiearb_block(agents, tiearb),
        "config": config,
        "config_hash": C.sha256_of(config)[:16],
        "utc": _now_iso(),
        "result": result,
    }
    record = {"manifest": manifest, "moves": moves, "result": result}
    # content signature (tamper-evident): sha256 over canonical manifest(-sig)+moves
    manifest["signature"] = C.sha256_of({"manifest": manifest, "moves": moves})
    return record


def write_record(record: dict, out_dir: Path, tag: str) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    seed = record["manifest"]["deck_seed"]
    p = out_dir / f"game_seed{seed}_{tag}.json"
    p.write_text(json.dumps(record, indent=1))
    return p


def play_paired(game, deck_seed, ctor_a, ctor_b, label_a, label_b, config,
                out_dir=None, tiearb=None) -> list[dict]:
    """Play the same deck twice, seats swapped: (A@0,B@1) then (B@0,A@1).
    Fresh agent instances per game (no cross-game state leak). Returns both records."""
    recs = []
    for tag, seats, labels in (
        ("a0", {0: ctor_a(), 1: ctor_b()}, {0: label_a, 1: label_b}),
        ("a1", {0: ctor_b(), 1: ctor_a()}, {0: label_b, 1: label_a}),
    ):
        rec = play_game(game, deck_seed, seats, labels, config | {"seat_layout": tag},
                        tiearb=tiearb)
        if out_dir:
            write_record(rec, out_dir, tag)
        recs.append(rec)
    return recs


# --------------------------------------------------------------------------- #
def self_test(execution=None, tiearb=None) -> int:
    print("=== play_harness self-test ===")
    from carcassonne_ai.game_wrapper import Game
    game = Game(enable_legal_moves_cache=True)
    seed = 777_000_001
    sims, k_dets = 48, 2   # LIGHT smoke config (NOT production strength)
    print(f"[1] one full fair-vs-fair game  seed={seed} sims={sims} k_dets={k_dets} "
          f"| {execution.describe() if execution else 'backend=python'} ...")
    t0 = time.time()

    def ctor_a():
        return _make_fair_agent(game, sims, k_dets, seed=101, execution=execution,
                                tiearb=tiearb)

    def ctor_b():
        return _make_fair_agent(game, sims, k_dets, seed=202, execution=execution,
                                tiearb=tiearb)

    config = {"sims": sims, "k_dets": k_dets,
              "champion": "puct_priors_v29_bmild_cap8 (champion_factory)",
              "exact_endgame": True, "ruleset": "2p_base_farmers"}
    out_dir = C.REPO_ROOT / "measurement/human_anchor/_selftest_games"
    recs = play_paired(game, seed, ctor_a, ctor_b, "fairA", "fairB", config,
                       out_dir=out_dir, tiearb=tiearb)
    dt = time.time() - t0
    r0, r1 = recs
    print(f"    played 2 games in {dt:.1f}s   "
          f"g0 result={r0['result']['scores']} winner_seat={r0['result']['winner_seat']}   "
          f"g1 result={r1['result']['scores']}")

    print("[2] logs + manifests written:")
    for p in sorted(out_dir.glob("game_seed*_a*.json")):
        rec = json.loads(p.read_text())
        m = rec["manifest"]
        paths = {mv["path"] for mv in rec["moves"]}
        print(f"    {p.name}: {len(rec['moves'])} moves  paths={sorted(paths)}  "
              f"agent_version={m['agent_version']}  leaf_hash={m['leaf_hash']}  "
              f"sig={m['signature'][:12]}...")

    print("[3] assertions:")
    # (a) paired rematch reproduced the deck
    assert r0["manifest"]["deck_hash"] == r1["manifest"]["deck_hash"], "deck NOT reproduced!"
    print(f"    deck reproduced: both games deck_hash={r0['manifest']['deck_hash']} OK")
    # (b) both games ran the full game (144 moves for a full base game)
    assert r0["result"]["n_moves"] > 100 and r1["result"]["n_moves"] > 100
    print(f"    full games: n_moves={r0['result']['n_moves']}, {r1['result']['n_moves']} OK")
    # (c) the exact-endgame handoff fired (a latch + >=1 exact move near the end)
    latched = any(mv["path"] == "exact" for mv in r0["moves"])
    print(f"    exact-endgame handoff fired in game0: {latched} "
          f"(latch_k seen: {sorted({mv['latch_k'] for mv in r0['moves'] if mv['latch_k']})})")
    # (d) signature verifies (recompute over manifest-minus-sig + moves)
    m = dict(r0["manifest"])
    sig = m.pop("signature")
    recomputed = C.sha256_of({"manifest": m, "moves": r0["moves"]})
    assert recomputed == sig, "signature does not verify!"
    print("    signature verifies OK")
    # (e) no clairvoyant leak: fair agent's neural_moves stays 0 (harness symmetry)
    assert all(getattr(a(), "neural_moves", 0) == 0 for a in (ctor_a, ctor_b))
    print("=== self-test PASSED ===")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="play_harness")
    ap.add_argument("--self-test", action="store_true", help="RUN one fair-vs-fair game + rematch")
    ap.add_argument("--human", type=int, choices=(0, 1), default=None,
                    help="play as this seat vs the fair champion")
    ap.add_argument("--seed", type=int, default=None, help="deck seed (random if unset)")
    ap.add_argument("--sims", type=int, default=None,
                    help="sims per determinization. DEFAULT = the PRODUCTION.yaml budget "
                         "(fair_deploy.sims_per_det, 1376 since the 2026-07-29 promotion; "
                         "was 688). Lower it (e.g. --sims 200) "
                         "ONLY to speed the AI up — that plays a WEAKER-than-champion agent and "
                         "the game log records a runtime_budget_override.")
    ap.add_argument("--k-dets", type=int, default=None,
                    help="determinizations per move. DEFAULT = the PRODUCTION.yaml budget "
                         "(fair_deploy.k_dets, 8 since the 2026-07-29 promotion; was 4).")
    ap.add_argument("--c-puct", type=float, default=3.0,
                    help="DEPRECATED / IGNORED (F1): the champion's exploration constant "
                         "(c_puct=1.5) is owned by champion_factory/PRODUCTION.yaml, not this "
                         "flag. Kept only so old invocations do not error.")
    ap.add_argument("--no-parallel", action="store_true",
                    help="force the SEQUENTIAL k-loop, ignoring the deploy profile's "
                         "parallel_workers. Same player (the split is behavior-identical, "
                         "tests/test_kparallel.py) — just ~6.37x slower per move at the "
                         "champion budget. Use it on a box with <8 usable cores, or to "
                         "reproduce a pre-2026-07-29 single-process run.")
    ap.add_argument("--profile", default="desktop",
                    help="deploy EXECUTION profile in PRODUCTION.yaml whose "
                         "parallel_workers is used (default: desktop = 8). NOTE this "
                         "selects only the WORKER COUNT here; the BUDGET still comes from "
                         "fair_deploy/--sims/--k-dets.")
    ap.add_argument("--backend", choices=("inherit", "python", "rust", "auto"),
                    default="inherit",
                    help="which ENGINE computes the champion's search. inherit "
                         "(DEFAULT) = champion_factory's own default, which today is "
                         "python — so a bare invocation is byte-identical to before "
                         "this flag, AND a future flip of that default reaches this "
                         "harness without editing it. python = pin the Python "
                         "champion. rust = carc_rs, the rustport core (~9.8x faster "
                         "per move at the champion budget). auto = read the deploy "
                         "profile's `backend` from PRODUCTION.yaml. This harness "
                         "drives the Rust mirror (start_game + advance for both "
                         "seats), so all four are safe; the ENGINE never changes the "
                         "play (G4/G6 identity gates).")
    ap.add_argument("--rust-threads", type=int, default=None,
                    help="backend=rust only: fold the k determinization worlds across "
                         "this many OS threads inside one GIL-released call (default: "
                         "the profile's rust_threads, else 1). The Rust analogue of "
                         "parallel_workers, and mutually exclusive with it.")
    ap.add_argument("--paired", action="store_true", help="play a seat-swapped rematch too")
    ap.add_argument("--out", type=Path, default=C.REPO_ROOT / "measurement/human_anchor/games")
    # --- THE TIE ARBITER (measurement/tiearb2_stage2_20260817) -------------------
    # PLUMBING, OFF BY DEFAULT. The knobs are `match.py`'s `--champ-tiearb-*` and
    # `eval_fair_puct`'s `--cand-tiearb-*` verbatim (only the prefix differs — in THIS
    # harness there is no "cand"/"champ" side to disambiguate), so a game played here
    # with the deploy shape is directly comparable to a graded cell.
    # ⚠️ ARMING THIS IS AN OWNER DECISION. This harness's default is and stays OFF;
    # a production flip is a governance/PRODUCTION.yaml change, not a flag habit.
    ap.add_argument("--tiearb-enabled", action="store_true",
                    help="ARM the tie arbiter on the champion. RUST-ONLY: re-decide an "
                         "exactly-tied TILE ply with terminal-grounded tier1-greedy "
                         "playouts. OFF BY DEFAULT — a bare invocation constructs the "
                         "champion with NO tiearb keyword at all, i.e. bit-for-bit the "
                         "pre-plumbing player. ⚠️ The leaf hash does NOT move, so the "
                         "wiring gates are the log's manifest.champion_manifests[*]."
                         "cand_tiearb dict and the per-game manifest.tiearb telemetry.")
    ap.add_argument("--tiearb-b", type=int, default=16,
                    help="B: CRN determinizations per fired ply, SHARED by every arm "
                         "(16 = the funded rung / the deploy shape of record).")
    ap.add_argument("--tiearb-j", type=int, default=4,
                    help="J: the cap on the afterstate-deduped tie set, applied by a "
                         "SEEDED DRAW (never index truncation); the champion's own "
                         "pooled_q_argmax pick is appended when the cap excluded it.")
    ap.add_argument("--tiearb-mode", choices=("argmax", "random"), default="argmax",
                    help="argmax = the ARB shape (take the world-mean argmax). random "
                         "= the RND control: identical playouts, values DISCARDED, arm "
                         "drawn by seeded RNG (matched wall clock).")
    ap.add_argument("--tiearb-salt", type=str, default="tiearb2-deploy-v1",
                    help="World/selection seed salt. The salt of record is "
                         "'tiearb2-deploy-v1'; a different salt is a different "
                         "experiment.")
    ap.add_argument("--tiearb-eps", type=float, default=0.0,
                    help="Tie membership tolerance on the outer chain value. 0.0 is "
                         "the COMMITTED setting — exact f64 equality, NOT a tolerance.")
    args = ap.parse_args(argv)

    # Resolved BEFORE either play path so the rust-only guard below fires AT LAUNCH,
    # on --self-test too, and never 20 minutes into a human's game. Hoisting
    # resolve_execution() above the --self-test branch is behaviour-identical: that
    # branch called it with these same four arguments.
    tiearb = _resolve_tiearb(args)
    execution = resolve_execution(args.backend, args.profile, args.rust_threads,
                                  args.no_parallel)
    if tiearb is not None and not execution.is_rust:
        # Precedent: eval_fair_puct's identical up-front refusal. The factory would
        # also raise (champion_factory: "tiearb is RUST-ONLY"), but that is a raise
        # per constructed agent, mid-run; this is one honest error before anything
        # is built. `--backend inherit`/`auto` resolving to rust is FINE and passes.
        ap.error(
            "--tiearb-enabled is RUST-ONLY (the arbiter binds at the pooled_q_argmax "
            "root hook in carc_core::fair::FairAgent); the resolved backend is "
            f"{execution['backend']!r} ({execution.describe()}). Re-run with "
            "--backend rust (or --backend auto/inherit on a box whose deploy profile "
            "resolves to rust) — refusing up front instead of failing per-agent.")
    if tiearb is not None:
        print(f"[tiearb] TIE ARBITER ARMED on the champion: {tiearb} (leaf hash does "
              "NOT move; the gates are the log's champion manifest cand_tiearb dict "
              "and the per-game manifest.tiearb firing telemetry)", flush=True)

    if args.self_test:
        return self_test(execution, tiearb=tiearb)

    from carcassonne_ai.champion_factory import load_production_spec
    from carcassonne_ai.game_wrapper import Game
    # Resolve the budget from governance/PRODUCTION.yaml unless the caller overrode it,
    # so a bare `--human 0` plays the CHAMPION budget (k8x1376=11008 since 2026-07-29,
    # was k4x688) and not a weaker stand-in. The EXECUTION profile (parallel_workers) is
    # resolved separately and is a LATENCY knob only — ~2.2 s/move split vs ~13.8 s/move
    # sequential, same player either way.
    _spec = load_production_spec()
    if args.sims is None:
        args.sims = _spec.sims_per_det
    if args.k_dets is None:
        args.k_dets = _spec.k_dets
    pw = execution["parallel_workers"]          # resolved above, before the guard
    game = Game(enable_legal_moves_cache=True)
    seed = args.seed if args.seed is not None else random.randint(1, 2_000_000_000)
    config = {"sims": args.sims, "k_dets": args.k_dets,
              "champion": "puct_priors_v29_bmild_cap8 (champion_factory)",
              "exact_endgame": True, "ruleset": "2p_base_farmers",
              # LATENCY provenance, not strength: which execution the log was produced by.
              # The ENGINE is provenance for the same reason and on the same terms — it
              # is gated behaviour-identical (G4/G6), so it can never explain a result.
              "parallel_workers": pw, "deploy_profile": args.profile,
              "backend": execution["backend"],
              "rust_threads": execution["rust_threads"]}
    print(f"[exec] budget k{args.k_dets}x{args.sims} = {args.k_dets * args.sims} sims/move | "
          f"{execution.describe()}"
          f"{'' if execution['source'] != 'profile' else f' (profile {args.profile!r})'}")

    if args.human is None:
        print("no --human seat and no --self-test: playing fair-vs-fair "
              f"(seed={seed}, sims={args.sims})")

        def ctor_a():
            return _make_fair_agent(game, args.sims, args.k_dets, seed=101,
                                    execution=execution, tiearb=tiearb)

        def ctor_b():
            return _make_fair_agent(game, args.sims, args.k_dets, seed=202,
                                    execution=execution, tiearb=tiearb)

        if args.paired:
            play_paired(game, seed, ctor_a, ctor_b, "fairA", "fairB", config,
                        out_dir=args.out, tiearb=tiearb)
        else:
            rec = play_game(game, seed, {0: ctor_a(), 1: ctor_b()},
                            {0: "fairA", 1: "fairB"}, config, tiearb=tiearb)
            print("wrote", write_record(rec, args.out, "a0"))
        return 0

    # human vs fair champion
    human_seat = args.human
    ai_seat = 1 - human_seat
    human = HumanCLIAgent(game)
    ai = _make_fair_agent(game, args.sims, args.k_dets, seed=303, execution=execution,
                          tiearb=tiearb)
    agents = {human_seat: human, ai_seat: ai}
    labels = {human_seat: "human", ai_seat: f"fair@{args.sims}"}
    rec = play_game(game, seed, agents, labels, config, tiearb=tiearb)
    p = write_record(rec, args.out, f"human{human_seat}")
    print(f"\n=== GAME OVER === scores={rec['result']['scores']} "
          f"winner_seat={rec['result']['winner_seat']}")
    print("wrote", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
