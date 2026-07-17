#!/usr/bin/env python3
"""A2 — Fair (imperfect-information / PIMC) deployable-config eval for the
PUCT-with-heuristic-priors CHAMPION vs a fixed heuristic rung.

Pre-registration / roadmap: docs/PROGRAM_ROADMAP_2026-07-07.md item A2.

WHY: the production champion (HeuristicPriorAgent, c1.5/tau5/float/visits @ ~2750
sims; governance/PRODUCTION.yaml) as shipped plays CLAIRVOYANT — its NeuralMCTS
descends the engine's pre-shuffled TRUE deck, so it "sees" the upcoming tiles. Any
human/superhuman strength claim is graded on the DEPLOYABLE FAIR config: the same
champion under imperfect information (root-determinization PIMC). This script
derives that fair config and refreshes the stale iter8-only clairvoyance tax
(CL-022, ~26.6 elo) at the champion's OWN config.

THREE ARMS (--info), all vs the SAME fixed rung on the SAME decks so their paired
Δ isolates the one variable that changes:
  - fair     : FairHeuristicPriorAgent (fair PIMC prefix; k_dets determinizations per
               move, pooled-Q) — the deployable config. DEFAULT.
  - clair    : the clairvoyant champion (HeuristicPriorAgent on the true deck) — the
               as-shipped strength; the CL-022 CLAIR arm at champion config.
  - fair-net : the fair PIMC prefix with IDENTICAL heuristic priors but a LEARNED
               deck-aware net leaf value (C-cheap; needs --net <sighted ckpt>). vs the
               `fair` arm on the same decks it isolates the VALUE component: does a
               deck-aware learned value shrink the clairvoyance tax? (Gate: fair-elo
               of fair-net minus fair >= +35 elo; C_CHEAP_SPEC §4.) The priors are
               byte-identical to `fair` (make_heuristic_prior_evaluator_with_net_value).
  - fair-netprior : the MIRROR of fair-net, and the STRENGTH arm for the DISTILLED net.
               fair-net swaps the VALUE; this swaps the PRIORS. The net's POLICY head
               supplies the PUCT priors while the value stays the FROZEN curve125
               champion leaf — the severed value loop, so a value collapse is impossible
               by construction (make_fair_net_prior_evaluator; the same evaluator the
               stage-2 flywheel gen uses). vs the `fair` arm on the same decks it
               isolates the POLICY component: do distilled priors beat the heuristic
               softmax priors at equal search budget?
               --net-mode / --net-lambda are INAPPLICABLE (there is no net value) and
               are REJECTED. The rep (sighted 81ch/42 vs non-sighted 78ch/10) is
               INFERRED from the checkpoint; a mismatch fails loud.
               ⚠️ Its frozen leaf is curve125 (the PRODUCTION champion the nets were
               distilled against), injected IN-PROCESS on the candidate side only. The
               h800 rung stays curve100 — see the CURVE125 block below for why you must
               NOT `source champ_env.sh` to get this.
ALL arms get the IDENTICAL fair MARGINALIZED exact endgame handoff (latched on the
first TILES decision with k_remaining<=K), so the only measured difference is the
SEARCH PREFIX (fair PIMC vs clairvoyant). The endgame is marginalized (honest
hidden-bag value), NOT clairvoyant — a clairvoyant K=3-4 solve would be the cheating
path and is intractable-fair anyway. tax = elo(clair) - elo(fair).

OPPONENT (--opponent) — WHO the candidate plays. DEFAULT `h800` = the fixed rung
(byte-unchanged; every pre-existing arm/result stays valid). The two head-to-head
modes replace the delta-of-deltas through the rung with a DIRECT match:
  - h800          : HeuristicMCTS @ rung_sims (default 800, c=3.0, v2.9 Bmild_cap8
                    curve100 leaf) — the CL-022 ruler
                    (measurement/clairvoyance/CLAIRVOYANCE_GAP_VERDICT.md "vs
                    HeuristicMCTS @ heur_sims=800, v2.7 leaf"), NO endgame (fixed
                    yardstick). DEFAULT.
  - fair-champion : the PRODUCTION champion itself — FairHeuristicPriorAgent with
                    HEURISTIC softmax priors, curve125 leaf, at the SAME budget and
                    the SAME fair machinery as the candidate. With `--info
                    fair-netprior` this is the "did the distillation work?" cell: a
                    PURE PRIOR-SWAP (net policy priors vs heuristic priors), every
                    other knob shared.
  - net           : a SECOND distilled net (--opp-net), run as a fair-netprior agent.
                    With `--info fair-netprior` this is the "does the bag matter?"
                    cell (sighted vs non-sighted distilled net). Each side's rep
                    (81ch/42 sighted vs 78ch/10) is inferred from ITS OWN checkpoint,
                    so a cross-rep match encodes each side correctly.
In BOTH head-to-head modes the two sides are production agents, so BOTH resolve the
FROZEN curve125 champion leaf (injected in-process per side — see the CURVE125 block
below), both get the same marginalized endgame handoff at K, and seat alternation +
deck pairing are unchanged (the candidate's seat is `a_seat`, which _build_work
balances over 0/1) — a prior-swap A/B where one side owned a seat would be worthless.
`diff` is always CANDIDATE - OPPONENT.

EQUAL-WALL-CLOCK: the fair champion's total per-move search budget = k_dets*sims,
targeted at the deployed clairvoyant champion's ~2750 sims (default k_dets=4 *
sims=688 ~= 2752 — ADOPTED 2026-07-13, CL-054; was k8*344, k4 beat k8 +5.18/z4.17
cost-neutral). The k_dets separate root expansions add a little fixed overhead,
so the fair arm gets a hair MORE compute than a single 2750 search — conservative
(if it still loses the tax, the tax is real).

GRID (docs/PROGRAM_ROADMAP A2): K in {2,4,8} (fair endgame handoff depth) x matched
sims. K=2 marginalized solves are RAM-safe; K>=3 marginalized is expensive (no
alpha-beta over chance nodes -> RAM/OOM regime) -> ATTENDED ONLY (see run_fair_grid.sh).

Pure CPU, net-free -> keep --workers <= threads, nice -n 19. CARCASSONNE_TT_CAP is
honored by the solver (env passthrough, recorded in the manifest).

Usage:
  # plumbing + K=2 handoff smoke (single process, tiny):
  nice -n 19 .venv/bin/python scripts/classical_search/eval_fair_puct.py \
      --info fair --exact-k 2 --k-dets 2 --sims 64 --games 2 --smoke

  # C-cheap fair-net plumbing smoke (RANDOM 81ch/42-scalar net, no training):
  nice -n 19 .venv/bin/python scripts/classical_search/eval_fair_puct.py \
      --info fair-net --exact-k 2 --k-dets 2 --sims 32 --games 2 --smoke

  # DISTILLED-net fair-netprior plumbing smoke (rep inferred from the ckpt; works for
  # BOTH the sighted 81ch/42 and the non-sighted 78ch/10 candidates):
  nice -n 19 .venv/bin/python scripts/classical_search/eval_fair_puct.py \
      --info fair-netprior --net <distilled ckpt> --exact-k 2 --k-dets 2 --sims 32 \
      --games 2 --workers 2 --smoke

  # fair-netprior A/B cell vs the SAME h800 rung on the SAME decks as the `fair` arm
  # (so the paired Δ isolates the POLICY component). CPU net per worker:
  CARCASSONNE_TT_CAP=200000 nice -n 19 .venv/bin/python -u \
      scripts/classical_search/eval_fair_puct.py \
      --info fair-netprior --net <distilled ckpt> \
      --exact-k 2 --k-dets 4 --sims 688 --rung-sims 800 --n 100 --paired \
      --seed-start 13000000000 --workers 14 \
      --out-root /mnt/c/carc-shared/classical_search --shared-claim --no-results-csv

  # C-cheap v2 RESIDUAL fair-net A/B cell (n=100 deck-paired, CPU net per worker):
  CARCASSONNE_TT_CAP=200000 nice -n 19 .venv/bin/python -u \
      scripts/classical_search/eval_fair_puct.py \
      --info fair-net --net <sighted_value.pt> --net-mode residual --net-lambda 0.25 \
      --exact-k 2 --k-dets 8 --sims 344 --rung-sims 800 --n 100 --paired \
      --seed-start 13000000000 --workers 14 \
      --out-root /mnt/c/carc-shared/classical_search --shared-claim --no-results-csv

  # SAME cell but GPU-batched via the carc-orch SHM server (much faster; the server
  # (81ch/42-scalar) is started SEPARATELY and verify_sighted_orch_parity MUST pass):
  #   .venv/bin/python scripts/canonical_az/verify_sighted_orch_parity.py --checkpoint <ckpt>
  #   TS=/tmp/fairnet.ts.pt; .venv/bin/python scripts/export_torchscript.py \
  #       --checkpoint <ckpt> --out $TS --device cuda
  #   nice -n 19 rust/carc-orch/run_server.sh --model $TS --transport shm \
  #       --shm-name fairnet --workers 14 --n-ch 81 --n-scalar 42 --device cuda \
  #       --max-batch 16 --batch-timeout-ms 2.0 --forwarders 4 --watchdog-secs 30 &
  CARCASSONNE_TT_CAP=200000 nice -n 19 .venv/bin/python -u \
      scripts/classical_search/eval_fair_puct.py \
      --info fair-net --net <sighted_value.pt> --orch-shm-name fairnet \
      --net-mode residual --net-lambda 0.25 --exact-k 2 --k-dets 8 --sims 344 \
      --rung-sims 800 --n 100 --paired --seed-start 13000000000 --workers 14 \
      --out-root /mnt/c/carc-shared/classical_search --shared-claim --no-results-csv

  # one K=2 fair screen cell (n=100 deck-paired):
  CARCASSONNE_TT_CAP=200000 nice -n 19 .venv/bin/python -u \
      scripts/classical_search/eval_fair_puct.py \
      --info fair --exact-k 2 --k-dets 8 --sims 344 --rung-sims 800 \
      --n 100 --paired --seed-start 13000000000 --workers 14 \
      --out-root /mnt/c/carc-shared/classical_search --shared-claim --no-results-csv
"""
from __future__ import annotations

import os

# v2.9 Bmild_cap8 leaf env — MUST precede the carcassonne_ai imports (DEFAULT_CONFIG
# reads these at import). Verbatim from eval_puct_priors.py / fair_agent_smoke.py.
_CANON_ENV = {
    "CARCASSONNE_V25_CAP": "8",
    "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-8,-4,-1,0,2,3,4,5",
    "CARCASSONNE_V25_MEEPLE_K": "2.0",
    "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_USE_CY_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1",
    "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    # ⚠️ The installed numpy is scipy-OpenBLAS (DYNAMIC_ARCH), NOT MKL — so the
    # OMP/MKL pins above are INERT for the real BLAS backend. Left unpinned,
    # OpenBLAS spawns a box-sized busy-waiting thread pool in EVERY worker; with
    # W30(local)+W22(laptop) that thrashes the scheduler and stalls forward
    # progress (the curve175 n=400 clair hang, root-caused 2026-07-13, commit
    # e006036 fixed the sibling eval_puct_priors the same way). This harness
    # shares the multi-worker --shared-claim pattern, so it has the same latent
    # hang risk. Pin to 1 — result-neutral (fair games are net-free CPU: Cython
    # leaf + PUCT tree, no BLAS matmul). MUST precede any numpy import; forked
    # workers inherit the env.
    "OPENBLAS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
}
for _k, _v in _CANON_ENV.items():
    os.environ.setdefault(_k, _v)

import argparse
import json
import math
import multiprocessing as mp
import socket
import sys
import time
from dataclasses import asdict, dataclass
from multiprocessing import Pool
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))  # endgame_solver
sys.path.insert(0, str(Path(__file__).resolve().parent))  # c5_leaf_override (sibling)

from carcassonne_ai import eval_provenance as ep  # noqa: E402
from carcassonne_ai.claim import try_claim as _try_claim  # noqa: E402
from carcassonne_ai.eval_provenance import deck_hash  # noqa: E402
from carcassonne_ai.fair_agent import (  # noqa: E402
    FairHeuristicPriorAgent,
    k_remaining,
)
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import (  # noqa: E402
    HeuristicPriorAgent,
    HeuristicPriorConfig,
    make_fair_net_prior_batch_evaluator,
    make_fair_net_prior_evaluator,
    make_heuristic_prior_evaluator,
    make_heuristic_prior_evaluator_with_residual_value,
    make_sighted_net_value_fn,
)
from carcassonne_ai.mcts import DEFAULT_C, HeuristicMCTS  # noqa: E402
from carcassonne_ai.run_manifest import code_rev, game_tag, write_manifest  # noqa: E402
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG  # noqa: E402

# C5 candidate-leaf override helpers — SHARED with eval_puct_priors.py (see
# c5_leaf_override.py); imported (not copy-pasted) so the two harnesses can never
# diverge on the --cand-leaf-json parse/coercion/cy-guard semantics. `_leaf_hash`
# is bit-identical to the old local definition (same asdict/json-sort/sha256[:16]).
from c5_leaf_override import (  # noqa: E402
    _assert_cy_float_path,
    _leaf_dict,
    _leaf_hash,
    _load_cand_leaf_cfg,
)

