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
  - bare-net      : ⚠️ DELIBERATELY ASYMMETRIC — our BLIND champion vs a SIGHTED
                    (CLAIRVOYANT) bare NeuralMCTS. See the BLIND-vs-SIGHTED block
                    below before touching it. Needs --opp-net.
In both SYMMETRIC head-to-head modes (fair-champion / net) the two sides are
production agents, so BOTH resolve the
FROZEN curve125 champion leaf (injected in-process per side — see the CURVE125 block
below), both get the same marginalized endgame handoff at K, and seat alternation +
deck pairing are unchanged (the candidate's seat is `a_seat`, which _build_work
balances over 0/1) — a prior-swap A/B where one side owned a seat would be worthless.
`diff` is always CANDIDATE - OPPONENT.

===========================================================================
BLIND vs SIGHTED (`--opponent bare-net`) — THE ASYMMETRY IS THE MEASUREMENT.
DO NOT "FIX" IT. DO NOT SYMMETRISE IT.
===========================================================================
This mode plays our BLIND (fair PIMC) champion against a SIGHTED (clairvoyant)
bare NeuralMCTS in its ANCHOR identity. The two sides differ on purpose in
THREE ways, every one of which HANDICAPS US:

  1. INFORMATION.  Candidate = FairHeuristicPriorAgent: it never sees the true
     deck (root determinization, k_dets reshuffled worlds, pooled-Q). Opponent =
     NeuralMCTS with fair_chance=False, i.e. it descends the engine's real
     pre-shuffled `state.deck` and SEES every upcoming tile. The measured
     clairvoyance tax at champion config is ~156 elo (CL-022 lineage) — that is
     a tax WE pay and the opponent does not.
  2. LEAF.  Candidate = the FROZEN production curve125 champion leaf
     (leaf_hash a36d2e15a3b3d71d). Opponent = the v2.9 Bmild_cap8 curve100 leaf
     with residual_scale=0.25 (leaf_hash 4bc26f12badbb10b) — NOT curve125. This
     is NOT a bug and NOT something to "make consistent": it is the exact leaf
     the RoD-v2 anchor rows in experiments/results.csv were played with, and the
     opponent is only interpretable as an anchor if it is bit-for-bit that agent.
     The harness therefore reports TWO DIFFERENT per-side leaf hashes here and
     HARD-FAILS if they ever come out equal (equality would mean the curve125
     injection leaked onto the opponent and silently replaced the anchor).
  3. ENDGAME.  Candidate keeps the marginalized exact-K<=2 tail; the opponent is
     BARE (no exact tail at all) — again exactly how the anchor rows were played.
     The one-sided tail needs no new machinery: the default `h800` rung has
     always been tail-less (_make_opponent returns a bare prefix, only
     _make_champion wraps in _MarginalizedHandoff), so "candidate-only tail" IS
     the harness's existing shape.

WHY ASYMMETRIC ON PURPOSE — AND WHY THAT IS **NOT** A LOWER BOUND (corrected
2026-07-27). This block used to say our side was "handicapped on all three axes",
making a win a conservative lower bound on the lineage gap. That was WRONG: only
the INFORMATION axis handicaps us. The asymmetries do not all point the same way:

    information -> we are HANDICAPPED  (blind vs sighted; measured tax ~156 elo)
    leaf        -> we are ADVANTAGED   (curve125 vs curve100+rs0.25 — CL-051
                                        established curve125 is a real leaf win)
    endgame     -> we are ADVANTAGED   (marginalized exact-K<=2 tail vs none)
    cost        -> NOT MATCHED         (candidate/opponent ms/move ran 0.29x at
                                        the 344 rung to 8.5x at 11008 in CL-069,
                                        so its direction depends on the rung)

The NET direction is therefore UNDETERMINED, and no bound exists in EITHER
direction. The honest claim is the narrow one: OUR CHAMPION, BLIND AND AT BUDGET
B, BEATS THE RoD-v2 ANCHOR AGENT PLAYING SIGHTED. It does NOT license "therefore
the lineage gap is at least this". A LOSS is equally confounded — it mixes the
blindness tax against our leaf/endgame edge — so do not report a loss as "the
net is stronger" either. None of this makes the cell less valuable: its worth is
that the opponent is OUT OF LINEAGE, which is exactly what made CL-069's flat
top something other than a self-anchoring artifact. The same corrected wording
is in scripts/classical_search/blind_curve_queue.sh — keep them in sync.

If you find yourself wanting to
give the opponent our leaf, take away its deck vision, or hand it the exact
tail — stop. Any of those destroys the meaning of the cell and makes the number
a different (and un-anchored) measurement.

The opponent's play knobs are PINNED (sims=200, c_puct=3.0, residual_scale=0.25,
bare) to the rod_v2 anchor harness — see BARE_NET_* below — so --opp-sims /
--opp-k-dets are REJECTED for this mode rather than silently reshaping the anchor.

TRANSPORT (net on GPU): the anchor's forwards may be served EITHER by a per-worker
CPU net (the historical path) or by the carc-orch SHM GPU server
(--opp-orch-shm-name; wrapper: scripts/classical_search/bare_net_opp_orch.sh). Only
ONE server is needed because the candidate side is net-free. This is a TRANSPORT
choice, not an identity change — same weights, same leaf, same knobs, same
clairvoyance — but GPU fp32 and CPU fp32 do not agree bit-for-bit, so a near-tied
argmax can flip. The anchor rows on record were played net-on-CPU; measure the
divergence (scripts/classical_search/bare_net_gpu_divergence.py) and disclose it in
the cell write-up rather than assuming it away. See BARE_NET_GPU_NOTE.

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

  # CL-060 re-open trigger — the DIRECT head-to-head the ladder could not run:
  # candidate k8x1376 (11008) vs the k4x688 (2752) DEPLOY champion. Both asymmetry
  # flags are needed: --opp-sims ALONE would give a k8x688=5504 opponent, NOT the
  # deploy config. Deck-paired, on a FRESH band.
  # ⚠️ Band history: 28e9 was originally written here as "unused", but the champion
  # action-log gen consumed it on 2026-07-21 (champ_action_logs_20260721 claims
  # seed_028000000000+). Using those decks for a confirmatory eval would grade on
  # decks already seen during root mining. 32e9 verified clean; RE-VERIFY before
  # launching (in use as of 2026-07-21: 13e9, 15e9, 22e9, 24e9, 25e9, 26e9, 28e9, 90e9).
  CARCASSONNE_TT_CAP=200000 nice -n 19 .venv/bin/python -u \
      scripts/classical_search/eval_fair_puct.py \
      --info fair --opponent fair-champion \
      --exact-k 2 --k-dets 8 --sims 1376 --opp-k-dets 4 --opp-sims 688 \
      --n 400 --paired --seed-start 32000000000 --workers 32 \
      --out-root /mnt/c/carc-shared/classical_search \
      --out-subdir cl060_h2h_k8x1376_vs_deploy_k4x688 --shared-claim --no-results-csv

  # BLIND vs SIGHTED — our fair champion (k4x344=1376, curve125, exact-K<=2) vs the
  # SIGHTED bare NeuralMCTS RoD-v2 iter_02 anchor. Read the BLIND-vs-SIGHTED block above.
  CARCASSONNE_TT_CAP=200000 nice -n 19 .venv/bin/python -u \
      scripts/classical_search/eval_fair_puct.py \
      --info fair --opponent bare-net \
      --opp-net /mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt \
      --exact-k 2 --k-dets 4 --sims 344 \
      --n 200 --paired --seed-start 68000000000 --workers 14 \
      --out-root /mnt/c/carc-shared/classical_search \
      --out-subdir blind_k4x1376_vs_sighted_rodv2_it02_b68e9 \
      --shared-claim --no-results-csv

  # SAME cell with the anchor's net on the GPU via carc-orch SHM (the standing default
  # for neural eval — per-worker batch-1 CPU forwards are latency-bound). ONE server:
  # the candidate side is net-free. Use the wrapper, which owns the server lifecycle,
  # the OMP pin and max_batch>=W:
  #   OPP_CKPT=/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt OW=14 \
  #     bash scripts/classical_search/bare_net_opp_orch.sh \
  #       --exact-k 2 --k-dets 4 --sims 344 --n 200 --paired \
  #       --seed-start 68000000000 --out-root /mnt/c/carc-shared/classical_search \
  #       --out-subdir blind_k4x1376_vs_sighted_rodv2_it02_b68e9 \
  #       --shared-claim --no-results-csv
  # ⚠️ GPU fp32 != CPU fp32 (reduction order). The anchor rows on record were played
  #    net-on-CPU; measure the decision divergence before citing a GPU cell against them:
  #      .venv/bin/python scripts/classical_search/bare_net_gpu_divergence.py \
  #          --opp-net <iter_02.pt> --max-positions 60

CRASH RESILIENCE (2026-08-14, after cell `oc2_C_d16p0_deploy11008`). A game that
RAISES no longer kills the pass. It is written as a failure record under
`<out>/failed/seed*_a*.json`, its `--shared-claim` claim is released, and the pool
carries on; `n_failed` / `failure_rate` / `failed_cells` / `failed_by_seat` land in
BOTH `summary.json` and `manifest.json`, and a rate above 0.5% of n trips the
pre-registered validity trigger (shouted at the end of the run, and stamped as
`validity_trigger_fired`). Failure records live in a SUBDIRECTORY and carry no
`diff`/`won_by_champ`, so no downstream glob of the cell dir can mistake one for a
game. A failed game counts as DONE on a later pass (these failures are
deck-deterministic); `--retry-failed` re-opens them after a code fix, bounded by
the record's lifetime `attempts` vs `--max-attempts`. A record whose game LATER
SUCCEEDED is RESOLVED — excluded from `n_failed`/`failure_rate` (the result file
is the arbiter) but kept on disk and reported under `n_resolved_failures`, so a
flaky game never voids a clean cell and never loses its diagnosis. Field/flag names mirror
`scripts/joshuabot/h2h.py` (commit 0102b72d) so the two harnesses stay one
convention.
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
from datetime import datetime, timezone
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
from carcassonne_ai import champion_factory  # noqa: E402  (F1: single construction point)
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
from carcassonne_ai.rule_based_player import RuleBasedPlayer  # noqa: E402
from carcassonne_ai import rules_profile as _rules_profile  # noqa: E402
from carcassonne_ai.run_manifest import (  # noqa: E402
    code_rev, game_tag, patch_manifest, write_manifest,
)
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


def _stamp_cand_leaf(cand_cfg, tag="head-to-head"):
    """CANDIDATE-SIDE ONLY, --allow-cand-curve-drift: a PRE-REGISTERED leaf-SHAPE cell.

    Deliberately does NOT require curve125 — the whole point of a curve-shape cell is a
    candidate curve that differs from the champion's. It is a sibling of (never a branch
    inside) `_assert_netprior_leaf`, so that function's promise — "the SAME check runs
    for both sides" — stays literally true for the OPPONENT arm, which is still pinned
    to curve125 and still goes through the unmodified assert.

    Still fails loud on a curve that is not a well-formed 8-entry finite float tuple:
    a null/short/NaN curve is a mis-specified cell, not a shape hypothesis."""
    curve = cand_cfg.v29_meeple_curve
    if curve is None:
        raise SystemExit(
            f"[{tag}] FATAL: --allow-cand-curve-drift requires an EXPLICIT candidate "
            "meeple curve, but the candidate leaf has v29_meeple_curve=None (curve OFF). "
            "A leaf-shape cell must name the shape it is testing.")
    try:
        vals = tuple(float(x) for x in curve)
    except (TypeError, ValueError) as e:
        raise SystemExit(f"[{tag}] FATAL: candidate v29_meeple_curve is not numeric: "
                         f"{curve!r} ({e})")
    if len(vals) != 8 or not all(math.isfinite(v) for v in vals):
        raise SystemExit(
            f"[{tag}] FATAL: candidate v29_meeple_curve must be 8 finite floats; got "
            f"{curve!r} (len={len(vals)}).")
    return {
        "curve": ("PRE-REGISTERED candidate curve shape (NOT curve125) — "
                  "--allow-cand-curve-drift"),
        "curve_values": list(vals),
        "cand_curve_drift_allowed": True,
        "leaf_hash": _leaf_hash(cand_cfg),
        "frozen_config_hash_champ_dialect": _frozen_hash_champ_dialect(cand_cfg),
        "curve125_reference": {"curve": list(CURVE125),
                               "leaf_hash": CURVE125_LEAF_HASH,
                               "frozen_config_hash": CURVE125_FROZEN_HASH},
        "note": ("ONLY the CANDIDATE arm may drift. The opponent arm is pinned to "
                 "curve125 and still passes the unmodified _assert_netprior_leaf, so "
                 "this cell is a curve-SHAPE contrast against the shipped champion."),
    }


