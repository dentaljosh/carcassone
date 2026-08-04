"""F13 exact-K tail machinery: per-arm K, per-solve WALL caps, downward fallback.

Prereg of record: measurement/exact_k_ladder_20260803/PREREG_DRAFT.md.

WHAT THIS ADDS (the three things the June-era exact ladder lacked)
-----------------------------------------------------------------
1. **Per-arm tail K.** Already structurally present in `eval_puct_priors._play_one`
   (`K` / `opp_K`), but only ever used to set a bare-net arm to 0. The harness now
   exposes `--opp-exact-k` so the candidate can run the rung's K against a K=4
   incumbent. Nothing here is needed for that beyond the counters.

2. **A per-solve WALL cap** (`--exact-wall-caps "5:300,6:600"`). The cap is keyed on
   the SOLVE SIZE (`k_remaining` at the solved position), not on the arm's nominal K —
   that is the only reading under which "K<=4 uncapped, K5 300 s, K6 600 s" is a
   statement about cost. Both arms carry the same map; the K<=4 incumbent simply never
   reaches a capped size, so the map is inert on its side.

3. **A downward fallback ladder on cap hit** (see `ExactTailState` below).

WHY FORK+SIGKILL IS THE WALL-CAP MECHANISM (and why it is state-safe)
--------------------------------------------------------------------
`carc_rs.MirrorState.solve_endgame` has **no** timeout/deadline/cancel parameter — the
only interruption inside `rust/carc/carc-core/src/endgame/mod.rs` is the NODE counter
(`if self.nodes > self.cfg.budget`), and `wall_ms` is measured by the pyo3 binding purely
for reporting. Worse, the solve runs under `py.allow_threads`, so a Python `SIGALRM`
handler cannot run until the FFI call has already returned: SIGALRM (the pattern used by
`run_oracle.py` / `gate_b_fair_pimc.py` around the *Python* solver) is structurally
incapable of capping a Rust solve. The three options were (a) add a deadline field to
`endgame::Config` and check it beside the node counter — a Rust core change plus a wheel
rebuild, i.e. a new bit-exactness surface on a measurement run; (b) node budget as a wall
proxy — but the pre-registered cap is in SECONDS and the nodes/second rate is not constant
across positions; (c) fork the solve into a child and have the parent SIGKILL it at the
deadline — the pattern `scripts/rustport/bench_exact_solver.py:175-226` already uses for
exactly this reason. We take (c).

It is state-safe by construction:
  * `solve_endgame` takes `&self` (`rust/carc/carc-py/src/lib.rs:553`) and
    `endgame_solver.solve` never mutates the board it is handed — the solve is a PURE
    FUNCTION of the position, so a killed attempt has no result to lose.
  * every byte the solve touches lives in the CHILD's copy-on-write address space. The
    parent's `MirrorState`, `Board` and RNG are physically unreachable from the child.
  * the parent only ever consumes a length-prefixed, fully-received JSON payload. A
    SIGKILLed child contributes NOTHING — there is no partial-write path into the
    parent's state, and no "corrupt on cap" case to reason about.
  * the child ends with `os._exit()`, so it runs no atexit hooks, flushes no inherited
    buffers, and cannot touch the shared-claim files or the per-game result JSON.

Cost: one fork per CAPPED solve only. `wall_cap_call` runs the solve INLINE when no cap
applies, so the K<=4 production tail is byte-identical to the pre-F13 path (this is what
makes the K4-vs-K4 identity smoke meaningful).
"""

from __future__ import annotations

import json
import os
import select
import signal
import time

# Pre-registered caps (PREREG_DRAFT.md "The cap-hit branch"): K<=4 uncapped,
# K=5 300 s, K=6 600 s. A CLI/config map, never hardcoded at a call site.
DEFAULT_WALL_CAPS: dict[int, float] = {5: 300.0, 6: 600.0}

# Pre-registered censoring rule: ">20% of a rung's latch solves cap out" => the rung
# reports "censored at rate r" and carries a not-a-verdict banner regardless of z.
CENSOR_THRESHOLD = 0.20