import endgame_solver as S  # noqa: E402

try:
    from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402
    _TILES_PHASE = GamePhase.TILES
except Exception:  # pragma: no cover
    _TILES_PHASE = None


# --------------------------------------------------------------------------- #
# C-cheap deck-aware NET value (the `fair-net` arm). torch + CarcassonneNet are   #
# imported lazily (only this arm needs them) so the fair/clair arms keep their    #
# net-free, torch-free startup.                                                   #
# --------------------------------------------------------------------------- #
def _load_net(path, device="cpu"):
    """Load a sighted (81ch/42-scalar) CarcassonneNet checkpoint for value read-out.
    Mirrors verify_sighted_orch_parity._load_net (arch dims live in the ckpt)."""
    import torch
    from carcassonne_ai.network import CarcassonneNet
    ck = torch.load(path, map_location=device, weights_only=False)
    n_ch = int(ck.get("n_input_channels", 78))
    n_scalar = int(ck.get("n_scalar_features", 10))
    net = CarcassonneNet(
        n_filters=ck.get("n_filters", 96), n_blocks=ck.get("n_blocks", 6),
        n_input_channels=n_ch, n_scalar_features=n_scalar,
        value_global_pool=bool(ck.get("value_global_pool", False)),
    ).to(device)
    net.load_state_dict(ck["model_state"])
    net.eval()
    if n_ch != 81 or n_scalar != 42 or not bool(ck.get("sighted", False)):
        print(f"[warn] --net is not an 81ch/42-scalar sighted net "
              f"(n_ch={n_ch} n_scalar={n_scalar} sighted={ck.get('sighted')}); "
              "the deck-aware fair-net arm expects the sighted rep.", file=sys.stderr)
    return net


def _random_sighted_net(device="cpu", value_global_pool=True, seed=0):
    """A randomly-initialized 81ch/42-scalar sighted net — the --smoke plumbing
    net (proves the fair-net path end-to-end without any training)."""
    import torch
    from carcassonne_ai.network import CarcassonneNet
    torch.manual_seed(seed)
    net = CarcassonneNet(
        n_input_channels=81, n_scalar_features=42,
        value_global_pool=value_global_pool,
    ).to(device)
    net.eval()
    return net

EVAL_ROOT = REPO / "data" / "classical_search"
RUNG_C = DEFAULT_C  # 3.0 — the CL-022 rung's HeuristicMCTS exploration constant
EXACT_BUDGET = int(os.environ.get("CARCASSONNE_EXACT_BUDGET", "2000000"))


# --------------------------------------------------------------------------- #
# CURVE125 — the PRODUCTION champion leaf, for the `fair-netprior` CANDIDATE and   #
# for BOTH sides of a head-to-head (--opponent fair-champion / net).               #
#                                                                                 #
# ⚠️ `_CANON_ENV` above pins the OLD curve100 (-8,-4,-1,0,2,3,4,5). That is CORRECT #
# and MUST NOT change: it resolves DEFAULT_CONFIG, which is the fixed h800 rung —  #
# the CL-022 ruler. The ruler must stay put.                                       #
#                                                                                  #
# But the distilled nets were trained against the PRODUCTION curve125 champion      #
# (scripts/distill_flywheel/champ_env.sh), so the frozen leaf VALUE inside the      #
# fair-netprior evaluator must be curve125 to match what the net was distilled      #
# against. We therefore inject curve125 IN-PROCESS on the candidate side only —     #
# exactly the --cand-leaf-json mechanism (dataclasses.replace on DEFAULT_CONFIG).   #
#                                                                                   #
# HEAD-TO-HEAD (--opponent != h800) injects the SAME curve125 cfg on the OPPONENT    #
# side too, via the same in-process mechanism and a SEPARATE cfg object: in a direct  #
# match both sides ARE production agents, so a curve100 opponent would be comparing   #
# the candidate against an agent nobody ships. The injection stays per-side —         #
# DEFAULT_CONFIG never moves, so the `h800` default path is untouched and the ruler   #
# survives even when both sides are on curve125.                                      #
#                                                                                   #
# ⚠️ Do NOT instead `source champ_env.sh`: _CANON_ENV uses os.environ.setdefault, so  #
# a pre-set CARCASSONNE_V29_MEEPLE_CURVE would win and move DEFAULT_CONFIG — i.e.    #
# move the RUNG to curve125 too, silently invalidating the ruler and every           #
# cross-arm comparison. The in-process override cannot do that. `_assert_rung_is_ruler`
# below enforces this even if the caller sources champ_env.sh anyway.
#
# TWO HASH DIALECTS (verified 2026-07-16 — they describe the SAME leaf function):
#   * a36d2e15a3b3d71d = c5_leaf_override._leaf_hash(candidate) — THIS harness's
#     dialect (meeple_k=2.0 from _CANON_ENV). Corroborated by tests/test_t3_optuna.py
#     CURVE125_LEAF_HASH and by every real C7 curve125 manifest (c7_s1_*/manifest.json
#     champ_leaf_hash) — so a fair-netprior cell is directly comparable to those cells.
#   * 6dfffd57051690f2 = measurement_infra.snapshot._frozen_config_hash(candidate with
#     meeple_k=0.0) — the champ_env.sh / distill-gen dialect (a DIFFERENT hash function
#     AND champ_env.sh deliberately does not export CARCASSONNE_V25_MEEPLE_K, so it
#     resolves meeple_k=0.0). meeple_k is INERT under a non-null curve — measured
#     byte-identical leaf values over 240 evals — so this is the same leaf, re-expressed.
# We assert BOTH: the first proves comparability with the sibling fair cells, the
# second proves the candidate's frozen leaf IS the champion the nets were distilled
# against. Asserting only one would leave a real mis-leaf failure mode open.
CURVE125 = (-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25)
CURVE100 = (-8.0, -4.0, -1.0, 0.0, 2.0, 3.0, 4.0, 5.0)
CURVE125_LEAF_HASH = "a36d2e15a3b3d71d"        # _leaf_hash dialect (this harness)
CURVE125_FROZEN_HASH = "6dfffd57051690f2"      # _frozen_config_hash dialect (champ_env)
RUNG_CURVE100_LEAF_HASH = "42af12fce22e1a0f"   # the CL-022 h800 ruler, must not move


def _curve125_leaf_cfg():
    """The production curve125 champion leaf = env DEFAULT_CONFIG with ONLY the
    meeple curve replaced (the --cand-leaf-json mechanism, applied in-process)."""
    import dataclasses as _dc
    return _dc.replace(DEFAULT_CONFIG, v29_meeple_curve=CURVE125)


def _frozen_hash_champ_dialect(cfg):
    """`_frozen_config_hash` of `cfg` re-expressed in the champ_env.sh dialect
    (meeple_k=0.0 — inert under a non-null curve). Returns None if the
    measurement_infra snapshot helper isn't importable (provenance is best-effort;
    the _leaf_hash assert below is the hard gate)."""
    import dataclasses as _dc
    try:
        sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))
        from snapshot import _frozen_config_hash
    except Exception:
        return None
    return _frozen_config_hash(_dc.replace(cfg, meeple_k=0.0))


def _assert_netprior_leaf(cand_cfg, strict=True, side="candidate", tag="fair-netprior"):
    """Verify a side's leaf is the production curve125 champion, in BOTH hash
    dialects, and return the provenance dict for the manifest.

    Semantic check first (robust to LeafConfig dataclass drift, which is exactly what
    staled the PRODUCTION.yaml 158f17ff fingerprint), then the two hash strings.

    `side`/`tag` only label the messages: the SAME check runs for the fair-netprior
    candidate and for both sides of a head-to-head, so the two can never drift."""
    curve = cand_cfg.v29_meeple_curve
    if curve is None or tuple(float(x) for x in curve) != CURVE125:
        raise SystemExit(
            f"[{tag}] FATAL: {side} leaf curve is {curve!r}, expected curve125 "
            f"{CURVE125!r}. The distilled nets were trained against the curve125 champion; "
            "a curve100 frozen leaf would evaluate a different agent than was distilled."
        )
    lh = _leaf_hash(cand_cfg)
    fh = _frozen_hash_champ_dialect(cand_cfg)
    prov = {
        "curve": "curve125 (production champion, CL-051)",
        "leaf_hash": lh,
        "leaf_hash_expected": CURVE125_LEAF_HASH,
        "frozen_config_hash_champ_dialect": fh,
        "frozen_config_hash_expected": CURVE125_FROZEN_HASH,
        "note": ("meeple_k is inert under a non-null curve; the two dialects "
                 "(this harness meeple_k=2.0 vs champ_env.sh meeple_k=0.0) are the "
                 "SAME leaf function, verified byte-identical on real boards."),
    }
    bad = []
    if lh != CURVE125_LEAF_HASH:
        bad.append(f"_leaf_hash {lh} != expected {CURVE125_LEAF_HASH}")
    if fh is not None and fh != CURVE125_FROZEN_HASH:
        bad.append(f"_frozen_config_hash {fh} != expected {CURVE125_FROZEN_HASH}")
    if bad:
        msg = (f"[{tag}] {side} leaf hash drift: " + "; ".join(bad) +
               ". The curve VALUES matched, so this is most likely an additive "
               "LeafConfig field changing the hash shape (the 158f17ff precedent) — "
               "re-baseline the constants if so. Re-run with --allow-leaf-hash-drift "
               "to proceed on the semantic (curve-values) check alone.")
        if strict:
            raise SystemExit("FATAL: " + msg)
        print("[warn] " + msg, file=sys.stderr)
        prov["hash_drift_allowed"] = True
    return prov


def _assert_rung_is_ruler():
    """The fixed h800 rung is env DEFAULT_CONFIG and MUST remain the curve100 CL-022
    ruler. Sourcing champ_env.sh before this harness would set the curve env, and
    _CANON_ENV's setdefault would NOT override it -> the rung would silently move to
    curve125 and every arm's elo would be measured against a different yardstick.
    Fail loud (fair-netprior only; the fair/fair-net arms are untouched)."""
    curve = DEFAULT_CONFIG.v29_meeple_curve
    if curve is None or tuple(float(x) for x in curve) != CURVE100:
        raise SystemExit(
            f"[fair-netprior] FATAL: the h800 RUNG's leaf curve is {curve!r}, expected the "
            f"curve100 CL-022 ruler {CURVE100!r}. Did you `source champ_env.sh` before "
            "running? _CANON_ENV uses setdefault, so a pre-set CARCASSONNE_V29_MEEPLE_CURVE "
            "MOVES THE RULER. Unset it: the candidate's curve125 leaf is injected "
            "in-process, the rung must stay curve100."
        )
    return _leaf_hash(DEFAULT_CONFIG)


def _load_net_rep(path, device="cpu"):
    """Load a distilled policy net and INFER its representation from the checkpoint
    (`sighted` / `n_input_channels` / `n_scalar_features` are all recorded by the
    distill trainer). Returns (net, rep). Fails LOUD on an internally-inconsistent
    checkpoint rather than mis-encoding at every leaf.

    The rep is inferred, never assumed. Three valid distill reps exist:
      * SIGHTED         81ch / 42sc (10 base + 32 bag; include_farm_scalars is OFF —
                        the sighted vector carries NO farm scalars).
      * NON-SIGHTED     78ch / 10sc (the production warmstart rep).
      * NON-SIGHTED+farm 78ch / 12sc (RoD-v2 / "Step-E farm-scalar" rep = 10 base + 2
                        farm scalars, include_farm_scalars=True).
    Picking the wrong encoder silently feeds the policy head a wrong-width / mis-typed
    scalar vector, so include_farm_scalars is derived HERE (ckpt field if present, else
    the codebase convention (n_scalar>10) and not sighted — shared with
    eval_net_vs_heuristic / train_iter / run_selfplay_iter) and cross-checked against
    the ckpt's declared dims. The guard stays strict for genuinely-unknown combos."""
    import torch
    from carcassonne_ai.network import CarcassonneNet
    ck = torch.load(path, map_location=device, weights_only=False)
    n_ch = int(ck.get("n_input_channels", 78))
    n_sc = int(ck.get("n_scalar_features", 10))
    sighted = bool(ck.get("sighted", False))
    # The 2 farm scalars ride on the NON-SIGHTED rep ONLY (the sighted 42 = 10 base +
    # 32 bag, no farm scalars). Prefer the ckpt's explicit flag; else the standard
    # convention. A 78/12 net therefore resolves include_farm_scalars=True and is
    # encoded by Game(sighted=False, include_farm_scalars=True) -> 78ch/12sc.
    include_farm = bool(ck.get("include_farm_scalars", (n_sc > 10) and not sighted))
    # cross-check the ckpt's own fields against the encoder they imply
    probe = Game(sighted=sighted, include_farm_scalars=include_farm)
    exp_ch, exp_sc = probe.get_input_channels(), probe.get_scalar_feature_size()
    if (n_ch, n_sc) != (exp_ch, exp_sc):
        raise SystemExit(
            f"FATAL: checkpoint {path} is internally inconsistent — it declares "
            f"sighted={sighted} / include_farm_scalars={include_farm} (which implies "
            f"{exp_ch}ch/{exp_sc}sc) but carries n_input_channels={n_ch} / "
            f"n_scalar_features={n_sc}. Refusing to guess the representation."
        )
    net = CarcassonneNet(
        n_filters=ck.get("n_filters", 96), n_blocks=ck.get("n_blocks", 6),
        n_input_channels=n_ch, n_scalar_features=n_sc,
        value_global_pool=bool(ck.get("value_global_pool", False)),
    ).to(device)
    net.load_state_dict(ck["model_state"])
    net.eval()
    rep = {"sighted": sighted, "n_input_channels": n_ch, "n_scalar_features": n_sc,
           "include_farm_scalars": include_farm,
           "value_global_pool": bool(ck.get("value_global_pool", False)),
           "iter": ck.get("iter"), "provenance": ck.get("provenance")}
    return net, rep


