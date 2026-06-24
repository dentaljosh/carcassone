"""Phase 7 (gate) — two-checkpoint net-vs-net via TWO carc-orch SHM orchestrators.

A two-distinct-checkpoint variant of v28_leaf_swap_orch.py. The two sides differ in
CHECKPOINT (each served by its OWN carc-orch SHM server) and MAY differ in the leaf
meeple_k. Everything else (sims, c_puct, residual_scale, seeds, pairing band, both
seats) is held IDENTICAL across the two sides so results are directly comparable to
the leaf-swap battery.

  A = checkpoint-a (the RoD candidate)  : NeuralMCTS@sims, A-net priors + leaf value
      tanh(virtual_score_v2(.., meeple_k=meeple_k_a)/15) + residual_scale*v_nn_A
      served by carc-orch SHM server A (--shm-eval-server-a)
  B = checkpoint-b (the iter8 parent)   : same, B-net + meeple_k_b, residual_scale
      served by carc-orch SHM server B (--shm-eval-server-b)

Each worker holds TWO SHM handles (one per server, keyed on shm_name so two handles
in one worker is fine — see shm_eval_handles.connect_shm). Side A's net forward is
served by server A; side B's by server B. The v2.7(/+meeple) leaf + residual run on
the CPU worker. Route to side A's mcts when current player == a_player, else side B.

NB: meeple_k is the LEGACY LeafConfig field -> _v28_active is False -> the leaf runs on
the FLAT (production) path, full speed, on each orchestrator. Residual head (residual_scale)
is kept on both sides — this is the PRODUCTION-REALISTIC drop-in test, not a pure-leaf
isolation.

Measurement only. Champion + production + PRODUCTION.yaml UNCHANGED. v2.7 frozen.

Requires BOTH carc-orch SHM servers already running
(launch via scripts/heuristic_v28/v28_net_vs_net_orch.sh).
"""
from __future__ import annotations
import argparse, dataclasses, hashlib, json, math, os, socket, sys, time
from dataclasses import asdict, dataclass
from pathlib import Path
import multiprocessing as mp

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "heuristic_v28"))
import v28_configs; v28_configs.set_prod_env()
from carcassonne_ai.claim import try_claim as _try_claim          # noqa: E402
from carcassonne_ai.game_wrapper import Game                       # noqa: E402
from carcassonne_ai.mcts import NeuralMCTS                         # noqa: E402
from carcassonne_ai.evaluators import make_v25_value_wrapper       # noqa: E402
from carcassonne_ai.remote_evaluators import make_remote_single_evaluator  # noqa: E402
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG         # noqa: E402

_W: dict = {}


@dataclass
class GameResult:
    seed: int
    a_player: int       # the seat (0/1) that side A (checkpoint-a) plays this game
    sims: int
    c_puct: float
    score_p0: int
    score_p1: int
    diff: int            # A(checkpoint-a) - B(checkpoint-b), seat-corrected
    won_by_a: bool
    drew: bool
    elapsed_s: float
    moves: int


def _result_path(out, sims, c, seed, a_player):
    return out / f"s{sims:04d}_c{str(c).replace('.','')}_seed{seed:09d}_a{a_player}.json"


def _try_load(p):
    if p.exists():
        try:
            return GameResult(**json.load(open(p)))
        except Exception:
            p.unlink(missing_ok=True)
    return None