class WallCapExceeded(Exception):
    """A single exact solve hit its pre-registered per-solve wall cap."""

    def __init__(self, cap_secs: float, k: int | None = None):
        self.cap_secs = float(cap_secs)
        self.k = k
        super().__init__(f"exact solve exceeded wall cap {cap_secs:g}s"
                         + (f" at k_remaining={k}" if k is not None else ""))


class ChildSolveFailed(Exception):
    """The forked solve child died for a reason that is NOT the wall cap."""


# --------------------------------------------------------------------------- #
# cap map                                                                      #
# --------------------------------------------------------------------------- #
def parse_wall_caps(spec: str | None) -> dict[int, float]:
    """Parse ``"5:300,6:600"`` -> ``{5: 300.0, 6: 600.0}``.

    ``None``/``""`` -> ``{}`` (no cap anywhere == the pre-F13 behaviour).
    ``"default"`` -> :data:`DEFAULT_WALL_CAPS`. A cap of ``0`` means "uncapped at
    this K" and is dropped, so ``"5:0"`` explicitly un-caps K=5 without deleting
    the flag. Raises ``ValueError`` on anything malformed — a mistyped cap must not
    silently become "no cap" on an overnight rung.
    """
    if spec is None:
        return {}
    spec = str(spec).strip()
    if not spec:
        return {}
    if spec == "default":
        return dict(DEFAULT_WALL_CAPS)
    caps: dict[int, float] = {}
    for tok in spec.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if ":" not in tok:
            raise ValueError(f"bad wall-cap token {tok!r} (want 'K:SECS', e.g. '5:300')")
        ks, vs = tok.split(":", 1)
        try:
            k = int(ks.strip())
            v = float(vs.strip())
        except ValueError as e:
            raise ValueError(f"bad wall-cap token {tok!r} (want 'K:SECS')") from e
        if k < 0:
            raise ValueError(f"bad wall-cap K={k} (must be >= 0)")
        if v < 0:
            raise ValueError(f"bad wall-cap secs={v} for K={k} (must be >= 0)")
        if v > 0:
            caps[k] = v
    return caps


def cap_for(caps: dict[int, float] | None, k: int) -> float | None:
    """The wall cap that applies to a solve of `k` remaining tiles (None = uncapped)."""
    if not caps:
        return None
    return caps.get(int(k))


def fmt_wall_caps(caps: dict[int, float] | None) -> str:
    """Round-trip a cap map back to the CLI spelling (stable key order)."""
    if not caps:
        return ""
    return ",".join(f"{k}:{caps[k]:g}" for k in sorted(caps))


