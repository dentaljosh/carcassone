"""On-device battery A/B bench workload — DEBUG BUILDS ONLY.

This module ships only in the debug APK (it lives in ``src/debug/python``, a
Chaquopy debug-sourceset dir) and is called only by the debug-sourceset
``BenchService``. Release builds contain neither.

WHAT IT DOES. Runs N champion decisions headlessly, back-to-back, from a fixed
seeded position stream, timing each decision, and writes one self-describing
JSON result. The host-side driver (``android/tools/battery_bench.sh``) samples
battery current/voltage over the same window and integrates joules; this module
is the workload half plus the *identity witness* (``move_hash``) that proves two
arms did byte-identical work.

WHY THE WORK IS IDENTICAL ACROSS ``rust_threads`` ARMS. The rust search folds
its k determinization worlds deterministically at any thread count
(``rust/carc/carc-core/src/fair/mod.rs::search_worlds`` + its
``thread_count_invariance`` test; re-confirmed by the battery-audit worktree
report at commit 7ae0d742). So two arms started from the same (seed, budget,
rules) play the same moves, and ``move_hash`` — a digest over the full applied
action trace plus the resolved budget and rules profile — must be equal. The
driver ABORTS rather than print energy numbers if it is not.

WHY IT IS ALSO IDENTICAL ACROSS **TIE-ARBITER** ARMS (added 2026-08-17 for the
on-device arbiter A/B, ``measurement/pixel_tiearb_ab_*``). The arbiter
(``carc-core/src/tiearb.rs``, armed by the ``tiearb_*`` SearchConfig knobs)
**changes the returned action at tied plies BY DESIGN**, so a free-running armed
arm would diverge from the champion after the first pick-change and the identity
gate above would — correctly — abort. This module therefore drives the
**CHAMPION TRAJECTORY** in every arm: after each decision it applies
``last_move()["tiearb_champ_pick"]`` (the champion's own ``pooled_q_argmax``
pick, which the rust side records precisely because it is the pick-change
baseline) rather than the arbiter's answer. The armed arm still *does all the
arbitration work* — the tie detector, the CRN world set, the B×arms tier-1
playouts — at exactly the positions the champion line visits, which is the work
whose seconds and joules are being priced; only the action fed back into the
game comes from the champion. Consequences, stated plainly:

  * the ``move_hash`` gate survives AT FULL STRENGTH — every arm walks the same
    positions, so a mismatch still means the arms did different work;
  * per-move energy/latency is comparable POSITION FOR POSITION, and the
    per-fired-ply cost is read off ``tiearb_secs`` directly;
  * this is a COST measurement, not a strength one. It prices arbitration along
    the champion trajectory — the same trajectory family the desktop firing rate
    ``phi`` was measured on — and says nothing about what the arbiter's picks
    are worth. Nothing here may be read as deploy evidence.

The arbiter neither consumes nor perturbs the agent's search RNG (it seeds its
common-random-numbers off ``salt`` + state digest + ply and works in a dedicated
``tiearb_scratch``), so the champion's own decisions along that trajectory are
bit-identical armed or not — which the hash gate then proves rather than
assumes.

WHAT IT NEVER TOUCHES:
  * the live app session (``android_bridge._S``) — a private ``_Session`` is
    constructed directly, never installed;
  * the autosave / finished-game archive (``files/current_game.json``,
    ``files/games/``) — those are written by Kotlin (SaveStore/ArchiveStore)
    for real games only; this module refuses an out_dir named ``games``;
  * governance — ``rust_threads`` is overridden on the constructed session
    object AFTER the normal YAML resolution ran; PRODUCTION.yaml is read (by
    the ordinary ``_build_opponent`` path) and never written.

Reuse contract: ``android_bridge._Session`` is used read-only — the subclass
below overrides nothing about seeding, ``_move_idx``, budget resolution or the
mirror protocol; it only replaces the session's resolved ``rust_threads`` value
with the bench arm's, which ``_Session._start_rust_mirror`` then passes to
``carc_rs.FairAgentRs(threads=...)`` exactly as it would the YAML value.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import traceback

import android_bridge as B

SCHEMA = "carc-battery-bench/v1"
# How the trajectory is driven. "champion_trajectory" == every arm applies the
# champion's own pooled_q_argmax pick, so the arbiter's work is priced without
# its pick-changes moving the board (module doc). In the digest.
REPLAY_POLICY = "champion_trajectory"

# The tie-arbiter settings of record (carc-core/src/tiearb.rs). Spelled here so
# a bench arm that names only `B` still measures the CONFIG THAT WOULD SHIP.
TIEARB_MODE_OF_RECORD = "argmax"
TIEARB_SALT_OF_RECORD = "tiearb2-deploy-v1"
TIEARB_EPS_OF_RECORD = 0.0

# Cumulative arbiter counters carried on FairAgentRs.stats(); summed across a
# mid-run session rebuild (the counters live on the agent, which is replaced).
_TIEARB_COUNTERS = ("tiearb_tile_plies", "tiearb_fired_plies",
                    "tiearb_pickchanges", "tiearb_arms_total",
                    "tiearb_playouts_total", "tiearb_errors",
                    "tiearb_partial_argmax")


class _BenchSession(B._Session):
    """A ``_Session`` whose resolved ``rust_threads`` (and, optionally, tie
    arbiter) are the bench arm's.

    ``_Session._build_opponent`` resolves ``rust_threads`` from the YAML mobile
    profile; ``_start_rust_mirror`` reads ``self.rust_threads`` when it builds
    ``FairAgentRs``. Overriding the attribute between those two steps (both run
    inside ``_Session.__init__``) is the narrowest possible hook: budget, leaf,
    seeding and every rule lever resolve exactly as in the real app, and the
    YAML is never edited. Thread count does not change play (see module doc).

    THE ARBITER HOOK is the same shape one level down. ``_start_rust_mirror``
    builds ``carc_rs.SearchConfigRs(...)`` positionally from the YAML-resolved
    spec knobs; the seven ``tiearb_*`` parameters are keyword-only with
    champion (OFF) defaults. So an armed arm patches ``SearchConfigRs`` on the
    ``carc_rs`` module for the duration of that ONE call and restores it
    immediately — no bridge code is edited, no other knob can move, and the
    unarmed arm never enters the patch at all. What was actually resolved is
    then read back off ``FairAgentRs.stats()`` and asserted field by field
    (:meth:`_assert_tiearb`): a bench that silently measured champion-vs-champion
    would be the classic zeroed-knob null.
    """

    def __init__(self, *, bench_rust_threads: int,
                 bench_tiearb: dict | None = None, **kw):
        t = int(bench_rust_threads)
        if t < 1:
            raise ValueError(f"bench_rust_threads must be >= 1, got {t}")
        self._bench_threads = t
        self._bench_tiearb = _resolve_tiearb(bench_tiearb)
        # ⚠️ THE BASE SESSION MUST NOT ARM ITS OWN ARBITER (added 2026-08-24 with
        # the mobile Settings-screen tiearb feature). `_Session` now defaults
        # `tiearb_level` to the app's own arbiter-on-by-default
        # (TIEARB_LEVEL_DEFAULT — B64 since 2026-08-29, B32 before it) — exactly what would
        # make the "control" arm above indistinguishable from an armed one, since
        # THIS class's own arming is a separate mechanism (the `SearchConfigRs`
        # monkeypatch in `_start_rust_mirror` below) driven by `bench_tiearb`, not
        # by the app Settings. `setdefault`, not assignment: a caller that passes
        # `tiearb_level` explicitly through `kw` still wins, and the `_assert_tiearb`
        # disagreement check below is what catches it if that ever conflicts with
        # `bench_tiearb` rather than silently double-arming.
        kw.setdefault("tiearb_level", B.TIEARB_LEVEL_OFF)
        super().__init__(**kw)

    def _build_opponent(self) -> None:
        super()._build_opponent()
        # Only meaningful on the rust path; after a degrade to python the
        # attribute is unused and the bench aborts anyway (see _run).
        if self.opponent_kind == "champion" and self.backend == B.BACKEND_RUST:
            self.rust_threads = self._bench_threads

    def _start_rust_mirror(self) -> None:
        ta = self._bench_tiearb
        if not ta["enabled"]:
            super()._start_rust_mirror()
            return
        import carc_rs

        orig = carc_rs.SearchConfigRs

        def _armed(*a, **kw):
            # setdefault, not assignment: if the bridge ever starts passing
            # these itself, its value wins and the assert below catches the
            # disagreement instead of this shim silently overriding it.
            kw.setdefault("tiearb_enabled", True)
            kw.setdefault("tiearb_b", int(ta["B"]))
            kw.setdefault("tiearb_j", int(ta["J"]))
            kw.setdefault("tiearb_mode", str(ta["mode"]))
            kw.setdefault("tiearb_salt", str(ta["salt"]))
            kw.setdefault("tiearb_eps", float(ta["eps"]))
            return orig(*a, **kw)

        carc_rs.SearchConfigRs = _armed
        try:
            super()._start_rust_mirror()
        finally:
            carc_rs.SearchConfigRs = orig

    def _assert_tiearb(self) -> dict:
        """The on-device J13 equivalent: prove the knob is where it was asked.

        Reads the RESOLVED arbiter block off the live rust agent and compares it
        to the arm's request. An armed arm whose wheel predates the arbiter, or
        whose shim failed to bind, would otherwise play a perfectly ordinary
        champion and be reported as an arbiter cost of ~zero — a null wearing
        the shape of a measurement. Raises; the caller turns that into
        ``ok: false`` on disk.
        """
        st = self.rs.stats()
        want = self._bench_tiearb
        got = {"enabled": bool(st["tiearb_enabled"]), "B": int(st["tiearb_b"]),
               "J": int(st["tiearb_j"]), "mode": str(st["tiearb_mode"]),
               "salt": str(st["tiearb_salt"]), "eps": float(st["tiearb_eps"])}
        if not want["enabled"]:
            # The control arm must be the champion byte-for-byte on this axis.
            if got["enabled"]:
                raise RuntimeError(
                    f"control arm resolved tiearb_enabled=True ({got}) — the "
                    f"arms are not a control/treatment pair")
            return got
        if got != {k: want[k] for k in got}:
            raise RuntimeError(
                f"tie arbiter did not resolve as requested: asked {want}, rust "
                f"reports {got} — stale carc_rs wheel, or the SearchConfigRs "
                f"shim did not bind")
        return got


def _resolve_tiearb(spec: dict | None) -> dict:
    """Normalize the arm's arbiter request. ``B <= 0`` (or ``None``) == OFF."""
    b = int((spec or {}).get("B", 0) or 0)
    if b <= 0:
        return {"enabled": False, "B": 0, "J": 0, "mode": "", "salt": "",
                "eps": 0.0}
    spec = spec or {}
    j = int(spec.get("J") or 4)
    if j < 1:
        raise ValueError(f"tiearb J must be >= 1, got {j}")
    eps = float(spec.get("eps") or 0.0)
    if not (eps >= 0.0):
        raise ValueError(f"tiearb eps must be >= 0, got {eps}")
    salt = str(spec.get("salt") or TIEARB_SALT_OF_RECORD)
    if not salt:
        raise ValueError("tiearb salt must be non-empty when armed")
    return {"enabled": True, "B": b, "J": j,
            "mode": str(spec.get("mode") or TIEARB_MODE_OF_RECORD),
            "salt": salt, "eps": eps}