def _random_net_rep(sighted=True, device="cpu", value_global_pool=True, seed=0):
    """A randomly-initialized net at the requested rep — the --smoke plumbing net
    (proves the fair-netprior path end-to-end without any training)."""
    import torch
    from carcassonne_ai.network import CarcassonneNet
    torch.manual_seed(seed)
    probe = Game(sighted=sighted)
    n_ch, n_sc = probe.get_input_channels(), probe.get_scalar_feature_size()
    net = CarcassonneNet(
        n_input_channels=n_ch, n_scalar_features=n_sc,
        value_global_pool=value_global_pool,
    ).to(device)
    net.eval()
    return net, {"sighted": bool(sighted), "n_input_channels": n_ch,
                 "n_scalar_features": n_sc, "value_global_pool": bool(value_global_pool),
                 "iter": None, "provenance": "RANDOM (smoke plumbing net)"}


# --------------------------------------------------------------------------- #
# Marginalized (FAIR) endgame handoff — mirrors eval_puct_priors._ExactHandoff  #
# but mode="marginalized"/alphabeta=False (the honest hidden-bag solve). Shared  #
# by BOTH the fair and clair champion arms so the endgame is identical and the   #
# clairvoyance tax isolates the search PREFIX. Generalized over the prefix agent #
# (`.move(board) -> int`).                                                       #
# --------------------------------------------------------------------------- #
class _MarginalizedHandoff:
    def __init__(self, prefix, game_plain, K: int, budget: int = EXACT_BUDGET):
        self._prefix = prefix
        self._game = game_plain
        self._K = int(K)
        self._budget = budget
        self._latched = False
        self.latch_k = None
        self.prefix_moves = 0
        self.exact_moves = 0
        self.n_timeouts = 0
        self.solver_secs = 0.0
        self.solver_nodes = 0
        self.max_solve_secs = 0.0
        self.prefix_secs = 0.0

    def _should_latch(self, state) -> bool:
        return (self._K > 0 and _TILES_PHASE is not None
                and state.phase == _TILES_PHASE and k_remaining(state) <= self._K)

    def move(self, board) -> int:
        if not self._latched and self._should_latch(board.state):
            self._latched = True
            self.latch_k = k_remaining(board.state)
        if not self._latched:
            t0 = time.perf_counter()
            mv = int(self._prefix.move(board))
            self.prefix_secs += time.perf_counter() - t0
            self.prefix_moves += 1
            return mv
        t0 = time.perf_counter()
        try:
            res = S.solve(self._game, board, mode="marginalized",
                          budget=self._budget, alphabeta=False)
            dt = time.perf_counter() - t0
            self.solver_secs += dt
            self.max_solve_secs = max(self.max_solve_secs, dt)
            self.solver_nodes += res.nodes
            self.exact_moves += 1
            return int(min(res.optimal_actions))
        except S.BudgetExceeded:
            # Marginalized solve too big at this K: fall back to the FAIR prefix
            # for THIS decision only (stays latched, retries next ply).
            self.solver_secs += time.perf_counter() - t0
            self.n_timeouts += 1
            t1 = time.perf_counter()
            mv = int(self._prefix.move(board))
            self.prefix_secs += time.perf_counter() - t1
            self.prefix_moves += 1
            return mv


class _RungPrefix:
    """Fixed rung: HeuristicMCTS @ rung_sims, c=3.0, v2.9 Bmild_cap8 leaf. NO
    endgame handoff (the CL-022 yardstick convention)."""

    def __init__(self, game, sims, seed, leaf_cfg):
        self._m = HeuristicMCTS(game=game, simulations=sims, c=RUNG_C, seed=seed,
                                heur_leaf="v2_7", leaf_cfg=leaf_cfg)

    def move(self, board) -> int:
        self._m.clear()
        return int(self._m.best_action(board))


def _build_champ_cfg(c_puct, tau_p, leaf_quantize, final_select, value_norm,
                     leaf_cfg=None):
    # leaf_cfg=None -> env DEFAULT_CONFIG (byte-identical to the pre-C5 path); a
    # non-None value is the --cand-leaf-json CANDIDATE override for the FAIR agent
    # ONLY (the h800 rung always keeps DEFAULT_CONFIG — see _RungPrefix callers).
    return HeuristicPriorConfig(
        c_puct=c_puct, tau_p=tau_p, leaf_quantize=leaf_quantize,
        final_select=final_select, value_norm=value_norm,
        leaf_cfg=(leaf_cfg if leaf_cfg is not None else DEFAULT_CONFIG),
    )


def _build_fairnet_evaluator(game, cfg, net_mode, net_lambda, *, net=None,
                             handles=None, sighted_game=None):
    """C-cheap fair-net leaf evaluator: heuristic priors (BYTE-IDENTICAL to the
    `fair` arm) + a SWAPPED value. ``value_fn`` = the mover-POV sighted net value,
    sourced from EITHER a per-worker CPU net OR the carc-orch SHM handles (the
    server owns the only net; the worker discards the remote priors — the fair
    champion's heuristic softmax priors are unchanged).

    net_mode == "residual" -> value = heur_value + λ·value_fn(board), clipped (v2).
    net_mode == "replace"  -> value = value_fn(board) (the CL-049 REPLACE path,
                              generalized over net OR orch, kept for the A/B)."""
    if handles is not None:
        from carcassonne_ai.remote_evaluators import make_remote_single_evaluator
        if sighted_game is None:
            sighted_game = Game(sighted=True)
        remote = make_remote_single_evaluator(handles, sighted_game)

        def value_fn(board):
            return float(remote(board)[1])   # keep ONLY the value, discard priors
    elif net is not None:
        value_fn, sighted_game = make_sighted_net_value_fn(
            game, net, sighted_game=sighted_game)
    else:
        raise ValueError("fair-net evaluator needs a CPU net or orch handles")

    if net_mode == "residual":
        return make_heuristic_prior_evaluator_with_residual_value(
            game, cfg, value_fn, net_lambda)
    if net_mode == "replace":
        base = make_heuristic_prior_evaluator(game, cfg)

        def evaluator(board):
            priors, _heur = base(board)
            return priors, float(value_fn(board))

        evaluator.heur_prior_cfg = cfg
        evaluator.leaf_cfg = base.leaf_cfg
        evaluator.leaf_name = f"{base.leaf_name}_netvalue_replace"
        evaluator.root_logits = base.root_logits
        evaluator.heuristic_base = base
        evaluator.value_fn = value_fn
        return evaluator
    raise ValueError(f"unknown net_mode {net_mode!r}")


def _make_champion(info, cfg, sims, k_dets, K, seed, game, net=None,
                   net_mode="residual", net_lambda=0.25, handles=None,
                   sighted_game=None, rep=None, batch_size=1):
    """Build the champion side, wrapped in the fair marginalized endgame at K.

    info=="fair"     -> FairHeuristicPriorAgent prefix (fair PIMC, endgame OFF here —
                        the _MarginalizedHandoff owns the endgame so both arms share it).
    info=="fair-net" -> FairHeuristicPriorAgent prefix with IDENTICAL heuristic priors
                        but the learned deck-aware net value (C-cheap), wired via the
                        `evaluator=` hook. RESIDUAL (default) blends heur+λ·net; REPLACE
                        swaps the value outright. Value from a CPU net OR orch handles.
    info=="fair-netprior"
                     -> the MIRROR of fair-net (the distilled-agent arm): the NET's
                        POLICY head supplies the PUCT priors while the value stays the
                        FROZEN curve125 champion leaf (the severed value loop). `cfg`
                        MUST already carry the curve125 candidate leaf.
    info=="clair"    -> HeuristicPriorAgent prefix (clairvoyant PUCT on the true deck)."""
    if info == "fair":
        prefix = FairHeuristicPriorAgent(game, cfg, sims=sims, k_dets=k_dets,
                                         seed=seed, exact_endgame=False)
    elif info == "fair-netprior":
        if net is None and handles is None:
            raise ValueError(
                "info=fair-netprior requires a loaded net (--net) or orch handles "
                "(--orch-shm-name)")
        # Encode rep: the explicit sighted_game (built per-side in _worker_init / _smoke
        # WITH include_farm_scalars) is authoritative. If only `rep` reached us, build the
        # encoder from it here — a bare `sighted=` bool CANNOT express the non-sighted
        # 78ch/12 (Step-E farm-scalar) rep, so relying on it would silently feed a
        # 12-scalar net a 10-scalar vector.
        if sighted_game is None and rep is not None:
            sighted_game = Game(sighted=bool(rep["sighted"]),
                                include_farm_scalars=bool(rep.get("include_farm_scalars", False)))
        _sighted_arg = (None if sighted_game is not None
                        else (bool(rep["sighted"]) if rep else None))
        evaluator = make_fair_net_prior_evaluator(
            cfg, net=net, handles=handles, sighted_game=sighted_game,
            sighted=_sighted_arg,
        )
        # LATENCY (2026-07-16): batch_size>1 collects that many leaves under virtual loss
        # -> ONE orch forward instead of a blocking IPC+GPU round-trip per expansion. Only
        # the net-prior CANDIDATE batches; the fair-champion opponent is net-free + serial.
        batch_evaluator = (
            make_fair_net_prior_batch_evaluator(
                cfg, net=net, handles=handles, sighted_game=sighted_game,
                sighted=_sighted_arg)
            if batch_size > 1 else None)
        prefix = FairHeuristicPriorAgent(game, cfg, sims=sims, k_dets=k_dets,
                                         seed=seed, exact_endgame=False,
                                         evaluator=evaluator,
                                         batch_size=batch_size,
                                         batch_evaluator=batch_evaluator)
    elif info == "fair-net":
        if net is None and handles is None:
            raise ValueError(
                "info=fair-net requires a loaded net (--net) or orch handles "
                "(--orch-shm-name)")
        evaluator = _build_fairnet_evaluator(
            game, cfg, net_mode, net_lambda, net=net, handles=handles,
            sighted_game=sighted_game)
        prefix = FairHeuristicPriorAgent(game, cfg, sims=sims, k_dets=k_dets,
                                         seed=seed, exact_endgame=False,
                                         evaluator=evaluator)
    else:  # clair
        prefix = HeuristicPriorAgent(game, cfg, simulations=(sims * k_dets), seed=seed)
    return _MarginalizedHandoff(prefix, Game(enable_legal_moves_cache=True), K)


# --------------------------------------------------------------------------- #
# OPPONENT (--opponent) — the non-candidate seat.                              #
# --------------------------------------------------------------------------- #
OPPONENT_MODES = ("h800", "fair-champion", "net")
_HEAD_TO_HEAD = ("fair-champion", "net")


def _make_opponent(opponent, cfg_dict, sims, k_dets, K, rung_sims, seed,
                   opp_leaf_cfg=None, net=None, handles=None, sighted_game=None,
                   rep=None):
    """Build the OPPONENT side.

    opponent=="h800"          -> the fixed CL-022 rung: HeuristicMCTS @ rung_sims on
                                 env DEFAULT_CONFIG (curve100). BYTE-IDENTICAL to the
                                 pre-`--opponent` construction — the ruler never takes
                                 a leaf override and never gets an endgame.
    opponent=="fair-champion" -> the PRODUCTION champion: FairHeuristicPriorAgent with
                                 HEURISTIC softmax priors on the curve125 leaf
                                 (`opp_leaf_cfg`), same budget + same marginalized
                                 endgame handoff at K as the candidate. Against an
                                 `--info fair-netprior` candidate this is a PURE
                                 prior-swap: only the prior source differs.
    opponent=="net"           -> a SECOND distilled net as a fair-netprior agent (net
                                 POLICY priors + the frozen curve125 leaf value). Its
                                 `rep`/`sighted_game` are resolved from ITS OWN
                                 checkpoint, so a cross-rep (81ch vs 78ch) match
                                 encodes each side on its own encoder.

    The opponent's search knobs ride on the SAME `cfg_dict` as the candidate — that is
    what makes a head-to-head a clean single-variable swap; only the leaf cfg is
    injected per-side. Those knobs DEFAULT to the production champion's, so a default
    invocation is literally "vs the shipped champion"; `_prod_deviations` warns if a
    sweep moved them. `seed+1` mirrors the rung's historical seed offset, so the two
    sides never share a determinization stream.
    """
    if opponent == "h800":
        return _RungPrefix(Game(enable_legal_moves_cache=True), rung_sims, seed + 1,
                           DEFAULT_CONFIG)
    if opponent not in _HEAD_TO_HEAD:
        raise ValueError(f"unknown opponent mode {opponent!r}")
    opp_cfg = _cfg_from_dict(cfg_dict, opp_leaf_cfg)
    info = "fair" if opponent == "fair-champion" else "fair-netprior"
    return _make_champion(info, opp_cfg, sims, k_dets, K, seed + 1,
                          Game(enable_legal_moves_cache=True), net=net,
                          handles=handles, sighted_game=sighted_game, rep=rep)