# --------------------------------------------------------------------------- #
# the wall cap itself                                                          #
# --------------------------------------------------------------------------- #
def wall_cap_call(fn, cap_secs: float | None, *, k: int | None = None,
                  poll_secs: float = 1.0):
    """Run ``fn()`` under a per-call wall cap; raise :class:`WallCapExceeded` on cap.

    ``fn`` must be a **pure function of the position** returning a JSON-serialisable
    value (the module docstring explains why that is the load-bearing precondition).

    ``cap_secs is None`` (or <= 0) runs ``fn()`` INLINE in this process — no fork, no
    pipe, no behaviour change at all. That is the K<=4 production path.

    Otherwise ``fn()`` runs in a forked child that writes ``json.dumps`` of its result
    to a pipe and ``os._exit(0)``s. The parent reads with a deadline and, on expiry,
    ``SIGKILL``s the child and reaps it. Nothing the child did can reach the parent.
    """
    if cap_secs is None or cap_secs <= 0:
        return fn()

    rfd, wfd = os.pipe()
    pid = os.fork()
    if pid == 0:                                    # ---- child ----
        # NOTHING in here may touch shared state: no result files, no claim files, no
        # atexit hooks (os._exit, not sys.exit). Failures are reported as a payload.
        try:
            os.close(rfd)
            try:
                payload = {"ok": True, "value": fn()}
            except BaseException as e:              # noqa: BLE001 - reported, not swallowed
                payload = {"ok": False, "exc": type(e).__name__, "msg": str(e)[:400]}
            buf = json.dumps(payload).encode()
            os.write(wfd, len(buf).to_bytes(8, "big") + buf)
            os.close(wfd)
        finally:
            os._exit(0)

    # ---- parent ----
    os.close(wfd)
    deadline = time.monotonic() + float(cap_secs)
    chunks: list[bytes] = []
    killed = False
    try:
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                killed = True
                break
            try:
                ready, _, _ = select.select([rfd], [], [], min(left, poll_secs))
            except InterruptedError:                # pragma: no cover - EINTR retry
                continue
            if not ready:
                continue
            b = os.read(rfd, 1 << 16)
            if not b:                               # child closed the pipe == done
                break
            chunks.append(b)
    finally:
        os.close(rfd)
        if killed:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:              # pragma: no cover - raced to exit
                pass
        try:
            os.waitpid(pid, 0)
        except ChildProcessError:                   # pragma: no cover
            pass

    if killed:
        raise WallCapExceeded(cap_secs, k)

    raw = b"".join(chunks)
    if len(raw) < 8:
        raise ChildSolveFailed(f"solve child produced {len(raw)} bytes (no payload)")
    n = int.from_bytes(raw[:8], "big")
    body = raw[8:8 + n]
    if len(body) != n:
        # Truncated => the child died mid-write. Treat as a failure, never as a result.
        raise ChildSolveFailed(f"solve child payload truncated ({len(body)}/{n} bytes)")
    payload = json.loads(body.decode())
    if not payload.get("ok"):
        raise ChildSolveFailed(f"{payload.get('exc')}: {payload.get('msg')}")
    return payload["value"]


# --------------------------------------------------------------------------- #
# the fallback ladder                                                          #
# --------------------------------------------------------------------------- #
class ExactTailState:
    """Per-arm, per-game tail state: effective K, cap-hit counters, fallback depth.

    ⚠️ HOW THE FALLBACK IS IMPLEMENTED, AND WHY IT IS NOT LITERALLY
    "the K-1 solve of the same position" (flagged, not improvised around):

    Neither solver has a DEPTH LIMIT. `endgame_solver.solve` and
    `carc_rs.MirrorState.solve_endgame` both solve the handed position to the end of
    the game; K is purely a LATCH THRESHOLD in the caller, never an argument to the
    solve (`endgame_solver.solve(game, board, mode, budget, alphabeta)` has no K, and
    `endgame::Config` carries only budget/tt_cap/alphabeta/chance_drop). So a "K-1
    solve of the same position" is not a constructible object — the only shallower
    exact solve of a position with `k` tiles left is the solve of the position one ply
    LATER, which has `k-1`.

    The faithful implementation of the prereg's INTENT ("the arm degrades toward the
    incumbent, biasing the measured effect toward ZERO") is therefore a downward
    threshold ladder:

        cap hit while solving a position with `k` remaining
          -> effective tail K drops to `k-1` (floored at `k_floor`, the incumbent K)
          -> the PREFIX SEARCH plays this ply — i.e. exactly what the K-1 arm would
             have done at this position; never a raw leaf
          -> next ply has `k-1` remaining, is <= the new threshold, and is solved
             (at the K-1 cap, which is smaller, so the recursion is monotone).

    If THAT solve also caps, the same rule fires again — this is the "recurse downward"
    clause, realised across plies rather than within one move (it cannot be within one
    move: there is no smaller solve of the same position). The ladder terminates at
    `k_floor`; with the pre-registered caps it terminates at k=4 anyway, since K<=4 is
    uncapped and can never cap out.
    """

    def __init__(self, k: int, *, caps: dict[int, float] | None = None,
                 k_floor: int = 0):
        self.k0 = int(k)               # the rung: the arm's NOMINAL tail K
        self.eff_k = int(k)            # the arm's CURRENT tail threshold (only decreases)
        self.k_floor = int(k_floor)
        self.caps = dict(caps or {})
        self.latch_solves = 0          # every exact-solve ATTEMPT made while latched
        self.capped_attempts = 0       # ... of which a wall cap applied to
        self.cap_hits = 0              # ... of which hit the cap
        self.cap_hits_by_k: dict[int, int] = {}
        self.fallback_depth = 0        # how many times eff_k stepped down

    # -- accounting ---------------------------------------------------------- #
    def note_attempt(self, k: int) -> float | None:
        """Record a solve attempt at size `k`; return the cap that applies (or None)."""
        self.latch_solves += 1
        cap = cap_for(self.caps, k)
        if cap is not None:
            self.capped_attempts += 1
        return cap

    def note_cap_hit(self, k: int) -> None:
        """Record a cap hit at size `k` and step the threshold DOWN (the ladder)."""
        k = int(k)
        self.cap_hits += 1
        self.cap_hits_by_k[k] = self.cap_hits_by_k.get(k, 0) + 1
        new_k = max(self.k_floor, k - 1)
        if new_k < self.eff_k:
            self.fallback_depth += 1
            self.eff_k = new_k

    def as_dict(self) -> dict:
        return {"exact_k": self.k0, "eff_k_final": self.eff_k, "k_floor": self.k_floor,
                "latch_solves": self.latch_solves,
                "capped_attempts": self.capped_attempts,
                "cap_hits": self.cap_hits,
                "cap_hits_by_k": dict(sorted(self.cap_hits_by_k.items())),
                "fallback_depth": self.fallback_depth}


