"""Runtime-verified evaluator provenance for the clean-eval ruler.

Motivated by the 2026-06-07 outside-review findings:
  R1  the strength yardstick (HeuristicMCTS) silently ran the **v1** leaf while
      the agent ran **v2.7** — the manifests could not have caught it because
      they recorded *labels*, not the function that actually executed.
  R7  a residual eval (residual_scale>0) could silently fall back to the pure
      v2.7 policy-only path (v_nn never consumed) and still look like a
      "residual" run in the dirname.

This module makes that class of defect impossible to miss:

  * `EvaluatorSpec` captures the FULL effective config of one side of a matchup
    (agent class, search impl, leaf name+version, policy source, checkpoint path
    + SHA256, code commit + dirty, sims, exploration constants, FPU, residual
    scale, value blend, caps, seed range, paired/unpaired, eval script + argv).
  * `build_eval_provenance` assembles both sides into the manifest `evaluator`
    block (see run_manifest.write_manifest(evaluator=...)).
  * `assert_provenance_consistent` cross-checks the SPEC against the RUNTIME
    counters (`_RuntimeCounters` on the leaf wrapper / `HeuristicMCTS.counters`)
    and raises `ProvenanceError` when the claimed leaf/value path is not the one
    that ran. This is the runtime proof the reviewers asked for — wired into the
    `--provenance-smoke` single-process path of the eval scripts (a Pool cannot
    aggregate per-worker counters, so the smoke owns the one process).
  * Seed-namespace guard (`assert_clean_eval_seed_range`) refuses an eval whose
    seed window overlaps the self-play deck namespace (R3/A9 train/test leak).

No new third-party dependency: `validate_evaluator_block` is a no-op when
`jsonschema` is not importable (the cluster boxes have no DNS to install it).
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

SCHEMA_ID = "carcassonne-evaluator-provenance/v1"

# --- Seed namespaces -------------------------------------------------------
# Self-play seeds are `iter*10_000 + game_idx`; for any realistic iter count
# (< ~100k) those live below 1e9. A clean eval must draw decks from ABOVE that
# ceiling so it can never replay a deck the net trained on (outside-review A9).
SELFPLAY_SEED_CEILING = 1_000_000_000
EVAL_SEED_FLOOR = 1_000_000_000


class ProvenanceError(AssertionError):
    """Raised when an eval's CLAIMED config disagrees with what actually ran
    (wrong leaf executed, residual path never fired, seed namespace overlap)."""


# --- File / git provenance helpers ----------------------------------------

def deck_hash(board) -> str:
    """Stable 16-hex identity of a game's shuffled deck, computed at init (before
    any tile is drawn). Lets a results row prove which deck it played and lets us
    detect overlap with trained-on self-play decks (outside-review A9)."""
    descs = tuple(t.description for t in board.state.deck)
    return hashlib.sha256(repr(descs).encode()).hexdigest()[:16]


def sha256_file(path) -> str | None:
    """Streamed SHA256 of a file, or None if the path is falsy / missing."""
    if not path:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit_and_dirty(repo: Path | None = None) -> tuple[str, bool]:
    """Return (full_commit_sha, dirty?). ('unknown', True) if git is unavailable
    — an unknown tree is treated as dirty so a row can never claim a clean
    commit it was not actually run at."""
    if repo is None:
        repo = Path(__file__).resolve().parents[2]
    try:
        sha = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if sha.returncode != 0 or not sha.stdout.strip():
            return "unknown", True
        full = sha.stdout.strip()
        porcelain = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        return full, bool(porcelain)
    except Exception:
        return "unknown", True


# --- Evaluator spec --------------------------------------------------------

@dataclass(frozen=True)
class EvaluatorSpec:
    """The full, resolved configuration of ONE side of an eval matchup.

    Every field a reviewer needs to know "exactly what played" is here, recorded
    from the live objects (not inferred from a label). `leaf_name`/`leaf_version`
    are the leaf evaluator that actually executes at every MCTS leaf; for the
    neural side that is the v2.7 wrapper (`make_v25_value_wrapper`), for the
    HeuristicMCTS opponent it is `mcts.leaf_name` ('v1' or 'v2_7')."""

    side: str                       # "A"/"B" or a role label
    agent_class: str                # e.g. "NeuralMCTS", "HeuristicMCTS"
    search_impl: str                # concrete search implementation class
    leaf_name: str                  # "v1" | "v2_7" | "v2_5" | "nn"
    leaf_version: str | None        # "1.0" | "2.7" | None
    policy_source: str              # "network" | "uniform" | "none"
    sims: int
    # exploration / value-path knobs
    c_puct: float | None = None
    fpu: float | None = None
    residual_scale: float = 0.0
    value_blend: float = 0.0
    cap: float | None = None
    opp_cap: float | None = None
    drop_three_open: bool | None = None
    closure_schedule: dict | None = None
    # checkpoint / code provenance
    checkpoint_path: str | None = None
    checkpoint_sha256: str | None = None
    code_commit: str = "unknown"
    dirty: bool = True
    # run context
    seed_range: list | None = None  # [start, end) inclusive-exclusive
    paired: bool | None = None
    eval_script: str | None = None
    argv: list | None = None

    def to_json(self) -> dict:
        d = dataclasses.asdict(self)
        # JSON keys are strings; keep closure_schedule keys round-trippable.
        if self.closure_schedule is not None:
            d["closure_schedule"] = {str(k): v for k, v in self.closure_schedule.items()}
        return d


def _leaf_cfg_fields(leaf_cfg) -> dict:
    """Pull the provenance-relevant fields off a LeafConfig (duck-typed)."""
    if leaf_cfg is None:
        return {}
    sched = getattr(leaf_cfg, "closure_p", None)
    drop_three = None
    if isinstance(sched, dict):
        drop_three = 3 not in sched and set(sched.keys()) == {1, 2}
    return {
        "cap": getattr(leaf_cfg, "bonus_cap", None),
        "opp_cap": getattr(leaf_cfg, "opp_bonus_cap", None),
        "residual_scale": float(getattr(leaf_cfg, "residual_scale", 0.0) or 0.0),
        "value_blend": float(getattr(leaf_cfg, "value_blend", 0.0) or 0.0),
        "drop_three_open": drop_three,
        "closure_schedule": dict(sched) if isinstance(sched, dict) else None,
    }


def spec_from_neural_mcts(
    mcts, *, side: str, checkpoint_path=None, sims: int | None = None,
    paired: bool | None = None, seed_range=None, eval_script=None, argv=None,
    policy_source: str = "network",
) -> EvaluatorSpec:
    """Build an EvaluatorSpec from a live NeuralMCTS + its v2.7-wrapped evaluator.

    Reads the leaf config / residual / blend off `mcts.evaluator.leaf_cfg` (the
    `_V25Wrapped` instance), so the recorded leaf is the one that will execute,
    not a label."""
    evaluator = getattr(mcts, "evaluator", None)
    leaf_cfg = getattr(evaluator, "leaf_cfg", None)
    policy_only = bool(getattr(evaluator, "policy_only", False))
    cfg_fields = _leaf_cfg_fields(leaf_cfg)
    commit, dirty = git_commit_and_dirty()
    # leaf the agent's MCTS evaluates with: the v2.7 wrapper unless it's a bare
    # policy-only evaluator (no leaf value computed).
    if leaf_cfg is not None:
        leaf_name, leaf_version = "v2_7", "2.7"
    elif policy_only:
        leaf_name, leaf_version = "none", None
    else:
        leaf_name, leaf_version = "nn", None
    return EvaluatorSpec(
        side=side,
        agent_class=type(mcts).__name__,
        search_impl=type(mcts).__name__,
        leaf_name=leaf_name,
        leaf_version=leaf_version,
        policy_source="none" if policy_only else policy_source,
        sims=int(sims if sims is not None else getattr(mcts, "simulations", 0)),
        c_puct=_as_float(getattr(mcts, "c_puct", getattr(mcts, "c", None))),
        fpu=_as_float(getattr(mcts, "fpu_reduction", None)),
        residual_scale=cfg_fields.get("residual_scale", 0.0),
        value_blend=cfg_fields.get("value_blend", 0.0),
        cap=cfg_fields.get("cap"),
        opp_cap=cfg_fields.get("opp_cap"),
        drop_three_open=cfg_fields.get("drop_three_open"),
        closure_schedule=cfg_fields.get("closure_schedule"),
        checkpoint_path=str(checkpoint_path) if checkpoint_path else None,
        checkpoint_sha256=sha256_file(checkpoint_path),
        code_commit=commit,
        dirty=dirty,
        seed_range=list(seed_range) if seed_range is not None else None,
        paired=paired,
        eval_script=eval_script,
        argv=list(argv) if argv is not None else None,
    )


def spec_from_heuristic_mcts(
    mcts, *, side: str, sims: int | None = None, paired: bool | None = None,
    seed_range=None, eval_script=None, argv=None,
) -> EvaluatorSpec:
    """Build an EvaluatorSpec from a live HeuristicMCTS opponent. The leaf is read
    from `mcts.leaf_name` ('v1' or 'v2_7') — the field whose mismatch was R1."""
    leaf_name = getattr(mcts, "leaf_name", "v1")
    leaf_version = {"v1": "1.0", "v2_7": "2.7", "v2_5": "2.5"}.get(leaf_name)
    commit, dirty = git_commit_and_dirty()
    # The v2.7 opponent leaf uses the same env-built DEFAULT_CONFIG as the agent.
    cap = opp_cap = drop_three = sched = None
    if leaf_name == "v2_7":
        try:
            from .virtual_score_v2 import DEFAULT_CONFIG
            f = _leaf_cfg_fields(DEFAULT_CONFIG)
            cap, opp_cap = f.get("cap"), f.get("opp_cap")
            drop_three, sched = f.get("drop_three_open"), f.get("closure_schedule")
        except Exception:
            pass
    return EvaluatorSpec(
        side=side,
        agent_class=type(mcts).__name__,
        search_impl=type(mcts).__name__,
        leaf_name=leaf_name,
        leaf_version=leaf_version,
        policy_source="none",  # HeuristicMCTS has no learned policy
        sims=int(sims if sims is not None else getattr(mcts, "simulations", 0)),
        c_puct=_as_float(getattr(mcts, "c_puct", getattr(mcts, "c", None))),
        fpu=None,
        cap=cap,
        opp_cap=opp_cap,
        drop_three_open=drop_three,
        closure_schedule=sched,
        checkpoint_path=None,
        checkpoint_sha256=None,
        code_commit=commit,
        dirty=dirty,
        seed_range=list(seed_range) if seed_range is not None else None,
        paired=paired,
        eval_script=eval_script,
        argv=list(argv) if argv is not None else None,
    )


def _as_float(x):
    return None if x is None else float(x)


def build_eval_provenance(specs, *, kind: str, argv=None, runtime_verified=None) -> dict:
    """Assemble the manifest `evaluator` block from both-sides EvaluatorSpecs.

    `runtime_verified` (optional dict): the result of the `--provenance-smoke`
    counter check — {"ok": bool, "counters": {...}, "checked": [...]}. Absent for
    a Pool run that did not run the smoke (the smoke is the runtime proof)."""
    commit, dirty = git_commit_and_dirty()
    block = {
        "schema": SCHEMA_ID,
        "kind": kind,
        "code_commit": commit,
        "dirty": dirty,
        "argv": list(argv) if argv is not None else None,
        "sides": [s.to_json() for s in specs],
        "runtime_verified": runtime_verified,
    }
    return block


# --- Runtime consistency assertions (the two reviewer checks) --------------

def _counter_get(counters: dict, *names, default=0):
    for n in names:
        if n in counters:
            return counters[n]
    return default


def assert_provenance_consistent(specs, counters_by_side: dict) -> dict:
    """Cross-check each side's SPEC against the leaf-path counters that actually
    ran. Raises ProvenanceError on any mismatch. Returns a summary dict.

    `counters_by_side`: {side_label: counters_dict}. Neural-side counters come
    from `_RuntimeCounters.as_dict()` (keys v25_calls/resid_path/blend_path/
    plain_path/net_value_path); HeuristicMCTS counters from `mcts.counters`
    (keys v1_calls/v2_7_calls).

    Checks:
      (a) leaf identity — a side claiming 'v2_7' must have run the v2.7 path and
          NOT v1 (and vice-versa). This is the R1 guard.
      (b) residual_scale>0 ⇒ the net-value residual path actually executed
          (R7 guard); residual==0 and value_blend==0 ⇒ NO net-value path ran
          (no silent leakage of the value head into a "pure heuristic" run).
    """
    checked = []
    for spec in specs:
        c = counters_by_side.get(spec.side)
        if c is None:
            # No counters captured for this side (e.g. its leaf is not
            # instrumented). Skip — absence is not a contradiction.
            continue
        is_heuristic = "v1_calls" in c or "v2_7_calls" in c
        is_neural = "v25_calls" in c

        if is_heuristic:
            v1 = _counter_get(c, "v1_calls")
            v27 = _counter_get(c, "v2_7_calls")
            if spec.leaf_name == "v2_7":
                if not (v27 > 0 and v1 == 0):
                    raise ProvenanceError(
                        f"side {spec.side!r} claims leaf v2_7 but ran "
                        f"v1_calls={v1}, v2_7_calls={v27} (expected v2_7>0, v1==0)")
            elif spec.leaf_name == "v1":
                if not (v1 > 0 and v27 == 0):
                    raise ProvenanceError(
                        f"side {spec.side!r} claims leaf v1 but ran "
                        f"v1_calls={v1}, v2_7_calls={v27} (expected v1>0, v2_7==0)")
            checked.append({"side": spec.side, "leaf": spec.leaf_name,
                            "v1_calls": v1, "v2_7_calls": v27})

        elif is_neural:
            v25 = _counter_get(c, "v25_calls")
            resid = _counter_get(c, "resid_path")
            blend = _counter_get(c, "blend_path")
            net_path = _counter_get(c, "net_value_path", default=resid + blend)
            if spec.leaf_name == "v2_7" and v25 <= 0:
                raise ProvenanceError(
                    f"side {spec.side!r} claims leaf v2_7 but v25_calls={v25} "
                    f"(the wrapped leaf never executed)")
            if spec.residual_scale > 0.0:
                if resid <= 0:
                    raise ProvenanceError(
                        f"side {spec.side!r} sets residual_scale="
                        f"{spec.residual_scale} but resid_path={resid} — the "
                        f"net-value residual never fired (R7 silent fallback)")
            elif spec.value_blend > 0.0:
                if blend <= 0:
                    raise ProvenanceError(
                        f"side {spec.side!r} sets value_blend={spec.value_blend} "
                        f"but blend_path={blend} — the value head was never blended")
            else:
                # pure heuristic leaf — no net-value path may have leaked in.
                if net_path > 0:
                    raise ProvenanceError(
                        f"side {spec.side!r} claims pure v2.7 (residual=0, blend=0) "
                        f"but net_value_path={net_path} — value head leaked in")
            checked.append({"side": spec.side, "leaf": spec.leaf_name,
                            "v25_calls": v25, "resid_path": resid,
                            "blend_path": blend, "net_value_path": net_path})

    return {"ok": True, "checked": checked, "counters": counters_by_side}


# --- Seed namespace guard --------------------------------------------------

def assert_clean_eval_seed_range(seed_start: int, n: int) -> None:
    """Raise ProvenanceError if [seed_start, seed_start+n) intersects the
    self-play seed namespace [0, SELFPLAY_SEED_CEILING). A clean eval must draw
    its decks from above the floor so it can never replay a trained-on deck."""
    if seed_start < EVAL_SEED_FLOOR:
        raise ProvenanceError(
            f"--seed-start {seed_start} is below the clean-eval floor "
            f"{EVAL_SEED_FLOOR} (overlaps the self-play deck namespace "
            f"[0,{SELFPLAY_SEED_CEILING})). Use --seed-start {EVAL_SEED_FLOOR} "
            f"or higher for a contamination-free eval (override only if you "
            f"explicitly want deck-comparability with an old run).")
    # [seed_start, seed_start+n) is fully above the ceiling iff seed_start >= it.


# --- Optional schema validation (no hard dep) ------------------------------

def validate_evaluator_block(block: dict) -> bool:
    """Validate `block` against EVALUATOR_SCHEMA.json if `jsonschema` is
    importable; otherwise a structural no-op that returns True. Never raises on a
    missing dependency (the cluster boxes are offline)."""
    schema_path = Path(__file__).resolve().parent / "schemas" / "EVALUATOR_SCHEMA.json"
    try:
        import jsonschema  # type: ignore
    except Exception:
        return True
    if not schema_path.is_file():
        return True
    schema = json.loads(schema_path.read_text())
    jsonschema.validate(block, schema)
    return True