def _assert_rung_is_ruler(tag="fair-netprior", who="h800 RUNG's"):
    """The fixed h800 rung is env DEFAULT_CONFIG and MUST remain the curve100 CL-022
    ruler. Sourcing champ_env.sh before this harness would set the curve env, and
    _CANON_ENV's setdefault would NOT override it -> the rung would silently move to
    curve125 and every arm's elo would be measured against a different yardstick.
    Fail loud (fair-netprior only; the fair/fair-net arms are untouched).

    `tag`/`who` only label the message. They default to the historical strings, so the
    legacy call site is byte-identical; --opponent bare-net reuses the SAME check with
    its own labels (its opponent leaf is derived from DEFAULT_CONFIG too, so a moved
    DEFAULT_CONFIG would silently replace the anchor rather than the ruler)."""
    curve = DEFAULT_CONFIG.v29_meeple_curve
    if curve is None or tuple(float(x) for x in curve) != CURVE100:
        raise SystemExit(
            f"[{tag}] FATAL: the {who} leaf curve is {curve!r}, expected the "
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


class _MirrorMarginalizedHandoff(_MarginalizedHandoff):
    """`_MarginalizedHandoff` around a prefix that OWNS A RUST MIRROR (--info clair
    --backend rust).

    `_drives_mirror` is duck-typed on `start_game`/`advance`, and the base wrapper has
    neither — so a mirror-owning prefix inside it would never be seated or advanced and
    would raise `MirrorDesync` on the second ply. Rather than give the base class those
    methods (which would make `_drives_mirror` true for the PYTHON fair arm too, and
    change a path that is byte-identical to every banked row), this subclass forwards
    them and is used ONLY on the rust clair arm.

    The endgame stays exactly where it was: the marginalized solver in the base class,
    shared with the python arm, so the clairvoyance tax still isolates the search PREFIX.
    The solver's moves are applied to the mirror by the harness's `_advance_mirrors`
    like any other action — that is the whole point of advancing on BOTH seats.
    """

    def start_game(self, board) -> None:
        self._prefix.start_game(board)

    def advance(self, action: int, board_after=None) -> None:
        self._prefix.advance(int(action), board_after)


class _RungPrefix:
    """Fixed rung: HeuristicMCTS @ rung_sims, c=3.0, v2.9 Bmild_cap8 leaf. NO
    endgame handoff (the CL-022 yardstick convention)."""

    def __init__(self, game, sims, seed, leaf_cfg):
        self._m = HeuristicMCTS(game=game, simulations=sims, c=RUNG_C, seed=seed,
                                heur_leaf="v2_7", leaf_cfg=leaf_cfg)

    def move(self, board) -> int:
        self._m.clear()
        return int(self._m.best_action(board))


class _GreedyPrefix:
    """tier1: the 1-ply RuleBasedPlayer — NO search, NO leaf, NO endgame handoff.

    This is bit-for-bit the `greedy` rung the Level-2 ladder rated
    (scripts/ladder_rung_eval.py::_GreedyAgent, leaf_name "v1_1ply"), which is what
    makes a vs-greedy number here comparable to the *_vs_greedy_n200 rows in
    experiments/results.csv. It owns its own Game only to resolve the legal mask
    (RuleBasedPlayer.choose_action takes one); it never searches, so --rung-sims /
    --opp-sims / --opp-k-dets are all inapplicable and are rejected in main().

    PURPOSE: this rung is the DECK-LUCK FLOOR. A 1-ply player that still steals
    games off the production champion is measuring variance the champion cannot
    search away, not strength — read the loss fraction as a floor, not a gap.
    """

    leaf_name = "v1_1ply"

    def __init__(self, game, seed):
        self._game = game
        self._p = RuleBasedPlayer(seed=seed)

    def move(self, board) -> int:
        mask = self._game.get_valid_moves(board)
        return int(self._p.choose_action(self._game, board, mask))


# --------------------------------------------------------------------------- #
# BARE SIGHTED NET opponent (--opponent bare-net) — the RoD-v2 anchor identity.  #
#                                                                               #
# ⚠️ READ THE "BLIND vs SIGHTED" BLOCK IN THE MODULE DOCSTRING BEFORE CHANGING    #
# ANYTHING HERE. This agent is deliberately CLAIRVOYANT (NeuralMCTS's default    #
# fair_chance=False descends the engine's TRUE deck) and deliberately runs a     #
# DIFFERENT leaf from our candidate. Both are load-bearing: they make the        #
# opponent bit-for-bit the agent every `net:<ckpt>` anchor row in                #
# experiments/results.csv was played by, which is the only reason its rating is  #
# interpretable at all. "Fixing" either one silently replaces the anchor.        #
#                                                                               #
# The play knobs below are COPIED VERBATIM from eval_puct_priors.py's NET_*      #
# constants (which in turn mirror scripts/level2/eval_hybrid_handoff.py's        #
# ITER8_* / _make_iter8_mcts, the harness behind the rodv2_iter02_vs_heur*_v29   #
# rows). They are pinned, not CLI-settable — --opp-sims / --opp-k-dets are       #
# rejected for this mode so a sweep can never reshape the anchor by accident.    #
# --------------------------------------------------------------------------- #
BARE_NET_SIMS = 200            # == eval_puct_priors.NET_SIMS
BARE_NET_CPUCT = 3.0           # == eval_puct_priors.NET_CPUCT
BARE_NET_RESIDUAL_SCALE = 0.25  # == eval_puct_priors.NET_RESIDUAL_SCALE
BARE_NET_MEEPLE_K = 2.0        # == eval_puct_priors.NET_MEEPLE_K (inert under a curve)
# The anchor's leaf, in this harness's _leaf_hash dialect. NOT curve125 — see above.
BARE_NET_LEAF_HASH = "4bc26f12badbb10b"

# ⚠️ TRANSPORT vs IDENTITY. The anchor's *play knobs* are pinned above; where the
# forward physically runs is NOT one of them, but it is not free either.
#
# Every RoD-v2 anchor row on record (rodv2_iter02_vs_heur6400_v29_n200 / _vs_heur3200)
# was played with the net on the CPU in fp32. Serving the same weights from the GPU
# (carc-orch, --opp-orch-shm-name) is the standing default for neural eval and is far
# faster, but GPU fp32 reduction order != CPU fp32 reduction order, so priors/value
# differ by ~1e-6..1e-4 and a NEAR-TIED argmax can flip. Over a 200-sim NeuralMCTS the
# per-move decision-divergence rate is an EMPIRICAL quantity, measured by
# scripts/classical_search/bare_net_gpu_divergence.py — read its output before citing a
# GPU-transport cell against a CPU-transport anchor row. The measured rate is recorded
# in the manifest under opponent.transport_numerics.
BARE_NET_GPU_NOTE = (
    "The anchor rows on record were played net-on-CPU (fp32). This cell served the "
    "SAME weights from the GPU via carc-orch SHM. Weights, leaf, search knobs and "
    "clairvoyance are identical; only float reduction order differs, which can flip a "
    "near-tied argmax. See scripts/classical_search/bare_net_gpu_divergence.py.")


def _bare_net_leaf_cfg():
    """The bare-net opponent's leaf: env DEFAULT_CONFIG (v2.9 Bmild_cap8, curve100 —
    the CL-022 ruler config) with residual_scale/meeple_k set to the anchor's values.

    Bit-identical by construction to eval_puct_priors._NetPrefix's inline
    `dc.replace(DEFAULT_CONFIG, residual_scale=NET_RESIDUAL_SCALE, meeple_k=NET_MEEPLE_K)`:
    the two harnesses share a VERBATIM `_CANON_ENV`, so their DEFAULT_CONFIG is the same
    object value, and the two replaced fields carry the same constants. (meeple_k=2.0 is
    already DEFAULT_CONFIG's value under _CANON_ENV, so that replace is a no-op in both
    files — it is kept for byte-parity with the anchor harness.)

    ⚠️ This is NOT curve125 and must never be made curve125."""
    import dataclasses as _dc
    return _dc.replace(DEFAULT_CONFIG, residual_scale=BARE_NET_RESIDUAL_SCALE,
                       meeple_k=BARE_NET_MEEPLE_K)


def _assert_bare_net_leaf(cfg, cand_cfg=None, strict=True):
    """Verify the bare-net opponent's leaf is the ANCHOR leaf — curve100 (NOT curve125),
    residual_scale 0.25 — and that it is NOT the candidate's leaf.

    The equality check against `cand_cfg` is the important one: the whole failure mode
    this mode invites is the curve125 in-process injection leaking onto the opponent,
    which would produce a perfectly plausible number for an agent that is not the anchor.
    Semantic checks first (robust to LeafConfig dataclass drift), hash last."""
    curve = cfg.v29_meeple_curve
    if curve is None or tuple(float(x) for x in curve) != CURVE100:
        raise SystemExit(
            f"[bare-net] FATAL: opponent leaf curve is {curve!r}, expected the curve100 "
            f"anchor leaf {CURVE100!r}. The RoD-v2 anchor rows were played on curve100 "
            "with residual_scale=0.25; a curve125 opponent is NOT the anchor and its "
            "rating is not interpretable. Do NOT 'symmetrise' the two sides.")
    if float(cfg.residual_scale) != BARE_NET_RESIDUAL_SCALE:
        raise SystemExit(
            f"[bare-net] FATAL: opponent leaf residual_scale={cfg.residual_scale!r}, "
            f"expected the anchor's {BARE_NET_RESIDUAL_SCALE}.")
    lh = _leaf_hash(cfg)
    if cand_cfg is not None and lh == _leaf_hash(cand_cfg):
        raise SystemExit(
            "[bare-net] FATAL: the candidate and opponent resolved the SAME leaf "
            f"({lh}). They MUST differ: the candidate is the frozen curve125 champion "
            "and the opponent is the curve100+rs0.25 anchor. Equality means the "
            "curve125 injection leaked onto the opponent side.")
    prov = {
        "curve": "curve100 (v2.9 Bmild_cap8 — the RoD-v2 anchor leaf, NOT curve125)",
        "residual_scale": float(cfg.residual_scale),
        "meeple_k": float(cfg.meeple_k),
        "leaf_hash": lh,
        "leaf_hash_expected": BARE_NET_LEAF_HASH,
        "differs_from_candidate_by_design": True,
        "note": ("Pinned to eval_puct_priors.py's NET_* anchor constants (== "
                 "eval_hybrid_handoff ITER8_*). The per-side leaves DIFFER ON PURPOSE; "
                 "see the BLIND vs SIGHTED block in this file's module docstring."),
    }
    if lh != BARE_NET_LEAF_HASH:
        msg = (f"[bare-net] opponent leaf hash drift: {lh} != expected "
               f"{BARE_NET_LEAF_HASH}. The curve values and residual_scale matched, so "
               "this is most likely an additive LeafConfig field reshaping the hash "
               "(the 158f17ff precedent) — re-baseline BARE_NET_LEAF_HASH if so. "
               "Re-run with --allow-leaf-hash-drift to proceed on the semantic check.")
        if strict:
            raise SystemExit("FATAL: " + msg)
        print("[warn] " + msg, file=sys.stderr)
        prov["hash_drift_allowed"] = True
    return prov


class _BareNetPrefix:
    """SIGHTED (clairvoyant) bare NeuralMCTS opponent — the RoD-v2 anchor identity.

    A VERBATIM mirror of eval_puct_priors.py's `_NetPrefix` (which mirrors
    eval_hybrid_handoff._make_iter8_mcts): make_v25_value_wrapper(base_eval, leaf_cfg)
    -> NeuralMCTS(simulations=200, c_puct=3.0). The only difference is that the leaf
    cfg is PASSED IN rather than rebuilt inline, so the manifest can report the leaf
    that is actually in use (default None rebuilds the identical cfg).

    ⚠️ CLAIRVOYANT BY DESIGN: NeuralMCTS's `fair_chance` default is False, so this
    search descends the engine's TRUE pre-shuffled deck. That is the handicap our
    blind candidate is being asked to overcome — do not pass fair_chance=True here.
    ⚠️ BARE BY DESIGN: no exact-K endgame handoff (the anchor rows were played bare)."""

    def __init__(self, base_eval, game_farm, seed, leaf_cfg=None):
        from carcassonne_ai.evaluators import make_v25_value_wrapper
        from carcassonne_ai.mcts import NeuralMCTS
        cfg = _bare_net_leaf_cfg() if leaf_cfg is None else leaf_cfg
        leaf = make_v25_value_wrapper(base_eval, cfg)
        self.leaf_cfg = cfg
        self._m = NeuralMCTS(game=game_farm, evaluator=leaf,
                             simulations=BARE_NET_SIMS, seed=seed,
                             c_puct=BARE_NET_CPUCT)
        # provenance handle for the tests / smoke asserts (fair_chance MUST be False)
        self.mcts = self._m

    def move(self, board) -> int:
        self._m.clear()
        return int(self._m.best_action(board))


def _make_bare_net_opponent(net, rep, seed, leaf_cfg=None, handles=None):
    """Per-game bare sighted NeuralMCTS opponent.

    The (priors, value) source is EITHER a worker-local CPU net (`net`) OR the
    carc-orch SHM eval-server (`handles`, --opp-orch-shm-name). Both factories have
    the identical call contract — `Callable[[Board], (priors[A], value)]` with the
    masked softmax already applied (evaluators.make_single_evaluator applies
    `net.policy_softmax_with_mask`; the orch server's TorchScript module bakes the
    same masked softmax in, see scripts/export_torchscript.py::_ScriptedEvaluator) —
    so NOTHING downstream of `base` changes: the same make_v25_value_wrapper, the
    same leaf, the same NeuralMCTS knobs, the same clairvoyance.

    ⚠️ NUMERICS: the orch path runs the net on the GPU in fp32 (carc-orch never
    enables fp16/TF32-only kernels beyond torch's defaults), the CPU path runs it on
    the CPU in fp32. Those are not bit-identical, so a near-tied argmax can flip.
    See BARE_NET_GPU_NOTE and scripts/classical_search/bare_net_gpu_divergence.py —
    the divergence is MEASURED, not assumed.

    The encoder width comes from the OPPONENT's own checkpoint rep (RoD-v2 iter_02 is
    the non-sighted 78ch/12sc 'Step-E farm-scalar' rep). For that rep this is exactly
    eval_puct_priors._make_net_prefix's `Game(enable_legal_moves_cache=True,
    include_farm_scalars=net_ns > 10)` (sighted defaults False there)."""
    if rep is None:
        raise ValueError("--opponent bare-net requires the opponent's checkpoint rep")
    if (net is None) == (handles is None):
        raise ValueError(
            "--opponent bare-net requires EXACTLY ONE evaluator source: a loaded CPU "
            "net (per-worker) or carc-orch SHM handles (--opp-orch-shm-name). "
            f"got net={net is not None} handles={handles is not None}")
    gf = Game(enable_legal_moves_cache=True,
              sighted=bool(rep["sighted"]),
              include_farm_scalars=bool(rep.get(
                  "include_farm_scalars", int(rep["n_scalar_features"]) > 10)))
    if handles is not None:
        # GPU-batched: the carc-orch server owns the only net; this process ships
        # (obs, scalars, mask) over shared memory. The client stays CPU-only, so
        # _CANON_ENV's CUDA_VISIBLE_DEVICES="" is untouched (see BARE_NET_GPU_NOTE).
        from carcassonne_ai.remote_evaluators import make_remote_single_evaluator
        base = make_remote_single_evaluator(handles, gf)
    else:
        from carcassonne_ai.evaluators import make_single_evaluator
        import torch
        base = make_single_evaluator(net, torch.device("cpu"), gf)
    return _BareNetPrefix(base, gf, seed, leaf_cfg=leaf_cfg)


def _build_champ_cfg(c_puct, tau_p, leaf_quantize, final_select, value_norm,
                     leaf_cfg=None, jrules_prior=None, jrules_filter=None):
    # leaf_cfg=None -> env DEFAULT_CONFIG (byte-identical to the pre-C5 path); a
    # non-None value is the --cand-leaf-json CANDIDATE override for the FAIR agent
    # ONLY (the h800 rung always keeps DEFAULT_CONFIG — see _RungPrefix callers).
    #
    # jrules_prior: J-RULES PRIOR surface B (CANDIDATE side only, rust-only) —
    # None (every historical run, and every opponent/rung build) constructs the
    # config with the dataclass defaults, byte-identical to the pre-B path; a
    # dict {dose, mask, scope} is the --cand-jrules-prior-* override. These are
    # SEARCH knobs, not leaf fields: the candidate's leaf hash stays the
    # champion's, so the wiring gate for a live term is the RESOLVED dose this
    # config carries into the manifest (as_manifest / cand_jrules_prior).
    # jrules_filter: J-RULES ROOT FILTER surface C (CANDIDATE side only,
    # rust-only) — None constructs the config with the dataclass defaults,
    # byte-identical to the pre-C path; a dict {mask, min_keep} is the
    # --cand-jrules-filter-* override. Like surface B these are SEARCH knobs,
    # not leaf fields: no leaf hash moves, so the wiring gates are the RESOLVED
    # cand_jrules_filter.mask in the manifest plus the per-game jf_dropped
    # counters (the filter must fire at least once across the cell).
    jr = {}
    if jrules_prior is not None:
        jr = dict(jrules_prior_dose=float(jrules_prior["dose"]),
                  jrules_prior_mask=int(jrules_prior["mask"]),
                  jrules_prior_scope=str(jrules_prior["scope"]))
    if jrules_filter is not None:
        jr.update(jrules_filter_mask=int(jrules_filter["mask"]),
                  jrules_filter_min_keep=int(jrules_filter["min_keep"]))
    return HeuristicPriorConfig(
        c_puct=c_puct, tau_p=tau_p, leaf_quantize=leaf_quantize,
        final_select=final_select, value_norm=value_norm,
        leaf_cfg=(leaf_cfg if leaf_cfg is not None else DEFAULT_CONFIG),
        **jr,
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


# --------------------------------------------------------------------------- #
# BACKEND — which ENGINE computes a fair agent (rustport P6, wired 2026-08-02).  #
# --------------------------------------------------------------------------- #
def _resolve_backend(backend) -> str:
    """``"auto"`` -> governance/PRODUCTION.yaml; anything else validated and returned.

    Kept here rather than inlined so the candidate side, the opponent side and the
    manifest all resolve the SAME string exactly once per process."""
    b = str(backend or "python")
    if b == "auto":
        b = str(champion_factory.load_production_spec().backend)
    if b not in champion_factory.KNOWN_BACKENDS:
        raise SystemExit(
            f"--backend must be one of {sorted(champion_factory.KNOWN_BACKENDS)} "
            f"or 'auto'; got {backend!r}")
    return b


def _drives_mirror(agent) -> bool:
    """Does this agent own a Rust game mirror that the caller must advance?

    Duck-typed on the lifecycle rather than isinstance so this module never has to
    import carc_rs (the python-backend path must stay importable on a box with no
    Rust wheel — that is the whole point of the --backend python escape hatch)."""
    return hasattr(agent, "start_game") and hasattr(agent, "advance")


def _start_mirrors(board, *agents) -> None:
    """Seat every mirror-owning agent on the REAL initial board (its deck)."""
    for a in agents:
        if a is not None and _drives_mirror(a):
            a.start_game(board)


def _advance_mirrors(action, *agents) -> None:
    """Apply ONE action to every mirror — BOTH seats, every ply.

    ⚠️ This is the whole call-protocol difference between the Python and Rust
    champions, and the reason the audit told us not to flip a default underneath
    the harnesses. A caller that skips it leaves the mirror frozen at the ply it
    first saw; since 2026-08-01 that raises MirrorDesync instead of silently
    answering for a stale position, but it is still a broken run."""
    for a in agents:
        if a is not None and _drives_mirror(a):
            a.advance(int(action))


def _make_champion(info, cfg, sims, k_dets, K, seed, game, net=None,
                   net_mode="residual", net_lambda=0.25, handles=None,
                   sighted_game=None, rep=None, batch_size=1,
                   oracle_prior_mult=None, oracle_prior_eps_coef=1e-3,
                   meeple_dedup=None, intra_reuse=None,
                   coreml_model=None, net_backend=None,
                   backend="python", rust_threads=None,
                   simsplit=None):
    """Build the champion side, wrapped in the fair marginalized endgame at K.

    ``backend`` (2026-08-02) selects the ENGINE for the ``fair`` arm: ``"python"``
    (default, byte-identical to every row already in experiments/results.csv),
    ``"rust"``, or ``"auto"`` (resolve governance/PRODUCTION.yaml). On ``"rust"`` the
    WHOLE ``_MarginalizedHandoff`` is replaced, not just its ``._prefix``: RustFairAgent
    was deliberately built to emit this wrapper's exact counter shape
    (``prefix_moves`` / ``prefix_secs`` / ``exact_moves`` / ``solver_secs`` /
    ``solver_nodes`` / ``max_solve_secs`` / ``n_timeouts`` / ``latch_k``) and
    ``FairAgentRs`` owns ``solve_marginalized``, so the endgame solve moves into Rust
    too and the read-out below is unchanged. ⚠️ The returned agent OWNS A MIRROR — the
    caller MUST call ``start_game(board)`` once and ``advance(action)`` for every
    applied action of BOTH seats (``_play_one`` / ``_smoke`` do; see ``_advance_mirrors``).

    Only the ``fair`` arm converts. ``fair-netprior`` / ``fair-net`` need an injected
    evaluator and ``clair`` needs the true-deck ruler; carc_rs has neither (Gap 3 of
    BACKEND_BYPASS_AUDIT_20260801 §3), so they RAISE under ``backend="rust"`` rather
    than silently returning a Python agent a manifest would then stamp as Rust.

    ``oracle_prior_mult`` (Track-F Gate A, CANDIDATE side only; None = OFF) engages the
    per-world oracle-prior probe on the ``fair`` arm — see FairHeuristicPriorAgent. It is
    passed ONLY by the candidate call sites (_play_one / _smoke); _make_opponent never
    forwards it, so the opponent side is never oracle-armed.

    ``meeple_dedup`` (CANDIDATE side only; None = OFF = byte-identical) collapses
    game-equivalent meeple actions inside the candidate's search — see
    carcassonne_ai.meeple_equiv. It is a per-AGENT kwarg rather than the process-wide
    ``CARCASSONNE_MEEPLE_DEDUP`` env flag for exactly the reason the oracle probe is:
    both players live in ONE worker process, and a screen needs a dedup-ON candidate
    against a dedup-OFF champion. ``_make_opponent`` never forwards it.

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
    ``simsplit`` (CANDIDATE side only; None = OFF = byte-identical) is the
    ``(sims_tile, sims_meeple)`` pair of the phase-asymmetric sims-split lever —
    per-world sims per decision phase, either element None = the shared ``sims``.
    ``--info fair`` only (the PIMC agent is the one with a two-decision turn
    structure); works on BOTH backends. ``_make_opponent`` never forwards it.

    info=="clair"    -> HeuristicPriorAgent prefix (clairvoyant PUCT on the true deck)."""
    backend = _resolve_backend(backend)
    if simsplit is not None and info != "fair":
        raise SystemExit(
            f"--sims-tile/--sims-meeple is a --info fair (candidate) knob; got "
            f"--info {info}. The split binds the fair PIMC agent's TILES/MEEPLES "
            "decisions; the clairvoyant ruler and the net arms are out of its "
            "tested surface.")
    _split_kw = ({} if simsplit is None
                 else {k: int(v) for k, v in
                       zip(("sims_tile", "sims_meeple"), simsplit)
                       if v is not None})
    if backend == "rust" and info == "clair":
        # THE CLAIRVOYANT RULER ON carc_rs (rustport P6). `_MarginalizedHandoff` drives
        # its prefix with `.move()`, which on `HeuristicPriorAgent` re-roots or clears
        # according to the CONFIG's `reuse_tree` — and ⚠️ `production_prior_cfg()`
        # carries `reuse_tree=True`, so this ruler RE-ROOTS between moves rather than
        # starting fresh. `RustCarryClairvoyantAgent` resolves the flag from `cfg` the
        # same way the Python agent does; it is also the class whose `best_action` /
        # `move` split matches Python's, so a future caller that reaches for
        # `best_action` gets the CARRIED search Python would have given it rather than
        # a silent fresh one. (`RustClairvoyantAgent` does neither — see its docstring.)
        # ⚠️ A RULER: gated by scripts/rustport/gate_clair_backend.py (full-game,
        # per-ply action + root stats, bit-exact) before it grades anything.
        prefix = champion_factory.build_clairvoyant_champion(
            game, cfg=cfg, simulations=(sims * k_dets), seed=seed, backend="rust")
        return _MirrorMarginalizedHandoff(prefix, Game(enable_legal_moves_cache=True), K)
    if backend == "rust":
        if info != "fair":
            raise SystemExit(
                f"--backend rust is a --info fair|clair capability; got --info {info}. "
                "carc_rs carries no net evaluator (fair-netprior / fair-net) — run "
                "those with --backend python.")
        if oracle_prior_mult is not None:
            raise SystemExit(
                "--oracle-prior-mult is a python-only search overlay (it presearches "
                "each world with the true deck); it has no carc_rs implementation. "
                "Run the oracle arm with --backend python.")
        # The WHOLE handoff, not just the prefix: RustFairAgent emits this wrapper's
        # counter shape and FairAgentRs.solve_marginalized moves the endgame solve into
        # Rust as well, so nothing downstream of here changes shape.
        return champion_factory.build_fair_champion(
            game, cfg=cfg, sims=sims, k_dets=k_dets, seed=seed,
            exact_endgame=True, exact_max_k=int(K), exact_budget=EXACT_BUDGET,
            backend="rust", rust_threads=rust_threads,
            **({} if meeple_dedup is None else dict(meeple_dedup=bool(meeple_dedup))),
            **({} if intra_reuse is None else dict(intra_reuse=bool(intra_reuse))),
            **_split_kw)
    if info == "fair":
        # F1: route through the champion factory (single construction point). Byte-
        # identical to FairHeuristicPriorAgent(game, cfg, sims=..., k_dets=..., seed=...,
        # exact_endgame=False) — build_fair_champion forwards these verbatim and leaves
        # every other kwarg at the agent's own default (parity-gated, see F1 report).
        # Track-F Gate A oracle-prior overlay (CANDIDATE only; None = OFF = byte-identical).
        _oracle_kw = ({} if oracle_prior_mult is None
                      else dict(oracle_prior_mult=int(oracle_prior_mult),
                                oracle_prior_eps_coef=float(oracle_prior_eps_coef)))
        # Same shape as _oracle_kw: absent when OFF, so the constructor call is the
        # pre-feature one and the candidate is byte-identical to the deploy champion.
        _dedup_kw = ({} if meeple_dedup is None
                     else dict(meeple_dedup=bool(meeple_dedup)))
        # C3-INTRA within-turn carry — same absent-when-OFF shape, same candidate-only
        # scope. NOTE the read-out caveat: ON does MORE total work per turn at equal
        # nominal sims (the meeple half searches on top of a carried subtree), so a
        # positive screen needs an equal-WALL-CLOCK confirm before it means anything.
        _intra_kw = ({} if intra_reuse is None
                     else dict(intra_reuse=bool(intra_reuse)))
        prefix = champion_factory.build_fair_champion(
            game, cfg=cfg, sims=sims, k_dets=k_dets, seed=seed, exact_endgame=False,
            **_oracle_kw, **_dedup_kw, **_intra_kw, **_split_kw)
    elif info == "fair-netprior":
        if net is None and handles is None and coreml_model is None:
            raise ValueError(
                "info=fair-netprior requires a loaded net (--net), orch handles "
                "(--orch-shm-name), or a CoreML model (--net-backend coreml "
                "--coreml-model)")
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
        # NET-FORWARD BACKEND (None/"torch" = the pre-existing path, byte-identical).
        # "coreml" routes the policy forward through an Apple .mlpackage on CPU_AND_NE —
        # the ANE path the equal-wall-clock gate's reopen condition (r <= ~1.5) names.
        # The torch `net` is NOT loaded in that mode; only the rep comes from --net.
        evaluator = make_fair_net_prior_evaluator(
            cfg, net=net, handles=handles, coreml_model=coreml_model,
            net_backend=net_backend, sighted_game=sighted_game,
            sighted=_sighted_arg,
        )
        # LATENCY (2026-07-16): batch_size>1 collects that many leaves under virtual loss
        # -> ONE orch forward instead of a blocking IPC+GPU round-trip per expansion. Only
        # the net-prior CANDIDATE batches; the fair-champion opponent is net-free + serial.
        # The CoreML backend REFUSES to build one (fixed batch-1 artifact: batching
        # would buy no transport win while batch_size>1 still engages virtual loss and
        # changes the search). That raise is the guard against copy-pasting the CUDA
        # gate's `--batch-size 6` onto the ANE cell.
        batch_evaluator = (
            make_fair_net_prior_batch_evaluator(
                cfg, net=net, handles=handles, coreml_model=coreml_model,
                net_backend=net_backend, sighted_game=sighted_game,
                sighted=_sighted_arg)
            if batch_size > 1 else None)
        prefix = champion_factory.build_fair_champion(
            game, cfg=cfg, sims=sims, k_dets=k_dets, seed=seed, exact_endgame=False,
            evaluator=evaluator, batch_size=batch_size, batch_evaluator=batch_evaluator)
    elif info == "fair-net":
        if net is None and handles is None:
            raise ValueError(
                "info=fair-net requires a loaded net (--net) or orch handles "
                "(--orch-shm-name)")
        evaluator = _build_fairnet_evaluator(
            game, cfg, net_mode, net_lambda, net=net, handles=handles,
            sighted_game=sighted_game)
        prefix = champion_factory.build_fair_champion(
            game, cfg=cfg, sims=sims, k_dets=k_dets, seed=seed, exact_endgame=False,
            evaluator=evaluator)
    else:  # clair
        prefix = champion_factory.build_clairvoyant_champion(
            game, cfg=cfg, simulations=(sims * k_dets), seed=seed)
    return _MarginalizedHandoff(prefix, Game(enable_legal_moves_cache=True), K)


# --------------------------------------------------------------------------- #
# OPPONENT (--opponent) — the non-candidate seat.                              #
# --------------------------------------------------------------------------- #
OPPONENT_MODES = ("h800", "greedy", "fair-champion", "net", "bare-net")
# _HEAD_TO_HEAD = the SYMMETRIC head-to-head modes: both sides are fair production
# agents, both resolve curve125, both take the marginalized endgame at K, and both
# ride the shared `champ_cfg_dict` search knobs. `bare-net` is DELIBERATELY NOT one
# of these — it is asymmetric on information, leaf AND endgame (see the BLIND vs
# SIGHTED block in the module docstring), so every _HEAD_TO_HEAD-gated behaviour
# (curve125-on-both, opponent endgame, opponent prefix-timing read-out, shared-knob
# framing) correctly does NOT apply to it. Adding it here would silently symmetrise
# the cell and destroy its meaning.
_HEAD_TO_HEAD = ("fair-champion", "net")
_BARE_NET = "bare-net"
_GREEDY = "greedy"
# LEAFLESS RUNGS = fixed reference opponents that are NOT production PIMC agents: no
# determinizations, no per-det budget, no endgame tail, and (for greedy) no leaf at all.
# Every manifest/summary field that is champion-shaped must be null for these.
_LEAFLESS_RUNGS = ("h800", _GREEDY)
# Opponent modes that need a checkpoint (--opp-net).
_NET_OPPONENTS = ("net", _BARE_NET)


def _make_opponent(opponent, cfg_dict, sims, k_dets, K, rung_sims, seed,
                   opp_leaf_cfg=None, net=None, handles=None, sighted_game=None,
                   rep=None, opp_sims=None, opp_k_dets=None,
                   backend="python", rust_threads=None):
    """Build the OPPONENT side.

    ``backend`` reaches ONLY the ``fair-champion`` head-to-head, which is the same
    production PIMC agent as the candidate. The rungs are deliberately excluded: h800
    (`_RungPrefix`), greedy (`_GreedyPrefix`) and bare-net are FROZEN RULERS whose
    ratings in experiments/results.csv are interpretable only because they are
    bit-for-bit unchanged, so they stay Python whatever --backend says (Class C of
    BACKEND_BYPASS_AUDIT_20260801 §4). That asymmetry is also why a converted
    champion-vs-h800 cell realises ~5x rather than ~8x end-to-end: only one side moves.

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

    `opp_sims` (--opp-sims) and `opp_k_dets` (--opp-k-dets) are the TWO deliberate
    exceptions to "same cfg both sides": when set, the head-to-head opponent runs at that
    per-determinization sims budget / that determinization COUNT while the candidate
    keeps `sims`/`k_dets`, so the match is an equal-WALL-CLOCK deployability check (or a
    whole-config A/B like CL-060's k8x1376 candidate vs the k4x688 DEPLOY champion)
    rather than an equal-budget swap. None -> symmetric (uses `sims`/`k_dets`).
    """
    if opponent == _GREEDY:
        # tier1 / the L2 ladder's `greedy` rung. No budget knobs at all (rejected at the
        # CLI); `seed + 1` keeps the two sides off a shared stream, as for every other
        # opponent. No _MarginalizedHandoff wrapper — leafless and tail-less by design,
        # the same shape the h800 rung has always had.
        return _GreedyPrefix(Game(enable_legal_moves_cache=True), seed + 1)
    if opponent == "h800":
        # The h800 rung's budget is rung_sims; opp_sims/opp_k_dets are inapplicable here
        # (and are rejected for --opponent h800 in main()), so `sims`/`k_dets`/
        # `opp_sims`/`opp_k_dets` are all ignored.
        return _RungPrefix(Game(enable_legal_moves_cache=True), rung_sims, seed + 1,
                           DEFAULT_CONFIG)
    if opponent == _BARE_NET:
        # ⚠️ BLIND vs SIGHTED (module docstring). The opponent is the SIGHTED bare
        # NeuralMCTS anchor: PINNED sims/c_puct (never `sims`/`k_dets`/`opp_sims`/
        # `opp_k_dets` — those are rejected at the CLI for this mode), its OWN
        # curve100+rs0.25 leaf (`opp_leaf_cfg`, NEVER the candidate's curve125), and
        # NO endgame handoff (no _MarginalizedHandoff wrapper — the candidate-only
        # tail is the same shape the default h800 rung has always had). `seed + 1`
        # keeps the two sides off a shared stream, as for every other opponent.
        # `handles` (carc-orch SHM, --opp-orch-shm-name) and `net` (per-worker CPU) are
        # the two transports for the SAME weights; exactly one must be set.
        return _make_bare_net_opponent(net, rep, seed + 1, leaf_cfg=opp_leaf_cfg,
                                       handles=handles)
    if opponent not in _HEAD_TO_HEAD:
        raise ValueError(f"unknown opponent mode {opponent!r}")
    opp_cfg = _cfg_from_dict(cfg_dict, opp_leaf_cfg)
    info = "fair" if opponent == "fair-champion" else "fair-netprior"
    # --opp-sims / --opp-k-dets: the head-to-head opponent may run an ASYMMETRIC
    # per-determinization budget AND/OR determinization count (the equal-wall-clock
    # deployability check: candidate at a reduced --sims vs the champion at full budget;
    # or CL-060's k8x1376 candidate vs the k4x688 deploy champion). None -> the shared
    # `sims`/`k_dets`, byte-identical to the symmetric head-to-head. The CANDIDATE keeps
    # `sims`/`k_dets` (see _play_one / _smoke).
    _opp_sims = sims if opp_sims is None else opp_sims
    _opp_k_dets = k_dets if opp_k_dets is None else opp_k_dets
    # Only the symmetric fair-champion head-to-head can convert: `net` (fair-netprior)
    # needs an evaluator carc_rs does not have, and _make_champion raises on it anyway.
    _opp_backend = backend if info == "fair" else "python"
    return _make_champion(info, opp_cfg, _opp_sims, _opp_k_dets, K, seed + 1,
                          Game(enable_legal_moves_cache=True), net=net,
                          handles=handles, sighted_game=sighted_game, rep=rep,
                          backend=_opp_backend, rust_threads=rust_threads)


# The PRODUCTION champion's search knobs (governance/PRODUCTION.yaml). These are ALSO
# governance/PRODUCTION.yaml (NOT the argparse defaults — those stay at the common
# k4×688 eval config, which since CL-071 is a *deviation* and prints as one);
# `_prod_deviations` exists to catch any gap between a cell's knobs and the champion.
# k_dets/sims track the CL-071 promotion (2026-07-29): champion budget is k8×1376=11008.
# The pre-promotion k4×688 stood here until 2026-07-30, inverting the banner for a day
# (true-champion cells flagged as deviant, superseded-budget cells blessed) — see the
# 2026-07-30 audit F9 class and the h2h prereg note (ceb49a9).
PROD_KNOBS = {"c_puct": 1.5, "tau_p": 5.0, "leaf_quantize": "float",
              "value_norm": 15.0, "k_dets": 8, "sims": 1376}


def _prod_deviations(args, sims_override=None, k_dets_override=None):
    """Which shared search knobs differ from governance/PRODUCTION.yaml. Empty list ==
    the head-to-head opponent is literally the shipped champion config.

    `sims_override` / `k_dets_override` (the opponent's --opp-sims / --opp-k-dets budget
    in an ASYMMETRIC run) substitute for the `sims` / `k_dets` knobs so the OPPONENT
    block reports ITS OWN deviation, not the candidate's — with --opp-sims/--opp-k-dets
    the two sides deliberately search different budgets, so the shared-knob framing no
    longer holds for those axes. None (symmetric) -> getattr(args, ...), byte-identical
    to the pre---opp-sims/--opp-k-dets behavior."""
    _ovr = {"sims": sims_override, "k_dets": k_dets_override}
    out = []
    for k, want in PROD_KNOBS.items():
        got = getattr(args, k)
        if _ovr.get(k) is not None:
            got = _ovr[k]
        if isinstance(want, float) and float(got) != want:
            out.append(f"{k}={got:g} (production {want:g})")
        elif not isinstance(want, float) and got != want:
            out.append(f"{k}={got} (production {want})")
    return out


def _opp_eff_sims(args):
    """The OPPONENT's per-determinization PUCT sims budget. Defaults to the shared
    --sims (SYMMETRIC head-to-head, byte-identical to pre---opp-sims); --opp-sims
    overrides it so the head-to-head opponent runs an ASYMMETRIC (equal-wall-clock)
    budget while the candidate keeps --sims. The h800 rung is unaffected — its budget
    is --rung-sims, and --opp-sims is rejected for --opponent h800."""
    return args.opp_sims if args.opp_sims is not None else args.sims


def _opp_eff_k_dets(args):
    """The OPPONENT's determinization COUNT. Defaults to the shared --k-dets (SYMMETRIC
    head-to-head, byte-identical to pre---opp-k-dets); --opp-k-dets overrides it so the
    head-to-head opponent runs a DIFFERENT number of determinizations while the
    candidate keeps --k-dets. The CL-060 re-open trigger needs this: candidate
    k8x1376 (11008) vs the k4x688 (2752) DEPLOY champion is not expressible with a
    shared --k-dets. The h800 rung is unaffected (it is not a PIMC agent at all), and
    --opp-k-dets is rejected for --opponent h800."""
    return args.opp_k_dets if args.opp_k_dets is not None else args.k_dets


def _opp_label(args, opp_rep=None):
    """Human label for the opponent side (summary header + manifest)."""
    if args.opponent == "h800":
        return f"HeuristicMCTS(h{args.rung_sims})"
    if args.opponent == _GREEDY:
        return "tier1 greedy (1-ply RuleBasedPlayer, no search, no leaf)"
    if args.opponent == _BARE_NET:
        rep = ("?" if opp_rep is None
               else ("sighted-rep" if opp_rep["sighted"] else "non-sighted-rep"))
        return (f"SIGHTED (CLAIRVOYANT) bare NeuralMCTS anchor "
                f"({Path(args.opp_net).name}, {rep}, sims={BARE_NET_SIMS}, "
                f"c_puct={BARE_NET_CPUCT:g}, v2.9 curve100 leaf + "
                f"residual_scale={BARE_NET_RESIDUAL_SCALE:g}, NO exact tail)")
    _oes = _opp_eff_sims(args)     # --opp-sims (asymmetric) or the shared --sims
    _oek = _opp_eff_k_dets(args)   # --opp-k-dets (asymmetric) or the shared --k-dets
    if args.opponent == "fair-champion":
        return (f"FAIR PRODUCTION CHAMPION (FairHeuristicPriorAgent, heuristic priors, "
                f"curve125 leaf, k{_oek}x{_oes})")
    rep = ("?" if opp_rep is None
           else ("sighted" if opp_rep["sighted"] else "non-sighted"))
    return (f"FAIR NET-PRIOR agent ({Path(args.opp_net).name}, {rep} rep, curve125 leaf, "
            f"k{_oek}x{_oes})")


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


def _oracle_telemetry(agent) -> dict:
    """Per-game Track-F Gate A oracle cost telemetry read off the CANDIDATE's
    FairHeuristicPriorAgent (empty {} for any non-oracle candidate, so the GameResult
    keeps the default zeros and _save omits them). ``agent`` is the fair PIMC agent
    behind the candidate's _MarginalizedHandoff (its ``._prefix``)."""
    if agent is None or getattr(agent, "oracle_prior_mult", None) is None:
        return {}
    return {
        "oracle_prior_moves": int(agent.oracle_moves),
        "oracle_presearch_worlds": int(agent.oracle_presearch_worlds),
        "oracle_presearch_secs": round(float(agent.oracle_presearch_secs), 3),
        "oracle_mainsearch_secs": round(float(agent.oracle_mainsearch_secs), 3),
        "oracle_presearch_leaf_calls": int(agent.oracle_presearch_leaf_calls),
        "oracle_mainsearch_leaf_calls": int(agent.oracle_mainsearch_leaf_calls),
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
    # Track-F Gate A oracle-prior per-game cost telemetry (CANDIDATE side; 0 unless the
    # candidate is oracle-armed). OMITTED from the serialized JSON for non-oracle cells
    # (see _save) so every legacy cell stays byte-identical to today's schema.
    oracle_prior_moves: int = 0
    oracle_presearch_worlds: int = 0
    oracle_presearch_secs: float = 0.0
    oracle_mainsearch_secs: float = 0.0
    oracle_presearch_leaf_calls: int = 0
    oracle_mainsearch_leaf_calls: int = 0
    # J-RULES ROOT FILTER surface C (CANDIDATE side): the per-game liveness
    # telemetry — {"dropped_total", "applicable_moves", "fires", "yields"}
    # read off FairAgentRs.stats() at game end. None for every non-filter cell
    # (legacy schema byte-identical). The prereg's positive control sums
    # dropped_total over the cell's records: a live-mask cell where that sum
    # is 0 never fired the filter and MUST NOT be read as a null.
    cand_jf: dict | None = None


# Track-F Gate A oracle-prior cost fields — OMITTED from the serialized per-game JSON for
# non-oracle cells (all zero there) so every legacy/non-oracle cell stays byte-identical
# to today's schema. _try_load re-fills them from the dataclass defaults, so a reload is
# lossless either way.
_ORACLE_RESULT_FIELDS = (
    "oracle_prior_moves", "oracle_presearch_worlds", "oracle_presearch_secs",
    "oracle_mainsearch_secs", "oracle_presearch_leaf_calls", "oracle_mainsearch_leaf_calls",
)


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
    d = asdict(r)
    if not d.get("oracle_prior_moves"):   # non-oracle cell -> omit oracle keys (schema-identical)
        for k in _ORACLE_RESULT_FIELDS:
            d.pop(k, None)
    tmp = p.with_name(f".{p.stem}.{socket.gethostname()}.{os.getpid()}.partial.json")
    json.dump(d, open(tmp, "w"))
    tmp.replace(p)


# --------------------------------------------------------------------------- #
# CRASH RESILIENCE — a per-game failure is DATA, not the end of the pass.       #
#                                                                              #
# ⚠️ House lesson, twice learned. (1) capoff / DECISIONS 2026-07-31: a game     #
# that dies deterministically and leaves ZERO records is the dangerous pattern  #
# — the loss is invisible and it can be CANDIDATE-CORRELATED (capoff's 16       #
# missing games were exactly the ones its own style drove into the 25x25 action #
# window wall). (2) 2026-08-14, cell `oc2_C_d16p0_deploy11008`: ONE game raising #
# `carc_rs.WindowTruncationError` out of `imap_unordered` killed the WHOLE pass, #
# and every game in flight lost its `--shared-claim` claim file → 14 of 800     #
# records lost (1 poisoned + 13 collateral) across 16 retry passes that each    #
# re-crashed on the identical position.                                        #
#                                                                              #
# So a raise becomes a FAILURE RECORD: written to `<out>/failed/`, counted, and #
# shouted about. Two properties are load-bearing and are what the tests pin:    #
#   * it can NEVER be mistaken for a game result — it lives in a SUBDIRECTORY   #
#     (every downstream reader globs the cell dir NON-recursively: `*.json`,    #
#     `seed*_a*.json`, `*seed*.json`), it carries `failed: true` and NO `diff` / #
#     `won_by_champ` / `drew` key, and `_try_load` never looks at it;          #
#   * it is BOUNDED — the record accumulates a lifetime `attempts` count, so a  #
#     deterministic crash cannot be retried forever (see `--max-attempts`).     #
# Mirrors `scripts/joshuabot/h2h.py` (commit 0102b72d) field-for-field:         #
# `failed` / `exc_type` / `exc` / `traceback` / `window_truncation` /           #
# `window_diag` / `window_root_record` / `n_failed` / `failure_rate` /          #
# `failed_cells` / `failed_by_seat` / `--retry-failed`. The two harnesses must  #
# not diverge into two conventions (the `ms_ratio` lesson, commit 56c69022).    #
# --------------------------------------------------------------------------- #
FAILED_SCHEMA = "carcassonne-eval-fair-puct/v1/failed"

#: Subdirectory of the cell dir that holds failure records. NOT the cell dir
#: itself — every downstream reader globs the cell dir non-recursively.
FAILED_DIRNAME = "failed"

#: Pre-registered validity trigger (house reference): failed games above this
#: fraction of n ⇒ STOP and investigate before reading the cell's number.
FAILURE_RATE_TRIGGER = 0.005


@dataclass
class GameFailure:
    """The in-process handle a worker returns for a game that RAISED. Deliberately
    NOT a `GameResult`: the driver appends only `GameResult`s to `results`, so a
    failure can never reach `_summary`'s statistics by construction."""
    seed: int
    a_seat: int
    attempts: int
    exc_type: str
    exc: str
    permanent: bool = False
    window_truncation: bool = False
    record: dict | None = None


def _failed_dir(out: Path) -> Path:
    return Path(out) / FAILED_DIRNAME


def _failed_path(out: Path, seed: int, a_seat: int) -> Path:
    return _failed_dir(out) / f"seed{seed:012d}_a{a_seat}.json"


def _load_failure(p: Path) -> dict | None:
    """A failure record, or None. A torn/garbage file is treated as absent (and
    left alone — unlike `_try_load`, which unlinks: a failure record is evidence)."""
    try:
        d = json.load(open(p))
    except Exception:
        return None
    return d if isinstance(d, dict) and d.get("failed") else None


def load_failures(out, include_resolved=False) -> dict:
    """The OUTSTANDING failure records in a cell, keyed by (seed, a_seat).

    ⚠️ RESOLVED failures are excluded by default. A game that failed on one pass
    and SUCCEEDED on a later ``--retry-failed`` pass leaves both a failure record
    and a result; counting the stale record would report ``n_failed=1`` on a cell
    that completed cleanly — and ``failure_rate`` is the input to the PRE-REGISTERED
    VALIDITY TRIGGER (>0.5% ⇒ stop and investigate), so an overstated rate can void
    a good cell. The RESULT FILE IS THE ARBITER: a record whose `_result_path`
    exists is resolved, which is authoritative with no bookkeeping and stays correct
    even when a --shared-claim PEER on another box played the successful retry.

    The record itself is never deleted — a transiently-failing game is evidence
    about the window-truncation family, and flaky-vs-deterministic is exactly the
    distinction worth keeping. Pass ``include_resolved=True`` for the forensic view;
    every returned record carries a `resolved` bool.
    """
    out = Path(out)
    d = _failed_dir(out)
    if not d.is_dir():
        return {}
    found = {}
    for p in sorted(d.glob("seed*_a*.json")):
        rec = _load_failure(p)
        if rec is None or "seed" not in rec or "a_seat" not in rec:
            continue
        seed, a_seat = int(rec["seed"]), int(rec["a_seat"])
        rec["resolved"] = _result_path(out, seed, a_seat).exists()
        if rec["resolved"] and not include_resolved:
            continue
        found[(seed, a_seat)] = rec
    return found


def _mark_failure_resolved(out: Path, seed: int, a_seat: int) -> None:
    """Stamp a superseded failure record `resolved: true` after its retry SUCCEEDED.

    Belt-and-braces on top of the read-side rule in :func:`load_failures` (which is
    what actually decides the counts): this makes the file SELF-DESCRIBING, so a
    human reading `failed/seed*.json` months later sees that the crash was later
    played through rather than mistaking it for a live exclusion.

    Costs one `exists()` on the success path and nothing else — a cell that never
    failed does no work here."""
    p = _failed_path(out, seed, a_seat)
    if not p.exists():                          # the overwhelmingly common case
        return
    rec = _load_failure(p)
    if rec is None or rec.get("resolved"):
        return
    rec["resolved"] = True
    rec["resolved_at"] = time.time()
    rec["resolved_by_host"] = socket.gethostname()
    try:
        _save_failure(p, rec)
    except Exception as e:                      # never let bookkeeping kill a game
        sys.stderr.write(f"[eval_fair_puct] could not stamp resolved failure {p}: {e}\n")


def failed_record(seed: int, a_seat: int, exc: BaseException, t0: float,
                  attempts: int, max_attempts: int, prior: dict | None = None) -> dict:
    """The record a game that RAISED leaves behind. Field names mirror
    `h2h.failed_record` (`failed`/`exc_type`/`exc`/`traceback`/`window_*`)."""
    import traceback as _tb

    from carcassonne_ai import window_truncation as _WT

    rec = {
        "schema": FAILED_SCHEMA,
        "failed": True,
        # `seed`/`a_seat` are this harness's native cell key; `deck_seed` is the
        # h2h-side spelling of the same number, carried so a cross-harness reader
        # (or a census) needs no per-harness special case.
        "seed": int(seed),
        "a_seat": int(a_seat),
        "deck_seed": int(seed),
        "info": _W.get("info"),
        "opponent": _W.get("opponent", "h800"),
        "exact_k": _W.get("exact_k"),
        "k_dets": _W.get("k_dets"),
        "sims": _W.get("sims"),
        "rung_sims": _W.get("rung_sims"),
        "attempts": int(attempts),
        "max_attempts": int(max_attempts),
        # ⚠️ THE TERMINATION GUARANTEE. Once the lifetime attempt budget is spent
        # the cell is permanently failed and `--retry-failed` will NOT re-open it.
        "permanent": bool(attempts >= max_attempts),
        "exc_type": type(exc).__name__,
        "exc": str(exc)[:2000],
        "traceback": "".join(_tb.format_exception(exc))[-4000:],
        "host": socket.gethostname(),
        "pid": os.getpid(),
        "finished_at": time.time(),
        "cell_secs": round(time.time() - t0, 2),
        "prior_attempts": int((prior or {}).get("attempts", 0)),
    }
    # F-c: an exclusion that says WHY (identical to h2h). `window_diag` is the
    # search's own EMPTY_MASK_DIAG payload — cause / mask counters / window /
    # depth / dropped coordinates — so a live crash lands census-ready.
    try:
        rec["window_truncation"] = _WT.is_window_truncation(exc)
        rec["window_diag"] = _WT.parse_diag(exc)
    except Exception:                          # diagnostics must never re-raise
        rec["window_truncation"] = False
        rec["window_diag"] = None
    root = getattr(exc, "window_root_record", None)
    if root is not None:
        rec["window_root_record"] = root
        rec["window_root_path"] = getattr(exc, "window_root_path", None)
    return rec


def _save_failure(p: Path, rec: dict) -> None:
    """Atomic rename-into-place, exactly like `_save` (a shared-claim peer must
    never read a half-written record)."""
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.stem}.{socket.gethostname()}.{os.getpid()}.partial.json")
    with open(tmp, "w") as fh:
        json.dump(rec, fh, indent=1, default=str)
    tmp.replace(p)


def _release_claim(p: Path) -> None:
    """Drop this game's `--shared-claim` claim file. THE fix for the collateral
    damage: a claim left behind by a dead pass is a claim-without-record, and a
    resume stalls on it forever until someone hand-cleans (memory:
    feedback_shared_claim_orphan_stall). A failed game releases its own claim, so
    the stall can never start."""
    try:
        p.with_suffix(".claim").unlink(missing_ok=True)
    except OSError as e:                        # never let cleanup kill the pass
        sys.stderr.write(f"[eval_fair_puct] could not release claim for {p}: {e}\n")


_W: dict = {}


def _worker_init(info, champ_cfg_dict, sims, k_dets, exact_k, rung_sims,
                 shared_claim, claim_host, claim_stale, net_ckpt=None,
                 net_mode="residual", net_lambda=0.25, orch_shm_name="", id_q=None,
                 cand_leaf_cfg=None, rep=None, opponent="h800", opp_leaf_cfg=None,
                 opp_net_ckpt=None, opp_rep=None, opp_orch_shm_name="", batch_size=1,
                 opp_sims=None, oracle_prior_mult=None, oracle_prior_eps_coef=1e-3,
                 opp_k_dets=None, meeple_dedup=None, intra_reuse=None,
                 netprior_backend=None, backend="python", rust_threads=None,
                 simsplit=None, cand_jrules_prior=None, cand_jrules_filter=None):
    _W["info"] = info
    # J-RULES PRIOR surface B (CANDIDATE side ONLY, rust-only; None = OFF =
    # byte-identical). A dict {dose, mask, scope} resolved once in main().
    _W["cand_jrules_prior"] = cand_jrules_prior
    # J-RULES ROOT FILTER surface C (CANDIDATE side ONLY, rust-only; None =
    # OFF = byte-identical). A dict {mask, min_keep} resolved once in main().
    _W["cand_jrules_filter"] = cand_jrules_filter
    # ENGINE (rustport P6). Resolved ONCE in main() and passed as a literal, never as
    # "auto" — a worker that re-resolved the YAML could disagree with the manifest.
    _W["backend"] = backend
    # ⚠️ FARM RULE: this is a GAME-PARALLEL pool, so each worker runs the Rust agent at
    # threads=1 and the game parallelism owns the cores. W16 x t8 = 128 hot threads is
    # the failure mode. main() defaults this to 1 for any pooled run and asserts it.
    _W["rust_threads"] = rust_threads
    if backend == "rust":
        _t = 1 if rust_threads is None else int(rust_threads)
        assert _t >= 1, f"rust_threads must be >=1; got {_t}"
        _W["rust_threads"] = _t
    # within-search leaf batching for the net-prior CANDIDATE (1 = serial byte-exact).
    _W["batch_size"] = batch_size
    # Track-F Gate A oracle-prior probe (CANDIDATE side; None = OFF).
    _W["oracle_prior_mult"] = oracle_prior_mult
    _W["oracle_prior_eps_coef"] = oracle_prior_eps_coef
    # MEEPLE-DEDUP search feature (CANDIDATE side; None = OFF = byte-identical).
    _W["meeple_dedup"] = meeple_dedup
    # C3-INTRA within-turn tree carry (CANDIDATE side; None = OFF = byte-identical).
    _W["intra_reuse"] = intra_reuse
    # SIMS-SPLIT (sims_tile, sims_meeple) pair (CANDIDATE side; None = OFF = byte-identical).
    _W["simsplit"] = simsplit
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
    # --opp-sims / --opp-k-dets: asymmetric per-det budget / determinization count for
    # the head-to-head opponent (None -> the shared `sims`/`k_dets`, symmetric). h800
    # ignores both (its budget is rung_sims and it is not a PIMC agent).
    _W["opp_sims"] = opp_sims
    _W["opp_k_dets"] = opp_k_dets
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
    # NET-FORWARD BACKEND for the fair-netprior candidate. `netprior_backend` is
    # (net_backend, coreml_model_path, compute_units) or None. None keeps every
    # pre-existing call byte-identical; it is ONE packed positional rather than three so
    # the two long `initargs=` tuples in main() grow by one entry, not three.
    _W["net_backend"], _cml_path, _cml_units = (netprior_backend or (None, None, None))
    _W["coreml_model"] = None

    if info == "fair-netprior":
        # The distilled-agent arm. The rep (sighted 81ch/42 vs non-sighted 78ch/10) was
        # resolved in main() from the CHECKPOINT and is passed down, so every worker
        # encodes exactly the rep the net was trained on.
        if _W["net_backend"] == "coreml":
            # Apple ANE. Each worker loads its OWN MLModel — a CoreML model is not
            # fork-safe and each worker predicts independently. The ANE is a SHARED
            # device that serialises requests, so W workers do NOT give W× the forward
            # throughput; the runbook sizes W accordingly and the equal-time probe must
            # be run at the SAME W as the cell (the gate's ops note 4: "W was
            # load-bearing and must not be optimised").
            #
            # NOTE the torch net is deliberately NOT loaded here. --net is still
            # required and is still the rep + provenance anchor, but in this mode it is
            # read once in main(), never in a worker.
            from carcassonne_ai.coreml_evaluator import load_coreml_model
            if not _cml_path:
                raise SystemExit(
                    "FATAL: --net-backend coreml needs --coreml-model <.mlpackage>")
            _W["coreml_model"] = load_coreml_model(_cml_path, compute_units=_cml_units)
            _W["sighted_game"] = Game(sighted=bool(rep["sighted"]))
        elif orch_shm_name:
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
    elif opponent == _BARE_NET:
        # BLIND vs SIGHTED: the opponent is a bare sighted NeuralMCTS. Two transports
        # for the SAME weights — carc-orch SHM (the GPU server owns the only net; the
        # standing default for neural eval) or a per-worker CPU net. The AGENT is
        # identical either way; only float reduction order differs (BARE_NET_GPU_NOTE).
        if opp_orch_shm_name:
            # Slot dims come from the OPPONENT's OWN resolved rep — hardcoding 78/12
            # would corrupt every forward for any other rep (the n_ch trap).
            from carcassonne_ai.shm_eval_handles import connect_shm
            # No net is loaded here (the server owns it), but evaluators/torch still
            # get imported downstream — pin the intra-op pool so W workers can't each
            # spin up a box-sized OpenMP pool. Same discipline as the CPU branch.
            import torch
            torch.set_num_threads(1)
            _W["opp_handles"] = connect_shm(opp_orch_shm_name, _wid,
                                            int(opp_rep["n_scalar_features"]),
                                            int(opp_rep["n_input_channels"]))
            # _make_bare_net_opponent builds the encoder Game per game from `opp_rep`
            # (it is BOTH the encoder and the NeuralMCTS game), exactly as on CPU.
            _W["opp_sighted_game"] = None
        else:
            # Same re-load cross-check as the `net` opponent above: main() resolved the
            # rep from the checkpoint, the worker re-loads and must agree.
            import torch
            torch.set_num_threads(1)     # mirrors eval_puct_priors._load_net_cpu
            _W["opp_net"], _oloaded = _load_net_rep(opp_net_ckpt, device="cpu")
            if (bool(_oloaded["sighted"]) != bool(opp_rep["sighted"])
                    or int(_oloaded["n_input_channels"]) != int(opp_rep["n_input_channels"])
                    or int(_oloaded["n_scalar_features"]) != int(opp_rep["n_scalar_features"])):
                raise SystemExit(
                    f"FATAL: worker re-loaded bare-net opponent {opp_net_ckpt} as "
                    f"sighted={_oloaded['sighted']} {_oloaded['n_input_channels']}ch/"
                    f"{_oloaded['n_scalar_features']}sc but main() resolved "
                    f"sighted={opp_rep['sighted']} {opp_rep['n_input_channels']}ch/"
                    f"{opp_rep['n_scalar_features']}sc")
            # _make_bare_net_opponent builds the encoder Game per game from `opp_rep`.
            _W["opp_sighted_game"] = None


def _args_simsplit(args):
    """The (sims_tile, sims_meeple) pair, or None when neither flag was passed —
    the OFF shape every pre-knob call keeps (nothing new reaches the agent)."""
    if args.sims_tile is None and args.sims_meeple is None:
        return None
    return (args.sims_tile, args.sims_meeple)


def _cfg_from_dict(d, leaf_cfg=None, jrules_prior=None, jrules_filter=None):
    # `jrules_prior`/`jrules_filter` reach ONLY the candidate construction site
    # in _play_one; the opponent/rung builders never pass them (None ==
    # pre-B/pre-C byte-identical).
    return _build_champ_cfg(d["c_puct"], d["tau_p"], d["leaf_quantize"],
                            d["final_select"], d["value_norm"], leaf_cfg,
                            jrules_prior=jrules_prior,
                            jrules_filter=jrules_filter)


def _play_one(args) -> GameResult | GameFailure | None:
    """One (seed, a_seat) game, GUARDED.

    A raise here used to propagate out of `imap_unordered` and kill the ENTIRE
    pass — taking every in-flight game's `--shared-claim` claim with it (the
    2026-08-14 `oc2_C_d16p0_deploy11008` incident: 1 poisoned game, 13 collateral).
    One pathological deck must cost one deck, not the cell. So anything short of
    an operator interrupt becomes a `GameFailure` + an on-disk failure record, the
    claim is released, and the pool carries on."""
    out_str, seed, a_seat = args[0], args[1], args[2]
    max_attempts = int(args[3]) if len(args) > 3 else 1
    out = Path(out_str)
    p = _result_path(out, seed, a_seat)
    cached = _try_load(p)
    if cached is not None:
        return cached
    if _W.get("shared_claim"):
        if not _try_claim(p.with_suffix(".claim"), _W["claim_host"], _W["claim_stale"]):
            return None
    t_fail = time.time()
    try:
        r = _play_one_inner(out, seed, a_seat, p)
        # A --retry-failed that SUCCEEDED supersedes its old failure record. The
        # counts are decided read-side (load_failures), but stamp the file so it
        # says so itself. Kept, never deleted: the diagnosis is evidence.
        _mark_failure_resolved(out, seed, a_seat)
        return r
    except (KeyboardInterrupt, SystemExit):     # operator/parent shutdown: propagate
        raise
    except BaseException as exc:                # noqa: BLE001 — incl. pyo3 PanicException
        prior = _load_failure(_failed_path(out, seed, a_seat))
        attempts = int((prior or {}).get("attempts", 0)) + 1
        rec = failed_record(seed, a_seat, exc, t_fail, attempts, max_attempts, prior)
        try:
            _save_failure(_failed_path(out, seed, a_seat), rec)
        except Exception as e:                  # a failed WRITE must still not be fatal
            sys.stderr.write(f"[eval_fair_puct] could not write failure record "
                             f"seed={seed} a_seat={a_seat}: {e}\n")
        finally:
            # ⚠️ ALWAYS, and always AFTER the record: a stranded claim with no
            # record is what stalls the next --resume.
            _release_claim(p)
        return GameFailure(seed=int(seed), a_seat=int(a_seat), attempts=attempts,
                           exc_type=rec["exc_type"], exc=rec["exc"],
                           permanent=bool(rec["permanent"]),
                           window_truncation=bool(rec.get("window_truncation")),
                           record=rec)


def _play_one_inner(out: Path, seed: int, a_seat: int, p: Path) -> GameResult:
    """The game itself. UNCHANGED from the pre-guard version — a zero-failure cell
    is bit-identical, because nothing on this path moved."""
    import random
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True)  # referee / deck driver
    board = game.get_init_board()
    dh = deck_hash(board)

    cfg = _cfg_from_dict(_W["champ_cfg_dict"], _W.get("cand_leaf_cfg"),
                         jrules_prior=_W.get("cand_jrules_prior"),
                         jrules_filter=_W.get("cand_jrules_filter"))
    champ = _make_champion(_W["info"], cfg, _W["sims"], _W["k_dets"], _W["exact_k"],
                           seed, Game(enable_legal_moves_cache=True),
                           net=_W.get("net"), net_mode=_W["net_mode"],
                           net_lambda=_W["net_lambda"], handles=_W.get("handles"),
                           coreml_model=_W.get("coreml_model"),
                           net_backend=_W.get("net_backend"),
                           sighted_game=_W.get("sighted_game"), rep=_W.get("rep"),
                           batch_size=_W.get("batch_size", 1),
                           oracle_prior_mult=_W.get("oracle_prior_mult"),
                           oracle_prior_eps_coef=_W.get("oracle_prior_eps_coef", 1e-3),
                           meeple_dedup=_W.get("meeple_dedup"),
                           intra_reuse=_W.get("intra_reuse"),
                           backend=_W.get("backend", "python"),
                           rust_threads=_W.get("rust_threads"),
                           simsplit=_W.get("simsplit"))
    rung = _make_opponent(
        _W.get("opponent", "h800"), _W["champ_cfg_dict"], _W["sims"], _W["k_dets"],
        _W["exact_k"], _W["rung_sims"], seed, opp_leaf_cfg=_W.get("opp_leaf_cfg"),
        net=_W.get("opp_net"), handles=_W.get("opp_handles"),
        sighted_game=_W.get("opp_sighted_game"), rep=_W.get("opp_rep"),
        opp_sims=_W.get("opp_sims"), opp_k_dets=_W.get("opp_k_dets"),
        backend=_W.get("backend", "python"),
        rust_threads=_W.get("rust_threads"))

    # Seat any Rust mirror on the REAL initial board before the first decision, and
    # advance it on EVERY applied action of BOTH seats below. No-op for python agents.
    _start_mirrors(board, champ, rung)

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
        _advance_mirrors(action, champ, rung)
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
        cand_jf=_cand_jf_telemetry(champ),
        opponent=_W.get("opponent", "h800"), **_opp_stats(rung),
        # Track-F Gate A: candidate oracle cost telemetry (empty {} for non-oracle cells,
        # so the fields stay at their dataclass-default zeros and _save omits them).
        **_oracle_telemetry(getattr(champ, "_prefix", None)),
    )
    _save(p, r)
    return r


