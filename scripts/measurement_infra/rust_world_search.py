"""Rust backend for the COMPONENT-LIBRARY probes — audit items A2 and A8.

WHY A SEPARATE MODULE.  `BACKEND_BYPASS_AUDIT_20260801.md` §2 classifies
`kwidth_agreement_probe` / `move_agreement_probe` / `gate_b_fair_pimc` /
`adaptive_k_census` as the "component library" shape: they build the champion and
then reach *inside* it — `agent._evaluator`, `agent._c_puct`,
`agent._min_pooled_visits`, `agent.det_seed_base` — and run the per-determinization
searches THEMSELVES.  Their Rust route is therefore not a `backend=` kwarg on the
builder (that hands back a whole PIMC player); it is
``MirrorState`` + ``set_unseen_deck`` + ``search_single``, i.e. the ONE piece those
probes actually borrow from the agent.  `src/carcassonne_ai/rust_agent.py` owns the
two whole-agent adapters and is not the place for a per-world primitive, so it lives
here, next to its only callers.

WHAT MOVES AND WHAT DOES NOT.  This is deliberately the SMALLEST possible seam:

    moves to Rust   ONE determinized world's PUCT search
                    (`fair_agent.search_one_world` -> `MirrorState.search_single`)
    stays in Python  the determinization draw (`FairHeuristicMCTSAgent.
                    reshuffled_determinization` on `random.Random(det_seed_base+1)`),
                    the pooling (`fair_agent._merge_root_stats`) and the decision rule
                    (`fair_agent.pooled_q_argmax`).

Keeping the determinization in Python is not laziness, it is the point.  Both probes'
correctness arguments are written in terms of that ONE rng stream (kwidth's world-prefix
cost trick; adaptive_k's replicate groups drawn from the SAME continuing stream after
the k searched worlds).  `FairAgentRs.determinizations()` builds its own MT19937 per
call and cannot hand the stream back, so using it would silently invalidate the
replicate groups.  Drawing in Python and installing the world with `set_unseen_deck`
preserves every one of those arguments verbatim, and costs one deck shuffle per world
against a 1376-sim search.

Keeping the pooling in Python means the DECISION RULE is literally the same function
object on both backends — the picks can only differ if the SEARCH differs, which is
exactly what the per-script identity gates test.

BIT-EXACTNESS.  `search_single`'s `pooled_stats` is documented (carc-py/src/lib.rs:877)
as *"`fair_agent.root_stats_list` — deduped, N>0, ROOT-POV-signed W"*, with W as a raw
f64 BIT pattern.  Unpacking the bits reproduces the identical double, so a Python merge
over Rust worlds is bit-identical to a Python merge over Python worlds whenever the two
searches agree.  The three gaps of the audit §3 apply and are ENFORCED, not approximated:

  * Gap 1 (no search seed) — CLOSED by `measurement/rustport_p6/GAP1_SEED_INVARIANCE.json`
    (75 cross-seed comparisons, bit-identical at every seed including `None`).  The
    per-world seed `det_seed_base+100+i` these probes pass is therefore genuinely inert;
    it is recorded in the manifest rather than silently dropped.
  * Gap 2 (no `reuse_tree`) — inert here: every per-world search is fresh-tree in the
    Python probes too (a new `NeuralMCTS` per world, `clear()`ed after).
  * Gap 3 (no evaluator injection) — `search_config_rs` raises on any python-only search
    variant (net, gumbel root, ...), so a probe that configures one fails closed.

⚠️ THREADS.  `search_single` has no thread pool; these probes are GAME-PARALLEL farms
(`mp.Pool` at W15/W16), where the documented failure mode is W x t hot threads.  The
per-world searcher is single-threaded by construction and the manifest records
`rust_threads: 1`.  `rust_threads` exists only for the whole-agent parity check, which a
farm never runs at W>1.
"""
from __future__ import annotations

import os
import struct

BACKENDS = ("python", "rust", "auto")

#: Set to "1" to force every probe in this family back onto the Python search without
#: touching a launcher.  Checked AFTER the flag, so it can override a `--backend rust`
#: baked into a running chain script.
FORCE_PYTHON_ENV = "CARC_PROBE_FORCE_PYTHON"


def resolve_backend(name: str) -> str:
    """`{python,rust,auto}` -> `{python,rust}`.  ``auto`` reads PRODUCTION.yaml.

    The escape hatch (`CARC_PROBE_FORCE_PYTHON=1`) wins over everything and says so on
    stderr — a silent downgrade would make a manifest lie about which engine ran.
    """
    import sys

    name = str(name)
    if name not in BACKENDS:
        raise ValueError(f"backend must be one of {BACKENDS}; got {name!r}")
    if os.environ.get(FORCE_PYTHON_ENV) == "1":
        if name != "python":
            print(f"[backend] {FORCE_PYTHON_ENV}=1 overrides --backend {name} -> python",
                  file=sys.stderr, flush=True)
        return "python"
    if name == "auto":
        from carcassonne_ai import champion_factory as CF

        return str(CF.load_production_spec().backend)
    return name