# The PRODUCTION champion's search knobs (governance/PRODUCTION.yaml). These are ALSO
# the argparse defaults, so a default head-to-head invocation IS "vs the shipped
# champion"; `_prod_deviations` exists to catch the case where a sweep moved them.
PROD_KNOBS = {"c_puct": 1.5, "tau_p": 5.0, "leaf_quantize": "float",
              "value_norm": 15.0, "k_dets": 4, "sims": 688}


def _prod_deviations(args):
    """Which shared search knobs differ from governance/PRODUCTION.yaml. Empty list ==
    the head-to-head opponent is literally the shipped champion config."""
    out = []
    for k, want in PROD_KNOBS.items():
        got = getattr(args, k)
        if isinstance(want, float) and float(got) != want:
            out.append(f"{k}={got:g} (production {want:g})")
        elif not isinstance(want, float) and got != want:
            out.append(f"{k}={got} (production {want})")
    return out


def _opp_label(args, opp_rep=None):
    """Human label for the opponent side (summary header + manifest)."""
    if args.opponent == "h800":
        return f"HeuristicMCTS(h{args.rung_sims})"
    if args.opponent == "fair-champion":
        return (f"FAIR PRODUCTION CHAMPION (FairHeuristicPriorAgent, heuristic priors, "
                f"curve125 leaf, k{args.k_dets}x{args.sims})")
    rep = ("?" if opp_rep is None
           else ("sighted" if opp_rep["sighted"] else "non-sighted"))
    return (f"FAIR NET-PRIOR agent ({Path(args.opp_net).name}, {rep} rep, curve125 leaf, "
            f"k{args.k_dets}x{args.sims})")


def _opp_stats(opp):
    """Instrumentation read-out that works for BOTH opponent shapes: `_RungPrefix`
    (no endgame, no counters -> zeros) and `_MarginalizedHandoff` (prefix/exact split).
    getattr-with-default keeps the h800 GameResult fields exactly as they were."""
    return {
        "opp_prefix_moves": int(getattr(opp, "prefix_moves", 0)),
        "opp_exact_moves": int(getattr(opp, "exact_moves", 0)),
        "opp_prefix_secs": round(float(getattr(opp, "prefix_secs", 0.0)), 3),
        "opp_solver_secs": round(float(getattr(opp, "solver_secs", 0.0)), 3),
        "opp_timeouts": int(getattr(opp, "n_timeouts", 0)),
        "opp_latch_k": getattr(opp, "latch_k", None),
    }


# _leaf_hash / _leaf_dict / _load_cand_leaf_cfg / _assert_cy_float_path are imported
# from the shared c5_leaf_override module (above) — identical to eval_puct_priors.py.


# --------------------------------------------------------------------------- #
@dataclass
class GameResult:
    seed: int
    a_seat: int            # seat the CANDIDATE (champion) plays this game
    info: str              # fair | clair | fair-net | fair-netprior
    exact_k: int
    k_dets: int
    sims: int
    rung_sims: int
    score_p0: int
    score_p1: int
    diff: int              # candidate - opponent (== champion - rung when opponent=h800)
    won_by_champ: bool
    drew: bool
    elapsed_s: float
    moves: int
    deck_hash: str = ""
    # champion instrumentation
    champ_prefix_moves: int = 0
    champ_exact_moves: int = 0
    champ_prefix_secs: float = 0.0
    champ_solver_secs: float = 0.0
    champ_timeouts: int = 0
    # opponent instrumentation. `rung_moves`/`rung_secs` keep their names and meaning
    # (opponent moves / opponent wall-clock) for reader compatibility; the `opp_*`
    # fields below are ADDITIVE and stay 0/None for the h800 rung (which has no
    # endgame handoff and no counters), so an h800 row is unchanged in every field
    # that existed before --opponent.
    rung_moves: int = 0
    rung_secs: float = 0.0
    latch_k: int | None = None
    opponent: str = "h800"
    opp_prefix_moves: int = 0
    opp_exact_moves: int = 0
    opp_prefix_secs: float = 0.0
    opp_solver_secs: float = 0.0
    opp_timeouts: int = 0
    opp_latch_k: int | None = None


def _result_path(out: Path, seed: int, a_seat: int) -> Path:
    return out / f"seed{seed:012d}_a{a_seat}.json"


def _try_load(p: Path):
    if p.exists():
        try:
            return GameResult(**json.load(open(p)))
        except Exception:
            p.unlink(missing_ok=True)
    return None


def _save(p: Path, r: GameResult):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.stem}.{socket.gethostname()}.{os.getpid()}.partial.json")
    json.dump(asdict(r), open(tmp, "w"))
    tmp.replace(p)


_W: dict = {}


def _worker_init(info, champ_cfg_dict, sims, k_dets, exact_k, rung_sims,
                 shared_claim, claim_host, claim_stale, net_ckpt=None,
                 net_mode="residual", net_lambda=0.25, orch_shm_name="", id_q=None,
                 cand_leaf_cfg=None, rep=None, opponent="h800", opp_leaf_cfg=None,
                 opp_net_ckpt=None, opp_rep=None, opp_orch_shm_name="", batch_size=1):
    _W["info"] = info
    # within-search leaf batching for the net-prior CANDIDATE (1 = serial byte-exact).
    _W["batch_size"] = batch_size
    _W["champ_cfg_dict"] = champ_cfg_dict
    # candidate-side leaf override (--cand-leaf-json; None -> DEFAULT_CONFIG). Reaches
    # ONLY the FAIR champion's search (via _cfg_from_dict below); the rung stays DEFAULT.
    _W["cand_leaf_cfg"] = cand_leaf_cfg
    _W["sims"] = sims
    _W["k_dets"] = k_dets
    _W["exact_k"] = exact_k
    _W["rung_sims"] = rung_sims
    _W["shared_claim"] = shared_claim
    _W["claim_host"] = claim_host
    _W["claim_stale"] = claim_stale
    _W["net_mode"] = net_mode
    _W["net_lambda"] = net_lambda
    _W["net"] = None
    _W["handles"] = None
    _W["sighted_game"] = None
    _W["rep"] = rep
    # opponent side (--opponent; "h800" -> nothing to wire, the rung is net-free)
    _W["opponent"] = opponent
    _W["opp_leaf_cfg"] = opp_leaf_cfg
    _W["opp_rep"] = opp_rep
    _W["opp_net"] = None
    _W["opp_handles"] = None
    _W["opp_sighted_game"] = None
    # ONE id per worker, shared by both SHM connections: the candidate and opponent
    # servers are separate processes (a server owns exactly one net), each sized for
    # `workers` slots, so slot w on each is this worker's. Popping twice would exhaust
    # the queue and hand a second worker the same slot.
    _wid = id_q.get() if (id_q is not None and (orch_shm_name or opp_orch_shm_name)) else None
    if info == "fair-netprior":
        # The distilled-agent arm. The rep (sighted 81ch/42 vs non-sighted 78ch/10) was
        # resolved in main() from the CHECKPOINT and is passed down, so every worker
        # encodes exactly the rep the net was trained on.
        if orch_shm_name:
            # carc-orch SHM: the GPU server owns the only net and returns masked-softmax
            # PRIORS; the value is the local frozen leaf. Size the SHM slots from the
            # RESOLVED rep — hardcoding 81/42 would corrupt a non-sighted server's I/O.
            from carcassonne_ai.shm_eval_handles import connect_shm
            _W["handles"] = connect_shm(orch_shm_name, _wid,
                                        int(rep["n_scalar_features"]),
                                        int(rep["n_input_channels"]))
            _W["sighted_game"] = Game(sighted=bool(rep["sighted"]))
        elif net_ckpt:
            _W["net"], _loaded = _load_net_rep(net_ckpt, device="cpu")
            if bool(_loaded["sighted"]) != bool(rep["sighted"]):
                raise SystemExit(
                    f"FATAL: worker re-loaded {net_ckpt} with sighted={_loaded['sighted']} "
                    f"but main() resolved sighted={rep['sighted']}")
            _W["sighted_game"] = Game(sighted=bool(rep["sighted"]))
    elif info == "fair-net" and orch_shm_name:
        # carc-orch SHM orchestrator: the server owns the only (GPU) net; this worker
        # is CPU-only and reads the sighted (81ch/42-scalar) VALUE over shared memory.
        # Each worker pops a unique SHM slot from id_q (mirrors clairvoyance_gap /
        # eval_m2_net_vs_net). Keep CUDA hidden (the _CANON_ENV sets it "").
        from carcassonne_ai.shm_eval_handles import connect_shm
        _W["handles"] = connect_shm(orch_shm_name, _wid, 42, 81)
        _W["sighted_game"] = Game(sighted=True)
    elif info == "fair-net" and net_ckpt:
        # per-worker net-on-CPU copy (the eval env hides CUDA; a 7M net ~30MB/worker),
        # loaded once per process, reused across games.
        _W["net"] = _load_net(net_ckpt, device="cpu")

    # --- opponent side. `fair-champion` is net-free (heuristic priors), so only the
    #     `net` opponent needs a net/handles — mirrored from the candidate wiring
    #     above, but keyed on the OPPONENT's own rep (a cross-rep 81ch-vs-78ch match
    #     is the whole point of the net-vs-net cell, so nothing here may be shared).
    if opponent == "net":
        if opp_orch_shm_name:
            from carcassonne_ai.shm_eval_handles import connect_shm
            _W["opp_handles"] = connect_shm(opp_orch_shm_name, _wid,
                                            int(opp_rep["n_scalar_features"]),
                                            int(opp_rep["n_input_channels"]))
            _W["opp_sighted_game"] = Game(
                sighted=bool(opp_rep["sighted"]),
                include_farm_scalars=bool(opp_rep.get("include_farm_scalars", False)))
        elif opp_net_ckpt:
            _W["opp_net"], _oloaded = _load_net_rep(opp_net_ckpt, device="cpu")
            if bool(_oloaded["sighted"]) != bool(opp_rep["sighted"]):
                raise SystemExit(
                    f"FATAL: worker re-loaded opponent {opp_net_ckpt} with "
                    f"sighted={_oloaded['sighted']} but main() resolved "
                    f"sighted={opp_rep['sighted']}")
            _W["opp_sighted_game"] = Game(
                sighted=bool(opp_rep["sighted"]),
                include_farm_scalars=bool(opp_rep.get("include_farm_scalars", False)))


def _cfg_from_dict(d, leaf_cfg=None):
    return _build_champ_cfg(d["c_puct"], d["tau_p"], d["leaf_quantize"],
                            d["final_select"], d["value_norm"], leaf_cfg)


def _play_one(args) -> GameResult | None:
    out_str, seed, a_seat = args
    out = Path(out_str)
    p = _result_path(out, seed, a_seat)
    cached = _try_load(p)
    if cached is not None:
        return cached
    if _W.get("shared_claim"):
        if not _try_claim(p.with_suffix(".claim"), _W["claim_host"], _W["claim_stale"]):
            return None

    import random
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True)  # referee / deck driver
    board = game.get_init_board()
    dh = deck_hash(board)

    cfg = _cfg_from_dict(_W["champ_cfg_dict"], _W.get("cand_leaf_cfg"))
    champ = _make_champion(_W["info"], cfg, _W["sims"], _W["k_dets"], _W["exact_k"],
                           seed, Game(enable_legal_moves_cache=True),
                           net=_W.get("net"), net_mode=_W["net_mode"],
                           net_lambda=_W["net_lambda"], handles=_W.get("handles"),
                           sighted_game=_W.get("sighted_game"), rep=_W.get("rep"),
                           batch_size=_W.get("batch_size", 1))
    rung = _make_opponent(
        _W.get("opponent", "h800"), _W["champ_cfg_dict"], _W["sims"], _W["k_dets"],
        _W["exact_k"], _W["rung_sims"], seed, opp_leaf_cfg=_W.get("opp_leaf_cfg"),
        net=_W.get("opp_net"), handles=_W.get("opp_handles"),
        sighted_game=_W.get("opp_sighted_game"), rep=_W.get("opp_rep"))

    t0 = time.perf_counter()
    moves = 0
    rung_moves = 0
    rung_secs = 0.0
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        if cur == a_seat:
            action = champ.move(board)
        else:
            r0 = time.perf_counter()
            action = rung.move(board)
            rung_secs += time.perf_counter() - r0
            rung_moves += 1
        board, _ = game.get_next_state(board, action)
        moves += 1
    elapsed = time.perf_counter() - t0
    s0, s1 = board.state.scores
    diff = (s0 - s1) if a_seat == 0 else (s1 - s0)
    r = GameResult(
        seed=seed, a_seat=a_seat, info=_W["info"], exact_k=_W["exact_k"],
        k_dets=_W["k_dets"], sims=_W["sims"], rung_sims=_W["rung_sims"],
        score_p0=int(s0), score_p1=int(s1), diff=int(diff),
        won_by_champ=(diff > 0), drew=(diff == 0), elapsed_s=round(elapsed, 3),
        moves=moves, deck_hash=dh,
        champ_prefix_moves=champ.prefix_moves, champ_exact_moves=champ.exact_moves,
        champ_prefix_secs=round(champ.prefix_secs, 3),
        champ_solver_secs=round(champ.solver_secs, 3),
        champ_timeouts=champ.n_timeouts,
        rung_moves=rung_moves, rung_secs=round(rung_secs, 3),
        latch_k=champ.latch_k,
        opponent=_W.get("opponent", "h800"), **_opp_stats(rung),
    )
    _save(p, r)
    return r


