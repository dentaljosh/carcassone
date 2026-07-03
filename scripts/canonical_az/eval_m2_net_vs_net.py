"""M2 per-iter health check — sighted candidate vs a FIXED blind reference net,
through TWO carc-orch SHM orchestrators (one per net). Fast + fixed-anchor
replacement for the slow net-vs-h3200 per-iter eval.

  A = candidate  : the M2 sighted net (81ch/42-scalar), served by SHM server A.
  B = reference  : a FIXED blind net (78ch, e.g. RoD-v2 iter_02), server B.

Each side is a NeuralMCTS: its OWN net priors (served by its OWN orch, so the
two reps never mix — A featurizes with Game(sighted=True), B with the blind
Game) + the v2.9 leaf VALUE via make_v25_value_wrapper (env-built DEFAULT_CONFIG;
residual_scale/value_blend=0 -> the net VALUE head is NOT used). So this is a
POLICY-strength health check on the shared v2.9 leaf substrate — the fixed-net
analogue of eval_net_vs_heuristic. (The sighted VALUE-head read-out is the
solver-scoring harness, M2_PLAN Part A — a separate step, NOT this.)

The reference MUST be a FIXED rung (never iter_(N-1)) — chain elo lies. Deck-
paired by seed (both seats each seed). Multi-box work-stealing via --shared-claim
+ a drain-to-completion barrier (identical to v28_net_vs_net_orch.py).

Requires BOTH carc-orch SHM servers already running (launch via
scripts/canonical_az/eval_m2_dual_orch.sh). Measurement only.
"""
from __future__ import annotations
import argparse, dataclasses, hashlib, json, math, os, socket, sys, time
from dataclasses import asdict, dataclass
from pathlib import Path
import multiprocessing as mp

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
from carcassonne_ai.claim import try_claim as _try_claim               # noqa: E402
from carcassonne_ai.game_wrapper import Game                           # noqa: E402
from carcassonne_ai.mcts import NeuralMCTS                             # noqa: E402
from carcassonne_ai.evaluators import make_v25_value_wrapper           # noqa: E402
from carcassonne_ai.remote_evaluators import make_remote_single_evaluator  # noqa: E402

_W: dict = {}


@dataclass
class GameResult:
    seed: int
    a_player: int       # seat (0/1) the candidate plays this game
    sims: int
    c_puct: float
    score_p0: int
    score_p1: int
    diff: int           # candidate - reference, seat-corrected
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


def _peek(path):
    import torch
    ck = torch.load(path, map_location="cpu", weights_only=False)
    return (int(ck.get("n_scalar_features", 10)),
            int(ck.get("n_input_channels", 78)),
            bool(ck.get("sighted", False)))