def backend_manifest(backend: str, *, rust_threads: int = 1, extra: dict | None = None) -> dict:
    """The manifest block every converted probe stamps.

    Records WHICH ENGINE RAN (not which one the YAML names) plus the carc_rs build
    fingerprint, so a record set never needs dirname archaeology to interpret.  On the
    Python backend it is a two-key block, so a `--backend python` run stays trivially
    comparable with a pre-conversion one.
    """
    out: dict = {
        "backend": str(backend),
        "backend_resolution": "resolved at launch by rust_world_search.resolve_backend "
                              f"(escape hatch: {FORCE_PYTHON_ENV}=1)",
    }
    if backend == "rust":
        from carcassonne_ai.rust_agent import backend_provenance

        out.update(backend_provenance())
        out["rust_threads"] = int(rust_threads)
        out["threads_note"] = ("per-world search_single is SINGLE-THREADED; these probes "
                               "are game-parallel farms, so rust_threads applies only to "
                               "the whole-agent parity check")
        out["seam"] = ("ONE determinized world's search (fair_agent.search_one_world -> "
                       "MirrorState.search_single). Determinization draw, pooling "
                       "(_merge_root_stats) and decision rule (pooled_q_argmax) stay in "
                       "Python and are the SAME function objects on both backends.")
        out["gap_status"] = {
            "gap1_search_seed": "CLOSED — measurement/rustport_p6/GAP1_SEED_INVARIANCE.json; "
                                "the per-world seed det_seed_base+100+i is inert",
            "gap2_reuse_tree": "inert — every per-world search is fresh-tree on both backends",
            "gap3_evaluator_injection": "enforced — search_config_rs raises on any "
                                        "python-only search variant",
        }
    if extra:
        out.update(extra)
    return out


def _f64(bits) -> float:
    """Raw IEEE-754 bits (as carc_rs emits them) -> the identical Python float."""
    return struct.unpack("<d", struct.pack("<Q", int(bits) & 0xFFFFFFFFFFFFFFFF))[0]


class RustWorldSearcher:
    """`fair_agent.search_one_world`, executed by carc_rs, on a seated mirror.

        ws = RustWorldSearcher(game, cfg, sims=1376, deck_seed=..., prefix=actions[:ply])
        ws.check_sync(board)                 # the mirror really IS at the probe's root
        stats = ws.search_world(det_board)   # [(action, N, W_rootpov)] — root_stats_list

    The mirror is seated by `MirrorState.from_seed(deck_seed)` + `advance` over the
    recorded prefix, which is the byte-equal counterpart of
    `root_replay.replay_actions` (`random.seed(deck_seed); Game().get_init_board()`),
    and `check_sync` proves it rather than assuming it — the same unconditional
    string_representation assert `rust_agent` made non-optional on 2026-08-01.

    `search_world` installs the caller's ALREADY-DETERMINIZED board's deck and searches;
    the mirror's placed board / next_tile / scores are untouched, so one seated mirror
    serves all k worlds of a root (`search_single` takes `&self`).
    """

    def __init__(self, game, cfg, *, sims: int, deck_seed: int, prefix, cfg_rs=None):
        import carc_rs

        from carcassonne_ai.rust_agent import search_config_rs

        self._game = game
        self._sims = int(sims)
        self._scfg = cfg_rs if cfg_rs is not None else search_config_rs(cfg, self._sims)
        self._ms = carc_rs.MirrorState.from_seed(str(int(deck_seed)))
        self._plies = 0
        for a in prefix:
            self._ms.advance(int(a))
            self._plies += 1
        self.searches = 0

    def check_sync(self, board, where: str = "seat") -> None:
        """Hard-assert the mirror equals `board` (byte-exact node key, the G1 surface)."""
        from carcassonne_ai.rust_agent import MirrorDesync

        want = self._game.string_representation(board)
        got = self._ms.string_repr()
        if want != got:
            raise MirrorDesync(
                f"rust world-searcher mirror desync at {where} (ply {self._plies})\n"
                f"  python: {want[:400]}\n  rust  : {got[:400]}")

    def unseen_deck(self) -> list:
        return list(self._ms.unseen_deck())

    def search_world(self, det_board) -> list:
        """ONE determinized world's search.  Returns `root_stats_list` shape.

        `det_board` is whatever `FairHeuristicMCTSAgent.reshuffled_determinization`
        produced: same placed board, same `next_tile`, permuted unseen deck.  Only the
        deck is read off it — the mirror supplies the position, which is what makes the
        `check_sync` above load-bearing.
        """
        self._ms.set_unseen_deck([t.description for t in det_board.state.deck])
        res = self._ms.search_single(self._scfg)
        self.searches += 1
        return [(int(a), int(n), _f64(w)) for a, n, w in res["pooled_stats"]]

    def search_world_full(self, det_board) -> dict:
        """`search_world` plus the rest of the raw surface (root N/W bits, children,
        priors) — what an identity gate compares."""
        self._ms.set_unseen_deck([t.description for t in det_board.state.deck])
        res = self._ms.search_single(self._scfg)
        self.searches += 1
        return dict(res)