# --------------------------------------------------------------------------- #
def _paired_z(results):
    """Paired z on per-deck seat-balanced margin (= eval_puct_priors._paired_z)."""
    by_seed = {}
    for r in results:
        by_seed.setdefault(r.seed, {})[r.a_seat] = r.diff
    ds = [(v[0] + v[1]) / 2.0 for v in by_seed.values() if 0 in v and 1 in v]
    if len(ds) < 2:
        return None, None, 0
    mean = sum(ds) / len(ds)
    var = sum((d - mean) ** 2 for d in ds) / (len(ds) - 1)
    se = math.sqrt(var / len(ds))
    z = mean / se if se > 0 else float("nan")
    return mean, z, len(ds)


def _summary(results, info, exact_k, k_dets, sims, rung_sims, opponent="h800",
             opp_label=None):
    n = len(results)
    w = sum(1 for r in results if r.won_by_champ)
    d = sum(1 for r in results if r.drew)
    losses = n - w - d
    avg = sum(r.diff for r in results) / n
    wr = (w + 0.5 * d) / n
    wr_se = math.sqrt(0.25 / n)
    wr_z = (wr - 0.5) / wr_se if wr_se > 0 else float("nan")
    if 0 < wr < 1:
        elo = 400.0 * math.log10(wr / (1 - wr))
        elo_sig = (400.0 / math.log(10)) * math.sqrt(wr * (1 - wr) / n) / (wr * (1 - wr))
    else:
        elo, elo_sig = math.copysign(800.0, wr - 0.5), float("nan")
    mean_d, z, npair = _paired_z(results)
    champ_latched = sum(1 for r in results if r.champ_exact_moves > 0)
    champ_ms = (sum(r.champ_prefix_secs for r in results) /
                max(1, sum(r.champ_prefix_moves for r in results))) * 1e3
    # ⚠️ `rung_secs`/`rung_moves` are timed by the DRIVER around opponent.move(), so they
    # include the marginalized ENDGAME SOLVE, whereas champ_prefix_secs is measured
    # INSIDE the handoff and excludes it. For the h800 rung that is a distinction without
    # a difference (no endgame -> rung_secs IS prefix time) and the historical number is
    # preserved. For a head-to-head opponent it is NOT: charging one side's solver time
    # into a "prefix ms/move" comparison against the other side's solver-free prefix made
    # two IDENTICAL agents look 4x apart. Use the handoff's own prefix counters instead.
    if opponent in _HEAD_TO_HEAD:
        rung_ms = (sum(r.opp_prefix_secs for r in results) /
                   max(1, sum(r.opp_prefix_moves for r in results))) * 1e3
    else:
        rung_ms = (sum(r.rung_secs for r in results) /
                   max(1, sum(r.rung_moves for r in results))) * 1e3
    solver_pergame = sum(r.champ_solver_secs for r in results) / n
    if opp_label is None:
        opp_label = (f"HeuristicMCTS(h{rung_sims})" if opponent == "h800"
                     else f"{opponent}")
    print()
    print(f"=== FAIR-PUCT[{info}] (K={exact_k}, k_dets={k_dets}, sims={sims}, "
          f"total~{k_dets * sims}) vs {opp_label} ===")
    print(f"games: {n}   candidate: {w}W / {d}D / {losses}L   winrate {wr:.3f} (z={wr_z:+.2f})")
    print(f"avg score diff (candidate - opponent): {avg:+.2f}")
    print(f"ELO: {elo:+.1f}  (+/- {elo_sig:.1f} 1sigma)")
    if mean_d is not None:
        print(f"PAIRED: {npair} decks   mean seat-balanced margin {mean_d:+.2f}   z = {z:+.2f}")
    print(f"prefix ms/move: candidate {champ_ms:.0f}  opponent {rung_ms:.0f}  "
          f"(ratio {champ_ms/max(1e-9,rung_ms):.2f}x)")
    print(f"fair endgame: candidate latched {champ_latched}/{n} games, "
          f"{solver_pergame:.2f}s solver/game, "
          f"timeouts={sum(r.champ_timeouts for r in results)}")
    if opponent in _HEAD_TO_HEAD:
        _opp_latched = sum(1 for r in results if r.opp_exact_moves > 0)
        _opp_solver = sum(r.opp_solver_secs for r in results) / n
        print(f"fair endgame: opponent  latched {_opp_latched}/{n} games, "
              f"{_opp_solver:.2f}s solver/game, "
              f"timeouts={sum(r.opp_timeouts for r in results)}")
    if abs(elo) <= 35 and not math.isnan(elo_sig):
        print(f"  POWER NOTE: |elo|<=35 at n={n} (1σ≈±{elo_sig:.0f}); a >=35-elo verdict needs n>=400.")
    return {
        "info": info, "exact_k": exact_k, "k_dets": k_dets, "sims": sims,
        "total_sims": k_dets * sims, "rung_sims": rung_sims,
        # `opponent`/`opponent_label` are additive; `diff`-derived stats (winrate/elo/
        # paired_mean_margin) are ALWAYS candidate-minus-opponent, which for the
        # default h800 opponent is exactly the historical champion-minus-rung.
        "opponent": opponent, "opponent_label": opp_label,
        "n": n, "W": w, "D": d, "L": losses, "winrate": wr, "winrate_z": wr_z,
        "elo": elo, "elo_sig_1sigma": elo_sig, "avg_diff": avg,
        "paired_mean_margin": mean_d, "paired_z": z, "n_paired": npair,
        "champ_prefix_ms_per_move": champ_ms, "rung_ms_per_move": rung_ms,
        "champ_latched_games": champ_latched, "solver_secs_per_game": solver_pergame,
        "champ_timeouts": sum(r.champ_timeouts for r in results),
    }