# --------------------------------------------------------------------------- #
def _cand_jf_telemetry(champ) -> dict | None:
    """Surface-C per-game liveness read (CANDIDATE side). None unless the
    worker was armed with cand_jrules_filter AND the champion is the rust fair
    agent (the only host of the filter); a filter-armed cell whose candidate is
    NOT a RustFairAgent is a wiring bug and raises rather than stamping None."""
    if _W.get("cand_jrules_filter") is None:
        return None
    rs = getattr(champ, "_rs", None)
    if rs is None:
        raise RuntimeError(
            "cand_jrules_filter is armed but the candidate has no FairAgentRs "
            "(surface C is rust-only) — the filter cannot have run")
    s = rs.stats()
    return {
        "dropped_total": int(s["jf_dropped_total"]),
        "applicable_moves": int(s["jf_applicable_moves"]),
        "fires": {str(k): int(v) for k, v in s["jf_fires"]},
        "yields": {str(k): int(v) for k, v in s["jf_yields"]},
    }


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


def _failure_block(results, failures, resolved=None) -> dict:
    """The EXCLUSION block. Key names mirror `h2h.summarize` exactly
    (`n_failed` / `failure_rate` / `failed_cells` / `failed_by_seat`), and they are
    ALWAYS present — a zero rate is stated, never inferred from a missing key or
    from a record count that does not add up.

    `failures` is the list of OUTSTANDING failure records for this cell (from
    `load_failures`). `resolved` is the list of records whose game later SUCCEEDED:
    those are NOT failures of this cell — they move no count, and above all they do
    not inflate `failure_rate`, which gates the pre-registered validity trigger.
    They are reported under their own keys so the forensic trail (a
    transiently-failing game is evidence about the window-truncation family) stays
    discoverable from the summary alone."""
    bad = list(failures or [])
    fixed = [r for r in (resolved or []) if r.get("resolved")]
    n_scored = len(results)
    n_records = n_scored + len(bad)
    rate = (len(bad) / n_records) if n_records else 0.0
    return {
        # ⚠️ THE EXCLUSION LINE. Read it before the elo.
        "n_failed": len(bad),
        "failure_rate": rate,
        # PRE-REGISTERED VALIDITY TRIGGER: >0.5% failed ⇒ stop and investigate
        # before reading this cell's number.
        "failure_rate_trigger": FAILURE_RATE_TRIGGER,
        "validity_trigger_fired": bool(rate > FAILURE_RATE_TRIGGER),
        "failed_cells": [{"seed": int(r.get("seed", -1)),
                          "a_seat": int(r.get("a_seat", -1)),
                          "attempts": int(r.get("attempts", 0)),
                          "permanent": bool(r.get("permanent")),
                          "exc_type": r.get("exc_type"),
                          "exc": r.get("exc"),
                          "window_truncation": bool(r.get("window_truncation")),
                          "window_diag": r.get("window_diag")} for r in bad],
        "failed_by_seat": {"0": sum(1 for r in bad if int(r.get("a_seat", -1)) == 0),
                           "1": sum(1 for r in bad if int(r.get("a_seat", -1)) == 1)},
        # NOT failures of this cell — a crash that a later pass played through.
        # Counted separately so a flaky game stays visible without voiding the cell.
        "n_resolved_failures": len(fixed),
        "resolved_failed_cells": [{"seed": int(r.get("seed", -1)),
                                   "a_seat": int(r.get("a_seat", -1)),
                                   "attempts": int(r.get("attempts", 0)),
                                   "exc_type": r.get("exc_type"),
                                   "window_truncation": bool(r.get("window_truncation"))}
                                  for r in fixed],
    }


