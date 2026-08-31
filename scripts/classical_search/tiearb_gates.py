"""TWO-SIDED TIE-ARBITER GATES — the vocabulary a both-sides cell needs.

Why this module exists (2026-08-31, owner-funded "fund plumbing now")
--------------------------------------------------------------------
Until today `eval_fair_puct.py` could arm THE TIE ARBITER on the CANDIDATE ONLY:
`_make_opponent` took no `tiearb` parameter and `_cfg_from_dict` reads five keys
by name, so the opponent seat was **structurally** disarmed. Three designs were
bent around that hole rather than around the science:

  * `measurement/phasegate_prep` — the B16 contortion,
  * S1 `G3` — the arb-OFF constraint,
  * the 2026-08-30 H2H prereg — whose "ARB-ON **both sides**" leg was simply
    INEXPRESSIBLE, and would have shipped as a confounded arb+fpu cell claiming
    a single variable.

The harness now has `--opp-tiearb-*`. But the *gate vocabulary* banked in those
rounds treats an armed opponent as a DEFECT — `measurement/phasegate_prep/
READ_RULE.md` `G-TIEARB-ARM` requires "Opponent: **no** tiearb container". Run a
healthy both-sides cell past that gate and it FAILS a good cell. Those frozen
prereg gates are NOT edited (a frozen prereg keeps its frozen gates); this module
is the *new* vocabulary future preregs cite instead.

The three states it covers, all first-class:

  ============  ============  ==================================================
  candidate     opponent      meaning
  ============  ============  ==================================================
  ARMED         ARMED         the symmetric both-sides cell (the leg that could
                              not be expressed before today)
  ARMED         ABSENT        the historical candidate-only cell — a ONE-SIDED
                              arm, and every banked arbiter row is one of these
  ABSENT        ABSENT        arb-off both sides (the dose ladder's footing)
  ============  ============  ==================================================

(ABSENT/ARMED — an opponent-only arm — is expressible too, and legal; the sign of
every statistic flips, which the harness shouts about at launch.)

⚠️ THE TWO SIDES HAVE DIFFERENT ABSENCE CONVENTIONS, on purpose, and this module
encodes the difference so no read-rule has to re-derive it:

  * `cand_tiearb` is stamped ALWAYS — armed or not — because `G-J4` makes an
    ABSENT `config.cand_tiearb` a FAIL. An unarmed candidate therefore reads as
    a full dict with `enabled: false`.
  * `opp_tiearb` is stamped ONLY when armed, because `G-TIEARB-ARM` makes a
    PRESENT opponent container a FAIL. An unarmed opponent reads as ABSENT.

Both are accepted as "unarmed" here (`enabled: false` and absent are the same
claim), so a manifest written by another driver — `scripts/carcasum_match`,
`scripts/jcz_match` — passes on its own convention.

Usage in a prereg's adjudicator::

    from tiearb_gates import assert_tiearb_sides, DEPLOYED_TIEARB_B64
    assert_tiearb_sides(manifest,
                        cand_expected=DEPLOYED_TIEARB_B64,
                        opp_expected=DEPLOYED_TIEARB_B64)     # both sides
    assert_tiearb_sides(manifest, cand_expected=DEPLOYED_TIEARB_B64,
                        opp_expected=None)                    # candidate-only
    assert_tiearb_sides(manifest, cand_expected=None, opp_expected=None)  # arb off
"""

from __future__ import annotations

# The knob spellings a resolved tiearb dict carries. `phase_gate` is included:
# a spec that omits it is under-specified (a silently-defaulted "all" on a gated
# cell makes it BE the ungated cell — measurement/phasegate_prep's whole lesson).
TIEARB_SPEC_KEYS = ("enabled", "B", "J", "mode", "salt", "eps", "phase_gate")

#: The deployed arbiter spec at B=64 (the post-2026-08-30 arb build). Kept here so
#: a prereg cites a symbol rather than re-typing seven keys; a cell that wants a
#: different rung passes its own dict.
DEPLOYED_TIEARB_B64 = {"enabled": True, "B": 64, "J": 4, "mode": "argmax",
                       "salt": "tiearb2-deploy-v1", "eps": 0.0, "phase_gate": "all"}

#: The B=16 funded rung (tiearb2 Stage 2 Phase B, and every phasegate cell).
DEPLOYED_TIEARB_B16 = {"enabled": True, "B": 16, "J": 4, "mode": "argmax",
                       "salt": "tiearb2-deploy-v1", "eps": 0.0, "phase_gate": "all"}

#: Where each side's resolved dict may live, in resolution order. The harness
#: writes BOTH the top-level and the `config.*` address (belt-and-braces: READ_RULE
#: §0.C.2 and DESIGN §4 disagreed once about which is canonical, and no gate should
#: have to win that argument). `config.opponent.tiearb` is the opponent block's own
#: mirror, for a reader who resolved the opponent record first.
_ADDRESSES = {
    "candidate": ("cand_tiearb", "config.cand_tiearb"),
    "opponent": ("opp_tiearb", "config.opp_tiearb", "config.opponent.tiearb"),
}