def _worker_init(shm_a, shm_b, id_q_a, id_q_b, dims_a, dims_b, fpu,
                 shared_claim, claim_host, claim_stale):
    from carcassonne_ai.shm_eval_handles import connect_shm
    ns_a, nch_a, sighted_a = dims_a
    ns_b, nch_b, sighted_b = dims_b
    # connect_shm is keyed on shm_name -> two handles in one worker is fine.
    _W["handles_a"] = connect_shm(shm_a, id_q_a.get(), ns_a, nch_a)
    _W["handles_b"] = connect_shm(shm_b, id_q_b.get(), ns_b, nch_b)
    # each side's Game must match its OWN net's rep (sighted 81ch or blind).
    _W["ga"] = Game(enable_legal_moves_cache=True, sighted=sighted_a,
                    include_farm_scalars=(ns_a > 10) and not sighted_a)
    _W["gb"] = Game(enable_legal_moves_cache=True, sighted=sighted_b,
                    include_farm_scalars=(ns_b > 10) and not sighted_b)
    _W["fpu"] = fpu
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
    ga, gb, fpu = _W["ga"], _W["gb"], _W["fpu"]
    base_a = make_remote_single_evaluator(_W["handles_a"], ga)
    base_b = make_remote_single_evaluator(_W["handles_b"], gb)
    # v2.9 leaf VALUE (env-built DEFAULT_CONFIG), net PRIORS. residual/blend=0 ->
    # net value head unused -> pure POLICY health check on the shared leaf.
    leaf_a = make_v25_value_wrapper(base_a, None)
    leaf_b = make_v25_value_wrapper(base_b, None)
    mcts_a = NeuralMCTS(game=ga, evaluator=leaf_a, simulations=sims, seed=seed,
                        c_puct=c_puct, fpu_reduction=fpu)
    mcts_b = NeuralMCTS(game=gb, evaluator=leaf_b, simulations=sims, seed=seed + 1,
                        c_puct=c_puct, fpu_reduction=fpu)
    # Advance a single board via ga (a stateless view over board.state); only the
    # acting side's tree differs. Keeps the deck/turn order shared + byte-identical.
    board = ga.get_init_board()
    t0 = time.perf_counter(); moves = 0
    while ga.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        mcts = mcts_a if cur == a_player else mcts_b
        mcts.clear()
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
    a0 = [r for r in results if r.a_player == 0]; a1 = [r for r in results if r.a_player == 1]
    def _wr(rs):
        return ((sum(r.won_by_a for r in rs) + 0.5 * sum(r.drew for r in rs)) / len(rs)) if rs else float("nan")
    print(f"\n=== {label}, NeuralMCTS@{sims}, n={n} ===")
    print(f"CAND: {w}W/{d}D/{losses}L  wr {wr:.3f}  avg diff {avg:+.2f}  z_margin {z:+.2f}  ELO {elo:+.1f} (+/-{es:.1f})")
    print(f"   paired: mean {pmean:+.2f} over {npairs} pairs  paired_z {pz:+.2f}")
    print(f"   by-seat: CAND@seat0 wr {_wr(a0):.3f} (n={len(a0)}) | CAND@seat1 wr {_wr(a1):.3f} (n={len(a1)})")
    sig = "VERDICT-RANGE" if (not math.isnan(es) and abs(elo) > 2 * es) else "INCONCLUSIVE"
    print(f"signal: {sig}")
    return {"label": label, "sims": sims, "n": n, "W": w, "D": d, "L": losses, "winrate": round(wr, 4),
            "avg_diff": round(avg, 3), "z_margin": round(z, 3), "elo": round(elo, 1),
            "elo_1sig": (round(es, 1) if not math.isnan(es) else None),
            "paired_mean": (round(pmean, 3) if not math.isnan(pmean) else None),
            "paired_z": (round(pz, 3) if not math.isnan(pz) else None), "n_pairs": npairs,
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
    ap.add_argument("--cand-ckpt", required=True, help="M2 sighted candidate (81ch)")
    ap.add_argument("--ref-ckpt", required=True, help="FIXED blind reference (e.g. RoD-v2 iter_02)")
    ap.add_argument("--shm-eval-server-cand", required=True)
    ap.add_argument("--shm-eval-server-ref", required=True)
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--sims", type=int, default=200)
    ap.add_argument("--c-puct", type=float, default=3.0)
    ap.add_argument("--fpu", type=float, default=0.6)
    ap.add_argument("--workers", type=int, default=28)
    ap.add_argument("--paired", action="store_true")
    ap.add_argument("--seed-start", type=int, default=1_906_220_000)
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--out-subdir", default=None)
    ap.add_argument("--shared-claim", action="store_true")
    ap.add_argument("--claim-stale-secs", type=int, default=300)
    ap.add_argument("--drain-timeout-secs", type=int, default=900)
    ap.add_argument("--claim-host", default=socket.gethostname())
    ap.add_argument("--summary-only", action="store_true")
    args = ap.parse_args(argv)
    if args.paired and args.n % 2:
        ap.error("--paired requires even --n")

    dims_a = _peek(args.cand_ckpt)   # (ns, n_ch, sighted)
    dims_b = _peek(args.ref_ckpt)
    sub = args.out_subdir or (
        f"m2nvn_{Path(args.cand_ckpt).stem}_vs_{Path(args.ref_ckpt).stem}"
        f"_s{args.sims}_fpu{str(args.fpu).replace('.','')}")
    out = Path(args.out_root) / sub
    out.mkdir(parents=True, exist_ok=True)
    json.dump({"kind": "m2_net_vs_net_orch",
               "cand_ckpt": args.cand_ckpt, "ref_ckpt": args.ref_ckpt,
               "sha256_cand": _sha256(args.cand_ckpt), "sha256_ref": _sha256(args.ref_ckpt),
               "dims_cand": dims_a, "dims_ref": dims_b,
               "shm_cand": args.shm_eval_server_cand, "shm_ref": args.shm_eval_server_ref,
               "sims": args.sims, "c_puct": args.c_puct, "fpu": args.fpu,
               "n": args.n, "paired": args.paired, "seed_start": args.seed_start,
               "leaf": "v2.9 env-built DEFAULT_CONFIG (residual/blend=0 -> pure policy check)",
               "note": "value-head read-out is the solver harness, NOT this"},
              open(out / "manifest.json", "w"), indent=2)

    tasks = [(str(out), s, ap_, args.sims, args.c_puct)
             for s, ap_ in _build_work(args.seed_start, args.n, args.paired)]
    label = f"CAND={Path(args.cand_ckpt).name} vs REF={Path(args.ref_ckpt).name} (v2.9 leaf, fpu {args.fpu})"
    if args.summary_only:
        res = [r for t in tasks if (r := _try_load(_result_path(out, args.sims, args.c_puct, t[1], t[2]))) is not None]
        if res:
            json.dump(_summary(res, args.sims, label), open(out / "result.json", "w"), indent=2)
        else:
            print("no cached results")
        return 0

    todo = [t for t in tasks if not _result_path(out, args.sims, args.c_puct, t[1], t[2]).exists()]
    print(f"[m2-nvn-orch] CAND={Path(args.cand_ckpt).name}{dims_a} REF={Path(args.ref_ckpt).name}{dims_b} "
          f"n={args.n} sims={args.sims} c={args.c_puct} fpu={args.fpu} | {len(tasks)-len(todo)} cached, "
          f"{len(todo)} to play, W={args.workers}, out={out}", flush=True)
    sys.stdout.flush()
    results = []
    if todo:
        ctx = mp.get_context("spawn")
        id_q_a = ctx.Queue(); id_q_b = ctx.Queue()
        for w in range(args.workers):
            id_q_a.put(w); id_q_b.put(w)
        t0 = time.perf_counter()
        with ctx.Pool(processes=args.workers, initializer=_worker_init,
                      initargs=(args.shm_eval_server_cand, args.shm_eval_server_ref, id_q_a, id_q_b,
                                dims_a, dims_b, args.fpu,
                                args.shared_claim, args.claim_host, args.claim_stale_secs)) as pool:
            done = 0
            for r in pool.imap_unordered(_play_one, todo, chunksize=1):
                if r is None:
                    continue
                results.append(r); done += 1
                if done % 20 == 0:
                    el = time.perf_counter() - t0
                    print(f"  {done} played by this box ({el/done:.1f}s/game)", flush=True)
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
                        print(f"  [drain] TIMEOUT — {len(remaining)} units missing; tallying partial", flush=True)
                        break
                    got = 0
                    for r in pool.imap_unordered(_play_one, remaining, chunksize=1):
                        if r is not None:
                            results.append(r); got += 1
                    if got == 0:
                        idle += 1
                        print(f"  [drain] {len(remaining)} unit(s) in flight on peer (idle {idle}); waiting", flush=True)
                        time.sleep(10)
                    else:
                        idle = 0
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