def _new_session(seed: int, threads: int, sims, k_dets,
                 tiearb: dict | None = None) -> _BenchSession:
    return _BenchSession(
        bench_rust_threads=threads,
        bench_tiearb=tiearb,
        seed=int(seed),
        human_player=0,
        opponent="champion",
        # None/None = the YAML champion budget (the production workload).
        # Non-None only from desktop tests, which shrink the search to prove
        # the identity mechanism cheaply.
        sims=sims,
        k_dets=k_dets,
        # verify=False: champion_factory's leaf proof is a fixed startup cost
        # proven elsewhere (the shipping app runs it); nothing here is archived
        # as a played game, and the bench window starts after setup anyway.
        verify=False,
        generation=0,
        backend=B.BACKEND_RUST,
        farm_rule=B.FARM_RULE_LATCHED,
    )


def _require_rust(s: _BenchSession) -> None:
    """The bench measures the production (rust) engine or nothing.

    A degraded session would still play — at the k4x688 python floor — which is
    a different workload, so energy numbers from it would silently answer the
    wrong question. Fail loudly instead.
    """
    if s.backend != B.BACKEND_RUST or s.rs is None:
        raise RuntimeError(
            f"rust backend unavailable — bench refuses to measure the python "
            f"fallback (rs_note={s.rs_note!r})")