def _shout_failures(block: dict, n_scored: int, tag="eval_fair_puct") -> None:
    """Print the exclusion line loudly. A cell must never quietly complete with a
    high failure rate — this is the operator-visible half of the validity trigger
    (the machine-readable half is `summary.json` / `manifest.json`)."""
    if block.get("n_resolved_failures"):
        # Informational, never a trigger: these games ended up PLAYED.
        print(f"\n[{tag}] {block['n_resolved_failures']} earlier failure(s) were "
              f"RESOLVED by a later successful retry — not counted as failures "
              f"(records kept in <out>/{FAILED_DIRNAME}/ with resolved: true): "
              f"{[(c['seed'], c['a_seat'], c['exc_type']) for c in block['resolved_failed_cells']]}",
              flush=True)
    if not block.get("n_failed"):
        return
    pct = 100.0 * (block.get("failure_rate") or 0.0)
    cells = [(c["seed"], c["a_seat"], c["exc_type"]) for c in block["failed_cells"]]
    print(f"\n⚠️ [{tag}] {block['n_failed']} FAILED GAME(S) = {pct:.2f}% of "
          f"{block['n_failed'] + n_scored} attempted — these are EXCLUSIONS, not "
          f"zeros, and a paired deck with one dead seat drops out of the PAIRED "
          f"margin entirely. by seat {block['failed_by_seat']}. Records in "
          f"<out>/{FAILED_DIRNAME}/. Cells: {cells}", flush=True)
    if block.get("validity_trigger_fired"):
        print(f"⚠️⚠️ [{tag}] VALIDITY TRIGGER FIRED: failed games "
              f"{pct:.2f}% > {100.0 * FAILURE_RATE_TRIGGER:.1f}% of n. "
              f"STOP AND INVESTIGATE BEFORE READING THIS CELL'S NUMBER.", flush=True)


def _filter_failed_todo(todo, prior_failures: dict, retry_failed: bool,
                        max_attempts: int):
    """Drop (or re-open) the games already on disk as FAILED records.

    Returns ``(todo, reopened, skipped, exhausted)``.

    ⚠️ This is THE termination guarantee, in three lines:
      * default (no ``--retry-failed``) — a failed game is DONE, exactly as in
        h2h's ``load_done``. These failures are deck-deterministic, so a plain
        relaunch would re-burn a full game-time per pathological cell forever;
        the 2026-08-14 incident did precisely that, 16 times.
      * ``--retry-failed`` — re-open it (the h2h semantics: after a code fix)…
      * …but ONLY while its LIFETIME ``attempts`` is under ``--max-attempts``.
        Past that it is PERMANENT: a wrapper looping ``--retry-failed`` still
        converges instead of grinding on a deterministic crash.
    """
    keep, reopened, skipped, exhausted = [], [], [], []
    for t in todo:
        rec = prior_failures.get((t[1], t[2]))
        if rec is None:
            keep.append(t)
        elif not retry_failed:
            skipped.append(t)
        elif int(rec.get("attempts", 0)) >= int(max_attempts):
            exhausted.append(t)
        else:
            reopened.append(t)
            keep.append(t)
    return keep, reopened, skipped, exhausted


def _patch_failure_manifest(out, block: dict, n_failed_this_leg: int) -> None:
    """Surface the exclusion count in the cell's `manifest.json` (h2h parity:
    `close_out` closes the run manifest with the same numbers). Top-level keys, so
    a reader can `jq .n_failed manifest.json` without knowing this harness."""
    patch_manifest(out, "n_failed", int(block.get("n_failed", 0)))
    patch_manifest(out, "failure_rate", block.get("failure_rate", 0.0))
    patch_manifest(out, "n_failed_this_leg", int(n_failed_this_leg))
    patch_manifest(out, "validity_trigger_fired",
                   bool(block.get("validity_trigger_fired")))
    patch_manifest(out, "failed_cells", block.get("failed_cells", []))
    patch_manifest(out, "failed_by_seat", block.get("failed_by_seat", {"0": 0, "1": 0}))
    patch_manifest(out, "n_resolved_failures", int(block.get("n_resolved_failures", 0)))
    patch_manifest(out, "resolved_failed_cells", block.get("resolved_failed_cells", []))