def _save(p, r):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.stem}.{socket.gethostname()}.{os.getpid()}.partial.json")
    json.dump(asdict(r), open(tmp, "w")); tmp.replace(p)


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _worker_init(shm_a, shm_b, id_q_a, id_q_b, ns_a, ns_b, residual_scale,
                 meeple_k_a, meeple_k_b, shared_claim, claim_host, claim_stale):
    from carcassonne_ai.shm_eval_handles import connect_shm
    # connect_shm is keyed on shm_name, so holding two handles in one worker is fine.
    _W["handles_a"] = connect_shm(shm_a, id_q_a.get(), ns_a)
    _W["handles_b"] = connect_shm(shm_b, id_q_b.get(), ns_b)
    _W["ns_a"] = ns_a
    _W["ns_b"] = ns_b
    # each side's Game must encode the scalar width its OWN net was trained on.
    _W["include_farm_a"] = ns_a > 10
    _W["include_farm_b"] = ns_b > 10
    _W["rs"] = residual_scale
    _W["mk_a"] = meeple_k_a
    _W["mk_b"] = meeple_k_b
    _W["shared_claim"] = shared_claim
    _W["claim_host"] = claim_host
    _W["claim_stale"] = claim_stale


def _play_one(args):
    out_str, seed, a_player, sims, c_puct = args
    out = Path(out_str)
    p = _result_path(out, sims, c_puct, seed, a_player)
    c = _try_load(p)
    if c is not None:
        return c
    if _W.get("shared_claim"):
        if not _try_claim(p.with_suffix(".claim"), _W["claim_host"], _W["claim_stale"]):
            return None
    import random
    random.seed(seed)
    # separate games so the two trees' legal caches don't mix; each side uses its OWN
    # net's scalar width and its OWN SHM handle (sequential per worker).
    ga = Game(enable_legal_moves_cache=True, include_farm_scalars=_W["include_farm_a"])
    gb = Game(enable_legal_moves_cache=True, include_farm_scalars=_W["include_farm_b"])
    base_a = make_remote_single_evaluator(_W["handles_a"], ga)
    base_b = make_remote_single_evaluator(_W["handles_b"], gb)
    cfg_a = dataclasses.replace(DEFAULT_CONFIG, residual_scale=_W["rs"], meeple_k=_W["mk_a"])
    cfg_b = dataclasses.replace(DEFAULT_CONFIG, residual_scale=_W["rs"], meeple_k=_W["mk_b"])
    leaf_a = make_v25_value_wrapper(base_a, cfg_a)
    leaf_b = make_v25_value_wrapper(base_b, cfg_b)
    mcts_a = NeuralMCTS(game=ga, evaluator=leaf_a, simulations=sims, seed=seed, c_puct=c_puct)
    mcts_b = NeuralMCTS(game=gb, evaluator=leaf_b, simulations=sims, seed=seed + 1, c_puct=c_puct)
    # IMPORTANT: both games must track the SAME board so the deck/turn order is shared.
    # We advance a single board; only the acting side's tree differs (the canonical board
    # carries the full state — each Game wrapper is a stateless view over board.state).
    board = ga.get_init_board()
    t0 = time.perf_counter(); moves = 0
    while ga.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        mcts = mcts_a if cur == a_player else mcts_b
        mcts.clear()
        # advance via ga only (identical to v28_leaf_swap_orch.py) — get_next_state is a
        # stateless transition over board.state; routing it through ga keeps the deck/turn
        # order byte-identical regardless of which side moved.
        board, _ = ga.get_next_state(board, mcts.best_action(board))
        moves += 1
    s0, s1 = board.state.scores
    diff = (s0 - s1) if a_player == 0 else (s1 - s0)
    r = GameResult(seed=seed, a_player=a_player, sims=sims, c_puct=c_puct,
                   score_p0=int(s0), score_p1=int(s1), diff=int(diff),
                   won_by_a=(diff > 0), drew=(diff == 0),
                   elapsed_s=time.perf_counter() - t0, moves=moves)
    _save(p, r)
    return r