def _tiearb_totals(stats: dict) -> dict:
    out = {k: int(stats[k]) for k in _TIEARB_COUNTERS}
    out["tiearb_secs"] = float(stats["tiearb_secs"])
    out["tiearb_first_error"] = stats.get("tiearb_first_error")
    return out


def _accum_tiearb(acc: dict, stats: dict) -> None:
    cur = _tiearb_totals(stats)
    for k in _TIEARB_COUNTERS:
        acc[k] = acc.get(k, 0) + cur[k]
    acc["tiearb_secs"] = acc.get("tiearb_secs", 0.0) + cur["tiearb_secs"]
    if acc.get("tiearb_first_error") is None:
        acc["tiearb_first_error"] = cur["tiearb_first_error"]


def _run(n_moves: int, rust_threads: int, seed: int, sims, k_dets,
         tiearb: dict | None = None) -> dict:
    if n_moves < 1:
        raise ValueError(f"n_moves must be >= 1, got {n_moves}")

    t_setup0 = time.monotonic()
    s = _new_session(seed, rust_threads, sims, k_dets, tiearb)
    _require_rust(s)
    arb = s._assert_tiearb()          # the on-device J13 equivalent
    setup_ms = (time.monotonic() - t_setup0) * 1000.0

    k = int(s.eff_k_dets)
    per_det = int(s.eff_sims)
    rules = s.rules_profile

    per_move_ms: list[float] = []
    arb_secs: list[float] = []       # per COUNTED decision; 0.0 when not fired
    arb_fired: list[int] = []
    trace: list[list[int]] = []      # [game_seed, action_id] per APPLIED action
    forced = 0
    games = [int(seed)]
    rebuild_ms = 0.0
    arb_acc: dict = {}

    # The energy window the host integrates over: device epoch millis, the same
    # clock the driver's sampler stamps with `date +%s%3N` on the device.
    t_start_ms = int(time.time() * 1000)
    t_loop0 = time.monotonic()
    while len(per_move_ms) < n_moves:
        if s.board.state.is_terminated():
            # Fixed position stream continues into the next seeded game. With
            # the default n_moves this never happens (a game is ~140 plies);
            # the rebuild cost is recorded so the window is interpretable.
            g = int(seed) + len(games)
            games.append(g)
            t_r0 = time.monotonic()
            # The arbiter counters live on the agent that is about to be thrown
            # away — bank them or the run under-reports its own firing rate.
            _accum_tiearb(arb_acc, s.rs.stats())
            s = _new_session(g, rust_threads, sims, k_dets, tiearb)
            _require_rust(s)
            s._assert_tiearb()
            rebuild_ms += (time.monotonic() - t_r0) * 1000.0
            continue
        gseed = games[-1]
        legal = s.legal_ids()
        if len(legal) == 1:
            # A forced action (single legal move, e.g. a forced pass) is part
            # of the trajectory but not a champion decision — searching it
            # would dilute per-move stats with ~0 ms entries.
            s.apply(legal[0])
            trace.append([gseed, int(legal[0])])
            forced += 1
            continue
        t0 = time.monotonic()
        action = int(s.pick(s.board))
        dt_ms = (time.monotonic() - t0) * 1000.0
        # CHAMPION-TRAJECTORY REPLAY (see module doc). `tiearb_champ_pick` is
        # the champion's own pooled_q_argmax pick and is meaningful only on a
        # ply where the arbiter fired; everywhere else `action` already IS it.
        lm = s.rs.last_move()
        fired = bool(lm["tiearb_fired"])
        applied = int(lm["tiearb_champ_pick"]) if fired else action
        arb_fired.append(1 if fired else 0)
        arb_secs.append(float(lm["tiearb_secs"]))
        s.apply(applied)
        if s.rs is None:
            # apply() degrades to the python floor on a mirror failure rather
            # than crashing the app — right for a game, wrong for a bench.
            raise RuntimeError(
                f"rust mirror degraded mid-bench after "
                f"{len(per_move_ms)} moves (rs_note={s.rs_note!r})")
        per_move_ms.append(dt_ms)
        trace.append([gseed, applied])
    loop_wall_ms = (time.monotonic() - t_loop0) * 1000.0
    t_end_ms = int(time.time() * 1000)
    _accum_tiearb(arb_acc, s.rs.stats())

    # FAIL LOUD on a knob that resolved but never bit. An armed arm that fires
    # nowhere is measuring the champion, and its "arbiter costs ~0" reading
    # would be indistinguishable from good news.
    if arb["enabled"] and arb_acc["tiearb_fired_plies"] == 0:
        raise RuntimeError(
            f"arbiter armed ({arb}) but fired on 0 of "
            f"{arb_acc['tiearb_tile_plies']} tile plies in {n_moves} moves — "
            f"refusing to report a champion-vs-champion null as an arbiter cost")

    # The identity witness. Everything that defines "the same work" is inside
    # the digest: the resolved budget, the rules profile, and every applied
    # action of every game in the stream (forced actions included).
    # ⚠️ `replay` is IN the digest but the tiearb config is NOT, and both on
    # purpose: every arm drives the champion trajectory, so the trace must match
    # across arms (that is the gate), while a future change to the replay POLICY
    # must invalidate comparisons against runs taken under the old one.
    hashed = json.dumps(
        {"schema": SCHEMA, "rules_profile": rules, "replay": REPLAY_POLICY,
         "k_dets": k, "sims_per_det": per_det, "trace": trace},
        sort_keys=True, separators=(",", ":"))
    move_hash = hashlib.sha256(hashed.encode()).hexdigest()

    n_fired = int(arb_acc["tiearb_fired_plies"])
    search_ms = sum(per_move_ms)
    return {
        "schema": SCHEMA,
        "ok": True,
        "n_moves": int(n_moves),
        "seed": int(seed),
        "rust_threads": int(rust_threads),
        "replay": REPLAY_POLICY,
        "tiearb": arb,
        "tiearb_telemetry": arb_acc,
        # Read off the rust per-decision record, so it is the arbiter's OWN
        # clock rather than a subtraction between arms.
        "arb_secs_per_decision": [round(x, 4) for x in arb_secs],
        "arb_fired_flags": arb_fired,
        "n_fired_decisions": int(sum(arb_fired)),
        "arb_s_per_fired_ply": (round(arb_acc["tiearb_secs"] / n_fired, 4)
                                if n_fired else None),
        "backend": s.backend,
        "k_dets": k,
        "sims_per_det": per_det,
        "total_sims": k * per_det,
        "rules_profile": rules,
        "budget_note": s.budget_note,      # non-null only under test budgets
        "move_hash": move_hash,
        "n_actions_applied": len(trace),
        "forced_actions": forced,
        "games_started": games,
        # Window for the host's trapezoid integration (device epoch millis).
        "t_start_ms": t_start_ms,
        "t_end_ms": t_end_ms,
        "setup_ms": round(setup_ms, 1),          # outside the window
        "rebuild_ms": round(rebuild_ms, 1),      # inside the window if nonzero
        "loop_wall_ms": round(loop_wall_ms, 1),
        "search_ms_total": round(search_ms, 1),
        "s_per_move_mean": round(search_ms / len(per_move_ms) / 1000.0, 4),
        "per_move_ms": [round(x, 1) for x in per_move_ms],
    }