def _summary(results, info, exact_k, k_dets, sims, rung_sims, opponent="h800",
             opp_label=None, opp_k_dets=None, opp_sims=None, failures=None,
             resolved=None):
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
                     else "tier1 greedy (1-ply RuleBasedPlayer)" if opponent == _GREEDY
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
    if opponent == _BARE_NET:
        # Restate the asymmetry wherever the number is printed, so a reader who only
        # sees the summary cannot mistake this for a like-for-like pairwise elo.
        print("  ⚠️ BLIND vs SIGHTED (deliberate): candidate is blind (fair PIMC) on the "
              "curve125 leaf with an exact-K tail; opponent is CLAIRVOYANT bare NeuralMCTS "
              "on the curve100+rs0.25 anchor leaf with no tail. NOT A BOUND IN EITHER "
              "DIRECTION: information handicaps us, but leaf and endgame ADVANTAGE us and "
              "cost is unmatched, so the net direction is undetermined. Report only the "
              "narrow claim — our blind champion at this budget beat/lost to the sighted "
              "RoD-v2 anchor — never 'the lineage gap is at least this'.")
    if abs(elo) <= 35 and not math.isnan(elo_sig):
        print(f"  POWER NOTE: |elo|<=35 at n={n} (1σ≈±{elo_sig:.0f}); a >=35-elo verdict needs n>=400.")
    # Track-F Gate A oracle-prior cost aggregation (per-world pre-search vs main-search
    # cost — mirrors the clairvoyant harness: pre/main ms/move + leaf ratio). Empty for
    # non-oracle cells, so an OFF summary is byte-identical.
    oracle_summary = {}
    oracle_games = [r for r in results if getattr(r, "oracle_prior_moves", 0) > 0]
    if oracle_games:
        om = sum(r.oracle_prior_moves for r in oracle_games)
        ow = sum(getattr(r, "oracle_presearch_worlds", 0) for r in oracle_games)
        pre_s = sum(r.oracle_presearch_secs for r in oracle_games)
        main_s = sum(r.oracle_mainsearch_secs for r in oracle_games)
        pre_lc = sum(r.oracle_presearch_leaf_calls for r in oracle_games)
        main_lc = sum(r.oracle_mainsearch_leaf_calls for r in oracle_games)
        oracle_summary = {
            "oracle_games": len(oracle_games),
            "oracle_prior_moves": om,
            "oracle_presearch_worlds": ow,
            "oracle_presearch_ms_per_move": (pre_s / max(1, om)) * 1e3,
            "oracle_mainsearch_ms_per_move": (main_s / max(1, om)) * 1e3,
            "oracle_total_ms_per_move": ((pre_s + main_s) / max(1, om)) * 1e3,
            "oracle_leaf_ratio": pre_lc / max(1, main_lc),
            "oracle_cost_multiple": (pre_s + main_s) / max(1e-9, main_s),
        }
        print(f"oracle-prior: {len(oracle_games)} games — {ow} per-world pre-searches — pre "
              f"{oracle_summary['oracle_presearch_ms_per_move']:.0f} + main "
              f"{oracle_summary['oracle_mainsearch_ms_per_move']:.0f} ms/move "
              f"(total {oracle_summary['oracle_total_ms_per_move']:.0f}, "
              f"{oracle_summary['oracle_cost_multiple']:.2f}x main-only; "
              f"leaf ratio {oracle_summary['oracle_leaf_ratio']:.2f}x)")
    # ASYMMETRY GUARD: the `k_dets`/`sims`/`total_sims` keys above are the CANDIDATE's.
    # That is unambiguous in a symmetric run (both sides share them) but NOT when
    # --opp-sims / --opp-k-dets moved the opponent, where a reader could take the
    # candidate's budget for the match's. Emit the opponent's OWN budget alongside —
    # only when it was explicitly set, so a symmetric run's summary.json is byte-
    # identical to the pre-change output.
    _asym_block = {}
    if opp_k_dets is not None or opp_sims is not None:
        _ok = k_dets if opp_k_dets is None else opp_k_dets
        _os_ = sims if opp_sims is None else opp_sims
        _asym_block = {
            "asymmetric_budgets": True,
            "candidate_k_dets": k_dets, "candidate_sims": sims,
            "candidate_total_sims": k_dets * sims,
            "opp_k_dets": _ok, "opp_sims": _os_, "opp_total_sims": _ok * _os_,
        }
    # THE EXCLUSION BLOCK — always present (h2h parity: a zero rate is STATED).
    _fail_block = _failure_block(results, failures, resolved)
    _shout_failures(_fail_block, n)
    return {
        "info": info, "exact_k": exact_k, "k_dets": k_dets, "sims": sims,
        "total_sims": k_dets * sims, "rung_sims": rung_sims,
        **_asym_block,
        **_fail_block,
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
        **oracle_summary,
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
           opp_label=None, cand_jrules_prior=None, cand_jrules_filter=None) -> int:
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
                           args.final_select, args.value_norm, cand_leaf_cfg,
                           jrules_prior=cand_jrules_prior,
                           jrules_filter=cand_jrules_filter)
    if cand_jrules_prior is not None:
        print(f"[smoke] J-RULES PRIOR surface B LIVE on the candidate: "
              f"{cand_jrules_prior} (leaf hash does NOT move — check the dose)")
    if cand_jrules_filter is not None:
        print(f"[smoke] J-RULES ROOT FILTER surface C LIVE on the candidate: "
              f"{cand_jrules_filter} (leaf hash does NOT move — the wiring "
              f"gates are the manifest's cand_jrules_filter.mask and the "
              f"per-game jf_dropped counters)")
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
    elif args.opponent == _BARE_NET:
        smoke_opp_net, opp_rep = _load_net_rep(args.opp_net, device="cpu")
        print(f"[smoke] opponent = BARE SIGHTED (CLAIRVOYANT) NeuralMCTS anchor "
              f"{args.opp_net} | rep="
              f"{'SIGHTED' if opp_rep['sighted'] else 'NON-SIGHTED'} "
              f"{opp_rep['n_input_channels']}ch/{opp_rep['n_scalar_features']}sc "
              f"(inferred from ITS OWN ckpt) | sims={BARE_NET_SIMS} "
              f"c_puct={BARE_NET_CPUCT:g} rs={BARE_NET_RESIDUAL_SCALE:g} | "
              f"leaf=v2.9 curve100 anchor leaf (NOT curve125) | NO exact tail\n"
              f"[smoke] ⚠️ ASYMMETRIC BY DESIGN: candidate BLIND (fair PIMC) vs "
              f"opponent SIGHTED (true deck). This is NOT a bound in either "
              f"direction — information handicaps us, leaf and endgame advantage "
              f"us, cost is unmatched. Report the narrow head-to-head claim only.")
    elif args.opponent == "fair-champion":
        print("[smoke] opponent = PRODUCTION fair champion (FairHeuristicPriorAgent, "
              "heuristic softmax priors, FROZEN curve125 champion leaf)")
    # fair-net smoke: load --net if given, else a randomly-initialized 81ch/42-scalar
    # net (pure plumbing proof — NO training). Other arms ignore the net.
    smoke_net = None
    smoke_sighted_game = None
    smoke_coreml_model = None
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
        if getattr(args, "net_backend", None) == "coreml":
            # The smoke is the ONLY cheap place to find out that the .mlpackage does not
            # load, or was exported at the wrong rep, before n=400 games commit to it.
            from carcassonne_ai.coreml_evaluator import load_coreml_model
            smoke_coreml_model = load_coreml_model(
                args.coreml_model, compute_units=args.coreml_compute_units)
            smoke_net = None      # the coreml branch must not fall back to torch
            print(f"[smoke] fair-netprior forward = CoreML {args.coreml_model} "
                  f"({args.coreml_compute_units})")
        print(f"[smoke] fair-netprior priors = {'ckpt ' + args.net if args.net else 'RANDOM'} "
              f"net | rep={'SIGHTED' if rep['sighted'] else 'NON-SIGHTED'} "
              f"{rep['n_input_channels']}ch/{rep['n_scalar_features']}sc "
              f"(value_global_pool={rep['value_global_pool']}) | value = FROZEN curve125 "
              f"champion leaf (NO net value)")
    print(f"[smoke] info={args.info} K={args.exact_k} k_dets={args.k_dets} sims={args.sims} "
          f"(total~{args.k_dets*args.sims}) | opponent={args.opponent}"
          + (f" (rung h{args.rung_sims} c{RUNG_C})" if args.opponent == "h800"
             else " (tier1: 1-ply RuleBasedPlayer, no search)" if args.opponent == _GREEDY
             else f" (SIGHTED bare NeuralMCTS, sims={BARE_NET_SIMS} "
                  f"c_puct={BARE_NET_CPUCT:g}, bare)" if args.opponent == _BARE_NET
             else f" (k_dets={_opp_eff_k_dets(args)} sims={_opp_eff_sims(args)}, "
                  f"same fair machinery)"))
    import random
    results = []
    t0 = time.perf_counter()
    # `--games` is the OPTIONAL alias for `--n` (resolved into args.n in main(), but
    # left as None here when the caller did not pass it). Reading it raw made a bare
    # `--smoke` crash with TypeError: '>' not supported between NoneType and int.
    # Fall back to a SINGLE game -- a smoke is a wiring proof, not an eval, so it must
    # NOT inherit args.n's default of 100.
    _n_smoke = args.games if args.games is not None else 1
    for i in range(max(1, _n_smoke)):
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
                               batch_size=args.batch_size,
                               oracle_prior_mult=args.oracle_prior_mult,
                               oracle_prior_eps_coef=args.oracle_prior_eps_coef,
                               meeple_dedup=(True if args.meeple_dedup else None),
                               intra_reuse=(True if args.intra_reuse else None),
                               coreml_model=smoke_coreml_model,
                               net_backend=getattr(args, "net_backend", None),
                               backend=args.backend,
                               rust_threads=args.rust_threads,
                               simsplit=_args_simsplit(args))
        rung = _make_opponent(
            args.opponent, champ_cfg_dict, args.sims, args.k_dets, args.exact_k,
            args.rung_sims, seed, opp_leaf_cfg=opp_leaf_cfg, net=smoke_opp_net,
            sighted_game=smoke_opp_game, rep=opp_rep, opp_sims=args.opp_sims,
            opp_k_dets=args.opp_k_dets, backend=args.backend,
            rust_threads=args.rust_threads)
        _start_mirrors(board, champ, rung)
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
            _advance_mirrors(act, champ, rung)
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
              + ("" if args.opponent in _LEAFLESS_RUNGS else
                 f" | opp prefix/exact={_os['opp_prefix_moves']}/{_os['opp_exact_moves']} "
                 f"latch_k={_os['opp_latch_k']} solver={_os['opp_solver_secs']:.2f}s "
                 f"to={_os['opp_timeouts']}"))
        if args.exact_k > 0:
            assert champ.exact_moves > 0, \
                "champion never reached the fair exact endgame (K too small / rung got all the endgames?)"
        assert champ.prefix_moves > 0, "prefix search never ran (K too big?)"
        if args.oracle_prior_mult is not None:
            op = getattr(champ, "_prefix", None)   # the FairHeuristicPriorAgent
            assert op is not None and op.oracle_prior_mult is not None, \
                "oracle candidate did not build an oracle-armed fair agent"
            assert op.oracle_moves > 0, "oracle candidate never ran a per-world pre-search"
            # THE per-world contract: one pre-search per determinization world per move.
            assert op.oracle_presearch_worlds == op.oracle_moves * args.k_dets, \
                (f"pre-search must run once PER WORLD per oracle move: worlds="
                 f"{op.oracle_presearch_worlds} != moves*k_dets="
                 f"{op.oracle_moves * args.k_dets}")
            assert op.last_reached_root, "oracle prior distribution never reached a world root"
            assert op.oracle_presearch_leaf_calls > op.oracle_mainsearch_leaf_calls, \
                "pre-search must run MORE leaf calls than the main search (mult>1)"
            print(f"[smoke]   oracle-prior mult={args.oracle_prior_mult} (per-world): "
                  f"moves={op.oracle_moves} worlds={op.oracle_presearch_worlds} "
                  f"pre={op.oracle_presearch_secs:.2f}s/{op.oracle_presearch_leaf_calls}leaves "
                  f"main={op.oracle_mainsearch_secs:.2f}s/{op.oracle_mainsearch_leaf_calls}leaves "
                  f"(leaf ratio {op.oracle_presearch_leaf_calls/max(1,op.oracle_mainsearch_leaf_calls):.2f}x, "
                  f"cost {(op.oracle_presearch_secs+op.oracle_mainsearch_secs)/max(1e-9,op.oracle_mainsearch_secs):.2f}x)")
        if args.opponent in _HEAD_TO_HEAD:
            # a head-to-head opponent is a production agent too: it must actually be
            # searching AND taking the same marginalized endgame handoff.
            assert _os["opp_prefix_moves"] > 0, \
                "opponent prefix search never ran (K too big?)"
            if args.exact_k > 0:
                assert _os["opp_exact_moves"] > 0, \
                    ("opponent never reached the fair exact endgame — both sides must "
                     "share the handoff for the match to be symmetric")
        if args.opponent == _BARE_NET:
            # The three load-bearing asymmetries (module docstring). Assert them here
            # rather than trusting the construction — a symmetrised cell would still
            # produce a plausible number.
            assert rung_moves > 0, "bare-net opponent never moved"
            assert isinstance(rung, _BareNetPrefix), \
                f"bare-net opponent is a {type(rung).__name__}, not _BareNetPrefix"
            assert rung.mcts.fair_chance is False, \
                ("bare-net opponent must be CLAIRVOYANT (fair_chance=False) — it is "
                 "the sighted anchor; blinding it changes what is being measured")
            assert _os["opp_exact_moves"] == 0 and _os["opp_latch_k"] is None, \
                "bare-net opponent must be BARE (no exact-K endgame handoff)"
            assert _leaf_hash(rung.leaf_cfg) != _leaf_hash(cfg.resolved_leaf_cfg()), \
                ("candidate and bare-net opponent resolved the SAME leaf — the "
                 "curve125 injection leaked onto the opponent")
            # On the rust backend the candidate IS the agent (no _MarginalizedHandoff
            # wrapper, so no `._prefix`), so check the agent itself in that case. The
            # assertion being made is about INFORMATION — blind fair PIMC, not a
            # sighted/clairvoyant searcher — which both engines satisfy identically;
            # it is not about which engine executes it.
            _cand_prefix = getattr(champ, "_prefix", champ)
            assert isinstance(_cand_prefix, FairHeuristicPriorAgent) or \
                _drives_mirror(_cand_prefix), \
                ("candidate must be the BLIND fair PIMC agent for a blind-vs-sighted "
                 f"cell; got {type(_cand_prefix).__name__}")

    summ = _summary(results, args.info, args.exact_k, args.k_dets, args.sims,
                    args.rung_sims, opponent=args.opponent, opp_label=opp_label,
                    opp_k_dets=args.opp_k_dets, opp_sims=args.opp_sims)
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
                         "every pre-existing arm/result is an h800 result. greedy = tier1, the "
                         "1-ply RuleBasedPlayer (== the L2 ladder's `greedy` rung, so the "
                         "number is comparable to the *_vs_greedy_n200 rows) — the DECK-LUCK "
                         "FLOOR cell: it measures what a searchless player still steals from "
                         "the champion on deck variance alone, so read the champion's non-win "
                         "fraction as a floor, NOT a strength gap. Unlike the h800 path the "
                         "candidate resolves curve125 here (it must be the SHIPPED champion); "
                         "the greedy side is leafless so nothing can leak. fair-champion = a "
                         "DIRECT head-to-head vs the PRODUCTION champion (FairHeuristicPriorAgent, "
                         "heuristic softmax priors, curve125 leaf, same budget/machinery) — with "
                         "--info fair-netprior this is the pure PRIOR-SWAP 'did the distillation "
                         "work?' cell. net = head-to-head vs a SECOND distilled net (--opp-net) "
                         "run as a fair-netprior agent — the 'does the bag matter?' cell (each "
                         "side's rep inferred from its OWN ckpt, so cross-rep 81ch-vs-78ch works). "
                         "Both SYMMETRIC head-to-head modes resolve curve125 on BOTH sides and keep "
                         "deck pairing + seat alternation; diff is always candidate - opponent. "
                         "bare-net = ⚠️ DELIBERATELY ASYMMETRIC: our BLIND fair champion vs a "
                         "SIGHTED (clairvoyant) BARE NeuralMCTS in its rod_v2 ANCHOR identity "
                         "(--opp-net; sims=200, c_puct=3.0, v2.9 curve100 leaf + "
                         "residual_scale=0.25, NO exact tail). The candidate keeps curve125 + "
                         "exact-K; the opponent does NOT get either. ⚠️ NOT A BOUND IN EITHER "
                         "DIRECTION (corrected 2026-07-27): information handicaps us but leaf "
                         "and endgame ADVANTAGE us and cost is unmatched, so the net sign is "
                         "undetermined — report only the narrow head-to-head claim. The value "
                         "of the cell is that the opponent is OUT OF LINEAGE. "
                         "Read the BLIND vs SIGHTED block in this file's module docstring before "
                         "changing anything about it — do NOT symmetrise it.")
    ap.add_argument("--opp-net", type=str, default=None,
                    help="--opponent net: path to the OPPONENT's distilled policy net. Its rep "
                         "(sighted 81ch/42 vs non-sighted 78ch/10) is inferred from THIS "
                         "checkpoint independently of --net, so a cross-rep match encodes each "
                         "side on its own encoder. Required for --opponent net. "
                         "--opponent bare-net: path to the SIGHTED bare-NeuralMCTS anchor "
                         "checkpoint (e.g. the RoD-v2 iter_02 anchor); same rep inference.")
    ap.add_argument("--opp-orch-shm-name", type=str, default=None,
                    help="--opponent net: serve the OPPONENT's priors from a SECOND carc-orch SHM "
                         "eval-server (a server owns exactly one net, so a net-vs-net orch run "
                         "needs two servers with distinct --shm-name, each sized --n-ch/--n-scalar "
                         "for ITS OWN net's rep and --workers to match). Omit for a per-worker CPU "
                         "opponent net. "
                         "--opponent bare-net: same flag, one server — it serves the anchor's "
                         "priors AND value (the candidate side is net-free, so no second server). "
                         "⚠️ The anchor rows on record were played net-on-CPU; GPU fp32 is not "
                         "bit-identical, so a near-tied argmax can flip. Quantify with "
                         "scripts/classical_search/bare_net_gpu_divergence.py before citing.")
    ap.add_argument("--net", type=str, default=None,
                    help="fair-net: path to the sighted (81ch/42-scalar) value-net checkpoint. "
                         "fair-netprior: path to the DISTILLED policy net (sighted 81ch/42 OR "
                         "non-sighted 78ch/10 — the rep is inferred from the checkpoint). "
                         "Under --smoke this may be omitted (a random net is used). "
                         "With --orch-shm-name it is NOT loaded per-worker (the server owns the "
                         "net) but is still recorded in the manifest for provenance.")
    ap.add_argument("--net-backend", choices=("torch", "coreml"), default=None,
                    help="fair-netprior: which device computes the POLICY forward. "
                         "Default (unset) = torch, byte-identical to every run on "
                         "record. `coreml` routes it through --coreml-model on Apple's "
                         "Neural Engine — the r<=~1.5 reopen condition of "
                         "measurement/classical_search/NETPRIOR_EQTIME_GATE_20260728.md "
                         "§6. In that mode --net is still REQUIRED (it anchors the rep "
                         "and the manifest provenance) but is never loaded in a worker. "
                         "⚠️ NOT behaviour-identical: fp16 accelerator arithmetic can "
                         "reorder near-tied priors, so the ANE agent is its own player "
                         "— run scripts/m5_bench/verify_coreml_evaluator.py first and "
                         "cite it. Requires --batch-size 1.")
    # --- ENGINE (rustport P6, wired 2026-08-02) ------------------------------- #
    ap.add_argument("--backend", choices=("python", "rust", "auto"), default="python",
                    help="which ENGINE computes the fair agent(s). `python` (default) "
                         "is byte-identical to every row already in "
                         "experiments/results.csv. `rust` runs carc_rs "
                         "(rust_agent.RustFairAgent) — BEHAVIOUR-IDENTICAL BY GATE, "
                         "not by construction: rustport G4 reproduced the deployed "
                         "champion bit-exactly (0/305,515 checks) and G6 read "
                         "14,384/14,384 identical actions over 100 full games. `auto` "
                         "resolves governance/PRODUCTION.yaml "
                         "champion.fair_deploy.backend. ⚠️ Reaches --info fair and "
                         "--info clair only (carc_rs has no net evaluator, so fair-net "
                         "/ fair-netprior stay python). --info clair became reachable "
                         "on 2026-08-02 when the persistent tree closed Gap 2; it is a "
                         "RULER, gated by scripts/rustport/gate_clair_backend.py. On "
                         "the opponent side --opponent fair-champion ONLY — the "
                         "h800 / greedy / bare-net rungs are FROZEN RULERS and stay "
                         "Python whatever this says. `--backend python` is the "
                         "permanent escape hatch and needs no Rust wheel installed.")
    ap.add_argument("--rust-threads", type=int, default=None,
                    help="OS threads the Rust agent folds its k_dets worlds across "
                         "(--backend rust only). ⚠️ FARM RULE: leave this UNSET in any "
                         "game-parallel run. It defaults to 1 whenever --workers > 1 "
                         "because the game parallelism owns the cores; W16 x t8 = 128 "
                         "hot threads is the documented failure mode. Raise it only "
                         "for a single-game / interactive latency measurement.")
    ap.add_argument("--coreml-model", type=str, default=None,
                    help="path to the .mlpackage for --net-backend coreml (build it "
                         "with scripts/m5_bench/export_cl067_coreml.py; its sidecar "
                         "manifest carries the source-checkpoint sha256).")
    ap.add_argument("--coreml-compute-units", type=str, default="CPU_AND_NE",
                    help="CoreML compute units, bound at LOAD time. CPU_AND_NE "
                         "(default) deliberately EXCLUDES the GPU — ALL lets CoreML "
                         "place the graph on a different device than the one the "
                         "0.42 ms / r~0.73 row was measured on.")
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
    ap.add_argument("--k-dets", type=int, default=4, help="determinizations per move (fair PIMC). ⚠️ THIS DEFAULT IS NO LONGER THE DEPLOY CHAMPION: since 2026-07-29 the champion of record is k8×1376=11008 (governance/PRODUCTION.yaml). Pass --k-dets 8 --sims 1376 to grade against the champion")
    ap.add_argument("--sims", type=int, default=688, help="PUCT sims per determinization. Default k4×688=2752 = the PRE-2026-07-29 deploy budget, kept so existing cells reproduce; the champion is k8×1376=11008")
    ap.add_argument("--sims-tile", type=int, default=None,
                    help="SIMS-SPLIT (CANDIDATE side only, --info fair): per-world sims "
                         "for TILES decisions; None = --sims. The phase-asymmetric "
                         "sims-split lever's play-time knob (docs/LEVER_INDEX.md §5). "
                         "Works on both backends (rust: stateless per-call override). "
                         "The opponent never sees it (_make_opponent does not forward).")
    ap.add_argument("--sims-meeple", type=int, default=None,
                    help="SIMS-SPLIT (CANDIDATE side only, --info fair): per-world sims "
                         "for MEEPLES decisions; None = --sims. See --sims-tile.")
    ap.add_argument("--opp-sims", type=int, default=None,
                    help="ASYMMETRIC search budgets: the head-to-head opponent "
                         "(--opponent fair-champion / net) runs at THIS per-determinization "
                         "sims budget while the CANDIDATE keeps --sims — the equal-WALL-CLOCK "
                         "deployability check (e.g. candidate k4x154 vs fair-champion k4x688). "
                         "Default None = the opponent uses the shared --sims (SYMMETRIC head-to-"
                         "head, byte-identical to today). Inapplicable to --opponent h800 (its "
                         "budget is --rung-sims) and rejected there.")
    ap.add_argument("--opp-k-dets", type=int, default=None,
                    help="ASYMMETRIC determinization COUNT: the head-to-head opponent "
                         "(--opponent fair-champion / net) runs THIS many determinizations "
                         "per move while the CANDIDATE keeps --k-dets. The sibling of "
                         "--opp-sims, and what makes a whole-config A/B expressible: CL-060's "
                         "re-open trigger is candidate k8x1376 (11008) vs the k4x688 (2752) "
                         "DEPLOY champion, which a shared --k-dets cannot express (--opp-sims "
                         "alone would give a k8x688=5504 opponent, not the deploy config). "
                         "Default None = the opponent uses the shared --k-dets (SYMMETRIC "
                         "head-to-head, byte-identical to today). Inapplicable to --opponent "
                         "h800 (not a PIMC agent; its budget is --rung-sims) and rejected there.")
    ap.add_argument("--batch-size", type=int, default=1,
                    help="fair-netprior CANDIDATE within-search leaf batching (LATENCY fix, "
                         "2026-07-16): >1 collects this many leaves under virtual loss -> ONE orch "
                         "forward per batch instead of a blocking round-trip per expansion. Default "
                         "1 = the byte-for-byte serial search (the +88.7 was measured at batch-1; "
                         "vloss CHANGES the search, so a batched run is a DIFFERENT — faster — agent). "
                         "ONLY the net-prior candidate batches; the fair-champion opponent stays serial. "
                         "SHM caps a request at MAX_K=8, so >8 chunks into ceil(N/8) round-trips.")
    ap.add_argument("--meeple-dedup", action="store_true",
                    help="MEEPLE-DEDUP on the CANDIDATE side (--info fair). At every "
                         "meeple-phase node the search keeps only the lowest-action-id "
                         "member of each set of GAME-EQUIVALENT actions (same connected "
                         "on-tile feature reachable from several sides), before the "
                         "priors are normalized and before any child exists — so the "
                         "prior mass is not split and no duplicate subtree is built. "
                         "The census measured 60.75%% of the champion's actionable "
                         "meeple decisions as carrying >=2 equivalent actions and 28.6%% "
                         "of its placements as chosen from a visit-diluted group "
                         "(measurement/classical_search/meeple_dedup_census_20260727.json). "
                         "Per-AGENT, so the OPPONENT is never deduped. Default OFF = "
                         "byte-identical to the deploy champion. Grouping is INTRA-TILE "
                         "only (a lower bound) — see carcassonne_ai.meeple_equiv.")
    ap.add_argument("--intra-reuse", action="store_true",
                    help="C3-INTRA WITHIN-TURN TREE CARRY on the CANDIDATE side "
                         "(--info fair). The fair champion makes TWO full-budget "
                         "searches per turn — the tile decision, then the meeple "
                         "decision — and the meeple half was measured at 52.5%% of "
                         "champion search time. No hidden information arrives between "
                         "them (the engine draws the next tile only at the END of the "
                         "meeple phase), so this carries the k_dets trees AND their "
                         "determinizations from the tile decision into the meeple "
                         "decision, re-rooted at the action actually played. Fair-LEGAL, "
                         "unlike the across-move reuse of CL-044 (clairvoyant-only). "
                         "Falls back to a fresh search on any mismatch. Per-AGENT, so "
                         "the OPPONENT never carries. Default OFF = byte-identical to "
                         "the deploy champion. "
                         "\u26a0 READ-OUT CAVEAT: ON does MORE total work per turn at "
                         "equal nominal sims (the meeple search runs its full `sims` ON "
                         "TOP of the carried subtree), so a positive result here is NOT "
                         "a win until an equal-WALL-CLOCK confirm reproduces it — the "
                         "house rule from CL-044's ms-ratio verification.")
    ap.add_argument("--oracle-prior-mult", type=int, default=None,
                    help="Track-F Gate A oracle-prior CONFIRM (CANDIDATE side, --info fair only). "
                         "When set to N (>=2), the fair PIMC candidate runs a PER-WORLD pre-search: "
                         "for EACH of the k_dets determinizations, a fresh champion search at "
                         "N x --sims runs FIRST on that world's reshuffled deck, its root VISIT "
                         "distribution is converted to a prior (same alias-fold + eps-floor as the "
                         "clairvoyant screen), and that world's normal --sims search runs with the "
                         "ROOT priors REPLACED by it (deeper node priors stay the heuristic "
                         "evaluator's). Pooled-Q across worlds is UNCHANGED. The pre-search tree is "
                         "NOT reused into the main search (isolates priors from depth). Default None "
                         "= OFF = byte-identical to the plain fair champion. MUTUALLY EXCLUSIVE with "
                         "a net candidate (--info fair-net/fair-netprior / --net): oracle priors "
                         "REPLACE the prior source. Requires --batch-size 1.")
    ap.add_argument("--oracle-prior-eps-coef", type=float, default=1e-3,
                    help="epsilon-floor coefficient for --oracle-prior-mult: each world's per-group "
                         "prior is floored at eps = coef / n_groups (keeps PUCT exploration of "
                         "pre-search-unvisited moves alive), then renormalized. Default 1e-3. "
                         "Ignored unless --oracle-prior-mult is set.")
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
    ap.add_argument("--cand-jrules-prior-dose", type=float, default=0.0,
                    help="J-RULES PRIOR surface B (measurement/jrules_priors_20260814): "
                         "boost the CANDIDATE search's expansion priors by the anchor's "
                         "J-rules — each legal child's dleaf gets dose*T(child) added "
                         "BEFORE the prior softmax (leaf values untouched; the leaf hash "
                         "does NOT move, so the manifest's cand_jrules_prior.dose is the "
                         "wiring gate). 0.0 (default) = OFF = byte-identical. RUST-ONLY: "
                         "a nonzero dose hard-exits unless the resolved backend is rust, "
                         "and a stale carc_rs wheel raises TypeError (fail-closed).")
    ap.add_argument("--cand-jrules-prior-mask", type=int, default=31,
                    help="surface-B per-rule ablation mask (JR_J1|J2|J5|J6|J8 == 31, the "
                         "default bundle). Only read when the dose is nonzero.")
    ap.add_argument("--cand-jrules-prior-scope", choices=("all", "own"), default="all",
                    help="surface-B scope: 'all' = every expansion, mover POV (the "
                         "primary; the structural analogue of the house priors); 'own' = "
                         "only root-player nodes (the opponent-model-free ablation; "
                         "measured cheaper, ~1.07x vs ~1.15x). Only read when the dose "
                         "is nonzero.")
    ap.add_argument("--cand-jrules-filter-mask", type=int, default=0,
                    help="J-RULES ROOT FILTER surface C (measurement/"
                         "jrules_filters_20260814): apply the anchor's HARD FILTERS "
                         "to the CANDIDATE's ROOT legal set before its PIMC searches "
                         "(bits 1=F-END, 2=F-J10, 4=F-J9, 8=F-J3; 11 == the bot's "
                         "`current` stack). MEEPLE-phase roots only; root only, never "
                         "in-tree; each filter yields rather than leave < min-keep "
                         "candidates. 0 (default) = OFF = byte-identical. The leaf "
                         "hash does NOT move — the manifest's cand_jrules_filter.mask "
                         "+ the per-game jf_dropped counters are the wiring gates. "
                         "RUST-ONLY: a nonzero mask hard-exits unless the resolved "
                         "backend is rust, and a stale carc_rs wheel raises TypeError "
                         "(fail-closed).")
    ap.add_argument("--cand-jrules-filter-min-keep", type=int, default=1,
                    help="surface-C never-empty guard: a filter that would leave "
                         "fewer than this many root candidates is SKIPPED for that "
                         "ply (the yield is counted per game). Default 1 == the "
                         "bot's own rule. Only read when the mask is nonzero.")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--games", type=int, default=None, help="alias for --n (convenience)")
    ap.add_argument("--paired", action="store_true")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--seed-start", type=int, default=13_000_000_000)
    ap.add_argument("--allow-selfplay-seeds", action="store_true")
    ap.add_argument("--out-root", type=str, default=None)
    ap.add_argument("--out-subdir", type=str, default=None)
    ap.add_argument("--retry-failed", action="store_true",
                    help="re-attempt games already on disk as FAILED records "
                         "(<out>/failed/). Default OFF: these failures are "
                         "deck-deterministic (same deck, same seeds, same "
                         "deterministic players ⇒ the same raise), so a retry just "
                         "re-burns a game-time — the 2026-08-14 incident re-crashed "
                         "identically 16 times. Use after a code fix. Same spelling "
                         "and semantics as scripts/joshuabot/h2h.py --retry-failed, "
                         "plus a hard bound: a game whose lifetime `attempts` has "
                         "reached --max-attempts is PERMANENT and is not re-opened.")
    ap.add_argument("--max-attempts", type=int, default=3,
                    help="LIFETIME attempt budget per game across all passes "
                         "(default 3). One attempt per pass; the count is persisted "
                         "in the failure record, so a --retry-failed loop always "
                         "terminates instead of grinding on a deterministic crash. "
                         "Raise it (or delete the record) to force more attempts.")
    ap.add_argument("--shared-claim", action="store_true")
    ap.add_argument("--claim-stale-secs", type=int, default=7200)
    ap.add_argument("--claim-host", type=str, default=socket.gethostname())
    ap.add_argument("--allow-leaf-hash-drift", action="store_true",
                    help="fair-netprior: downgrade the candidate curve125 leaf-HASH assert to a "
                         "warning (the curve-VALUES check still hard-fails). Only for a known "
                         "additive LeafConfig field change that reshapes the hash — see the "
                         "158f17ff precedent in scripts/distill_flywheel/champ_env.sh.")
    ap.add_argument("--allow-cand-curve-drift", action="store_true",
                    help="PRE-REGISTERED LEAF-SHAPE CELLS ONLY (--info fair --opponent "
                         "fair-champion): let the CANDIDATE's --cand-leaf-json carry a "
                         "v29_meeple_curve that differs from the champion's curve125, "
                         "instead of hard-exiting. The OPPONENT arm stays PINNED to "
                         "curve125 (unchanged assert) — this is a curve-SHAPE contrast "
                         "against the shipped champion, never a both-sides move. The "
                         "candidate's resolved curve and leaf hash are stamped in "
                         "manifest.json (cand_leaf_cfg / cand_leaf_hash / "
                         "champion.netprior_leaf), along with cand_curve_drift_allowed. "
                         "The curve must still be 8 finite floats.")
    ap.add_argument("--summary-only", action="store_true")
    ap.add_argument("--no-results-csv", action="store_true",
                    help="do not append to experiments/results.csv (this eval NEVER writes it; "
                         "flag kept for launcher symmetry / explicit intent)")
    ap.add_argument("--smoke", action="store_true")
    _rules_profile.add_argument(ap)          # F9 A0
    args = ap.parse_args(argv)
    # F9 A0 — resolve the rules profile ONCE, before any Game() is constructed,
    # and publish it to the environment so every spawn worker inherits the same
    # one. `walled` (the default) adds no argument to any Game(...) call, so this
    # line is inert for every existing cell; it is what makes a non-walled cell
    # expressible at all, and what puts the profile in manifest.json.
    _rules_profile.activate(args.rules_profile)
    if args.games is not None:
        args.n = args.games
    if args.k_dets < 1:
        ap.error("--k-dets must be >= 1")
    if args.paired and args.n % 2 != 0:
        ap.error("--paired requires an even --n")
    if args.batch_size < 1:
        ap.error("--batch-size must be >= 1")
    if args.max_attempts < 1:
        # A budget of 0 would make every game permanently failed before it ran.
        ap.error("--max-attempts must be >= 1")
    if args.batch_size > 1 and args.info != "fair-netprior":
        # Only the fair-netprior candidate has a batched net-prior evaluator wired.
        # fair/clair have no per-leaf net round-trip; fair-net batches a VALUE net for
        # which no batch factory exists yet. Fail loud rather than silently ignore.
        ap.error("--batch-size > 1 only applies to --info fair-netprior "
                 f"(got --info {args.info}); it would be silently ignored otherwise")

    if args.orch_shm_name and args.info not in ("fair-net", "fair-netprior"):
        ap.error("--orch-shm-name only applies to --info fair-net / fair-netprior")

    # ---- Track-F Gate A oracle-prior validation (CANDIDATE side, --info fair only) ----
    if args.oracle_prior_mult is not None:
        if args.info != "fair":
            # The oracle prior REPLACES the candidate's prior source; the net arms already
            # own the prior (fair-netprior) or the value (fair-net). Reject rather than
            # silently ignore the flag or double-source the priors.
            ap.error("--oracle-prior-mult requires --info fair (the heuristic-prior "
                     f"candidate); it is mutually exclusive with --info {args.info} — the "
                     "oracle prior REPLACES the prior source, incompatible with the "
                     "net-value/net-prior arms.")
        if args.net is not None:
            ap.error("--oracle-prior-mult is mutually exclusive with --net (a net "
                     "candidate): the oracle prior REPLACES the prior source. Drop one.")
        if args.oracle_prior_mult < 2:
            ap.error("--oracle-prior-mult must be >= 2 (a pre-search LARGER than production)")
        # NB: --batch-size>1 is already rejected for --info fair by the batch gate above
        # (batching only applies to fair-netprior), so oracle (which requires --info fair)
        # can never reach batching via the CLI; the agent still hard-rejects the combo if
        # constructed directly (FairHeuristicPriorAgent oracle_prior_mult + batch_size>1).

    # ---- opponent-mode validation -------------------------------------------------
    if args.opp_sims is not None:
        if args.opp_sims < 1:
            ap.error("--opp-sims must be >= 1")
        if args.opponent == "h800":
            # h800 already owns a budget flag (--rung-sims); silently swallowing
            # --opp-sims there would mislead. Fail loud (fail-loudly).
            ap.error("--opp-sims applies to a head-to-head opponent "
                     "(--opponent fair-champion / net); the h800 rung's budget is "
                     "--rung-sims. Use --rung-sims for the h800 rung.")
        if args.opponent == _GREEDY:
            ap.error("--opp-sims applies to a head-to-head opponent "
                     "(--opponent fair-champion / net); the greedy rung is a 1-ply "
                     "RuleBasedPlayer with NO search budget at all.")
    if args.opp_k_dets is not None:
        if args.opp_k_dets < 1:
            ap.error("--opp-k-dets must be >= 1")
        if args.opponent == "h800":
            # The h800 rung is a plain HeuristicMCTS, not a PIMC agent — it has no
            # determinizations at all, and it already owns a budget flag (--rung-sims).
            # Silently swallowing --opp-k-dets there would mislead. Fail loud.
            ap.error("--opp-k-dets applies to a head-to-head opponent "
                     "(--opponent fair-champion / net); the h800 rung is not a PIMC "
                     "agent (no determinizations) and its budget is --rung-sims.")
        if args.opponent == _GREEDY:
            ap.error("--opp-k-dets applies to a head-to-head opponent "
                     "(--opponent fair-champion / net); the greedy rung is a 1-ply "
                     "RuleBasedPlayer (no determinizations, no search).")
    if args.opponent in _NET_OPPONENTS and not args.opp_net:
        ap.error(f"--opponent {args.opponent} requires --opp-net <checkpoint>")
    if args.opp_net and args.opponent not in _NET_OPPONENTS:
        ap.error("--opp-net only applies to --opponent net / bare-net")
    if args.opp_orch_shm_name and args.opponent not in _NET_OPPONENTS:
        # h800 / fair-champion are net-free — there is nothing for a server to serve.
        ap.error("--opp-orch-shm-name only applies to a net opponent "
                 "(--opponent net / bare-net); "
                 f"--opponent {args.opponent} is net-free")
    if args.opponent == _BARE_NET:
        # The anchor's play knobs are PINNED (BARE_NET_*). Swallowing a budget flag here
        # would silently produce a DIFFERENT agent than the results.csv anchor rows, so
        # fail loud — same discipline as the h800 rung.
        for _f, _v in (("--opp-sims", args.opp_sims), ("--opp-k-dets", args.opp_k_dets)):
            if _v is not None:
                ap.error(
                    f"{_f} does not apply to --opponent bare-net: the opponent's config is "
                    f"PINNED to the rod_v2 anchor identity (sims={BARE_NET_SIMS}, "
                    f"c_puct={BARE_NET_CPUCT:g}, residual_scale={BARE_NET_RESIDUAL_SCALE:g}, "
                    "bare) so it stays bit-for-bit the agent every net:<ckpt> anchor row in "
                    "experiments/results.csv was played by. Moving it would break the anchor.")
        if args.info != "fair":
            # The cell only means "BLIND vs SIGHTED" when our side is the fair PIMC
            # champion. Anything else is a different (and un-preregistered) measurement.
            print(f"[warn] --opponent bare-net with --info {args.info}: the intended cell is "
                  "--info fair (our BLIND champion vs the SIGHTED anchor). "
                  + ("--info clair makes BOTH sides clairvoyant, so this is not a "
                     "blind-vs-sighted cell at all. "
                     if args.info == "clair" else "")
                  + "Do not report this as the blind-vs-sighted result.",
                  file=sys.stderr)
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

    # --allow-cand-curve-drift is scoped to the ONE pre-registered cell shape it was
    # built for: the symmetric fair-vs-fair-champion head-to-head. Everywhere else the
    # curve125 pin is load-bearing for a DIFFERENT reason (the nets were distilled
    # against curve125; the bare-net anchor is an identity; greedy is the shipped
    # champion's deck-luck floor), so refuse rather than quietly weaken it.
    if args.allow_cand_curve_drift and not (args.info == "fair"
                                            and args.opponent == "fair-champion"):
        ap.error("--allow-cand-curve-drift applies ONLY to a pre-registered leaf-SHAPE "
                 "cell: --info fair --opponent fair-champion (got "
                 f"--info {args.info} --opponent {args.opponent}). Every other arm pins "
                 "curve125 for a reason that is not about leaf shape (distill parity for "
                 "fair-netprior / net, the rod_v2 anchor identity for bare-net, the "
                 "shipped-champion claim for greedy and the h800 ruler cells).")

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
    _bare_net = args.opponent == _BARE_NET
    # --opponent greedy: the CANDIDATE must be the SHIPPED champion (curve125 per
    # governance/PRODUCTION.yaml), because this cell's whole claim is "what the
    # production agent drops to a 1-ply player". The opponent is LEAFLESS (a rule-based
    # 1-ply player evaluates no leaf at all), so there is no opponent-side injection and
    # no leak risk. NB this deliberately differs from the h800 default path, which keeps
    # the candidate on curve100 so it matches the frozen CL-022 ruler cells.
    _greedy = args.opponent == _GREEDY
    # The curve125 candidate injection fires for the fair-netprior arm (the net was
    # distilled against curve125), for any SYMMETRIC head-to-head (both sides are
    # production agents, so both must be the shipped curve125 champion leaf), AND for
    # --opponent bare-net — where it fires on the CANDIDATE ONLY, because that side is
    # the shipped production champion while the opponent must stay on the curve100
    # anchor leaf (see the BLIND vs SIGHTED block; the two leaves DIFFER by design).
    if args.info == "fair-netprior" or _h2h or _bare_net or _greedy:
        if not _h2h:
            # The rung is the ruler ONLY when there IS a rung. Head-to-head has no rung,
            # so this assert is skipped there — but the curve125 asserts below are
            # strictly stronger (they pin BOTH sides' actual resolved leaves), so nothing
            # goes unchecked. The h800 default path keeps the original hard gate.
            # bare-net has no rung either, but it DOES need this: its opponent leaf is
            # dataclasses.replace(DEFAULT_CONFIG, ...), so a moved DEFAULT_CONFIG would
            # silently swap the anchor's leaf out from under it.
            rung_ruler_hash = _assert_rung_is_ruler(
                *(("bare-net", "SIGHTED anchor opponent's base (env DEFAULT_CONFIG)")
                  if _bare_net else ()))
        if cand_leaf_cfg is None:
            cand_leaf_cfg = _curve125_leaf_cfg()
            _assert_cy_float_path(cand_leaf_cfg)
        if args.allow_cand_curve_drift:
            # Pre-registered leaf-SHAPE cell: STAMP the candidate curve instead of
            # asserting curve125. Gated above to --info fair + --opponent fair-champion,
            # so this branch is unreachable for every other arm. The OPPONENT block
            # below is untouched and still runs the unmodified curve125 assert.
            netprior_leaf_prov = _stamp_cand_leaf(cand_leaf_cfg, tag="head-to-head")
        else:
            netprior_leaf_prov = _assert_netprior_leaf(
                cand_leaf_cfg, strict=not args.allow_leaf_hash_drift, side="candidate",
                tag=(args.info if args.info == "fair-netprior" else "head-to-head"))
        # label for the head-to-head banner; literally "curve125" unless drift is on, so
        # an unset-flag run's stdout is byte-identical to before.
        _cand_curve_desc = ("PRE-REGISTERED SHAPE (NOT curve125)"
                            if args.allow_cand_curve_drift else "curve125")
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
        elif _bare_net:
            # ⚠️ THE OPPONENT DOES **NOT** GET curve125. It gets the RoD-v2 ANCHOR leaf
            # (curve100 + residual_scale 0.25), because it is only interpretable as an
            # anchor if it is bit-for-bit the agent the results.csv rows were played by.
            # _assert_bare_net_leaf hard-fails if this ever equals the candidate's leaf
            # (i.e. if the curve125 injection leaked across), which is the single most
            # likely way to produce a plausible but meaningless number here.
            opp_leaf_cfg = _bare_net_leaf_cfg()
            # NOTE: _assert_cy_float_path is deliberately NOT applied to this cfg. That
            # guard exists for the CANDIDATE's Cython float leaf path; the bare-net leaf
            # is consumed by evaluators.make_v25_value_wrapper (virtual_score_v2), a
            # different code path, and the anchor harness never applied it either.
            opp_leaf_prov = _assert_bare_net_leaf(
                opp_leaf_cfg, cand_cfg=cand_leaf_cfg,
                strict=not args.allow_leaf_hash_drift)
        if _bare_net:
            print(f"[bare-net] ⚠️ BLIND (candidate) vs SIGHTED (opponent) — the asymmetry "
                  f"is the measurement; see the module docstring. Do NOT symmetrise.\n"
                  f"[bare-net] candidate frozen leaf: curve125 "
                  f"leaf_hash={netprior_leaf_prov['leaf_hash']} "
                  f"frozen_config_hash="
                  f"{netprior_leaf_prov['frozen_config_hash_champ_dialect']} (champ_env dialect)\n"
                  f"[bare-net] opponent  frozen leaf: v2.9 Bmild_cap8 curve100 + "
                  f"residual_scale={opp_leaf_prov['residual_scale']:g} (the rod_v2 ANCHOR "
                  f"leaf, NOT curve125) leaf_hash={opp_leaf_prov['leaf_hash']}\n"
                  f"[bare-net] PER-SIDE LEAVES DIFFER (required): "
                  f"{'YES' if opp_leaf_prov['leaf_hash'] != netprior_leaf_prov['leaf_hash'] else 'NO'}"
                  f" | env DEFAULT_CONFIG (unmoved) leaf_hash={rung_ruler_hash}\n"
                  f"[bare-net] endgame: candidate exact-K<={args.exact_k} marginalized tail; "
                  f"opponent BARE (no tail) — one-sided by design", flush=True)
        elif _h2h:
            print(f"[head-to-head] opponent={args.opponent}\n"
                  f"[head-to-head] candidate frozen leaf: {_cand_curve_desc} "
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
        elif _greedy:
            print(f"[greedy] ⚠️ DECK-LUCK FLOOR cell: the PRODUCTION champion vs the "
                  f"1-ply RuleBasedPlayer (tier1). Read the champion's non-win fraction "
                  f"as the floor deck luck imposes, NOT as a strength gap.\n"
                  f"[greedy] candidate frozen leaf: curve125 "
                  f"leaf_hash={netprior_leaf_prov['leaf_hash']} "
                  f"frozen_config_hash="
                  f"{netprior_leaf_prov['frozen_config_hash_champ_dialect']} (champ_env dialect)\n"
                  f"[greedy] opponent: LEAFLESS 1-ply RuleBasedPlayer (no search, no "
                  f"leaf, no exact tail) | env DEFAULT_CONFIG (unmoved) "
                  f"leaf_hash={rung_ruler_hash}", flush=True)
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
    elif args.opponent == _BARE_NET:
        _oprobe, opp_rep = _load_net_rep(args.opp_net, device="cpu")
        del _oprobe       # main() only needs the rep; workers load their own copy
        print(f"[bare-net] opp_net={args.opp_net}\n"
              f"[bare-net] opponent rep="
              f"{'SIGHTED' if opp_rep['sighted'] else 'NON-SIGHTED'} "
              f"{opp_rep['n_input_channels']}ch/{opp_rep['n_scalar_features']}sc "
              f"(inferred from ITS OWN checkpoint) | agent=BARE NeuralMCTS "
              f"sims={BARE_NET_SIMS} c_puct={BARE_NET_CPUCT:g} "
              f"fair_chance=False (CLAIRVOYANT — descends the TRUE deck) | "
              f"priors+value=net, value replaced by the v2.9 curve100 leaf + net "
              f"residual (residual_scale={BARE_NET_RESIDUAL_SCALE:g})", flush=True)
    opp_label = _opp_label(args, opp_rep)

    # A head-to-head is only a clean single-variable swap if the two sides share every
    # search knob; those knobs default to the PRODUCTION champion's, so warn loudly if
    # a sweep has moved them off production (the opponent tracks them either way — the
    # A/B stays valid, but it is no longer "vs the shipped champion").
    if args.opponent in _HEAD_TO_HEAD:
        _oes = _opp_eff_sims(args)
        _oek = _opp_eff_k_dets(args)
        _asym_s = args.opp_sims is not None and args.opp_sims != args.sims
        _asym_k = args.opp_k_dets is not None and args.opp_k_dets != args.k_dets
        _asym = _asym_s or _asym_k
        if _asym:
            # The two sides deliberately search DIFFERENT budgets (equal-wall-clock check,
            # or a whole-config A/B like CL-060's k8x1376 vs the k4x688 deploy champion),
            # so it is NOT the single-variable prior swap the symmetric head-to-head is.
            _axes = ("/".join(x for x, on in (("--opp-sims", _asym_s),
                                              ("--opp-k-dets", _asym_k)) if on))
            print(f"[warn] {_axes}: ASYMMETRIC search budgets — candidate "
                  f"k{args.k_dets}x{args.sims} (total {args.k_dets * args.sims}) vs "
                  f"opponent {args.opponent} k{_oek}x{_oes} (total "
                  f"{_oek * _oes}). This is an equal-WALL-CLOCK / whole-config "
                  "deployability check, NOT the single-variable prior swap the symmetric "
                  "head-to-head is: the two sides search different budgets. diff/elo stay "
                  "candidate-minus-opponent.", file=sys.stderr)
        # The OPPONENT's deviation from the shipped champion uses ITS OWN budget
        # (--opp-sims/--opp-k-dets when asymmetric; the shared --sims/--k-dets otherwise).
        _off = _prod_deviations(args, sims_override=_oes, k_dets_override=_oek)
        if _off:
            _swap = ("the opponent's budget is set per-side via --opp-sims/--opp-k-dets; "
                     "the other shared knobs still apply to both sides" if _asym else
                     "BOTH sides use these values, so the swap stays single-variable")
            print("[warn] --opponent " + args.opponent + ": the search config "
                  "deviates from governance/PRODUCTION.yaml (" + "; ".join(_off) + "). "
                  + _swap + ", but the opponent is NOT the shipped production champion "
                  "— do not report this cell as 'vs production'.", file=sys.stderr)
    elif args.opponent == _BARE_NET:
        # bare-net shares NO search knobs with the candidate (its config is pinned), so
        # the "single-variable swap" framing above does not apply. What DOES matter is
        # whether OUR side is the shipped champion — report that, and restate the
        # interpretation rule so it lands in every run log.
        _off = _prod_deviations(args)
        print("[bare-net] candidate = " + ("the shipped production champion config"
                                           if not _off else
                                           "OFF production config (" + "; ".join(_off) + ")")
              + f", BLIND (fair PIMC k{args.k_dets}x{args.sims} = "
              f"{args.k_dets * args.sims} total) with the exact-K<={args.exact_k} tail.",
              file=sys.stderr)
        print("[bare-net] INTERPRETATION (corrected 2026-07-27): this is NOT a bound in "
              "either direction. Information HANDICAPS us (~156 elo), but leaf (curve125) "
              "and endgame (exact-K tail) ADVANTAGE us and cost is not matched, so the net "
              "sign is undetermined. Report only the narrow claim — our blind champion at "
              "this budget vs the sighted RoD-v2 anchor. Do NOT report a win as 'the "
              "lineage gap is at least this', nor a loss as 'the net is stronger'. What "
              "the cell buys is an OUT-OF-LINEAGE ruler.",
              file=sys.stderr)

    # ENGINE (rustport P6). Resolved ONCE here so the workers and the manifest can never
    # disagree — a worker that re-read the YAML could resolve "auto" differently from the
    # manifest that describes the run.
    _backend = _resolve_backend(args.backend)
    if _backend == "rust" and args.info not in ("fair", "clair"):
        ap.error(f"--backend rust reaches --info fair|clair only; got --info {args.info} "
                 "(carc_rs has no net evaluator)")
    # J-RULES PRIOR surface B: resolve the CANDIDATE-ONLY knobs once, fail fast.
    # None == OFF == every historical run, byte-identical. The resolved dict is
    # what the workers consume AND what the manifest stamps (the wiring gate is
    # the RESOLVED dose — this surface deliberately moves no leaf hash).
    _cand_jrules_prior = None
    if float(args.cand_jrules_prior_dose) != 0.0:
        if _backend != "rust":
            ap.error(f"--cand-jrules-prior-dose {args.cand_jrules_prior_dose} is "
                     f"RUST-ONLY (surface B lives in carc_core::search); resolved "
                     f"backend is {_backend!r}. The python search path would "
                     "fail-loud in every worker — refusing up front instead.")
        if args.info != "fair":
            ap.error("--cand-jrules-prior-dose applies to the FAIR candidate "
                     f"(--info fair); got --info {args.info}")
        _cand_jrules_prior = dict(dose=float(args.cand_jrules_prior_dose),
                                  mask=int(args.cand_jrules_prior_mask),
                                  scope=str(args.cand_jrules_prior_scope))
        # Construct once here so a bad mask/scope dies at launch, not in a worker
        # (HeuristicPriorConfig.__post_init__ validates), and so a stale carc_rs
        # wheel dies HERE with the fail-closed TypeError rather than 30 s in.
        _probe_cfg = _build_champ_cfg(args.c_puct, args.tau_p, args.leaf_quantize,
                                      args.final_select, args.value_norm,
                                      None, jrules_prior=_cand_jrules_prior)
        from carcassonne_ai.rust_agent import search_config_rs as _sc_rs
        _sc_rs(_probe_cfg, 8)  # TypeError here == rebuild the wheel on THIS box
    # J-RULES ROOT FILTER surface C: same resolve-once / fail-fast pattern.
    _cand_jrules_filter = None
    if int(args.cand_jrules_filter_mask) != 0:
        if _backend != "rust":
            ap.error(f"--cand-jrules-filter-mask {args.cand_jrules_filter_mask} is "
                     f"RUST-ONLY (surface C lives in carc_core::fair); resolved "
                     f"backend is {_backend!r}. The python search path would "
                     "fail-loud in every worker — refusing up front instead.")
        if args.info != "fair":
            ap.error("--cand-jrules-filter-mask applies to the FAIR candidate "
                     f"(--info fair; the filter binds in the fair agent's PIMC "
                     f"root); got --info {args.info}")
        _cand_jrules_filter = dict(mask=int(args.cand_jrules_filter_mask),
                                   min_keep=int(args.cand_jrules_filter_min_keep))
        # Construct once so a bad mask/min_keep dies at launch (__post_init__
        # validates) and a stale carc_rs wheel dies HERE with the fail-closed
        # TypeError rather than 30 s into the first worker.
        _probe_cfg_c = _build_champ_cfg(args.c_puct, args.tau_p, args.leaf_quantize,
                                        args.final_select, args.value_norm,
                                        None, jrules_filter=_cand_jrules_filter)
        from carcassonne_ai.rust_agent import search_config_rs as _sc_rs_c
        _sc_rs_c(_probe_cfg_c, 8)  # TypeError == rebuild the wheel on THIS box
    if args.rust_threads is not None and _backend != "rust":
        ap.error(f"--rust-threads is a --backend rust knob; got --backend {_backend}")
    if args.rust_threads is not None and args.info == "clair":
        # rust_threads splits the k_dets WORLDS of the PIMC agent across OS threads.
        # The clairvoyant ruler has no determinizations — one tree, one world — so
        # there is nothing to split and the knob would be silently dropped (and then
        # stamped into the manifest as if it had applied).
        ap.error("--rust-threads is a --info fair knob (it splits the PIMC agent's "
                 "k_dets worlds); the clairvoyant ruler runs ONE search and has no "
                 "worlds to split")
    # ⚠️ THE FARM RULE, enforced not merely documented. In a game-parallel pool the
    # game parallelism owns the cores; W16 x t8 = 128 hot threads is the failure mode
    # that motivates this. Explicit parameter, farm default 1, resolved value asserted
    # and printed here and stamped into the manifest below.
    _rust_threads = None
    if _backend == "rust":
        _pooled = int(getattr(args, "workers", 1) or 1) > 1 and not args.smoke
        if args.rust_threads is None:
            _rust_threads = 1
        else:
            _rust_threads = int(args.rust_threads)
            if _pooled and _rust_threads != 1:
                ap.error(
                    f"--rust-threads {_rust_threads} with --workers {args.workers}: a "
                    "game-parallel farm must run the Rust agent at threads=1 (game "
                    "parallelism owns the cores). Use --workers 1 for a threaded "
                    "latency measurement.")
        assert _rust_threads >= 1, f"resolved rust_threads={_rust_threads}"
        print(f"[backend] engine=rust (from --backend {args.backend}) "
              f"rust_threads={_rust_threads} workers={getattr(args, 'workers', 1)} "
              f"{'[FARM: threads=1 per worker]' if _pooled else '[single-process]'}",
              flush=True)
    # Write the RESOLVED values back so _smoke (which early-returns just below)
    # and the pooled path read the same literals, never the raw "auto".
    args.backend, args.rust_threads = _backend, _rust_threads

    # SIMS-SPLIT (--sims-tile/--sims-meeple): candidate-side, --info fair only.
    # Fail HERE (one clean ap.error) rather than as a worker-pool traceback; the
    # agent constructors enforce the same rules a second time (defense in depth).
    _simsplit = _args_simsplit(args)
    if _simsplit is not None:
        if args.info != "fair":
            ap.error(f"--sims-tile/--sims-meeple is a --info fair (candidate) knob; "
                     f"got --info {args.info}")
        for _nm, _v in (("--sims-tile", args.sims_tile),
                        ("--sims-meeple", args.sims_meeple)):
            if _v is not None and int(_v) < 1:
                ap.error(f"{_nm} must be >= 1; got {_v}")
        if args.intra_reuse:
            ap.error("--sims-tile/--sims-meeple and --intra-reuse are mutually "
                     "exclusive (carried trees were built at the tile budget)")
        if args.oracle_prior_mult is not None:
            ap.error("--sims-tile/--sims-meeple and --oracle-prior-mult are mutually "
                     "exclusive (the probe's pre-search budget is defined against a "
                     "single production sims)")
        _st = args.sims if args.sims_tile is None else args.sims_tile
        _sm = args.sims if args.sims_meeple is None else args.sims_meeple
        print(f"[sims-split] CANDIDATE searches TILES at k{args.k_dets}x{_st} and "
              f"MEEPLES at k{args.k_dets}x{_sm} (per-turn total "
              f"{args.k_dets * (_st + _sm)} vs symmetric "
              f"{2 * args.k_dets * args.sims}); opponent untouched.", flush=True)

    if args.smoke:
        if args.orch_shm_name or args.opp_orch_shm_name:
            ap.error("--smoke does not drive the orch path (single-process CPU only); "
                     "run verify_sighted_orch_parity.py + an --orch-shm-name n=20 eval instead")
        return _smoke(args, cand_leaf_cfg, opp_leaf_cfg=opp_leaf_cfg, opp_rep=opp_rep,
                      cand_jrules_prior=_cand_jrules_prior,
                      cand_jrules_filter=_cand_jrules_filter,
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

    # NET-FORWARD BACKEND (fair-netprior only). Packed into ONE positional so the two
    # long `initargs=` tuples grow by one entry. None == the pre-existing torch path.
    _netprior_backend = None
    if args.net_backend or args.coreml_model:
        if args.info != "fair-netprior":
            ap.error("--net-backend / --coreml-model apply to --info fair-netprior only")
        if args.net_backend == "coreml":
            if not args.coreml_model:
                ap.error("--net-backend coreml requires --coreml-model <.mlpackage>")
            if not Path(args.coreml_model).exists():
                ap.error(f"--coreml-model: no such path {args.coreml_model}")
            if args.batch_size > 1:
                # Would raise in the worker anyway; failing in main() costs 0 games.
                ap.error("--net-backend coreml requires --batch-size 1 (the exported "
                         "model is fixed batch-1; batching would engage virtual loss "
                         "for no transport win)")
            if args.orch_shm_name:
                ap.error("--net-backend coreml and --orch-shm-name are two different "
                         "forward transports; pick one")
        elif args.coreml_model:
            ap.error("--coreml-model given without --net-backend coreml")
        _netprior_backend = (args.net_backend, args.coreml_model,
                             args.coreml_compute_units)
        print(f"[fair-netprior] net_backend={args.net_backend} "
              f"model={args.coreml_model} units={args.coreml_compute_units}\n"
              f"[fair-netprior] ⚠️ NOT byte-identical to the torch backend (fp16 can "
              f"reorder near-tied priors) — cite verify_coreml_evaluator.py", flush=True)

    if not args.summary_only and not args.allow_selfplay_seeds:
        ep.assert_clean_eval_seed_range(args.seed_start, args.n)

    cfg = _build_champ_cfg(args.c_puct, args.tau_p, args.leaf_quantize,
                           args.final_select, args.value_norm, cand_leaf_cfg,
                           jrules_prior=_cand_jrules_prior,
                           jrules_filter=_cand_jrules_filter)
    champ_cfg_dict = {"c_puct": args.c_puct, "tau_p": args.tau_p,
                      "leaf_quantize": args.leaf_quantize,
                      "final_select": args.final_select, "value_norm": args.value_norm}

    # the `_vs_h{rung_sims}` segment is the OPPONENT identity; a head-to-head must NEVER
    # land in the same auto out-dir as the h800 cell at the same knobs (Trap 1). The
    # h800 tag is unchanged.
    if args.opponent == "h800":
        _vs = f"vs_h{args.rung_sims}"
    elif args.opponent == _GREEDY:
        _vs = "vs_greedy"
    elif args.opponent == "fair-champion":
        _vs = "vs_fairchamp"
    elif args.opponent == _BARE_NET:
        # distinct from the `net` mode's `vs_net-*` (that is a FAIR net-prior agent on
        # OUR leaf; this is the SIGHTED bare anchor) so the two can never share a cached
        # out-dir at the same candidate knobs (Trap 1).
        _vs = f"vs_sightedbare-{Path(args.opp_net).stem}"
    else:
        _vs = f"vs_net-{Path(args.opp_net).stem}"
    # ASYMMETRIC opponent budget (--opp-k-dets / --opp-sims) is part of the OPPONENT's
    # identity: a k4x688 deploy-champion cell and a k8x688 cell at the same candidate
    # knobs are DIFFERENT opponents, and sharing an auto out-dir would let one cell's
    # cached per-game .json be reused by the other (Trap 1 — wrong results, not merely a
    # confusing name). Empty when both flags are unset, so the symmetric auto tag is
    # byte-identical to today. An explicit --out-subdir still owns the dir name.
    if args.opp_k_dets is not None or args.opp_sims is not None:
        _vs = f"{_vs}-k{_opp_eff_k_dets(args)}x{_opp_eff_sims(args)}"
    # Track-F Gate A oracle-prior suffix rides on the CANDIDATE segment ONLY (before the
    # `_vs_<opponent>` identity), so an oracle cell never shares an out-dir with the plain
    # candidate and the OPPONENT label (_opp_label / opponent manifest block) stays clean.
    _cand_oracle = "" if args.oracle_prior_mult is None else f"-oracle{args.oracle_prior_mult}"
    tag = (f"fair_{args.info}_c{args.c_puct:g}_tau{args.tau_p:g}_{args.leaf_quantize}"
           f"_kd{args.k_dets}_s{args.sims}{_cand_oracle}_{_vs}_k{args.exact_k}")
    if cand_leaf_cfg is not None:
        # a leaf A/B: keep the auto tag / default out-dir distinct per candidate leaf
        # so cells never silently share a directory (Trap 1). An explicit --out-subdir
        # (the Stage-3 launcher path, e.g. c5_s3_curve125_fair) still owns the dir name.
        tag = f"{tag}-leaf{_leaf_hash(cand_leaf_cfg)[:8]}"
    sub = args.out_subdir or tag
    root = Path(args.out_root) if args.out_root else EVAL_ROOT
    out = root / sub
    out.mkdir(parents=True, exist_ok=True)

    # The 4th element is the per-cell LIFETIME attempt budget; `_play_one` reads
    # it positionally and defaults to 1 for a 3-tuple, so every other consumer of
    # `tasks` (which only ever reads t[1]/t[2]) is untouched.
    tasks = [(str(out), seed, a_seat, args.max_attempts)
             for seed, a_seat in _build_work(args.seed_start, args.n, args.paired)]

    if args.summary_only:
        results = [r for t in tasks if (r := _try_load(_result_path(out, t[1], t[2]))) is not None]
        _all = load_failures(out, include_resolved=True)
        _cell = [_all[(t[1], t[2])] for t in tasks if (t[1], t[2]) in _all]
        if results:
            summ = _summary(results, args.info, args.exact_k, args.k_dets, args.sims,
                            args.rung_sims, opponent=args.opponent, opp_label=opp_label,
                            opp_k_dets=args.opp_k_dets, opp_sims=args.opp_sims,
                            failures=[r for r in _cell if not r.get("resolved")],
                            resolved=[r for r in _cell if r.get("resolved")])
            json.dump(summ, open(out / "summary.json", "w"), indent=2)
            _patch_failure_manifest(out, summ, 0)
        else:
            print("no cached results yet")
        return 0

    leaf_cfg = cfg.resolved_leaf_cfg()          # FAIR champion side (override or DEFAULT_CONFIG)
    rung_leaf_cfg = DEFAULT_CONFIG              # h800 rung is ALWAYS env DEFAULT_CONFIG (the ruler)
    # human label for the champion leaf: reflects the --cand-leaf-json override when active
    # (the Trap-1 mislabel mitigation — a candidate cell is NOT "v2.9 Bmild_cap8").
    if cand_leaf_cfg is None:
        _champ_leaf_label = "v2.9 Bmild_cap8 (DEFAULT_CONFIG)"
    elif (args.info == "fair-netprior" or _h2h or _bare_net) and args.cand_leaf_json is None:
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
    # The OPPONENT's per-det sims budget + determinization count (--opp-sims/--opp-k-dets
    # when asymmetric, else the shared --sims/--k-dets). Byte-identical to args.sims /
    # args.k_dets when those flags are unset, so an unset run's manifest is unchanged in
    # every opponent field.
    opp_eff_sims = _opp_eff_sims(args)
    opp_eff_k_dets = _opp_eff_k_dets(args)
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
                     # NET-FORWARD BACKEND: stamped ONLY when the caller actually bound
                     # one, on the same no-drift terms as champion_factory's
                     # exact_budget / parallel_workers blocks — a run that did not pass
                     # the flag carries a manifest byte-identical to the pre-feature one.
                     **({"net_backend": champion_factory.net_backend_manifest_block(
                            args.net_backend, model_path=args.coreml_model,
                            compute_units=args.coreml_compute_units, source="cli")}
                        if _netprior_backend else {}),
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
        # --opp-sims / --opp-k-dets: the opponent's ASYMMETRIC per-det budget and
        # determinization count. None (absent-semantics) when unset -> the opponent used
        # the shared --sims/--k-dets (symmetric head-to-head).
        "opp_sims": args.opp_sims,
        "opp_k_dets": args.opp_k_dets,
        "opponent": {
            "mode": args.opponent,
            "label": opp_label,
            "agent": ("HeuristicMCTS" if args.opponent == "h800" else
                      "RuleBasedPlayer (1-ply greedy, tier1; == the L2 ladder's "
                      "`greedy` rung, scripts/ladder_rung_eval.py::_GreedyAgent)"
                      if args.opponent == _GREEDY else
                      "FairHeuristicPriorAgent" if args.opponent == "fair-champion" else
                      "FairHeuristicPriorAgent + distilled net POLICY priors "
                      "(frozen curve125 champion leaf value; severed value loop)"),
            "priors_source": ("random_expansion_uct (no priors)" if args.opponent == "h800"
                              else "none (no search: 1-ply hand-coded rules)"
                              if args.opponent == _GREEDY
                              else "net_policy_head" if args.opponent == "net"
                              else "heuristic_softmax_dleaf_tau"),
            "value_source": ("v2.9 curve100 heuristic leaf (DEFAULT_CONFIG ruler)"
                             if args.opponent == "h800"
                             else "none (leafless: 1-ply rule ordering, no evaluation)"
                             if args.opponent == _GREEDY else "frozen_v29_curve125_leaf"),
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
            # the OPPONENT's determinization count: --opp-k-dets when asymmetric, else the
            # shared --k-dets (== args.k_dets, byte-identical when --opp-k-dets is unset).
            "k_dets": (None if args.opponent in _LEAFLESS_RUNGS else opp_eff_k_dets),
            # the OPPONENT's per-det budget: --opp-sims when asymmetric, else the shared
            # --sims (== args.sims, byte-identical to today when --opp-sims is unset).
            "sims_per_det": (None if args.opponent in _LEAFLESS_RUNGS else opp_eff_sims),
            "total_sims": (None if args.opponent in _LEAFLESS_RUNGS
                           else opp_eff_k_dets * opp_eff_sims),
            "endgame": (None if args.opponent in _LEAFLESS_RUNGS
                        else {"mode": "marginalized", "exact_k": args.exact_k,
                              "exact_budget": EXACT_BUDGET}),
            "leaf": (f"v2.9 Bmild_cap8 (DEFAULT_CONFIG, leaf{_leaf_hash(rung_leaf_cfg)[:8]})"
                     if args.opponent == "h800"
                     else "none (LEAFLESS: the 1-ply RuleBasedPlayer evaluates no leaf)"
                     if args.opponent == _GREEDY
                     else f"FROZEN v2.9 curve125 production champion leaf, auto-injected "
                          f"in-process (leaf{_leaf_hash(opp_leaf_cfg)[:8]})"),
            "leaf_hash": (_leaf_hash(rung_leaf_cfg) if args.opponent == "h800"
                          else None if args.opponent == _GREEDY
                          else _leaf_hash(opp_leaf_cfg)),
            "leaf_cfg": (_leaf_dict(rung_leaf_cfg) if args.opponent == "h800"
                         else None if args.opponent == _GREEDY
                         else _leaf_dict(opp_leaf_cfg)),
            "curve125_leaf_provenance": opp_leaf_prov,
            "champ_cfg": (None if args.opponent in _LEAFLESS_RUNGS else champ_cfg_dict),
            "production_config_deviations": (_prod_deviations(args, sims_override=opp_eff_sims,
                                                              k_dets_override=opp_eff_k_dets)
                                             if args.opponent in _HEAD_TO_HEAD else None),
            "provenance": ("CL-022 ruler (CLAIRVOYANCE_GAP_VERDICT.md, h800 v2.7)"
                           if args.opponent == "h800"
                           else "the Level-2 ladder's `greedy` rung (RuleBasedPlayer, "
                                "1-ply, leaf v1_1ply) — bit-for-bit the opponent in the "
                                "*_vs_greedy_n200 rows of experiments/results.csv, which "
                                "is what makes this cell comparable to them. DECK-LUCK "
                                "FLOOR cell: the champion's non-win fraction here is a "
                                "variance floor, not a strength gap."
                           if args.opponent == _GREEDY
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
        # explicit aliases/derivations so a cell is readable without knowing the
        # harness's conventions (n is GAMES; a paired cell plays each deck twice).
        "band_seed_start": args.seed_start,
        "n_decks": (args.n // 2 if args.paired else args.n),
        "seatings_per_deck": (2 if args.paired else 1),
        # False for every historical cell; True ONLY for a pre-registered leaf-SHAPE
        # cell (--allow-cand-curve-drift), where the CANDIDATE curve deliberately
        # differs from the opponent's pinned curve125. The literal 8-entry curves are
        # already in champion.leaf_cfg.v29_meeple_curve / opp_leaf_cfg.v29_meeple_curve
        # (and cand_leaf_cfg here), so they are not duplicated.
        "cand_curve_drift_allowed": bool(args.allow_cand_curve_drift),
        "cand_curve_drift": (netprior_leaf_prov if args.allow_cand_curve_drift else None),
        "leaf_hash": _leaf_hash(leaf_cfg), "code_rev": code_rev(),
        # C5 Stage-3 per-side leaf provenance (Trap 1: a worker missing the env exports
        # silently runs the wrong leaf — the per-side leaf_hash is the mitigation). The
        # FAIR champion side carries the --cand-leaf-json override; the rung is DEFAULT.
        "cand_leaf_json": args.cand_leaf_json,
        "cand_leaf_cfg": _leaf_dict(leaf_cfg),
        "cand_leaf_hash": _leaf_hash(leaf_cfg),
        # J-RULES PRIOR surface B (CANDIDATE side only; None == OFF == every
        # historical cell). ⚠️ THE WIRING GATE FOR A LIVE TERM IS THIS RESOLVED
        # DICT — surface B moves NO leaf hash (cand_leaf_hash above can EQUAL
        # the champion's on a live-term cell), so a moved-hash check proves
        # nothing here. A reader must check cand_jrules_prior.dose directly.
        "cand_jrules_prior": _cand_jrules_prior,
        # J-RULES ROOT FILTER surface C (CANDIDATE side; None = OFF). Same
        # inverted-hash situation as surface B: no leaf hash moves, so THIS
        # resolved dict + the per-game jf_dropped counters are the wiring gates.
        "cand_jrules_filter": _cand_jrules_filter,
        # rung_leaf_* is the env DEFAULT_CONFIG. For --opponent h800 it IS the opponent's
        # leaf (the ruler). For a head-to-head no agent uses it — it is recorded anyway as
        # the PROOF that the in-process curve125 injection did not move DEFAULT_CONFIG.
        "rung_leaf_cfg": _leaf_dict(rung_leaf_cfg),
        "rung_leaf_hash": _leaf_hash(rung_leaf_cfg),
        "opp_leaf_cfg": (_leaf_dict(opp_leaf_cfg) if opp_leaf_cfg is not None else None),
        "opp_leaf_hash": (_leaf_hash(opp_leaf_cfg) if opp_leaf_cfg is not None else None),
        # False (not None) for bare-net: the sides are checked AND deliberately differ.
        "both_sides_curve125": (False if _bare_net else
                                bool(opp_leaf_cfg is not None
                                     and _leaf_hash(opp_leaf_cfg) == _leaf_hash(leaf_cfg))
                                if _h2h else None),
        # NOTE: must stay accurate under ASYMMETRIC budgets (--opp-sims / --opp-k-dets).
        # The old text hardcoded "targets ~2750 sims", which reads as FALSE whenever the
        # candidate is deliberately off the deploy budget (e.g. the CL-060 k8x1376=11008
        # H2H). Describe what this run actually did instead of asserting a fixed target.
        "equal_wall_clock_note": (
            (f"BLIND vs SIGHTED: candidate k_dets={args.k_dets}x{args.sims}"
             f"={args.k_dets * args.sims} total per move (fair PIMC, curve125, exact-K<="
             f"{args.exact_k}) vs a PINNED bare NeuralMCTS anchor at sims={BARE_NET_SIMS} "
             f"c_puct={BARE_NET_CPUCT:g} (clairvoyant, curve100+rs"
             f"{BARE_NET_RESIDUAL_SCALE:g}, no tail). NOT an equal-budget or "
             "equal-wall-clock cell — the opponent is a fixed anchor identity, not a "
             "budget-matched sibling.")
            if _bare_net else
            (f"ASYMMETRIC budgets: candidate k_dets={args.k_dets}x{args.sims}"
             f"={args.k_dets * args.sims} total vs opponent "
             f"k_dets={_opp_eff_k_dets(args)}x{args.opp_sims if args.opp_sims is not None else args.sims}"
             f"={_opp_eff_k_dets(args) * (args.opp_sims if args.opp_sims is not None else args.sims)}"
             " total per move — this is NOT an equal-sims cell; see the summary's "
             "'asymmetric_budgets' block for the per-side record")
            if (_h2h and (args.opp_sims is not None or args.opp_k_dets is not None))
            # Symmetric branch keeps the PRE-CHANGE string verbatim so an unset-flag run
            # stays byte-identical to every historical manifest (the parity property).
            else ("champion total per-move budget k_dets*sims targets the "
                  "deployed clairvoyant champion ~2750 sims (equal wall-clock; "
                  "k_dets root expansions add a little fixed overhead)")),
        "env": {k: os.environ.get(k) for k in _CANON_ENV},
    }
    # ---- BLIND vs SIGHTED (--opponent bare-net) manifest correction. Written as a
    # post-hoc override rather than by threading a third branch through every ternary
    # above, so the h800 and head-to-head expressions stay LITERALLY unchanged (they are
    # what produced last night's cells). Every key here is one the generic `else` branch
    # would have filled with head-to-head (curve125 / fair-agent) semantics that are
    # WRONG for this mode — most dangerously `leaf`, which would have claimed curve125.
    if _bare_net:
        man_cfg["opponent"].update({
            "agent": "NeuralMCTS (BARE — no exact-K endgame handoff)",
            "clairvoyant": True,
            "fair_chance": False,
            "priors_source": "net_policy_head",
            "value_source": ("v2.9 curve100 heuristic leaf + net-value residual "
                             f"(residual_scale={BARE_NET_RESIDUAL_SCALE:g}) — "
                             "make_v25_value_wrapper, the rod_v2 anchor construction"),
            "net": args.opp_net,
            # bare-net consumes BOTH net heads over whichever transport is in use.
            # ⚠️ ADDITIVITY: under the CPU transport this key keeps its exact
            # pre-change value and NO new key is introduced (see the orch-only block
            # below), so a per-worker-CPU manifest stays byte-identical to the ones
            # last night's cells wrote.
            "priors_transport": (("carc-orch SHM (" + args.opp_orch_shm_name + ")")
                                 if args.opp_orch_shm_name else "per-worker CPU net"),
            "c_puct": BARE_NET_CPUCT,
            "sims": BARE_NET_SIMS,
            "k_dets": None,          # not a PIMC agent
            "sims_per_det": None,
            "total_sims": BARE_NET_SIMS,
            "endgame": None,         # BARE by design (one-sided tail)
            "leaf": (f"v2.9 Bmild_cap8 curve100 + residual_scale="
                     f"{BARE_NET_RESIDUAL_SCALE:g} — the rod_v2 ANCHOR leaf, "
                     f"NOT curve125 (leaf{_leaf_hash(opp_leaf_cfg)[:8]})"),
            "curve125_leaf_provenance": None,   # this side is deliberately NOT curve125
            "anchor_leaf_provenance": opp_leaf_prov,
            "champ_cfg": None,       # shares NO search knobs with the candidate
            "production_config_deviations": None,
            "pinned_knobs": {"sims": BARE_NET_SIMS, "c_puct": BARE_NET_CPUCT,
                             "residual_scale": BARE_NET_RESIDUAL_SCALE,
                             "meeple_k": BARE_NET_MEEPLE_K,
                             "source": "eval_puct_priors.py NET_* == "
                                       "eval_hybrid_handoff.py ITER8_*"},
            "provenance": ("rod_v2 ANCHOR identity — bit-for-bit the agent behind the "
                           "net:<ckpt> anchor rows in experiments/results.csv "
                           "(rodv2_iter02_vs_heur6400_v29_n200 / _vs_heur3200_v29_n200); "
                           "play knobs pinned, NOT CLI-settable"),
        })
        # ---- GPU transport (--opp-orch-shm-name): keys added ONLY when the orch path
        # is in use, so a per-worker-CPU bare-net manifest stays byte-identical to the
        # pre-change output. The anchor rows on record were played net-on-CPU; a reader
        # of THIS manifest must be able to see that this cell was not, without having to
        # know the flag. Same discipline as the `net` opponent's priors_transport.
        if args.opp_orch_shm_name:
            man_cfg["opponent"].update({
                "value_transport": "carc-orch SHM (" + args.opp_orch_shm_name + ")",
                "net_device": "cuda (the carc-orch server owns the net; workers are CPU)",
                "transport_numerics": {
                    "anchor_rows_played_on": "cpu fp32 (per-worker net)",
                    "this_cell_played_on": "cuda fp32 (carc-orch SHM TorchScript)",
                    "identical": ["weights", "leaf", "sims", "c_puct", "residual_scale",
                                  "clairvoyance (fair_chance=False)",
                                  "masked-softmax priors", "bare (no endgame tail)"],
                    "differs": "float reduction order only",
                    "note": BARE_NET_GPU_NOTE,
                    "measure_with": "scripts/classical_search/bare_net_gpu_divergence.py",
                },
            })
        man_cfg["asymmetry"] = {
            "mode": "BLIND (candidate) vs SIGHTED (opponent) — DELIBERATE, DO NOT SYMMETRISE",
            "information": {"candidate": "fair PIMC root determinization (blind)",
                            "opponent": "NeuralMCTS fair_chance=False (sees the true deck)",
                            "measured_clairvoyance_tax_elo": 156},
            "leaf": {"candidate": _leaf_hash(leaf_cfg),
                     "opponent": _leaf_hash(opp_leaf_cfg),
                     "differ": _leaf_hash(leaf_cfg) != _leaf_hash(opp_leaf_cfg),
                     "required_to_differ": True},
            "endgame": {"candidate": f"marginalized exact-K<={args.exact_k}",
                        "opponent": "none (bare)"},
            "cost": {"matched": False,
                     "note": ("candidate/opponent ms/move ran 0.29x (344 rung) to 8.5x "
                              "(11008 rung) across CL-069; see the per-cell ms/move "
                              "fields for this cell's own ratio")},
            "favours": {"information": "opponent", "leaf": "candidate",
                        "endgame": "candidate", "cost": "unmatched"},
            "is_bound": False,
            "interpretation": ("CORRECTED 2026-07-27 — this is NOT a bound in either "
                               "direction. Earlier manifests claimed 'every axis handicaps "
                               "the candidate, so a WIN is a conservative LOWER BOUND on "
                               "the lineage gap'; that was wrong. Only INFORMATION "
                               "handicaps the candidate (~156 elo clairvoyance tax). LEAF "
                               "(curve125 vs curve100+rs0.25) and ENDGAME (exact-K tail vs "
                               "none) ADVANTAGE the candidate, and COST is unmatched, so "
                               "the net sign is undetermined. Report only the narrow claim: "
                               "the blind candidate at this budget beat/lost to the sighted "
                               "RoD-v2 anchor. Neither a win ('the lineage gap is at least "
                               "this') nor a loss ('the net is stronger') is licensed. The "
                               "cell's value is that the opponent is OUT OF LINEAGE."),
        }
        man_cfg["result_semantics"]["note"] = (
            man_cfg["result_semantics"]["note"]
            + " ⚠️ BLIND vs SIGHTED: this elo is NOT a like-for-like pairwise rating — the "
              "candidate is blind, curve125 and tail-equipped; the opponent is clairvoyant, "
              "curve100+rs0.25 and bare. See the `asymmetry` block.")

    # Track-F Gate A oracle-prior provenance — added ONLY when the probe is ON (CANDIDATE
    # side), so a plain (OFF) manifest stays byte-identical to the pre-change output. Top-
    # level scalar + a config block; the block is also stamped into the champion (candidate)
    # sub-manifest. The OPPONENT block is untouched (candidate-only, per _opp_label).
    if args.oracle_prior_mult is not None:
        oracle_block = {
            "oracle_prior_mult": args.oracle_prior_mult,
            "presearch_sims_per_det": args.sims * args.oracle_prior_mult,
            "main_sims_per_det": args.sims,
            "k_dets": args.k_dets,
            "eps_coef": args.oracle_prior_eps_coef,
            "scope": ("ROOT priors only (deeper node priors = heuristic evaluator); PER-WORLD "
                      "pre-search on EACH determinization's reshuffled deck; the pre-search "
                      "tree is NOT reused into that world's main search; pooled-Q across "
                      "worlds is UNCHANGED"),
            "applies_to": "candidate",
            "per_world": True,
        }
        man_cfg["oracle_prior_mult"] = args.oracle_prior_mult
        man_cfg["oracle_prior"] = oracle_block
        man_cfg["champion"]["oracle_prior"] = oracle_block
        man_cfg["champion"]["priors_source"] = (
            "heuristic_softmax_dleaf_tau + per-world oracle ROOT-prior override (Gate A)")
    # MEEPLE-DEDUP provenance — added ONLY when the feature is ON (CANDIDATE side), so a
    # plain (OFF) manifest stays byte-identical to the pre-change output. Same shape and
    # same candidate-only scope as the oracle-prior block above.
    if args.meeple_dedup:
        from carcassonne_ai import meeple_equiv as _me

        dedup_block = {
            "enabled": True,
            "prior_mode": _me.PRIOR_MODE,
            "grouping": "carcassonne_ai.meeple_equiv.feature_groups (INTRA-TILE only)",
            "scope": ("meeple-phase nodes ONLY (root and interior); keeps the lowest "
                      "action id of each group, folds the dropped members' prior mass "
                      "onto it, renormalizes over the survivors. The true legal mask "
                      "from game.get_valid_moves is UNCHANGED; tile-phase actions and "
                      "the pass action are untouched."),
            "applies_to": "candidate",
            "census": "measurement/classical_search/meeple_dedup_census_20260727.json",
        }
        man_cfg["meeple_dedup"] = dedup_block
        man_cfg["champion"]["meeple_dedup"] = dedup_block
    # SIMS-SPLIT provenance — added ONLY when a knob is set (CANDIDATE side), so a
    # plain (OFF) manifest stays byte-identical to the pre-change output. Same shape
    # and same candidate-only scope as the meeple-dedup block above.
    if _simsplit is not None:
        _st = args.sims if args.sims_tile is None else int(args.sims_tile)
        _sm = args.sims if args.sims_meeple is None else int(args.sims_meeple)
        simsplit_block = {
            "sims_tile": args.sims_tile,        # None = inherited the shared --sims
            "sims_meeple": args.sims_meeple,
            "effective_sims_tile": _st,
            "effective_sims_meeple": _sm,
            "default_sims_per_det": args.sims,
            "per_turn_total_sims": args.k_dets * (_st + _sm),
            "symmetric_per_turn_total_sims": 2 * args.k_dets * args.sims,
            "scope": ("CANDIDATE side only. Per-world sims per decision PHASE: TILES "
                      "decisions search each of the k_dets worlds at sims_tile, "
                      "MEEPLES decisions at sims_meeple (None = the shared --sims). "
                      "Determinization draws, per-world seeds, pooled-Q, the "
                      "forced-move short-circuit and the exact-K latch are untouched; "
                      "on --backend rust this is a stateless per-call sims override "
                      "(FairAgentRs.choose_action(sims_override=...), "
                      "last_move()['sims_used'] is the per-move evidence)."),
            "applies_to": "candidate",
            "lever": "phase-asymmetric sims split (docs/LEVER_INDEX.md §5)",
        }
        man_cfg["sims_split"] = simsplit_block
        man_cfg["champion"]["sims_split"] = simsplit_block
    # ENGINE provenance — stamped ONLY when the run is not on the python default, on the
    # same no-hash-drift terms as every block around it (a python-backend manifest stays
    # byte-identical to every manifest already on disk). Records WHICH carc_rs build
    # executed and at how many threads, because a latency number is uninterpretable
    # without the thread count and a bit-exactness claim is uninterpretable without the
    # wheel's own version + tile-data digests.
    if _backend != "python":
        from carcassonne_ai.rust_agent import backend_provenance

        man_cfg["backend"] = {
            "name": _backend,
            "default": "python",
            "requested": args.backend,
            "rust_threads": _rust_threads,
            "workers": int(getattr(args, "workers", 1) or 1),
            "threads_policy": (
                "FARM: game parallelism owns the cores, so each worker process runs "
                "the Rust agent at threads=1 (W16 x t8 = 128 hot threads is the "
                "failure mode this prevents)"
                if int(getattr(args, "workers", 1) or 1) > 1 else
                "single-process: threads is a latency knob, not a farm setting"),
            "converted_sides": (
                ["candidate", "opponent"] if args.opponent in _HEAD_TO_HEAD
                else ["candidate"]),
            "unconverted_note": (
                "the h800 / greedy / bare-net rungs are FROZEN RULERS and stay Python "
                "by design, so an asymmetric cell realises a smaller end-to-end "
                "speedup than the champion-side multiplier — read rung_ms_per_move "
                "next to champ_prefix_ms_per_move before quoting one"),
            "note": "BEHAVIOUR-IDENTICAL BY GATE (rustport G4/G6), not by "
                    "construction. It is an ENGINE, not a player — no strength claim "
                    "moves with it.",
            **backend_provenance(),
        }
    # C3-INTRA provenance — added ONLY when the carry is ON (CANDIDATE side), so a plain
    # (OFF) manifest stays byte-identical to the pre-change output. Same shape and same
    # candidate-only scope as the meeple-dedup block above.
    if args.intra_reuse:
        from carcassonne_ai import intra_reuse as _ir

        intra_block = {
            "enabled": True,
            "flag": _ir.ENV_VAR,
            "scope": ("carries the k_dets trees AND their determinized decks from a "
                      "turn's TILE decision into the SAME turn's MEEPLE decision, "
                      "re-rooted at the tile action actually played; any mismatch "
                      "(opponent moved, restore, forced move, exact-endgame latch, new "
                      "game) discards and searches fresh"),
            "budget_semantics": ("the meeple decision still runs `sims` NEW simulations "
                                 "per determinization ON TOP of the carried visits"),
            "read_out_caveat": ("ON does MORE total work per turn at equal nominal sims "
                                "-> a positive screen REQUIRES an equal-wall-clock "
                                "confirm (CL-044 ms-ratio house rule)"),
            "information_legality": ("no hidden information arrives between the two "
                                     "decisions (StateUpdater draws the next tile only "
                                     "at the END of the meeple phase), unlike the "
                                     "ACROSS-move reuse of CL-044"),
            "applies_to": "candidate",
        }
        man_cfg["intra_turn_reuse"] = intra_block
        man_cfg["champion"]["intra_turn_reuse"] = intra_block
    write_manifest(out, kind="eval_fair_puct", game=game_tag(Game()),
                   config=man_cfg, overwrite=True)

    todo = [t for t in tasks if not _result_path(out, t[1], t[2]).exists()]
    # ⚠️ TERMINATION. A cell already on disk as a FAILED record is treated as DONE
    # (h2h `load_done`): these failures are deck-deterministic — same deck, same
    # seeds, same deterministic players ⇒ the same raise — so a plain relaunch
    # would re-burn a full game-time per pathological cell forever (the observed
    # 16 identical re-crashes). `--retry-failed` re-opens them for a code fix, and
    # even that is bounded by the record's lifetime `attempts` vs --max-attempts.
    prior_failures = load_failures(out)
    if prior_failures:
        todo, _reopened, _skipped, _exhausted = _filter_failed_todo(
            todo, prior_failures, args.retry_failed, args.max_attempts)
        print(f"  [failures] {len(prior_failures)} prior failed game(s) on disk: "
              f"{len(_reopened)} re-opened by --retry-failed, {len(_skipped)} skipped "
              f"(default; use --retry-failed after a code fix), {len(_exhausted)} "
              f"PERMANENT (attempts >= --max-attempts {args.max_attempts}) — records "
              f"in {out / FAILED_DIRNAME}", flush=True)
    workers = args.workers or min(os.cpu_count() or 1, len(todo) or 1)
    print(f"fair-puct[{tag}]: info={args.info} n={args.n} paired={args.paired} K={args.exact_k} "
          f"k_dets={args.k_dets} sims={args.sims} | {len(tasks)-len(todo)} cached, "
          f"{len(todo)} to play, {workers} workers, out={out}")
    sys.stdout.flush()

    _cand_orch = bool(args.orch_shm_name) and args.info in ("fair-net", "fair-netprior")
    _opp_orch = bool(args.opp_orch_shm_name) and args.opponent in _NET_OPPONENTS
    orch = _cand_orch or _opp_orch
    results = []
    n_failed_this_leg = 0
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
                      f"{'sighted' if opp_rep['sighted'] else 'non-sighted'} "
                      # bare-net consumes BOTH heads (priors steer PUCT, value feeds the
                      # residual leaf); the `net` opponent discards the remote value.
                      f"{'PRIORS+VALUE' if args.opponent == _BARE_NET else 'PRIORS'})",
                      flush=True)
            if _opp_orch and args.opponent == _BARE_NET:
                print("  [orch] ⚠️ bare-net TRANSPORT NOTE: " + BARE_NET_GPU_NOTE,
                      flush=True)
            _pool_cm = _ctx.Pool(
                processes=workers, initializer=_worker_init,
                initargs=(args.info, champ_cfg_dict, args.sims, args.k_dets, args.exact_k,
                          args.rung_sims, args.shared_claim, args.claim_host,
                          args.claim_stale_secs, args.net, args.net_mode, args.net_lambda,
                          (args.orch_shm_name or ""), _id_q, cand_leaf_cfg, netprior_rep,
                          args.opponent, opp_leaf_cfg, args.opp_net, opp_rep,
                          (args.opp_orch_shm_name or ""), args.batch_size,
                          args.opp_sims, args.oracle_prior_mult,
                          args.oracle_prior_eps_coef, args.opp_k_dets,
                          (True if args.meeple_dedup else None),
                          (True if args.intra_reuse else None),
                          _netprior_backend, _backend, _rust_threads,
                          _simsplit, _cand_jrules_prior, _cand_jrules_filter))
        else:
            _pool_cm = Pool(
                processes=workers, initializer=_worker_init,
                initargs=(args.info, champ_cfg_dict, args.sims, args.k_dets, args.exact_k,
                          args.rung_sims, args.shared_claim, args.claim_host,
                          args.claim_stale_secs, args.net, args.net_mode, args.net_lambda,
                          "", None, cand_leaf_cfg, netprior_rep,
                          args.opponent, opp_leaf_cfg, args.opp_net, opp_rep, "",
                          args.batch_size, args.opp_sims, args.oracle_prior_mult,
                          args.oracle_prior_eps_coef, args.opp_k_dets,
                          (True if args.meeple_dedup else None),
                          (True if args.intra_reuse else None),
                          _netprior_backend, _backend, _rust_threads,
                          _simsplit, _cand_jrules_prior, _cand_jrules_filter))
        with _pool_cm as pool:
            done = 0
            for r in pool.imap_unordered(_play_one, todo, chunksize=1):
                if r is None:
                    continue
                if isinstance(r, GameFailure):
                    # RECORDED, NOT FATAL. The pool CONTINUES; the game is an
                    # EXCLUSION (record in <out>/failed/, counted in the summary).
                    n_failed_this_leg += 1
                    print(f"  ⚠️ FAILED GAME seed={r.seed} a_seat={r.a_seat} "
                          f"{r.exc_type}: {str(r.exc)[:300]} "
                          f"(attempt {r.attempts}/{args.max_attempts}"
                          f"{', PERMANENT' if r.permanent else ''}"
                          f"{', window_truncation' if r.window_truncation else ''}"
                          f"; {n_failed_this_leg} failed so far — the pool CONTINUES, "
                          f"the claim was released, see the summary's n_failed)",
                          flush=True)
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

    # Re-read the failure records from DISK (not just this leg's): a --resume must
    # never hide failures banked by an earlier leg, and a --shared-claim peer's
    # failures belong to the cell just as much as ours.
    _fails_now = load_failures(out, include_resolved=True)
    _cell_recs = [_fails_now[(t[1], t[2])] for t in tasks if (t[1], t[2]) in _fails_now]
    # A record whose game later SUCCEEDED is NOT a failure of this cell (the result
    # file is the arbiter). Counting it would overstate `failure_rate`, which gates
    # the pre-registered validity trigger.
    cell_failures = [r for r in _cell_recs if not r.get("resolved")]
    cell_resolved = [r for r in _cell_recs if r.get("resolved")]
    if not results:
        print("no results")
        _fb = _failure_block([], cell_failures, cell_resolved)
        _shout_failures(_fb, 0)
        _patch_failure_manifest(out, _fb, n_failed_this_leg)
        return 0
    summ = _summary(results, args.info, args.exact_k, args.k_dets, args.sims,
                    args.rung_sims, opponent=args.opponent, opp_label=opp_label,
                    opp_k_dets=args.opp_k_dets, opp_sims=args.opp_sims,
                    failures=cell_failures, resolved=cell_resolved)
    json.dump(summ, open(out / "summary.json", "w"), indent=2)
    print(f"[summary.json] wrote {out/'summary.json'}")
    # n_failed / failure_rate / failed_cells into manifest.json too (h2h parity:
    # `close_out` puts the exclusion block in the run manifest). Single-key merges,
    # so a racing --shared-claim peer can at worst lose its own stamp.
    _patch_failure_manifest(out, summ, n_failed_this_leg)
    # END timestamp: the manifest's `utc` is written BEFORE the first game, so a cell's
    # wall-clock span was previously unrecoverable. Single-key merge (never a rewrite),
    # so a racing --shared-claim peer can at worst lose its own stamp.
    patch_manifest(out, "utc_end",
                   datetime.now(timezone.utc).isoformat(timespec="seconds"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