def _paired_z(results):
    """Paired-by-seed margin z: for each seed where BOTH a_player=0 and a_player=1 exist,
    average the two A-B diffs (cancels deck luck), then z over the per-seed paired means.
    Returns (paired_mean, paired_z, n_pairs) or (nan, nan, 0) if no complete pairs."""
    by_seed = {}
    for r in results:
        by_seed.setdefault(r.seed, {})[r.a_player] = r.diff
    pairs = [(v[0] + v[1]) / 2.0 for v in by_seed.values() if 0 in v and 1 in v]
    n = len(pairs)
    if n == 0:
        return float("nan"), float("nan"), 0
    mean = sum(pairs) / n
    var = sum((x - mean) ** 2 for x in pairs) / (n - 1) if n > 1 else 0.0
    sd = math.sqrt(var)
    z = (mean / (sd / math.sqrt(n))) if sd > 0 else float("nan")
    return mean, z, n


def _summary(results, sims, label):
    n = len(results); w = sum(r.won_by_a for r in results); d = sum(r.drew for r in results)
    losses = n - w - d; avg = sum(r.diff for r in results) / n; wr = (w + 0.5 * d) / n
    diffs = [r.diff for r in results]; mean = sum(diffs) / n
    var = sum((x - mean) ** 2 for x in diffs) / (n - 1) if n > 1 else 0.0
    sd = math.sqrt(var); z = (mean / (sd / math.sqrt(n))) if sd > 0 else float("nan")
    if 0 < wr < 1:
        elo = 400.0 * math.log10(wr / (1 - wr))
        es = (400.0 / math.log(10)) * math.sqrt(wr * (1 - wr) / n) / (wr * (1 - wr))
    else:
        elo, es = math.copysign(800.0, wr - 0.5), float("nan")
    pmean, pz, npairs = _paired_z(results)
    # by-seat breakdown (A as seat 0 vs A as seat 1)
    a0 = [r for r in results if r.a_player == 0]; a1 = [r for r in results if r.a_player == 1]
    def _wr(rs):
        return ((sum(r.won_by_a for r in rs) + 0.5 * sum(r.drew for r in rs)) / len(rs)) if rs else float("nan")
    print(f"\n=== {label}, NeuralMCTS@{sims}, n={n} ===")
    print(f"A: {w}W/{d}D/{losses}L  wr {wr:.3f}  avg diff {avg:+.2f}  z_margin {z:+.2f}  ELO {elo:+.1f} (+/-{es:.1f})")
    print(f"   paired: mean {pmean:+.2f} over {npairs} pairs  paired_z {pz:+.2f}")
    print(f"   by-seat: A@seat0 wr {_wr(a0):.3f} (n={len(a0)}) | A@seat1 wr {_wr(a1):.3f} (n={len(a1)})")
    sig = "VERDICT-RANGE" if (not math.isnan(es) and abs(elo) > 2 * es) else "INCONCLUSIVE"
    print(f"signal: {sig}")
    return {"label": label, "sims": sims, "n": n, "W": w, "D": d, "L": losses, "winrate": round(wr, 4),
            "avg_diff": round(avg, 3), "z_margin": round(z, 3), "elo": round(elo, 1),
            "elo_1sig": (round(es, 1) if not math.isnan(es) else None),
            "paired_mean": (round(pmean, 3) if not math.isnan(pmean) else None),
            "paired_z": (round(pz, 3) if not math.isnan(pz) else None), "n_pairs": npairs,
            "a_seat0_wr": (round(_wr(a0), 4) if a0 else None),
            "a_seat1_wr": (round(_wr(a1), 4) if a1 else None),
            "signal": sig}