def run_bench(n_moves, rust_threads, seed, out_dir, tag,
              sims=None, k_dets=None,
              tiearb_b=0, tiearb_j=4, tiearb_mode=None, tiearb_salt=None,
              tiearb_eps=0.0) -> str:
    """Entry point for ``BenchService`` (and for the desktop tests).

    Runs the workload, writes ``<out_dir>/<tag>.json`` atomically, and returns
    the same JSON string. Never raises across JNI: failures come back (and land
    on disk) as ``{"ok": false, ...}`` so the host driver can report them.

    ``sims``/``k_dets`` exist for the desktop tests only; the on-device service
    never passes them, so the phone always benches the YAML champion budget.

    ``tiearb_b <= 0`` (the default) is the CHAMPION AS DEPLOYED — no arbiter
    keyword reaches the rust config at all. A positive ``tiearb_b`` arms the tie
    arbiter at that many CRN worlds, with mode/salt/eps defaulting to the
    settings of record; the trajectory stays the champion's either way (module
    doc), so armed and unarmed runs remain hash-comparable.
    """
    tag = str(tag)
    out_dir = str(out_dir)
    # Belt-and-braces: the E4 archive dir is files/games/ and this bench must
    # never write there — not results, not even its own error report. A refused
    # out_dir disables the disk write entirely (the JSON is still returned).
    writable = os.path.basename(os.path.normpath(out_dir)) != "games"
    try:
        if not writable:
            raise ValueError(
                f"out_dir {out_dir!r} refused: 'games' is the E4 archive dir")
        if not tag or any(c in tag for c in "/\\\0"):
            raise ValueError(f"bad tag {tag!r}")
        payload = _run(int(n_moves), int(rust_threads), int(seed),
                       sims, k_dets,
                       {"B": tiearb_b, "J": tiearb_j, "mode": tiearb_mode,
                        "salt": tiearb_salt, "eps": tiearb_eps})
    except BaseException as exc:  # noqa: BLE001 — must not raise across JNI
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        payload = {
            "schema": SCHEMA, "ok": False, "tag": tag,
            "rust_threads": int(rust_threads), "tiearb_b": int(tiearb_b or 0),
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
    payload["tag"] = tag
    text = json.dumps(payload, indent=1)
    if not writable:
        return text
    # A malformed tag still gets its error report on disk, under a safe name.
    safe_tag = (tag if tag and not any(c in tag for c in "/\\\0")
                else "bench_error")
    try:
        os.makedirs(out_dir, exist_ok=True)
        tmp = os.path.join(out_dir, f".{safe_tag}.json.tmp")
        with open(tmp, "w") as f:
            f.write(text)
        os.replace(tmp, os.path.join(out_dir, f"{safe_tag}.json"))
    except OSError:
        # Desktop tests pass a writable tmpdir; on device filesDir is writable.
        # If the write itself fails the returned JSON still carries the result.
        pass
    return text