# --------------------------------------------------------------------------- #
# censoring                                                                    #
# --------------------------------------------------------------------------- #
def censored_rate(cap_hits: int, latch_solves: int) -> float:
    """The PRE-REGISTERED censoring statistic: cap hits / latch solves.

    The prereg's words are "if >20% of a rung's latch solves cap out", so the
    denominator is every exact-solve attempt made while latched — NOT just the ones a
    cap applied to. `censored_rate_capped` below is the (larger, more diagnostic)
    conditional rate; it is reported alongside but does NOT redefine the trigger.
    """
    latch_solves = int(latch_solves)
    if latch_solves <= 0:
        return 0.0
    return int(cap_hits) / latch_solves


def censored_rate_capped(cap_hits: int, capped_attempts: int) -> float:
    """Diagnostic: cap hits / attempts that a cap actually applied to."""
    capped_attempts = int(capped_attempts)
    if capped_attempts <= 0:
        return 0.0
    return int(cap_hits) / capped_attempts


def is_censored(rate: float, threshold: float = CENSOR_THRESHOLD) -> bool:
    """True iff the rung must carry the not-a-verdict banner (>20%, strictly)."""
    return float(rate) > float(threshold)


def censoring_block(cand: dict, champ: dict,
                    threshold: float = CENSOR_THRESHOLD) -> dict:
    """Per-cell censoring summary from the two arms' aggregated counter dicts.

    The trigger is evaluated on the CANDIDATE arm — it is the only side whose tail K
    the ladder moves; the incumbent's K<=4 tail is uncapped by construction, and its
    counters are carried only so a nonzero value is visible as an instrument alarm.
    """
    rate = censored_rate(cand.get("cap_hits", 0), cand.get("latch_solves", 0))
    return {
        "threshold": threshold,
        "candidate": dict(cand),
        "opponent": dict(champ),
        "censored_rate": rate,
        "censored_rate_capped": censored_rate_capped(
            cand.get("cap_hits", 0), cand.get("capped_attempts", 0)),
        "censored": is_censored(rate, threshold),
        "banner": ("⚠️ CENSORED at rate %.3f (>%.2f of latch solves capped out) — "
                   "NOT A VERDICT regardless of z; prereg decision map branch 3 "
                   "(raise caps x3 on this rung, n=200 re-run)." % (rate, threshold)
                   if is_censored(rate, threshold) else ""),
        "opponent_cap_hits_alarm": bool(champ.get("cap_hits", 0)),
    }