def _build_work(seed_start, n, paired):
    if not paired:
        return [(seed_start + i, i % 2) for i in range(n)]
    work = []
    for i in range(n // 2):
        work.append((seed_start + i, 0)); work.append((seed_start + i, 1))
    return work


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint-a", required=True, help="side A checkpoint (the RoD candidate)")
    ap.add_argument("--checkpoint-b", required=True, help="side B checkpoint (the iter8 parent)")
    ap.add_argument("--shm-eval-server-a", required=True, help="carc-orch SHM name for side A (running)")
    ap.add_argument("--shm-eval-server-b", required=True, help="carc-orch SHM name for side B (running)")
    ap.add_argument("--meeple-k-a", type=float, default=2.0)
    ap.add_argument("--meeple-k-b", type=float, default=2.0)
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--sims", type=int, default=200)
    ap.add_argument("--c-puct", type=float, default=3.0)
    ap.add_argument("--residual-scale", type=float, default=0.25)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--paired", action="store_true")
    ap.add_argument("--seed-start", type=int, default=1_906_220_000)
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--out-subdir", default=None)
    ap.add_argument("--shared-claim", action="store_true")
    ap.add_argument("--claim-stale-secs", type=int, default=300)  # was 5400 (90min): 300s lets a
    # dead box's in-flight claims be reclaimed WITHIN a screen by the drain barrier below; a
    # sims=200 game is <60s, so a LIVE claim is never falsely judged stale.
    ap.add_argument("--drain-timeout-secs", type=int, default=900)  # bound the drain wait
    ap.add_argument("--claim-host", default=socket.gethostname())
    ap.add_argument("--summary-only", action="store_true")
    args = ap.parse_args(argv)
    if args.paired and args.n % 2:
        ap.error("--paired requires even --n")

    import torch
    # peek each checkpoint SEPARATELY — do not assume the two nets share a scalar width.
    ns_a = int(torch.load(args.checkpoint_a, map_location="cpu", weights_only=False).get("n_scalar_features", 10))
    ns_b = int(torch.load(args.checkpoint_b, map_location="cpu", weights_only=False).get("n_scalar_features", 10))
    sub = args.out_subdir or (
        f"nvn_{Path(args.checkpoint_a).stem}_mk{str(args.meeple_k_a).replace('.','')}"
        f"_vs_{Path(args.checkpoint_b).stem}_mk{str(args.meeple_k_b).replace('.','')}"
        f"_s{args.sims}_rs{str(args.residual_scale).replace('.','')}")
    out = Path(args.out_root) / sub
    out.mkdir(parents=True, exist_ok=True)
    json.dump({"kind": "net_vs_net_orch",
               "checkpoint_a": args.checkpoint_a, "checkpoint_b": args.checkpoint_b,
               "sha256_a": _sha256(args.checkpoint_a), "sha256_b": _sha256(args.checkpoint_b),
               "n_scalar_a": ns_a, "n_scalar_b": ns_b,
               "shm_a": args.shm_eval_server_a, "shm_b": args.shm_eval_server_b,
               "meeple_k_a": args.meeple_k_a, "meeple_k_b": args.meeple_k_b,
               "sims": args.sims, "c_puct": args.c_puct, "residual_scale": args.residual_scale,
               "n": args.n, "paired": args.paired, "seed_start": args.seed_start,
               "A": "net(%s)+v2.7+meeple_k%g leaf, resid %g" % (Path(args.checkpoint_a).name, args.meeple_k_a, args.residual_scale),
               "B": "net(%s)+v2.7+meeple_k%g leaf, resid %g" % (Path(args.checkpoint_b).name, args.meeple_k_b, args.residual_scale),
               "base_env": v28_configs.PROD_ENV}, open(out / "manifest.json", "w"), indent=2)

    tasks = [(str(out), s, ap_, args.sims, args.c_puct) for s, ap_ in _build_work(args.seed_start, args.n, args.paired)]
    label = (f"A={Path(args.checkpoint_a).name}+mk{args.meeple_k_a} vs "
             f"B={Path(args.checkpoint_b).name}+mk{args.meeple_k_b} (resid {args.residual_scale})")
    if args.summary_only:
        res = [r for t in tasks if (r := _try_load(_result_path(out, args.sims, args.c_puct, t[1], t[2]))) is not None]
        if res:
            json.dump(_summary(res, args.sims, label), open(out / "result.json", "w"), indent=2)
        else:
            print("no cached results")
        return 0

    todo = [t for t in tasks if not _result_path(out, args.sims, args.c_puct, t[1], t[2]).exists()]
    print(f"[net-vs-net-orch] A={Path(args.checkpoint_a).name}(ns={ns_a}) B={Path(args.checkpoint_b).name}(ns={ns_b}) "
          f"n={args.n} sims={args.sims} c={args.c_puct} resid={args.residual_scale} "
          f"mk_a={args.meeple_k_a} mk_b={args.meeple_k_b} | {len(tasks)-len(todo)} cached, "
          f"{len(todo)} to play, W={args.workers}, shm_a={args.shm_eval_server_a}, shm_b={args.shm_eval_server_b}, out={out}", flush=True)
    sys.stdout.flush()
    results = []
    if todo:
        ctx = mp.get_context("spawn")
        id_q_a = ctx.Queue(); id_q_b = ctx.Queue()
        for w in range(args.workers):
            id_q_a.put(w); id_q_b.put(w)
        t0 = time.perf_counter()
        with ctx.Pool(processes=args.workers, initializer=_worker_init,
                      initargs=(args.shm_eval_server_a, args.shm_eval_server_b, id_q_a, id_q_b,
                                ns_a, ns_b, args.residual_scale, args.meeple_k_a, args.meeple_k_b,
                                args.shared_claim, args.claim_host, args.claim_stale_secs)) as pool:
            done = 0
            for r in pool.imap_unordered(_play_one, todo, chunksize=1):
                if r is None:
                    continue   # peer claimed this unit (work-stealing) — skip, drain waits below
                results.append(r); done += 1
                if done % 10 == 0:
                    el = time.perf_counter() - t0
                    print(f"  {done} played by this box ({el/done:.1f}s/game)", flush=True)
            # ---- DRAIN-TO-COMPLETION BARRIER (2026-06-23 fix for 2-box work-stealing) ----
            # Without this, a client finishing its imap pass tallies a PARTIAL result: it
            # SKIPPED (never waited on) units the peer claimed, so the fast box writes
            # result.json at e.g. 80/100 while the slow box is still playing. Instead, keep
            # re-mapping the still-missing units until ALL N have JSON: a unit the peer is
            # actively playing has a fresh claim -> _play_one returns None fast (no dup work);
            # a DEAD peer's claims go stale (--claim-stale-secs) -> we reclaim + play them.
            # Self-balancing + self-healing with NO speed-ratio prediction. No-op single-box.
            if args.shared_claim:
                drain_deadline = time.perf_counter() + args.drain_timeout_secs
                idle = 0
                while True:
                    remaining = [t for t in tasks
                                 if not _result_path(out, args.sims, args.c_puct, t[1], t[2]).exists()]
                    if not remaining:
                        print(f"  [drain] complete — all {len(tasks)} units have results", flush=True)
                        break
                    if time.perf_counter() > drain_deadline:
                        print(f"  [drain] TIMEOUT after {args.drain_timeout_secs}s — {len(remaining)} "
                              f"units still missing; tallying partial", flush=True)
                        break
                    got = 0
                    for r in pool.imap_unordered(_play_one, remaining, chunksize=1):
                        if r is not None:
                            results.append(r); got += 1
                    if got == 0:
                        idle += 1
                        print(f"  [drain] {len(remaining)} unit(s) in flight on the peer "
                              f"(idle round {idle}); waiting", flush=True)
                        time.sleep(10)
                    else:
                        idle = 0
                        print(f"  [drain] reclaimed+played {got}; {len(remaining)-got} left", flush=True)
    for t in tasks:
        p = _result_path(out, args.sims, args.c_puct, t[1], t[2])
        if p.exists() and not any(r.seed == t[1] and r.a_player == t[2] for r in results):
            cc = _try_load(p)
            if cc:
                results.append(cc)
    if results:
        json.dump(_summary(results, args.sims, label), open(out / "result.json", "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