def _build_work(seed_start, n, paired):
    if not paired:
        return [(seed_start + i, i % 2) for i in range(n)]
    work = []
    for i in range(n // 2):
        work.append((seed_start + i, 0))
        work.append((seed_start + i, 1))
    return work


# --------------------------------------------------------------------------- #
def _smoke(args, cand_leaf_cfg=None, rep=None, opp_leaf_cfg=None, opp_rep=None,
           opp_label=None) -> int:
    """Single-process plumbing + fair-handoff-fires proof: play `games` paired
    games, print move/handoff counts, assert the fair marginalized endgame fired,
    and print an elo/z summary. Exits 0 on success.

    `cand_leaf_cfg` / `rep` / `opp_leaf_cfg` / `opp_rep` are resolved by main() (the
    per-side curve125 injection + the checkpoint-inferred representations) and passed
    down, so the smoke exercises the SAME leaves and the SAME reps the real run would.

    ⚠️ The smoke is SINGLE-PROCESS: it never runs `_worker_init`, so it does NOT cover
    worker rep-passing or SHM slot sizing. Drive a small real `--workers 2` run to
    exercise those."""
    cfg = _build_champ_cfg(args.c_puct, args.tau_p, args.leaf_quantize,
                           args.final_select, args.value_norm, cand_leaf_cfg)
    champ_cfg_dict = {"c_puct": args.c_puct, "tau_p": args.tau_p,
                      "leaf_quantize": args.leaf_quantize,
                      "final_select": args.final_select, "value_norm": args.value_norm}
    # opponent side: `fair-champion` is net-free; `net` loads its OWN checkpoint at
    # its OWN rep (never the candidate's).
    smoke_opp_net = None
    smoke_opp_game = None
    if args.opponent == "net":
        smoke_opp_net, opp_rep = _load_net_rep(args.opp_net, device="cpu")
        smoke_opp_game = Game(
            sighted=bool(opp_rep["sighted"]),
            include_farm_scalars=bool(opp_rep.get("include_farm_scalars", False)))
        print(f"[smoke] opponent = net {args.opp_net} | "
              f"rep={'SIGHTED' if opp_rep['sighted'] else 'NON-SIGHTED'} "
              f"{opp_rep['n_input_channels']}ch/{opp_rep['n_scalar_features']}sc "
              f"(inferred from ITS OWN ckpt) | priors=net_policy_head "
              f"value=FROZEN curve125 champion leaf")
    elif args.opponent == "fair-champion":
        print("[smoke] opponent = PRODUCTION fair champion (FairHeuristicPriorAgent, "
              "heuristic softmax priors, FROZEN curve125 champion leaf)")
    # fair-net smoke: load --net if given, else a randomly-initialized 81ch/42-scalar
    # net (pure plumbing proof — NO training). Other arms ignore the net.
    smoke_net = None
    smoke_sighted_game = None
    if args.info == "fair-net":
        smoke_net = (_load_net(args.net, device="cpu") if args.net
                     else _random_sighted_net(device="cpu",
                                              value_global_pool=args.value_global_pool))
        print(f"[smoke] fair-net value = {'ckpt ' + args.net if args.net else 'RANDOM'} "
              f"81ch/42-scalar net (value_global_pool={args.value_global_pool}) "
              f"net_mode={args.net_mode} net_lambda={args.net_lambda:g}")
    elif args.info == "fair-netprior":
        # rep comes from the CHECKPOINT (main() resolved it); a random net for the
        # net-less plumbing smoke defaults to the sighted rep.
        if args.net:
            smoke_net, rep = _load_net_rep(args.net, device="cpu")
        else:
            smoke_net, rep = _random_net_rep(
                sighted=True, device="cpu", value_global_pool=args.value_global_pool)
        smoke_sighted_game = Game(sighted=bool(rep["sighted"]))
        print(f"[smoke] fair-netprior priors = {'ckpt ' + args.net if args.net else 'RANDOM'} "
              f"net | rep={'SIGHTED' if rep['sighted'] else 'NON-SIGHTED'} "
              f"{rep['n_input_channels']}ch/{rep['n_scalar_features']}sc "
              f"(value_global_pool={rep['value_global_pool']}) | value = FROZEN curve125 "
              f"champion leaf (NO net value)")
    print(f"[smoke] info={args.info} K={args.exact_k} k_dets={args.k_dets} sims={args.sims} "
          f"(total~{args.k_dets*args.sims}) | opponent={args.opponent}"
          + (f" (rung h{args.rung_sims} c{RUNG_C})" if args.opponent == "h800"
             else f" (k_dets={args.k_dets} sims={args.sims}, same fair machinery)"))
    import random
    results = []
    t0 = time.perf_counter()
    for i in range(max(1, args.games)):
        a_seat = i % 2
        seed = args.seed_start + (i // 2)
        random.seed(seed)
        game = Game(enable_legal_moves_cache=True)
        board = game.get_init_board()
        dh = deck_hash(board)
        champ = _make_champion(args.info, cfg, args.sims, args.k_dets, args.exact_k,
                               seed, Game(enable_legal_moves_cache=True), net=smoke_net,
                               net_mode=args.net_mode, net_lambda=args.net_lambda,
                               sighted_game=smoke_sighted_game, rep=rep,
                               batch_size=args.batch_size)
        rung = _make_opponent(
            args.opponent, champ_cfg_dict, args.sims, args.k_dets, args.exact_k,
            args.rung_sims, seed, opp_leaf_cfg=opp_leaf_cfg, net=smoke_opp_net,
            sighted_game=smoke_opp_game, rep=opp_rep)
        moves = 0
        rung_moves = 0
        rung_secs = 0.0
        while game.get_game_ended(board, 0) == 0.0:
            cur = board.state.current_player
            mask = game.get_valid_moves(board)
            if cur == a_seat:
                act = champ.move(board)
            else:
                r0 = time.perf_counter()
                act = rung.move(board)
                rung_secs += time.perf_counter() - r0
                rung_moves += 1
            assert mask[act], f"illegal action {act}"
            board, _ = game.get_next_state(board, act)
            moves += 1
        s0, s1 = board.state.scores
        diff = (s0 - s1) if a_seat == 0 else (s1 - s0)
        _os = _opp_stats(rung)
        results.append(GameResult(
            seed=seed, a_seat=a_seat, info=args.info, exact_k=args.exact_k,
            k_dets=args.k_dets, sims=args.sims, rung_sims=args.rung_sims,
            score_p0=int(s0), score_p1=int(s1), diff=int(diff),
            won_by_champ=(diff > 0), drew=(diff == 0), elapsed_s=0.0, moves=moves,
            deck_hash=dh, champ_prefix_moves=champ.prefix_moves,
            champ_exact_moves=champ.exact_moves, champ_prefix_secs=champ.prefix_secs,
            champ_solver_secs=champ.solver_secs, champ_timeouts=champ.n_timeouts,
            rung_moves=rung_moves, rung_secs=rung_secs, latch_k=champ.latch_k,
            opponent=args.opponent, **_os))
        print(f"[smoke] a_seat={a_seat}: {s0}-{s1} diff(cand-opp)={diff:+d} moves={moves} | "
              f"cand prefix/exact={champ.prefix_moves}/{champ.exact_moves} "
              f"latch_k={champ.latch_k} solver={champ.solver_secs:.2f}s to={champ.n_timeouts}"
              + ("" if args.opponent == "h800" else
                 f" | opp prefix/exact={_os['opp_prefix_moves']}/{_os['opp_exact_moves']} "
                 f"latch_k={_os['opp_latch_k']} solver={_os['opp_solver_secs']:.2f}s "
                 f"to={_os['opp_timeouts']}"))
        if args.exact_k > 0:
            assert champ.exact_moves > 0, \
                "champion never reached the fair exact endgame (K too small / rung got all the endgames?)"
        assert champ.prefix_moves > 0, "prefix search never ran (K too big?)"
        if args.opponent in _HEAD_TO_HEAD:
            # a head-to-head opponent is a production agent too: it must actually be
            # searching AND taking the same marginalized endgame handoff.
            assert _os["opp_prefix_moves"] > 0, \
                "opponent prefix search never ran (K too big?)"
            if args.exact_k > 0:
                assert _os["opp_exact_moves"] > 0, \
                    ("opponent never reached the fair exact endgame — both sides must "
                     "share the handoff for the match to be symmetric")

    summ = _summary(results, args.info, args.exact_k, args.k_dets, args.sims,
                    args.rung_sims, opponent=args.opponent, opp_label=opp_label)
    if args.out_root:
        out = Path(args.out_root) / (args.out_subdir or "fair_smoke_k2")
        out.mkdir(parents=True, exist_ok=True)
        json.dump(summ, open(out / "summary.json", "w"), indent=2)
        print(f"[smoke] wrote {out/'summary.json'}")
    print(f"[smoke] OK — fair plumbing + marginalized endgame verified "
          f"({time.perf_counter()-t0:.1f}s for {len(results)} games)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="eval_fair_puct")
    ap.add_argument("--info", choices=("fair", "clair", "fair-net", "fair-netprior"),
                    default="fair",
                    help="fair = FairHeuristicPriorAgent PIMC (deployable, default); "
                         "clair = clairvoyant champion (CL-022 CLAIR arm at champion config); "
                         "fair-net = fair PIMC with IDENTICAL heuristic priors but a learned "
                         "deck-aware net leaf VALUE (C-cheap; needs --net); "
                         "fair-netprior = the MIRROR (the distilled-agent STRENGTH arm): net "
                         "POLICY-head priors + the FROZEN curve125 champion leaf value (severed "
                         "value loop; needs --net; rep auto-inferred from the ckpt)")
    ap.add_argument("--opponent", choices=OPPONENT_MODES, default="h800",
                    help="WHO the candidate plays. h800 (DEFAULT, byte-unchanged) = the fixed "
                         "CL-022 HeuristicMCTS rung @ --rung-sims on the curve100 ruler leaf; "
                         "every pre-existing arm/result is an h800 result. fair-champion = a "
                         "DIRECT head-to-head vs the PRODUCTION champion (FairHeuristicPriorAgent, "
                         "heuristic softmax priors, curve125 leaf, same budget/machinery) — with "
                         "--info fair-netprior this is the pure PRIOR-SWAP 'did the distillation "
                         "work?' cell. net = head-to-head vs a SECOND distilled net (--opp-net) "
                         "run as a fair-netprior agent — the 'does the bag matter?' cell (each "
                         "side's rep inferred from its OWN ckpt, so cross-rep 81ch-vs-78ch works). "
                         "Both head-to-head modes resolve curve125 on BOTH sides and keep deck "
                         "pairing + seat alternation; diff is always candidate - opponent.")
    ap.add_argument("--opp-net", type=str, default=None,
                    help="--opponent net: path to the OPPONENT's distilled policy net. Its rep "
                         "(sighted 81ch/42 vs non-sighted 78ch/10) is inferred from THIS "
                         "checkpoint independently of --net, so a cross-rep match encodes each "
                         "side on its own encoder. Required for --opponent net.")
    ap.add_argument("--opp-orch-shm-name", type=str, default=None,
                    help="--opponent net: serve the OPPONENT's priors from a SECOND carc-orch SHM "
                         "eval-server (a server owns exactly one net, so a net-vs-net orch run "
                         "needs two servers with distinct --shm-name, each sized --n-ch/--n-scalar "
                         "for ITS OWN net's rep and --workers to match). Omit for a per-worker CPU "
                         "opponent net.")
    ap.add_argument("--net", type=str, default=None,
                    help="fair-net: path to the sighted (81ch/42-scalar) value-net checkpoint. "
                         "fair-netprior: path to the DISTILLED policy net (sighted 81ch/42 OR "
                         "non-sighted 78ch/10 — the rep is inferred from the checkpoint). "
                         "Under --smoke this may be omitted (a random net is used). "
                         "With --orch-shm-name it is NOT loaded per-worker (the server owns the "
                         "net) but is still recorded in the manifest for provenance.")
    ap.add_argument("--net-mode", choices=("replace", "residual"), default=None,
                    help="fair-net value combiner: residual (default, C-cheap v2) = "
                         "heur_value + net_lambda*net_value (clipped); replace (CL-049) = "
                         "net_value fully replaces the heuristic leaf value. "
                         "INAPPLICABLE to fair-netprior (that arm has no net value at all — "
                         "its value is the frozen champion leaf), which rejects it.")
    ap.add_argument("--net-lambda", type=float, default=None,
                    help="residual blend weight λ (net_mode=residual only). λ=0 is "
                         "byte-identical to the `fair` arm (a catastrophe pre-check).")
    ap.add_argument("--orch-shm-name", type=str, default=None,
                    help="fair-net arm: connect workers to the carc-orch SHM eval-server "
                         "(GPU-batched value) instead of loading a CPU net per worker. The "
                         "server (81ch/42-scalar sighted, --n-ch 81 --n-scalar 42) must be "
                         "started separately; run verify_sighted_orch_parity.py FIRST.")
    ap.add_argument("--value-global-pool", action="store_true", default=True,
                    help="fair-net --smoke random net: build with KataGo-style value global "
                         "pooling (the recommended C-cheap arch; default True)")
    ap.add_argument("--no-value-global-pool", dest="value_global_pool", action="store_false")
    ap.add_argument("--exact-k", type=int, default=2,
                    help="fair marginalized endgame handoff at k_remaining<=K (the A2 grid axis)")
    ap.add_argument("--k-dets", type=int, default=4, help="determinizations per move (fair PIMC); deploy default k4 (CL-054, 2026-07-13; was 8)")
    ap.add_argument("--sims", type=int, default=688, help="PUCT sims per determinization (k4×688=2752 total; was 344 at k8)")
    ap.add_argument("--batch-size", type=int, default=1,
                    help="fair-netprior CANDIDATE within-search leaf batching (LATENCY fix, "
                         "2026-07-16): >1 collects this many leaves under virtual loss -> ONE orch "
                         "forward per batch instead of a blocking round-trip per expansion. Default "
                         "1 = the byte-for-byte serial search (the +88.7 was measured at batch-1; "
                         "vloss CHANGES the search, so a batched run is a DIFFERENT — faster — agent). "
                         "ONLY the net-prior candidate batches; the fair-champion opponent stays serial. "
                         "SHM caps a request at MAX_K=8, so >8 chunks into ceil(N/8) round-trips.")
    ap.add_argument("--rung-sims", type=int, default=800, help="fixed HeuristicMCTS rung sims (CL-022=800)")
    # champion knobs (governance/PRODUCTION.yaml defaults)
    ap.add_argument("--c-puct", type=float, default=1.5)
    ap.add_argument("--tau-p", type=float, default=5.0)
    ap.add_argument("--leaf-quantize", choices=("int", "float"), default="float")
    ap.add_argument("--final-select", choices=("Q", "visits", "lcb"), default="visits")
    ap.add_argument("--value-norm", type=float, default=15.0)
    ap.add_argument("--cand-leaf-json", type=str, default=None,
                    help="C5 Stage-3: override ONLY the FAIR champion's leaf LeafConfig — "
                         "inline JSON (a '{...}' object of field->value, replace-fields on the "
                         "env DEFAULT_CONFIG) or a path to such a JSON file. The h800 rung ALWAYS "
                         "keeps env DEFAULT_CONFIG (the CL-022 ruler must not move). Absent -> "
                         "byte-identical to today (default-OFF). closure_p keys coerced to int, "
                         "v29_meeple_curve to a tuple (null -> curve OFF); the candidate must stay "
                         "on the Cython float leaf (object-forcing terms are rejected). Shares the "
                         "parser/guard with eval_puct_priors.py (c5_leaf_override.py). "
                         "e.g. curve125: '{\"v29_meeple_curve\": [-10,-5,-1.25,0,2.5,3.75,5,6.25]}'.")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--games", type=int, default=None, help="alias for --n (convenience)")
    ap.add_argument("--paired", action="store_true")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--seed-start", type=int, default=13_000_000_000)
    ap.add_argument("--allow-selfplay-seeds", action="store_true")
    ap.add_argument("--out-root", type=str, default=None)
    ap.add_argument("--out-subdir", type=str, default=None)
    ap.add_argument("--shared-claim", action="store_true")
    ap.add_argument("--claim-stale-secs", type=int, default=7200)
    ap.add_argument("--claim-host", type=str, default=socket.gethostname())
    ap.add_argument("--allow-leaf-hash-drift", action="store_true",
                    help="fair-netprior: downgrade the candidate curve125 leaf-HASH assert to a "
                         "warning (the curve-VALUES check still hard-fails). Only for a known "
                         "additive LeafConfig field change that reshapes the hash — see the "
                         "158f17ff precedent in scripts/distill_flywheel/champ_env.sh.")
    ap.add_argument("--summary-only", action="store_true")
    ap.add_argument("--no-results-csv", action="store_true",
                    help="do not append to experiments/results.csv (this eval NEVER writes it; "
                         "flag kept for launcher symmetry / explicit intent)")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args(argv)
    if args.games is not None:
        args.n = args.games
    if args.k_dets < 1:
        ap.error("--k-dets must be >= 1")
    if args.paired and args.n % 2 != 0:
        ap.error("--paired requires an even --n")
    if args.batch_size < 1:
        ap.error("--batch-size must be >= 1")
    if args.batch_size > 1 and args.info != "fair-netprior":
        # Only the fair-netprior candidate has a batched net-prior evaluator wired.
        # fair/clair have no per-leaf net round-trip; fair-net batches a VALUE net for
        # which no batch factory exists yet. Fail loud rather than silently ignore.
        ap.error("--batch-size > 1 only applies to --info fair-netprior "
                 f"(got --info {args.info}); it would be silently ignored otherwise")

    if args.orch_shm_name and args.info not in ("fair-net", "fair-netprior"):
        ap.error("--orch-shm-name only applies to --info fair-net / fair-netprior")

    # ---- opponent-mode validation -------------------------------------------------
    if args.opponent == "net" and not args.opp_net:
        ap.error("--opponent net requires --opp-net <checkpoint>")
    if args.opp_net and args.opponent != "net":
        ap.error("--opp-net only applies to --opponent net")
    if args.opp_orch_shm_name and args.opponent != "net":
        ap.error("--opp-orch-shm-name only applies to --opponent net")
    if args.opponent in _HEAD_TO_HEAD and args.info == "clair":
        # a clairvoyant candidate vs a fair opponent is a legitimate DIRECT tax
        # measurement, but it is NOT a prior-swap — say so rather than let it read as one.
        print("[warn] --info clair vs a FAIR head-to-head opponent measures the "
              "CLAIRVOYANCE advantage directly (the candidate sees the true deck, the "
              "opponent does not). This is NOT a like-for-like prior swap.",
              file=sys.stderr)

    # --net-mode / --net-lambda are INAPPLICABLE to fair-netprior: that arm has no net
    # value at all (its value is the FROZEN champion leaf — the severed value loop), so
    # a value-combiner knob would be silently inert. Reject rather than mislead.
    # (Sentinel defaults of None make "explicitly passed" detectable; the effective
    # defaults are restored below so the fair-net arm stays byte-identical.)
    if args.info == "fair-netprior":
        _inapplicable = [f for f, v in (("--net-mode", args.net_mode),
                                        ("--net-lambda", args.net_lambda)) if v is not None]
        if _inapplicable:
            ap.error(
                f"{' / '.join(_inapplicable)} {'is' if len(_inapplicable) == 1 else 'are'} "
                "inapplicable to --info fair-netprior: that arm takes its PRIORS from the net "
                "policy head and its VALUE from the FROZEN curve125 champion leaf — there is no "
                "net value to combine. Use --info fair-net for the net-VALUE arm.")
    elif args.net_mode is not None and args.info != "fair-net":
        ap.error("--net-mode only applies to --info fair-net")
    # restore the historical effective defaults (fair-net behavior byte-unchanged)
    if args.net_mode is None:
        args.net_mode = "residual"
    if args.net_lambda is None:
        args.net_lambda = 0.25

    # C5 Stage-3 candidate-leaf override (--cand-leaf-json). None -> the FAIR champion
    # keeps env DEFAULT_CONFIG (byte-identical to today). The h800 rung NEVER takes it.
    try:
        cand_leaf_cfg = _load_cand_leaf_cfg(args.cand_leaf_json)
        if cand_leaf_cfg is not None:
            _assert_cy_float_path(cand_leaf_cfg)
    except ValueError as e:
        ap.error(str(e))                       # messages already carry the flag name
    except (OSError, json.JSONDecodeError) as e:
        ap.error(f"--cand-leaf-json: {e}")

    # ---- FROZEN curve125 leaf injection. Two triggers, one mechanism:
    #   * --info fair-netprior : the CANDIDATE's frozen leaf must be the production
    #     curve125 champion (that is what the nets were distilled against), while the
    #     h800 rung stays the curve100 CL-022 ruler.
    #   * any head-to-head (--opponent != h800): BOTH sides are production agents, so
    #     both resolve curve125 (there is no rung to protect).
    # Injected IN-PROCESS (the --cand-leaf-json mechanism, per-side cfg objects) so the
    # env DEFAULT_CONFIG can never move. Explicit --cand-leaf-json still wins on the
    # CANDIDATE side only; the opponent/reference side never takes it.
    netprior_leaf_prov = None
    rung_ruler_hash = None
    opp_leaf_cfg = None
    opp_leaf_prov = None
    _h2h = args.opponent in _HEAD_TO_HEAD
    # The curve125 candidate injection fires for the fair-netprior arm (the net was
    # distilled against curve125) AND for any head-to-head (both sides are production
    # agents, so both must be the shipped curve125 champion leaf).
    if args.info == "fair-netprior" or _h2h:
        if not _h2h:
            # The rung is the ruler ONLY when there IS a rung. Head-to-head has no rung,
            # so this assert is skipped there — but the curve125 asserts below are
            # strictly stronger (they pin BOTH sides' actual resolved leaves), so nothing
            # goes unchecked. The h800 default path keeps the original hard gate.
            rung_ruler_hash = _assert_rung_is_ruler()
        if cand_leaf_cfg is None:
            cand_leaf_cfg = _curve125_leaf_cfg()
            _assert_cy_float_path(cand_leaf_cfg)
        netprior_leaf_prov = _assert_netprior_leaf(
            cand_leaf_cfg, strict=not args.allow_leaf_hash_drift, side="candidate",
            tag=(args.info if args.info == "fair-netprior" else "head-to-head"))
        if _h2h:
            # The OPPONENT is the production champion (or a second production-config
            # net): ALWAYS curve125, never the user's --cand-leaf-json (which is a
            # CANDIDATE-side knob — the reference side must not move with it, exactly
            # as the h800 rung never takes it).
            opp_leaf_cfg = _curve125_leaf_cfg()
            _assert_cy_float_path(opp_leaf_cfg)
            opp_leaf_prov = _assert_netprior_leaf(
                opp_leaf_cfg, strict=not args.allow_leaf_hash_drift, side="opponent",
                tag="head-to-head")
        if _h2h:
            print(f"[head-to-head] opponent={args.opponent}\n"
                  f"[head-to-head] candidate frozen leaf: curve125 "
                  f"leaf_hash={netprior_leaf_prov['leaf_hash']} "
                  f"frozen_config_hash="
                  f"{netprior_leaf_prov['frozen_config_hash_champ_dialect']} (champ_env dialect)\n"
                  f"[head-to-head] opponent  frozen leaf: curve125 "
                  f"leaf_hash={opp_leaf_prov['leaf_hash']} "
                  f"frozen_config_hash="
                  f"{opp_leaf_prov['frozen_config_hash_champ_dialect']} (champ_env dialect)\n"
                  f"[head-to-head] BOTH SIDES curve125: "
                  f"{'YES' if opp_leaf_prov['leaf_hash'] == netprior_leaf_prov['leaf_hash'] else 'NO'}"
                  f" | env DEFAULT_CONFIG (unmoved, no rung in play) "
                  f"leaf_hash={_leaf_hash(DEFAULT_CONFIG)}", flush=True)
        else:
            print(f"[fair-netprior] candidate frozen leaf: curve125 "
                  f"leaf_hash={netprior_leaf_prov['leaf_hash']} "
                  f"frozen_config_hash={netprior_leaf_prov['frozen_config_hash_champ_dialect']} "
                  f"(champ_env dialect) | h800 rung ruler leaf_hash={rung_ruler_hash} (curve100, "
                  f"unmoved)", flush=True)

    # ---- opponent side: resolve the OPPONENT's rep from ITS OWN checkpoint (never the
    # candidate's — the net-vs-net cell is deliberately cross-rep) + label the side.
    opp_rep = None
    if args.opponent == "net":
        _oprobe, opp_rep = _load_net_rep(args.opp_net, device="cpu")
        del _oprobe       # main() only needs the rep; workers load their own copy
        print(f"[head-to-head] opp_net={args.opp_net}\n"
              f"[head-to-head] opponent rep="
              f"{'SIGHTED' if opp_rep['sighted'] else 'NON-SIGHTED'} "
              f"{opp_rep['n_input_channels']}ch/{opp_rep['n_scalar_features']}sc "
              f"(inferred from ITS OWN checkpoint) | priors=net_policy_head "
              f"value=frozen_v29_curve125_leaf", flush=True)
    opp_label = _opp_label(args, opp_rep)

    # A head-to-head is only a clean single-variable swap if the two sides share every
    # search knob; those knobs default to the PRODUCTION champion's, so warn loudly if
    # a sweep has moved them off production (the opponent tracks them either way — the
    # A/B stays valid, but it is no longer "vs the shipped champion").
    if args.opponent in _HEAD_TO_HEAD:
        _off = _prod_deviations(args)
        if _off:
            print("[warn] --opponent " + args.opponent + ": the shared search config "
                  "deviates from governance/PRODUCTION.yaml (" + "; ".join(_off) + "). "
                  "BOTH sides use these values, so the swap stays single-variable, but "
                  "the opponent is NOT the shipped production champion — do not report "
                  "this cell as 'vs production'.", file=sys.stderr)

    if args.smoke:
        if args.orch_shm_name or args.opp_orch_shm_name:
            ap.error("--smoke does not drive the orch path (single-process CPU only); "
                     "run verify_sighted_orch_parity.py + an --orch-shm-name n=20 eval instead")
        return _smoke(args, cand_leaf_cfg, opp_leaf_cfg=opp_leaf_cfg, opp_rep=opp_rep,
                      opp_label=opp_label)

    if args.info in ("fair-net", "fair-netprior") and not args.net:
        # --net is required even under --orch-shm-name: the worker does NOT load it
        # (the server owns the net), but it is recorded in the manifest for provenance.
        ap.error(f"--info {args.info} requires --net <checkpoint> (except under --smoke)")

    # fair-netprior: resolve the REPRESENTATION from the checkpoint ONCE in main (the
    # workers re-load and cross-check against it). Inferring beats a flag: the ckpt is
    # self-describing, and a wrong rep is a silent mis-encode, not a crash.
    netprior_rep = None
    if args.info == "fair-netprior":
        _probe_net, netprior_rep = _load_net_rep(args.net, device="cpu")
        del _probe_net    # main() only needs the rep; workers load their own copy
        print(f"[fair-netprior] net={args.net}\n"
              f"[fair-netprior] rep={'SIGHTED' if netprior_rep['sighted'] else 'NON-SIGHTED'} "
              f"{netprior_rep['n_input_channels']}ch/{netprior_rep['n_scalar_features']}sc "
              f"(inferred from the checkpoint) | priors=net_policy_head "
              f"value=frozen_v29_curve125_leaf", flush=True)

    if not args.summary_only and not args.allow_selfplay_seeds:
        ep.assert_clean_eval_seed_range(args.seed_start, args.n)

    cfg = _build_champ_cfg(args.c_puct, args.tau_p, args.leaf_quantize,
                           args.final_select, args.value_norm, cand_leaf_cfg)
    champ_cfg_dict = {"c_puct": args.c_puct, "tau_p": args.tau_p,
                      "leaf_quantize": args.leaf_quantize,
                      "final_select": args.final_select, "value_norm": args.value_norm}

    # the `_vs_h{rung_sims}` segment is the OPPONENT identity; a head-to-head must NEVER
    # land in the same auto out-dir as the h800 cell at the same knobs (Trap 1). The
    # h800 tag is unchanged.
    if args.opponent == "h800":
        _vs = f"vs_h{args.rung_sims}"
    elif args.opponent == "fair-champion":
        _vs = "vs_fairchamp"
    else:
        _vs = f"vs_net-{Path(args.opp_net).stem}"
    tag = (f"fair_{args.info}_c{args.c_puct:g}_tau{args.tau_p:g}_{args.leaf_quantize}"
           f"_kd{args.k_dets}_s{args.sims}_{_vs}_k{args.exact_k}")
    if cand_leaf_cfg is not None:
        # a leaf A/B: keep the auto tag / default out-dir distinct per candidate leaf
        # so cells never silently share a directory (Trap 1). An explicit --out-subdir
        # (the Stage-3 launcher path, e.g. c5_s3_curve125_fair) still owns the dir name.
        tag = f"{tag}-leaf{_leaf_hash(cand_leaf_cfg)[:8]}"
    sub = args.out_subdir or tag
    root = Path(args.out_root) if args.out_root else EVAL_ROOT
    out = root / sub
    out.mkdir(parents=True, exist_ok=True)

    tasks = [(str(out), seed, a_seat)
             for seed, a_seat in _build_work(args.seed_start, args.n, args.paired)]

    if args.summary_only:
        results = [r for t in tasks if (r := _try_load(_result_path(out, t[1], t[2]))) is not None]
        if results:
            summ = _summary(results, args.info, args.exact_k, args.k_dets, args.sims,
                            args.rung_sims, opponent=args.opponent, opp_label=opp_label)
            json.dump(summ, open(out / "summary.json", "w"), indent=2)
        else:
            print("no cached results yet")
        return 0

    leaf_cfg = cfg.resolved_leaf_cfg()          # FAIR champion side (override or DEFAULT_CONFIG)
    rung_leaf_cfg = DEFAULT_CONFIG              # h800 rung is ALWAYS env DEFAULT_CONFIG (the ruler)
    # human label for the champion leaf: reflects the --cand-leaf-json override when active
    # (the Trap-1 mislabel mitigation — a candidate cell is NOT "v2.9 Bmild_cap8").
    if cand_leaf_cfg is None:
        _champ_leaf_label = "v2.9 Bmild_cap8 (DEFAULT_CONFIG)"
    elif (args.info == "fair-netprior" or _h2h) and args.cand_leaf_json is None:
        # auto-injected curve125 (NOT a user --cand-leaf-json) — label it honestly
        _champ_leaf_label = (f"FROZEN v2.9 curve125 production champion leaf, auto-injected "
                             f"in-process (leaf{_leaf_hash(leaf_cfg)[:8]})")
    else:
        _champ_leaf_label = f"candidate override --cand-leaf-json (leaf{_leaf_hash(leaf_cfg)[:8]})"
    _AGENT_NAME = {
        "fair": "FairHeuristicPriorAgent",
        "fair-net": "FairHeuristicPriorAgent + deck-aware net value (C-cheap)",
        "fair-netprior": ("FairHeuristicPriorAgent + distilled net POLICY priors "
                          "(frozen curve125 champion leaf value; severed value loop)"),
        "clair": "HeuristicPriorAgent (clairvoyant)",
    }
    _NP = args.info == "fair-netprior"
    man_cfg = {
        "info": args.info,
        "champion": {"agent": _AGENT_NAME[args.info],
                     **cfg.as_manifest(),
                     "k_dets": args.k_dets, "sims_per_det": args.sims,
                     "total_sims": args.k_dets * args.sims,
                     "batch_size": args.batch_size,   # within-search leaf batching (1=serial; fair-netprior only)
                     "net": (args.net if args.info in ("fair-net", "fair-netprior") else None),
                     "net_mode": (args.net_mode if args.info == "fair-net" else None),
                     "net_lambda": (args.net_lambda if (args.info == "fair-net"
                                    and args.net_mode == "residual") else None),
                     "value_transport": (("carc-orch SHM (" + args.orch_shm_name + ")")
                                         if (args.info == "fair-net" and args.orch_shm_name)
                                         else ("per-worker CPU net" if args.info == "fair-net"
                                               else None)),
                     # --- fair-netprior (the distilled-agent arm) provenance ---
                     # priors_source is recorded for EVERY arm (additive metadata): the
                     # fair/fair-net/clair arms all steer on the heuristic softmax(Δleaf/τ);
                     # only fair-netprior swaps in the net policy head.
                     "priors_source": ("net_policy_head" if _NP
                                       else "heuristic_softmax_dleaf_tau"),
                     "rep": (("sighted" if netprior_rep["sighted"] else "non-sighted")
                             if _NP else None),
                     "rep_dims": ({"n_input_channels": netprior_rep["n_input_channels"],
                                   "n_scalar_features": netprior_rep["n_scalar_features"],
                                   "sighted": netprior_rep["sighted"],
                                   "inferred_from": "checkpoint (n_input_channels/"
                                                    "n_scalar_features/sighted)"}
                                  if _NP else None),
                     "net_rep_provenance": ({"iter": netprior_rep["iter"],
                                             "value_global_pool": netprior_rep["value_global_pool"],
                                             "train_provenance": netprior_rep["provenance"]}
                                            if _NP else None),
                     "priors_transport": (("carc-orch SHM (" + args.orch_shm_name + ")")
                                          if (_NP and args.orch_shm_name)
                                          else ("per-worker CPU net" if _NP else None)),
                     "netprior_leaf": (netprior_leaf_prov if _NP else None),
                     "leaf": _champ_leaf_label,
                     "value_source": (
                         "frozen_v29_curve125_leaf" if _NP
                         else ("learned deck-aware net (sighted 81ch/42-scalar), "
                               + ("residual heur+%g*net" % args.net_lambda
                                  if args.net_mode == "residual" else "replace net-only"))
                         if args.info == "fair-net"
                         else ("v2.9 heuristic leaf" if cand_leaf_cfg is None
                               else "v2.9 heuristic leaf, CANDIDATE override (--cand-leaf-json)")),
                     "aggregation": ("single clairvoyant search (final_select)" if args.info == "clair"
                                     else "pooled-Q over k_dets determinizations (final_select inert)")},
        "endgame": {"mode": "marginalized", "exact_k": args.exact_k,
                    "exact_budget": EXACT_BUDGET, "shared_by_both_arms": True,
                    "tt_cap": os.environ.get("CARCASSONNE_TT_CAP")},
        # --- OPPONENT (--opponent). `rung` below is retained VERBATIM for the h800
        # default so every existing manifest reader keeps working; in a head-to-head it
        # is null (there IS no rung) and `opponent` carries the full second-side record.
        "opponent_mode": args.opponent,
        "opponent": {
            "mode": args.opponent,
            "label": opp_label,
            "agent": ("HeuristicMCTS" if args.opponent == "h800" else
                      "FairHeuristicPriorAgent" if args.opponent == "fair-champion" else
                      "FairHeuristicPriorAgent + distilled net POLICY priors "
                      "(frozen curve125 champion leaf value; severed value loop)"),
            "priors_source": ("random_expansion_uct (no priors)" if args.opponent == "h800"
                              else "net_policy_head" if args.opponent == "net"
                              else "heuristic_softmax_dleaf_tau"),
            "value_source": ("v2.9 curve100 heuristic leaf (DEFAULT_CONFIG ruler)"
                             if args.opponent == "h800" else "frozen_v29_curve125_leaf"),
            "net": (args.opp_net if args.opponent == "net" else None),
            "rep": ((("sighted" if opp_rep["sighted"] else "non-sighted"))
                    if opp_rep else None),
            "rep_dims": ({"n_input_channels": opp_rep["n_input_channels"],
                          "n_scalar_features": opp_rep["n_scalar_features"],
                          "sighted": opp_rep["sighted"],
                          "include_farm_scalars": opp_rep.get("include_farm_scalars", False),
                          "inferred_from": "the OPPONENT's own checkpoint (independent "
                                           "of --net; a cross-rep match is supported)"}
                         if opp_rep else None),
            "net_rep_provenance": ({"iter": opp_rep["iter"],
                                    "value_global_pool": opp_rep["value_global_pool"],
                                    "train_provenance": opp_rep["provenance"]}
                                   if opp_rep else None),
            "priors_transport": (("carc-orch SHM (" + args.opp_orch_shm_name + ")")
                                 if (args.opponent == "net" and args.opp_orch_shm_name)
                                 else ("per-worker CPU net" if args.opponent == "net"
                                       else None)),
            "c": (RUNG_C if args.opponent == "h800" else None),
            "sims": (args.rung_sims if args.opponent == "h800" else None),
            "k_dets": (None if args.opponent == "h800" else args.k_dets),
            "sims_per_det": (None if args.opponent == "h800" else args.sims),
            "total_sims": (None if args.opponent == "h800" else args.k_dets * args.sims),
            "endgame": (None if args.opponent == "h800"
                        else {"mode": "marginalized", "exact_k": args.exact_k,
                              "exact_budget": EXACT_BUDGET}),
            "leaf": (f"v2.9 Bmild_cap8 (DEFAULT_CONFIG, leaf{_leaf_hash(rung_leaf_cfg)[:8]})"
                     if args.opponent == "h800"
                     else f"FROZEN v2.9 curve125 production champion leaf, auto-injected "
                          f"in-process (leaf{_leaf_hash(opp_leaf_cfg)[:8]})"),
            "leaf_hash": (_leaf_hash(rung_leaf_cfg) if args.opponent == "h800"
                          else _leaf_hash(opp_leaf_cfg)),
            "leaf_cfg": (_leaf_dict(rung_leaf_cfg) if args.opponent == "h800"
                         else _leaf_dict(opp_leaf_cfg)),
            "curve125_leaf_provenance": opp_leaf_prov,
            "champ_cfg": (None if args.opponent == "h800" else champ_cfg_dict),
            "production_config_deviations": (_prod_deviations(args)
                                             if args.opponent in _HEAD_TO_HEAD else None),
            "provenance": ("CL-022 ruler (CLAIRVOYANCE_GAP_VERDICT.md, h800 v2.7)"
                           if args.opponent == "h800"
                           else "governance/PRODUCTION.yaml champion config; both sides "
                                "share every search knob (single-variable swap)"),
        },
        "result_semantics": {
            "diff": "candidate - opponent (per game, from the candidate's a_seat)",
            "winrate_elo_paired": "candidate vs opponent",
            "note": ("For --opponent h800 this is IDENTICAL to the historical "
                     "champion-minus-rung semantics and the numbers are directly "
                     "comparable to every earlier cell. For a head-to-head the elo is "
                     "an ABSOLUTE pairwise elo between the two agents, NOT an elo "
                     "against the h800 rung — do NOT compare it to a vs-h800 cell or "
                     "subtract one from the other."),
            "seat_balance": ("a_seat (the CANDIDATE's seat) alternates 0/1 over the same "
                             "deck under --paired; _paired_z averages the two seats per "
                             "deck, so neither side owns a seat."),
        },
        "rung": ({"agent": "HeuristicMCTS", "heur_leaf": "v2_7", "c": RUNG_C,
                  "sims": args.rung_sims, "endgame": None,
                  # the ruler NEVER takes the candidate override — always env DEFAULT_CONFIG.
                  "leaf": f"v2.9 Bmild_cap8 (DEFAULT_CONFIG, leaf{_leaf_hash(rung_leaf_cfg)[:8]})",
                  "leaf_hash": _leaf_hash(rung_leaf_cfg),
                  "provenance": "CL-022 ruler (CLAIRVOYANCE_GAP_VERDICT.md, h800 v2.7)"}
                 if args.opponent == "h800" else None),
        "n": args.n, "paired": args.paired, "seed_start": args.seed_start,
        "leaf_hash": _leaf_hash(leaf_cfg), "code_rev": code_rev(),
        # C5 Stage-3 per-side leaf provenance (Trap 1: a worker missing the env exports
        # silently runs the wrong leaf — the per-side leaf_hash is the mitigation). The
        # FAIR champion side carries the --cand-leaf-json override; the rung is DEFAULT.
        "cand_leaf_json": args.cand_leaf_json,
        "cand_leaf_cfg": _leaf_dict(leaf_cfg),
        "cand_leaf_hash": _leaf_hash(leaf_cfg),
        # rung_leaf_* is the env DEFAULT_CONFIG. For --opponent h800 it IS the opponent's
        # leaf (the ruler). For a head-to-head no agent uses it — it is recorded anyway as
        # the PROOF that the in-process curve125 injection did not move DEFAULT_CONFIG.
        "rung_leaf_cfg": _leaf_dict(rung_leaf_cfg),
        "rung_leaf_hash": _leaf_hash(rung_leaf_cfg),
        "opp_leaf_cfg": (_leaf_dict(opp_leaf_cfg) if opp_leaf_cfg is not None else None),
        "opp_leaf_hash": (_leaf_hash(opp_leaf_cfg) if opp_leaf_cfg is not None else None),
        "both_sides_curve125": (bool(opp_leaf_cfg is not None
                                     and _leaf_hash(opp_leaf_cfg) == _leaf_hash(leaf_cfg))
                                if _h2h else None),
        "equal_wall_clock_note": ("champion total per-move budget k_dets*sims targets the "
                                  "deployed clairvoyant champion ~2750 sims (equal wall-clock; "
                                  "k_dets root expansions add a little fixed overhead)"),
        "env": {k: os.environ.get(k) for k in _CANON_ENV},
    }
    write_manifest(out, kind="eval_fair_puct", game=game_tag(Game()),
                   config=man_cfg, overwrite=True)

    todo = [t for t in tasks if not _result_path(out, t[1], t[2]).exists()]
    workers = args.workers or min(os.cpu_count() or 1, len(todo) or 1)
    print(f"fair-puct[{tag}]: info={args.info} n={args.n} paired={args.paired} K={args.exact_k} "
          f"k_dets={args.k_dets} sims={args.sims} | {len(tasks)-len(todo)} cached, "
          f"{len(todo)} to play, {workers} workers, out={out}")
    sys.stdout.flush()

    _cand_orch = bool(args.orch_shm_name) and args.info in ("fair-net", "fair-netprior")
    _opp_orch = bool(args.opp_orch_shm_name) and args.opponent == "net"
    orch = _cand_orch or _opp_orch
    results = []
    if todo:
        t0 = time.perf_counter()
        if orch:
            # carc-orch SHM: spawn context (CUDA-clean re-import) + a worker-id Queue
            # so each CPU worker pops a unique SHM slot (mirrors clairvoyance_gap / eval_m2).
            # A net-vs-net orch run attaches to TWO servers (one net each) — the worker
            # pops ONE id and uses that slot on both.
            _ctx = mp.get_context("spawn")
            _id_q = _ctx.Queue()
            for _w in range(workers):
                _id_q.put(_w)
            if _cand_orch:
                _dims = (f"{netprior_rep['n_input_channels']}ch/"
                         f"{netprior_rep['n_scalar_features']}-scalar "
                         f"{'sighted' if netprior_rep['sighted'] else 'non-sighted'} PRIORS"
                         if _NP else "81ch/42-scalar sighted value")
                print(f"  [orch] candidate SHM eval-server '{args.orch_shm_name}': {workers} "
                      f"CPU workers attach to /dev/shm/carc_{args.orch_shm_name} ({_dims})",
                      flush=True)
            if _opp_orch:
                print(f"  [orch] opponent  SHM eval-server '{args.opp_orch_shm_name}': "
                      f"{workers} CPU workers attach to "
                      f"/dev/shm/carc_{args.opp_orch_shm_name} "
                      f"({opp_rep['n_input_channels']}ch/{opp_rep['n_scalar_features']}-scalar "
                      f"{'sighted' if opp_rep['sighted'] else 'non-sighted'} PRIORS)",
                      flush=True)
            _pool_cm = _ctx.Pool(
                processes=workers, initializer=_worker_init,
                initargs=(args.info, champ_cfg_dict, args.sims, args.k_dets, args.exact_k,
                          args.rung_sims, args.shared_claim, args.claim_host,
                          args.claim_stale_secs, args.net, args.net_mode, args.net_lambda,
                          (args.orch_shm_name or ""), _id_q, cand_leaf_cfg, netprior_rep,
                          args.opponent, opp_leaf_cfg, args.opp_net, opp_rep,
                          (args.opp_orch_shm_name or ""), args.batch_size))
        else:
            _pool_cm = Pool(
                processes=workers, initializer=_worker_init,
                initargs=(args.info, champ_cfg_dict, args.sims, args.k_dets, args.exact_k,
                          args.rung_sims, args.shared_claim, args.claim_host,
                          args.claim_stale_secs, args.net, args.net_mode, args.net_lambda,
                          "", None, cand_leaf_cfg, netprior_rep,
                          args.opponent, opp_leaf_cfg, args.opp_net, opp_rep, "",
                          args.batch_size))
        with _pool_cm as pool:
            done = 0
            for r in pool.imap_unordered(_play_one, todo, chunksize=1):
                if r is None:
                    continue
                results.append(r)
                done += 1
                if done % 10 == 0 or done == len(todo):
                    el = time.perf_counter() - t0
                    print(f"  {done}/{len(todo)} played ({el/done:.1f}s/game, "
                          f"~{(len(todo)-done)*el/done/60:.0f} min left)", flush=True)
    for t in tasks:
        p = _result_path(out, t[1], t[2])
        if p.exists() and not any(r.seed == t[1] and r.a_seat == t[2] for r in results):
            c = _try_load(p)
            if c:
                results.append(c)

    if not results:
        print("no results")
        return 0
    summ = _summary(results, args.info, args.exact_k, args.k_dets, args.sims,
                    args.rung_sims, opponent=args.opponent, opp_label=opp_label)
    json.dump(summ, open(out / "summary.json", "w"), indent=2)
    print(f"[summary.json] wrote {out/'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