class TiearbGateError(AssertionError):
    """A two-sided tie-arbiter gate FAILED. AssertionError so an adjudicator that
    already catches assertion failures keeps working unchanged."""


def _dig(manifest, dotted: str):
    cur = manifest
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def resolve_tiearb(manifest, side: str):
    """`(spec, address)` for one side, or `(None, None)` when the side is ABSENT.

    `side` is "candidate" or "opponent". A dict found at ANY of that side's
    addresses wins, first address first. The returned dict is the RAW one — on the
    top-level address it may also carry the realized close-out counts
    (`fired_plies`, `fired_early`, …); comparisons here are made on the SPEC keys
    only, so a manifest read before or after close-out gates identically."""
    if side not in _ADDRESSES:
        raise ValueError(f"side must be 'candidate' or 'opponent'; got {side!r}")
    for addr in _ADDRESSES[side]:
        val = _dig(manifest, addr)
        if isinstance(val, dict):
            return val, addr
    return None, None


def _armed(spec) -> bool:
    """ABSENT and `enabled: false` are THE SAME CLAIM — "this seat did not
    arbitrate" — and both are accepted, because the two sides (and the external
    carcasum/jcz drivers) legitimately spell it differently."""
    return isinstance(spec, dict) and bool(spec.get("enabled"))


def check_tiearb_sides(manifest, cand_expected=None, opp_expected=None):
    """`(ok, findings)` — the non-raising form of `assert_tiearb_sides`.

    `cand_expected` / `opp_expected`:
      * `None`  => that seat MUST be unarmed (absent, or `enabled: false`).
      * a dict  => that seat MUST be armed AND every key in the dict must match
                   the resolved spec exactly. Extra keys on the manifest side
                   (realized counts) are ignored; a MISSING expected key is a
                   FAIL, never a default — a `phase_gate` that is absent means a
                   stale wheel whose arbiter ran UNGATED.

    `findings` is a list of human-readable strings: one per side, plus one per
    mismatch. It is returned on success too, so an adjudicator can print what it
    actually verified rather than "ok"."""
    findings = []
    ok = True
    for side, expected in (("candidate", cand_expected), ("opponent", opp_expected)):
        spec, addr = resolve_tiearb(manifest, side)
        armed = _armed(spec)
        where = addr or "ABSENT"
        if expected is None:
            if armed:
                ok = False
                findings.append(
                    f"FAIL {side}: expected UNARMED, but {where} carries an ARMED "
                    f"arbiter {_spec_str(spec)}")
            else:
                findings.append(
                    f"ok {side}: unarmed ({where}"
                    + (", enabled=false)" if spec is not None else ")"))
            continue
        if not armed:
            ok = False
            findings.append(
                f"FAIL {side}: expected ARMED {_spec_str(expected)}, but the seat is "
                + ("ABSENT from the manifest" if spec is None
                   else f"present-but-disabled at {where}"))
            continue
        bad = []
        for k, want in expected.items():
            if k not in spec:
                bad.append(f"{k} MISSING (absent is never a default)")
            elif spec[k] != want:
                bad.append(f"{k}={spec[k]!r} != {want!r}")
        if bad:
            ok = False
            findings.append(f"FAIL {side} @ {where}: " + "; ".join(bad))
        else:
            findings.append(f"ok {side}: ARMED {_spec_str(expected)} @ {where}")
    return ok, findings


def assert_tiearb_sides(manifest, cand_expected=None, opp_expected=None):
    """Raise `TiearbGateError` unless BOTH seats match. Returns the findings list
    on success so the caller can log what was verified."""
    ok, findings = check_tiearb_sides(manifest, cand_expected, opp_expected)
    if not ok:
        raise TiearbGateError(
            "two-sided tie-arbiter gate FAILED:\n  " + "\n  ".join(findings))
    return findings


def _spec_str(spec) -> str:
    if not isinstance(spec, dict):
        return repr(spec)
    return "{" + ", ".join(f"{k}={spec[k]!r}" for k in TIEARB_SPEC_KEYS
                           if k in spec) + "}"


def tiearb_sides_summary(summary):
    """`{side: {games, phi, fired_plies, pickchanges}}` read off a summary.json.

    The PLAY-derived companion to the config gate above: a manifest proves the
    knob was REQUESTED, these counters prove it BOUND. A both-sides cell whose
    `opp_tiearb_games` is 0 (or absent) never arbitrated on the opponent seat and
    is a ONE-SIDED cell wearing a symmetric cell's name — the exact defect the
    opponent-side plumbing exists to end."""
    out = {}
    for side, prefix in (("candidate", "tiearb_"), ("opponent", "opp_tiearb_")):
        if not summary.get(f"{prefix}games"):
            out[side] = None
            continue
        out[side] = {
            "games": summary[f"{prefix}games"],
            "phi": summary.get(f"{prefix}phi"),
            "fired_plies": summary.get(f"{prefix}fired_plies_total"),
            "pickchanges": summary.get(f"{prefix}pickchanges_total"),
            "G_FIRE_fired": summary.get(f"{prefix}G_FIRE_fired"),
        }
    return out
