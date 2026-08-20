#!/usr/bin/env python3
"""R5 — the rung-3 (`J > 4`) READ-OUT driver.

⭐ **THIS IS A DRIVER + EMITTER, NOT AN ESTIMATOR.** Every statistic, the root
bootstrap, the arms×worlds assembly, the §D4.18 failed-record accounting and the
READ_RULE §5 branch table are **imported from `analyze_widening`** (`AW`), which
is the checked tool of record. Nothing here re-derives a number that module
already computes; where a quantity genuinely has no `AW` constructor it is built
from `AW`'s own row schema and says so in a comment.

Licensed by `measurement/tiearb_widening_20260817/rung3_r5/READ_RULE.md` rev
R5.1 — §4 ("the branch table is CARRIED VERBATIM from R3.3 §5"), §2 (the gate
set), §6 (what the read-out prints). Population authority:
`RUN/ARMS_R5.json` (DESIGN ruling 2026-08-19) — **READ, never re-derived by
subtraction.**

Addresses this file writes (**every one is `[post-scoring]`** — see §1's
existence-time markers; the marker list is emitted explicitly under
`widening.markers` so the `A1` pass audits the LIST and an address added without
its fixture FAILS `A1` rather than passing silently):

    widening.j_rider.s2.{delta_ora, ci95_ora, r_ora, ci95_r_ora, ora_j4_ci95,
                         delta_arb, ci95_arb, n_capped, xfree_window,
                         r_ora_reported}          §5 PRIMARY
    widening.j_rider.d_draw.{n_checked, agreement_rate, d_draw_ran}   §5 rider
    widening.completion.s2_n                       G-COMPLETE
    widening.failed.{n_failed_rids, n_attempted, rate, by_class}      G-FAILED
    widening.gates.<gate>.{ok, resolved_at}        every §2 gate, NEVER
                                                   short-circuited
    widening.supply_chain.{…}                      §6, CORPUS_R5's realized ints
    widening.branch.{fired, reasons, mandatory_prints}                §5

⛔ **P1 — THE S1-RIDER PROHIBITION.** The carried §5 address list includes
`widening.j_rider.s1_replication.*` and `widening.j_rider.interaction.*`. **Those
are S1 quantities and R5 HAS NO S1 STRATUM.** They are emitted with their value
`null` and an ABSENCE WITNESS, and carry no number, CI or boolean anywhere. A
rider with no stratum behind it is not a weak result; **it is not a result.**

⛔ **P2 — TOKEN DISCIPLINE, INVERTED FROM R4.** R4's rung 3 fired NO branch, so
no branch token could appear anywhere. **R5 fires one.** Its token appears — and
**no other branch token may appear anywhere** in `READOUT_R5.json` or
`READOUT_R5.md`, and the non-fired rows are never narrated as near-misses.
`VOID_S2` **must not appear at all**: R5 is the SUCCESSOR to that void, not a
continuation of it, so `AW.void_rung3_block` and `AW.VOID_S2` are never called or
copied here.

⚠️ **THE PRINT-vs-TOKEN TENSION, and how both bars are kept.** READ_RULE §5's
third mandatory print is *about* the "cap was free" row, and the natural phrasing
spells that row's token on every branch — which P2 forbids. `AW.xfree_window`
does exactly that in its `note`. So this module keeps **every numeric field of
`AW.xfree_window` verbatim** and replaces only its prose, which names the row by
the schema's own key `xfree_window` (lowercase, no hyphen — it does not match the
token) plus plain English. The print is NOT dropped and the token bar is NOT
weakened. The same technique — `AW.VOID_FORBIDDEN_READINGS`' option (b) — is
applied to mandatory print (i), which would otherwise spell the partial-
resolution row's token.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import analyze_widening as AW                                       # noqa: E402
import analyze_tiletie as AT                                        # noqa: E402

# --------------------------------------------------------------------------- #
# committed constants — R5's, not R4's                                          #
# --------------------------------------------------------------------------- #
STRATUM = "s2"                       # READ_RULE §0 R8: `s2` EVERYWHERE, never `r5`
PROFILE = "walled"
JUDGE_ORACLE = "clair-puct"          # ADJUDICATES
JUDGE_ARBITER = "tier1-greedy"       # RIDES — it adjudicates nothing
E_WORLDS = 16                        # M = 32 ⇒ parity halves of 16
M_EXPECTED = 32                      # READ_RULE §2 G-M: ⚠️ NOT 128
N2_COMMITTED = 1060
GATE_FLOOR_COMMITTED = 1007          # ⌈0.95 × 1060⌉
FAILED_BOUND_FRAC = 0.02
LEG_LADDER_EXPECTED = (1060, 1060, 1060, 1060, 866, 509, 366, 265, 171, 110, 66, 9)
LEG_PAIRS_TOTAL = 6602
WORLD_SEED_SALT = AW.WORLD_SEED_SALT_OF_RECORD
DEPLOYED_CAP_J = AW.DEPLOYED_CAP_J_OF_RECORD
BOOT_REPS = AW.BOOT_REPS             # 2,000 — the ONE pre-committed root bootstrap
BOOT_SEED = AW.BOOT_SEED             # 20260819

#: §1 — every address this file writes exists only after scoring. "as carried"
#: is NOT a marker; each address gets exactly one, and it is this one.
MARKER = "[post-scoring]"

#: The schema's address set, in the spelling READ_RULE §2/§5 address them.
#: ⭐ `A1` audits THIS LIST against the committed fixture, so an address added
#: without its fixture entry FAILS rather than passing silently.
SCHEMA_ADDRESSES = (
    "widening.j_rider.s2.delta_ora",
    "widening.j_rider.s2.ci95_ora",
    "widening.j_rider.s2.r_ora",
    "widening.j_rider.s2.ci95_r_ora",
    "widening.j_rider.s2.ora_j4_ci95",
    "widening.j_rider.s2.delta_arb",
    "widening.j_rider.s2.ci95_arb",
    "widening.j_rider.s2.n_capped",
    "widening.j_rider.s2.xfree_window",
    "widening.j_rider.s2.r_ora_reported",
    "widening.j_rider.d_draw.n_checked",
    "widening.j_rider.d_draw.agreement_rate",
    "widening.j_rider.d_draw.d_draw_ran",
    "widening.completion.s2_n",
    "widening.failed.n_failed_rids",
    "widening.failed.n_attempted",
    "widening.failed.rate",
    "widening.failed.by_class",
    "widening.gates",
    "widening.supply_chain",
    "widening.branch.fired",
    "widening.branch.reasons",
    "widening.branch.mandatory_prints",
)

#: JSON types for the `A1` fixture. **TYPES ONLY — no value is computed, printed
#: or stored** (READ_RULE §1, the `A1` pass). ⚠️ This diverges from the RUN dir's
#: existing `fixtures/READOUT.fixture.json`, which carries EXEMPLAR VALUES
#: (`1007`, `1060`); see `FIXTURE_NAMING_CONFLICT` below — handled and reported,
#: not resolved.
SCHEMA_TYPES = {
    "widening.j_rider.s2.delta_ora": "number|null",
    "widening.j_rider.s2.ci95_ora": "array[2]",
    "widening.j_rider.s2.r_ora": "number|null",
    "widening.j_rider.s2.ci95_r_ora": "array[2]|null",
    "widening.j_rider.s2.ora_j4_ci95": "array[2]",
    "widening.j_rider.s2.delta_arb": "number|null",
    "widening.j_rider.s2.ci95_arb": "array[2]",
    "widening.j_rider.s2.n_capped": "integer",
    "widening.j_rider.s2.xfree_window": "object",
    "widening.j_rider.s2.r_ora_reported": "boolean",
    "widening.j_rider.d_draw.n_checked": "integer|null",
    "widening.j_rider.d_draw.agreement_rate": "number|null",
    "widening.j_rider.d_draw.d_draw_ran": "boolean",
    "widening.completion.s2_n": "integer",
    "widening.failed.n_failed_rids": "integer",
    "widening.failed.n_attempted": "integer",
    "widening.failed.rate": "number",
    "widening.failed.by_class": "object",
    "widening.gates": "object",
    "widening.supply_chain": "object",
    "widening.branch.fired": "string",
    "widening.branch.reasons": "array",
    "widening.branch.mandatory_prints": "object",
}

#: ⚠️ NAMING CONFLICT, HANDLED AND REPORTED — NOT RESOLVED. The DESIGN's fixture
#: LIST names `fixtures/READOUT.fixture.json`; its execution-layer ruling names
#: `fixtures/READOUT_R5.fixture.json`; and the real RUN dir contains the FORMER.
#: This tool PREFERS `READOUT_R5`, ACCEPTS `READOUT`, and RECORDS which it used —
#: because silently picking one is how an address audit ends up auditing a file
#: nobody committed.
FIXTURE_PREFERRED = "READOUT_R5.fixture.json"
FIXTURE_ACCEPTED = "READOUT.fixture.json"
FIXTURE_NAMING_CONFLICT = (
    "The DESIGN's fixture list names `fixtures/READOUT.fixture.json` while its "
    "execution-layer ruling names `fixtures/READOUT_R5.fixture.json`, and the "
    "RUN dir contains the former. This tool PREFERS READOUT_R5, ACCEPTS "
    "READOUT, and records which name it used. The conflict is DISCLOSED, not "
    "resolved — resolving it is a prereg amendment, not an analyzer decision."
)


# --------------------------------------------------------------------------- #
# P2 — the token bar, made mechanical                                           #
# --------------------------------------------------------------------------- #
#: The twelve rung-3 branch tokens. ⚠️ They live HERE, in the analyzer's source,
#: and are NEVER written into either emitted file except the ONE that fired.
BRANCH_TOKEN_RE = re.compile(
    r"\bX-(?:CONFIRMED|ABOVE|PARTIAL|BELOW|FREE|INCONCLUSIVE)(?:-D)?\b")

#: R4's void token. R5 is the SUCCESSOR to that void, not a continuation of it,
#: so this string must appear NOWHERE in either emitted file. Spelled here in
#: pieces so that even this module's own source cannot be mistaken for an
#: emission when a naive grep runs over the tree.
VOID_TOKEN_FORBIDDEN = "VOID" + "_S2"


def scan_branch_tokens(text: str) -> set:
    """Every rung-3 branch token occurring in `text`, MAXIMAL-MUNCH.

    ⚠️ A naive substring grep is WRONG here: `X-CONFIRMED` is a prefix of
    `X-CONFIRMED-D`, so a run that legitimately fired the sub-table row would
    read as if it had also printed the main-table row. The regex consumes the
    `-D` suffix greedily, so each occurrence resolves to exactly one token.
    """
    return set(BRANCH_TOKEN_RE.findall(text or ""))


def token_bar_violations(text: str, fired: str) -> dict:
    """`{extra_tokens, void_token_present}` — the P2 bar as data, not prose."""
    seen = scan_branch_tokens(text)
    return {
        "tokens_seen": sorted(seen),
        "extra_tokens": sorted(seen - ({fired} if fired else set())),
        "void_token_present": VOID_TOKEN_FORBIDDEN in (text or ""),
    }


# --------------------------------------------------------------------------- #
# the three MANDATORY PRINTS (READ_RULE §5, carried verbatim from R3.3)          #
# --------------------------------------------------------------------------- #
#: (i) ⚠️ The natural phrasing of this print SPELLS the partial-resolution row's
#: token, which P2 forbids on every branch but that one. `AW.VOID_FORBIDDEN_
#: READINGS` faced the identical problem and took option (b): state the
#: prohibition WITHOUT naming the row, and point at the READ_RULE, which is
#: where a reader looks for the names anyway. Same choice here — the CONTENT of
#: the print is intact; only the token is withheld.
PRINT_SEPARABILITY = (
    "SEPARABILITY, carried blind spot: this design CANNOT separate 1.400 from "
    "1.244. The gap is Delta = 0.054, which is z 1.28-2.00 across the "
    "pre-registered sd_delta bracket [0.9, 1.4] — under 2 sigma at every point "
    "of it. A point estimate that lands BETWEEN the two predictions reads as "
    "the partial-resolution row of the branch table (READ_RULE §5 names it; it "
    "is deliberately not spelled here) ONLY IF the realized CI EXCLUDES 1.400 "
    "OUTRIGHT — never 'whichever of the two the reader prefers'."
)

#: (ii) the corrected magnitude's own power statement.
PRINT_UNRESOLVED_0842 = (
    "POWER: the corrected prediction +0.0842 is UNRESOLVED at the top of the "
    "sd_delta bracket — z = 1.995 at sd_delta = 1.4, i.e. it fails 2 sigma by a "
    "hair at the pessimistic end. It resolves at 2 sigma iff sd_delta <= 1.371 "
    "(READ_RULE §4's power table at n2 = 1,060; se(Delta_ora) = "
    "sd_delta/sqrt(1060) in [0.0276, 0.0430])."
)


def sanitized_xfree_window(xf: dict) -> dict:
    """⭐ `AW.xfree_window`'s NUMERIC FIELDS VERBATIM, prose re-worded token-free.

    Mandatory print (iii) is the attainability window AT THE REALIZED se for the
    "cap was free" row: the interval of POINT ESTIMATES for which that row was
    reachable, plus a plain statement when it was empty or near-empty — so a
    NON-firing result is not read as evidence AGAINST the cap being free.

    `AW.xfree_window` computes exactly that and returns it with a `note` that
    spells the row's token. Nothing numeric is recomputed here: `half_width`,
    `lo`, `hi`, `empty`, `requires_negative_point_estimate`, `point_estimate`
    and `reachable_for_point_estimate` are passed through untouched. Only the
    prose is replaced, and it names the row by THIS SCHEMA'S OWN KEY —
    `xfree_window`, lowercase and unhyphenated, which does not match the token.
    """
    out = {k: xf.get(k) for k in
           ("half_width", "lo", "hi", "empty",
            "requires_negative_point_estimate", "point_estimate",
            "reachable_for_point_estimate")}
    empty = out.get("empty")
    needs_neg = out.get("requires_negative_point_estimate")
    if empty is None:
        prose = ("UNDEFINED: the realized CI is absent, so the attainability "
                 "window for the `xfree_window` row has no realized se to be "
                 "computed at.")
    elif empty:
        prose = ("EMPTY at the realized se: there is NO point estimate for "
                 "which the `xfree_window` row ('the cap was free') was "
                 "reachable. Its non-firing is therefore NOT evidence against "
                 "the cap being free — the row could not have fired whatever "
                 "the data said.")
    elif needs_neg:
        prose = ("NEAR-EMPTY at the realized se: the `xfree_window` row ('the "
                 "cap was free') required a strictly NEGATIVE point estimate "
                 f"(reachable only on [{out['lo']!r}, {out['hi']!r})). Its "
                 "non-firing is NOT evidence against the cap being free.")
    else:
        prose = (f"The `xfree_window` row ('the cap was free') was reachable "
                 f"only for point estimates in [{out['lo']!r}, {out['hi']!r}) "
                 f"at the realized se. At sd_delta = 1.4 that bar is a point "
                 f"estimate <= +0.0015 — essentially zero — so a non-firing "
                 f"result is not evidence against the cap being free.")
    out["attainability"] = prose
    out["source"] = ("analyze_widening.xfree_window — numeric fields verbatim; "
                     "prose re-worded so no branch token is spelled (see the "
                     "module docstring's print-vs-token note)")
    return out


def mandatory_prints(xfree: dict) -> dict:
    """The three prints READ_RULE §5 requires ON EVERY BRANCH."""
    return {
        "i_separability_1400_vs_1244": PRINT_SEPARABILITY,
        "ii_0842_unresolved_at_bracket_top": PRINT_UNRESOLVED_0842,
        "iii_attainability_window_at_realized_se": xfree.get("attainability"),
        "iii_window": {k: xfree.get(k) for k in
                       ("lo", "hi", "half_width", "empty",
                        "requires_negative_point_estimate",
                        "point_estimate", "reachable_for_point_estimate")},
        "printed_on": "EVERY branch, fired or not — these are disclosures about "
                      "the DESIGN, graded by the run, not results of it",
    }


# --------------------------------------------------------------------------- #
# P1 — the S1-rider prohibition                                                  #
# --------------------------------------------------------------------------- #
S1_ABSENCE_WITNESS = (
    "R5 HAS NO S1 STRATUM. This address is carried in the §5 address list "
    "because that list was inherited from R3.3/R4, which had one. Nothing was "
    "measured for it here — no positions, no worlds, no contrast. It is NOT a "
    "weak result, NOT a null result and NOT inconclusive: there is no result. "
    "Any number reported at this address would be a number about a different "
    "run."
)


def s1_rider_absence_block(address: str) -> dict:
    """A carried S1 address, emitted with its ABSENCE WITNESS and no value.

    ⚠️ Deliberately carries NO numeric and NO boolean field. A boolean here
    ('measured: false') is still a measurement-shaped answer to a question that
    was never asked, and the whole point of P1 is that the question has no
    stratum behind it.
    """
    return {
        "address": address,
        "value": None,
        "ci95": None,
        "witness": S1_ABSENCE_WITNESS,
        "stratum": "S1 — absent from this run",
        "adjudicates": "nothing; there is nothing to adjudicate with",
    }


# --------------------------------------------------------------------------- #
# small helpers                                                                  #
# --------------------------------------------------------------------------- #
def _load_json(path):
    p = Path(path)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


def _sha256(path) -> str:
    p = Path(path)
    if not p.is_file():
        return ""
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _get(d, dotted, default=None):
    cur = d
    for part in str(dotted).split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def _gate(name, ok, resolved_at, why, **detail) -> dict:
    """One gate row. `ok` is a BOOLEAN, never None — an unresolvable conjunct is
    FALSE (READ_RULE §1: ABSENT IS FAIL), and `why` names the failing row."""
    return {"gate": name, "ok": bool(ok), "resolved_at": resolved_at,
            "why": why, "detail": detail}


def committed_parameters(floors, staging) -> dict:
    """The run's committed PARAMETERS, read from the artifacts that carry them.

    ⭐ READ_RULE §2a is explicit that these are **parameters committed in
    `RUN/FLOORS_R5.json`** (and, for the leg ladder, witnessed in
    `RUN/STAGING_R5.json`) — so the ARTIFACT is the authority and this module's
    constants are a DEFAULT for when it is absent, plus a cross-check. Hard-
    coding a second copy of a committed parameter is how an amended floors file
    ends up silently disagreeing with the tool that grades against it; the
    disagreement is DISCLOSED here (`agrees_with_module_pin`) rather than
    resolved by one side quietly winning.

    ⚠️ The population's own identity is NOT one of these knobs: `G-CORPUS`
    pins `ARMS_R5.json` by **sha256**, which is bit-for-bit and cannot be
    loosened by a floors edit.
    """
    n2 = (floors or {}).get("n2")
    n2 = int(n2) if isinstance(n2, (int, float)) else N2_COMMITTED
    floor = (floors or {}).get("gate_floor")
    floor = int(floor) if isinstance(floor, (int, float)) else -(-95 * n2 // 100)
    ladder = (staging or {}).get("leg_ladder_expected")
    ladder = (tuple(int(x) for x in ladder) if isinstance(ladder, list) and ladder
              else LEG_LADDER_EXPECTED)
    pairs = (staging or {}).get("n_total_pairs")
    pairs = int(pairs) if isinstance(pairs, (int, float)) else sum(ladder)
    return {
        "n2": n2, "gate_floor": floor, "leg_ladder": ladder,
        "n_total_pairs": pairs,
        "source": {"n2": "RUN/FLOORS_R5.json::n2",
                   "gate_floor": "RUN/FLOORS_R5.json::gate_floor",
                   "leg_ladder": "RUN/STAGING_R5.json::leg_ladder_expected",
                   "n_total_pairs": "RUN/STAGING_R5.json::n_total_pairs"},
        "module_pin": {"n2": N2_COMMITTED,
                       "gate_floor": GATE_FLOOR_COMMITTED,
                       "leg_ladder": list(LEG_LADDER_EXPECTED),
                       "n_total_pairs": LEG_PAIRS_TOTAL},
        "agrees_with_module_pin": bool(
            n2 == N2_COMMITTED and floor == GATE_FLOOR_COMMITTED
            and ladder == LEG_LADDER_EXPECTED and pairs == LEG_PAIRS_TOTAL),
    }


# --------------------------------------------------------------------------- #
# the §2 gate set — EVERY gate resolved, NEVER short-circuited                   #
# --------------------------------------------------------------------------- #
def gate_corpus(corpus, floors, arms_index, arms_path, params) -> dict:
    """`G-CORPUS` — the corpus is R4's post-exclusion S2 leg ADOPTED AS-IS, plus
    R5's own exclusion list, and `ARMS_R5.json` is the MATERIALIZED POPULATION
    AUTHORITY. ⭐ The population is READ from that file; it is never re-derived
    by subtraction (DESIGN ruling 2026-08-19, shape (a))."""
    if corpus is None:
        return _gate("G-CORPUS", False, "RUN/CORPUS_R5.json",
                     "CORPUS_R5.json is ABSENT or unreadable — READ_RULE §1: "
                     "ABSENT IS FAIL; the corpus-identity row cannot resolve")
    committed_leg_sha = _get(floors or {}, "corpus_provenance.leg_sha256")
    committed_excl_sha = _get(floors or {}, "corpus_provenance.r4_exclusion_list_sha256")
    arms_sha_committed = corpus.get("arms_r5_sha256")
    arms_sha_actual = _sha256(arms_path) if arms_path else ""
    excluded = sorted(corpus.get("excluded_rids") or [])
    n_positions = corpus.get("n_positions")
    n_rids = len(arms_index or {})
    # the SUBTRACTION-FREE half of the identity that this tool can witness:
    # no excluded rid may survive into the authority.
    leaked = sorted(set(excluded) & set(arms_index or {}))
    conj = {
        "leg_sha256_matches_committed":
            bool(committed_leg_sha) and corpus.get("leg_sha256") == committed_leg_sha,
        "r4_exclusion_list_sha256_matches_committed":
            bool(committed_excl_sha)
            and corpus.get("r4_exclusion_list_sha256") == committed_excl_sha,
        "n_positions_equals_committed_n2": n_positions == params["n2"],
        "excluded_rids_count_is_4": len(excluded) == 4,
        "excluded_rids_identity_gated": bool(excluded) and not leaked,
        "arms_r5_n_rids_equals_committed_n2": n_rids == params["n2"],
        "arms_r5_sha256_matches": bool(arms_sha_committed)
                                  and arms_sha_actual == arms_sha_committed,
        "max_per_game_3": corpus.get("max_positions_per_seed") == 3,
        "min_ply_0": _get(floors or {}, "min_ply") == 0,
        "cap_j_inf": _get(floors or {}, "cap_j") is None,
    }
    bad = sorted(k for k, v in conj.items() if not v)
    return _gate(
        "G-CORPUS", not bad,
        "RUN/CORPUS_R5.json::{leg_path, leg_sha256, r4_exclusion_list_sha256, "
        "n_in, n_excluded_r5, n_positions, excluded_rids, arms_r5_sha256} · "
        "RUN/ARMS_R5.json",
        None if not bad else
        f"G-CORPUS row FAILED on conjunct(s) {bad}. The identity is GATED, not "
        f"only the count (REVIEW_R4 P1): the four excluded rids are "
        f"tt_sp_135000000839_p2 plus the later-ordered member of each of the 3 "
        f"same-band dupe groups, and ARMS_R5.json's sha must equal the "
        f"committed arms_r5_sha256.",
        conjuncts=conj, n_arms_rids=n_rids, excluded_rids=excluded,
        committed_parameters=params,
        excluded_rids_leaked_into_authority=leaked,
        arms_r5_sha256_actual=arms_sha_actual,
        arms_r5_sha256_committed=arms_sha_committed,
        both_direction_identity_witness=_get(
            floors or {}, "population_authority.identity"),
        note="the BOTH-DIRECTIONS identity (rids == R4_ARMS.rids - "
             "excluded_rids) is asserted at BUILD time and witnessed in "
             "FLOORS_R5.json::population_authority; this analyzer checks the "
             "half it can see WITHOUT re-deriving the population — that no "
             "excluded rid survives into the authority — and reports the "
             "build-time witness rather than repeating the subtraction")


def gate_staged(staging, arms_index, leg_rids_observed, params) -> dict:
    """`G-STAGED` — the staged dir is a witnessed TRANSCRIPTION of the population
    authority, not a second population.

    ⭐ The EXACT per-leg predicate: for every `r`, `set(leg_r rids) == {rid :
    len(arms) > r}`. ⚠️ "subset" is too weak — a TRUNCATED leg is exactly what
    the adopted R4 build shipped, and only the exact predicate detects it."""
    ladder = params["leg_ladder"]
    expected_by_leg = {}
    for r in range(1, len(ladder) + 1):
        expected_by_leg[r] = {rid for rid, m in (arms_index or {}).items()
                              if len(m.get("arms") or []) > r}
    per_leg, leg_bad = {}, []
    for r, exp in sorted(expected_by_leg.items()):
        obs = set(leg_rids_observed.get(r) or ())
        row = {"n_expected": len(exp), "n_observed": len(obs),
               "n_missing": len(exp - obs), "n_extra": len(obs - exp),
               "exact": exp == obs,
               "pinned": ladder[r - 1],
               "pinned_matches_expected": len(exp) == ladder[r - 1]}
        per_leg[f"leg{r}"] = row
        if not (row["exact"] and row["pinned_matches_expected"]):
            leg_bad.append(f"leg{r}")
    total_pairs = sum(len(v) for v in expected_by_leg.values())
    conj = {
        "arms_copy_identical": (staging or {}).get("arms_copy_identical") is True,
        "staged_arms_sha_equals_authority":
            bool((staging or {}).get("arms_r5_sha256"))
            and (staging or {}).get("staged_arms_sha256")
                == (staging or {}).get("arms_r5_sha256"),
        "rid_sets_equal": (staging or {}).get("rid_sets_equal") is True,
        "missing_in_leg_empty": (staging or {}).get("missing_in_leg") == [],
        "missing_in_arms_empty": (staging or {}).get("missing_in_arms") == [],
        "n_arms_rids_equals_committed_n2":
            (staging or {}).get("n_arms_rids") == params["n2"],
        "stage_chunks_rid_set_agrees":
            (staging or {}).get("stage_chunks_rid_set_agrees") is True,
        "per_leg_exact_predicate": not leg_bad,
        "total_pairs_equals_committed":
            total_pairs == params["n_total_pairs"],
    }
    if staging is None:
        conj = {k: False for k in conj}
        conj["per_leg_exact_predicate"] = not leg_bad
    bad = sorted(k for k, v in conj.items() if not v)
    return _gate(
        "G-STAGED", not bad,
        "RUN/STAGING_R5.json::{arms_r5_sha256, staged_arms_sha256, "
        "arms_copy_identical, n_leg_rids, n_arms_rids, rid_sets_equal, "
        "missing_in_leg, missing_in_arms, stage_chunks_rid_set_agrees, "
        "n_chunks}",
        None if not bad else
        f"G-STAGED row FAILED on conjunct(s) {bad}"
        + (f"; the EXACT per-leg predicate failed on {leg_bad} — equality "
           f"across legs is FALSE from leg5 and 'subset' is too weak to catch "
           f"a truncated leg, which is precisely what the adopted R4 build "
           f"shipped" if leg_bad else ""),
        conjuncts=conj, per_leg=per_leg, total_pairs=total_pairs,
        pinned_ladder=list(ladder), committed_parameters=params,
        note="CORPUS_R5's identity does NOT cover this layer — it is written "
             "before staging exists (DESIGN staging recipe, ruling (c))")


def gate_internal_dupe(dupe, corpus) -> dict:
    """`G-INTERNAL-DUPE` — (i) IDENTITY-DERIVED `d_internal <= 0.05`; (ii) the
    CONSISTENCY conjunct, which carries the falsifiable content.

    ⚠️ §2.1: BOTH degeneracy gates are CORPUS-IDENTITY checks, not discovery
    gates — `d_internal` is a deterministic function of a sha-pinned file and
    cannot fail unless the sha check already has. A CONSISTENCY mismatch RAISES.
    """
    if dupe is None:
        return _gate("G-INTERNAL-DUPE", False, "RUN/GATE_INTERNAL_DUPE.json",
                     "GATE_INTERNAL_DUPE.json is ABSENT or unreadable — "
                     "ABSENT IS FAIL", raises=False)
    plies = sorted({int(k) for k in (dupe.get("ply_histogram") or {})})
    conj = {
        "d_internal_le_0.05": (dupe.get("d_internal") is not None
                               and float(dupe["d_internal"]) <= 0.05),
        "n_dupe_groups_is_3": dupe.get("n_dupe_groups") == 3,
        "n_dupe_positions_is_6": dupe.get("n_dupe_positions") == 6,
        "every_member_at_ply_2": plies == [2],
        "all_pairs_same_band_137e9":
            bool(dupe.get("band_pairs"))
            and all(p == "137e9<->137e9" for p in dupe["band_pairs"]),
        "leg_sha256_matches_corpus":
            bool((corpus or {}).get("leg_sha256"))
            and dupe.get("leg_sha256") == (corpus or {}).get("leg_sha256"),
    }
    bad = sorted(k for k, v in conj.items() if not v)
    # the CONSISTENCY half is the half that RAISES (§2). The raise is DEFERRED
    # to after every other gate has resolved, so one failing row can never stop
    # the rest of the gate set from being reported.
    consistency = ("n_dupe_groups_is_3", "n_dupe_positions_is_6",
                   "every_member_at_ply_2", "all_pairs_same_band_137e9")
    raises = any(not conj[k] for k in consistency)
    return _gate(
        "G-INTERNAL-DUPE", not bad, "RUN/GATE_INTERNAL_DUPE.json::"
        "{n_positions, n_dupe_groups, n_dupe_positions, d_internal, "
        "ply_histogram, band_pairs, leg_sha256}",
        None if not bad else
        f"G-INTERNAL-DUPE row FAILED on conjunct(s) {bad}"
        + ("; the CONSISTENCY conjunct is the falsifiable half and a mismatch "
           "RAISES (READ_RULE §2)" if raises else ""),
        conjuncts=conj, raises=raises, d_internal=dupe.get("d_internal"),
        identity_check_only="READ_RULE §2.1: both degeneracy gates establish "
                            "'the corpus is the one that was measured' and "
                            "NOTHING ELSE — a real, falsifiable property, and "
                            "all they establish")


def gate_disjoint(dis) -> dict:
    """`G-DISJOINT` — the LEAKAGE guard. ⛔ The DIGEST layer is NOT carried in
    R5 (READ_RULE §0).

    ⭐ **THE ABSENCE LICENCE IS BOUNDED ON FOUR SIDES** (DESIGN 2026-08-20,
    FIX 1). The emitter has declared `layers_absent` with a reason since R3.3 —
    *"a fabricated `0` would read as a proof that was never performed"* — and
    that declaration PRE-DATES the blind commit; this consumer simply never
    inherited the handling and read a declared-absent layer as `null` ⇒ FAIL.
    That is the `ci95` class: an address named that its own emitter does not
    write. But "respect `layers_absent`" must not decay into "any missing layer
    is excused", which would convert the leakage guard into this campaign's
    signature PASS-ALWAYS disease. So:

      b_rid      REQUIRED PRESENT on EVERY comparison, and `n_intersection == 0`.
                 ⛔ NO absence licence at all — a rid identity always exists.
      a_root_id  zero if present; VACUOUS on a comparison ONLY IF BOTH
                 `"a_root_id" in layers_absent` AND `layers_absent_reason` is
                 non-empty. A bare list with no reason does not excuse it.
      NEITHER present nor declared absent ⇒ FAIL (ABSENT-IS-FAIL survives).
      ANTI-VACUITY: `a_root_id` must be PRESENT-and-zero on ≥ 1 comparison, or
                 the gate FAILS as structurally vacuous — a root layer excused
                 everywhere has stopped being a guard.

    Satisfiable and not by accident: on the real artifact `b_rid` is present on
    all four comparisons and `a_root_id` on three, declared absent on exactly
    one (`s2_vs_exclude_rids` — a JSON reference list has no root identity), so
    the anti-vacuity clause has 3 of 4 comparisons behind it.
    """
    if dis is None:
        return _gate("G-DISJOINT", False, "RUN/GATE_DISJOINT_R5.json",
                     "GATE_DISJOINT_R5.json is ABSENT or unreadable — "
                     "ABSENT IS FAIL")
    per = {}
    rid_bad, root_bad, undeclared, n_root_present_zero = [], [], [], 0
    for name, cmp_ in sorted((dis.get("comparisons") or {}).items()):
        cmp_ = cmp_ or {}
        layers = cmp_.get("layers") or {}
        absent = list(cmp_.get("layers_absent") or [])
        reason = str(cmp_.get("layers_absent_reason") or "").strip()
        row = {}

        # ---- b_rid: required, no licence ---------------------------------- #
        n_rid = (layers.get("b_rid") or {}).get("n_intersection")
        row["b_rid"] = n_rid
        if n_rid != 0:
            rid_bad.append(f"{name}.b_rid={n_rid!r}")
            if "b_rid" in absent:
                # ⛔ named as absent — which the rid layer may never be
                undeclared.append(f"{name}.b_rid (declared absent — the rid "
                                  f"layer carries NO absence licence)")

        # ---- a_root_id: zero if present, vacuous only if DECLARED --------- #
        if "a_root_id" in layers:
            n_root = (layers.get("a_root_id") or {}).get("n_intersection")
            row["a_root_id"] = n_root
            row["a_root_id_state"] = "present"
            if n_root == 0:
                n_root_present_zero += 1
            else:
                root_bad.append(f"{name}.a_root_id={n_root!r}")
        elif "a_root_id" in absent and reason:
            row["a_root_id"] = None
            row["a_root_id_state"] = "vacuous (declared absent WITH reason)"
        else:
            row["a_root_id"] = None
            row["a_root_id_state"] = "UNDECLARED"
            undeclared.append(
                f"{name}.a_root_id (neither present nor declared absent"
                + ("" if "a_root_id" not in absent else
                   " — listed in layers_absent but layers_absent_reason is "
                   "EMPTY, and an undocumented absence is not a licence")
                + ")")
        per[name] = row

    conj = {
        "passed": dis.get("passed") is True,
        "n_comparisons_present": bool(per),
        "b_rid_present_and_zero_on_every_comparison": not rid_bad,
        "a_root_id_zero_wherever_present": not root_bad,
        "no_undeclared_absent_layer": not undeclared,
        # ⭐ anti-vacuity — the clause that stops the licence eating the gate
        "a_root_id_present_and_zero_on_at_least_one": n_root_present_zero >= 1,
    }
    bad_c = sorted(k for k, v in conj.items() if not v)
    why = []
    if rid_bad:
        why.append(f"rid layer: {rid_bad}")
    if root_bad:
        why.append(f"root layer: {root_bad}")
    if undeclared:
        why.append(f"undeclared absences: {undeclared}")
    if not conj["a_root_id_present_and_zero_on_at_least_one"]:
        why.append("STRUCTURALLY VACUOUS: a_root_id is present-and-zero on NO "
                   "comparison, so the root layer proved nothing anywhere")
    return _gate(
        "G-DISJOINT", not bad_c,
        "RUN/GATE_DISJOINT_R5.json::{passed, comparisons.<name>.layers."
        "{a_root_id,b_rid}.n_intersection, comparisons.<name>."
        "{layers_absent, layers_absent_reason}}",
        None if not bad_c else
        f"G-DISJOINT row FAILED on conjunct(s) {bad_c}"
        + ("; " + "; ".join(why) if why else ""),
        conjuncts=conj, comparisons=per,
        n_root_present_zero=n_root_present_zero,
        absence_licence="BOUNDED ON FOUR SIDES (DESIGN 2026-08-20 FIX 1): b_rid "
                        "has none; a_root_id needs layers_absent AND a non-empty "
                        "reason; undeclared absence FAILS; and a_root_id must be "
                        "present-and-zero somewhere or the gate is vacuous",
        digest_layer="NOT CARRIED in R5 (READ_RULE §0)")


def gate_band(corpus) -> dict:
    """`G-BAND` — (i) RANGE at the SEED level; (ii) MINING CEILING at the
    POSITIONS level. ⛔ `n_duplicate_seeds == 0` is DELETED (§2.2 N1): a set of
    DISTINCT seeds has no duplicates by construction, so the conjunct was
    vacuous; `max_positions_per_seed <= 3` carries the real invariant."""
    if corpus is None:
        return _gate("G-BAND", False, "RUN/CORPUS_R5.json",
                     "CORPUS_R5.json is ABSENT or unreadable — ABSENT IS FAIL")
    ranges = corpus.get("seed_ranges") or {}
    conj = {
        "n_out_of_band_is_0": corpus.get("n_out_of_band") == 0,
        "n_seeds_136e9_is_0": corpus.get("n_seeds_136e9") == 0,
        "max_positions_per_seed_le_3":
            (corpus.get("max_positions_per_seed") is not None
             and corpus["max_positions_per_seed"] <= 3),
        "banked_range_committed":
            ranges.get("banked_135e9") == [135000000350, 135000000849],
        "extension_range_committed":
            ranges.get("extension_137e9") == [137000000508, 137000005347],
        "released_unused_136e9_declared":
            ranges.get("released_unused") == 136000000000,
    }
    bad = sorted(k for k, v in conj.items() if not v)
    return _gate(
        "G-BAND", not bad,
        "RUN/CORPUS_R5.json::{seed_ranges, n_distinct_seeds, n_out_of_band, "
        "n_seeds_136e9, max_positions_per_seed}",
        None if not bad else f"G-BAND row FAILED on conjunct(s) {bad}",
        conjuncts=conj, n_distinct_seeds=corpus.get("n_distinct_seeds"),
        deleted_conjunct="n_duplicate_seeds == 0 — DELETED (§2.2 N1), not "
                         "re-based: vacuous at the seed level, and R4's "
                         "game-level referent does not exist here")


def gate_complete(s2_n, params) -> dict:
    """`G-COMPLETE` — `n_analysed >= 1007` (= ⌈0.95 × 1060⌉ at the committed
    `n2`), AFTER exclusions and AFTER §3's failed-record drop."""
    floor = params["gate_floor"]
    ok = s2_n >= floor
    return _gate(
        "G-COMPLETE", ok, "READOUT::widening.completion.s2_n",
        None if ok else
        f"G-COMPLETE row FAILED: n_analysed = {s2_n} < the committed floor "
        f"{floor} (= ceil(0.95 x {params['n2']})). The count is evaluated "
        f"AFTER exclusions and AFTER the §3 whole-rid drop — an exclusion can "
        f"never be used to explain away a shortfall after the fact.",
        s2_n=s2_n, floor=floor, n2_committed=params["n2"],
        committed_parameters=params, evaluated_after_exclusions=True)


def gate_failed(failed_block, n_attempted) -> dict:
    """`G-FAILED` — (i) `n_failed_rids / n_attempted <= 0.02`; (ii) any failed
    record whose class is NOT `WindowTruncationError` RAISES regardless of count.

    ⚠️ Conjunct (ii) is enforced UPSTREAM, inside `AW.build_rows`, which refuses
    outright. Reaching this function at all means (ii) held."""
    n_failed = failed_block.get("n_failed_rids", 0)
    rate = (n_failed / n_attempted) if n_attempted else 0.0
    ok = rate <= FAILED_BOUND_FRAC
    return _gate(
        "G-FAILED", ok,
        "READOUT::widening.failed.{n_failed_rids, n_attempted, rate, by_class}",
        None if ok else
        f"G-FAILED row (i) FAILED: {n_failed}/{n_attempted} = {rate:.4f} "
        f"exceeds the committed bound {FAILED_BOUND_FRAC}",
        n_failed_rids=n_failed, n_attempted=n_attempted, rate=rate,
        bound=FAILED_BOUND_FRAC,
        unknown_class_rule="enforced upstream by analyze_widening.build_rows, "
                           "which REFUSES on any class that is not "
                           f"{AW.KNOWN_FAILURE_CLASS!r} regardless of count",
        corrected_expectation_r5=(
            "READ_RULE §3, CORRECTED: R5's corpus sits slightly DEEPER than "
            "S1's (mean ply 69.15 vs 66.50; 63.3% at ply >= 50), in exactly "
            "the region where the encoder-window limitation fires, so the "
            "pre-registered expectation is EQUAL-OR-HIGHER than S1's realized "
            "0.30%, NOT lower. Where collisions happen is not where the "
            "population lives."))


def gate_m(run_manifest, smoke, leg_manifests) -> dict:
    """`G-M` — `m_worlds == 32` ∧ `b_ceiling_from_m == 16`. ⚠️ NOT 128.

    Two markers by design (§2 R1): the `[post-corpus]` smoke address halts the
    run BEFORE ~300 Wh is spent; the `[post-scoring]` manifest address is the
    one this read-out resolves."""
    pre = (smoke or {}).get("m_worlds")            # ⭐ TOP-LEVEL (§2.2 N2)
    post_m = (run_manifest or {}).get("m_worlds")
    post_b = (run_manifest or {}).get("b_ceiling_from_m")
    fb = [(_get(m or {}, "resolved_config.m"), p) for p, m in leg_manifests]
    fb_ok = (all(v == M_EXPECTED for v, _ in fb) if fb else None)
    conj = {
        "smoke_m_worlds_is_32": pre == M_EXPECTED,
        "manifest_m_worlds_is_32": post_m == M_EXPECTED,
        "manifest_b_ceiling_is_16": post_b == 16,
    }
    # the leg-manifest fallback resolves and is RETAINED (§2.2): it is the
    # spelling verified against tier1_rust_leg.py:401, not a blanket rename.
    if post_m is None and fb_ok is not None:
        conj["manifest_m_worlds_is_32"] = fb_ok
    bad = sorted(k for k, v in conj.items() if not v)
    return _gate(
        "G-M", not bad,
        "pre-leg RUN/SMOKE_R5.json::m_worlds (TOP-LEVEL) · post "
        "RUN/RUN_MANIFEST_R5.json::{m_worlds,b_ceiling_from_m} · fallback "
        "RUN/legs/s2/tier1-greedy/walled/leg<N>/manifest.json::resolved_config.m",
        None if not bad else
        f"G-M row FAILED on conjunct(s) {bad} — the constant this revision "
        f"exists to correct is m_worlds == 32, NOT 128",
        conjuncts=conj, smoke_m_worlds=pre, manifest_m_worlds=post_m,
        manifest_b_ceiling_from_m=post_b, leg_fallback_ok=fb_ok,
        leg_fallback_values=[v for v, _ in fb])


def gate_salt(run_manifest, plan, arms_index, leg_manifests) -> dict:
    """`G-SALT` — the salt is a MODULE CONSTANT, so the conjunct is that the run
    RECORDED the constant of record, not that a flag was passed."""
    salt = (run_manifest or {}).get("world_seed_salt")
    fb = [(_get(m or {}, "resolved_config.world_seed_salt"), p)
          for p, m in leg_manifests]
    fb_ok = (all(v == WORLD_SEED_SALT for v, _ in fb) if fb else None)
    missing_cap_seed = sorted(r for r, m in (arms_index or {}).items()
                              if m.get("cap_seed") is None)
    conj = {
        "world_seed_salt_of_record": salt == WORLD_SEED_SALT,
        "deployed_cap_j_is_4": (plan or {}).get("deployed_cap_j") == DEPLOYED_CAP_J,
        "cap_seed_present_for_every_rid":
            bool(arms_index) and not missing_cap_seed,
    }
    if salt is None and fb_ok is not None:
        conj["world_seed_salt_of_record"] = fb_ok
    bad = sorted(k for k, v in conj.items() if not v)
    return _gate(
        "G-SALT", not bad,
        "RUN/RUN_MANIFEST_R5.json::world_seed_salt · "
        "RUN/corpus/positions_s2/POSITIONS_PLAN.json::deployed_cap_j · "
        "RUN/ARMS_R5.json::<rid>.cap_seed · fallback "
        "RUN/legs/s2/tier1-greedy/walled/leg<N>/manifest.json::"
        "resolved_config.world_seed_salt",
        None if not bad else
        f"G-SALT row FAILED on conjunct(s) {bad}"
        + (f"; {len(missing_cap_seed)} rid(s) carry no cap_seed, e.g. "
           f"{missing_cap_seed[:5]}" if missing_cap_seed else ""),
        conjuncts=conj, world_seed_salt=salt,
        expected_world_seed_salt=WORLD_SEED_SALT,
        deployed_cap_j=(plan or {}).get("deployed_cap_j"),
        n_cap_seed_missing=len(missing_cap_seed), leg_fallback_ok=fb_ok)


def gate_backend(run_manifest, leg_manifests) -> dict:
    """`G-BACKEND` — `arb_backend == "rust"`; every `tier1-greedy/walled` leg
    resolves `rust`; `arb_legal_mask_cache == true`."""
    by_leg = (run_manifest or {}).get("resolved_backend_by_leg") or {}
    arb_legs = {k: v for k, v in by_leg.items() if k.startswith(JUDGE_ARBITER)}
    fb = [(_get(m or {}, "resolved_config.legal_mask_cache"), p)
          for p, m in leg_manifests]
    fb_ok = (all(v is True for v, _ in fb) if fb else None)
    cache = (run_manifest or {}).get("arb_legal_mask_cache")
    conj = {
        "arb_backend_is_rust": (run_manifest or {}).get("arb_backend") == "rust",
        "every_arbiter_leg_resolves_rust":
            bool(arb_legs) and all(v == "rust" for v in arb_legs.values()),
        "arb_legal_mask_cache_true": cache is True,
    }
    if cache is None and fb_ok is not None:
        conj["arb_legal_mask_cache_true"] = fb_ok
    bad = sorted(k for k, v in conj.items() if not v)
    return _gate(
        "G-BACKEND", not bad,
        "RUN/RUN_MANIFEST_R5.json::{arb_backend, resolved_backend_by_leg, "
        "arb_legal_mask_cache} · fallback RUN/legs/s2/tier1-greedy/walled/"
        "leg<N>/manifest.json::resolved_config.legal_mask_cache",
        None if not bad else f"G-BACKEND row FAILED on conjunct(s) {bad}",
        conjuncts=conj, n_arbiter_legs=len(arb_legs), leg_fallback_ok=fb_ok)


def gate_ddraw(d_draw) -> dict:
    """`G-DDRAW` — `d_draw_ran == true`. R2: either the conjunct exists or the
    discharge claim goes; the conjunct exists."""
    ok = bool(d_draw.get("d_draw_ran"))
    return _gate(
        "G-DDRAW", ok,
        "READOUT::widening.j_rider.d_draw.d_draw_ran · RUN/D_DRAW.json",
        None if ok else
        "G-DDRAW row FAILED: D_DRAW.json was not supplied or does not report a "
        "completed run, so rider I7's dedupe-partition conditional is NOT "
        "discharged. The previous revision CLAIMED W9 discharged it while the "
        "mechanical rule still permitted the R4 outcome — the conjunct exists "
        "precisely so the claim cannot outrun the artifact.",
        d_draw_ran=ok, n_checked=d_draw.get("n_checked"),
        agreement_rate=d_draw.get("agreement_rate"))


def gate_leaf(run_manifest, smoke) -> dict:
    """`G-LEAF` (carried) — the harness leaf hash equals the expected one.

    ⚠️ SPEC GAP, REPORTED NOT RESOLVED: READ_RULE §2's carried-gate row spells
    this address only as "as carried"; the concrete spelling comes from the
    R3.3/R4 emitters (`preflight.checks.leaf_hash`). It is named here so the
    gate binds; if the pair later spells it differently, THIS is the line to
    change."""
    src = None
    for name, d in (("RUN_MANIFEST_R5.json", run_manifest),
                    ("SMOKE_R5.json", smoke)):
        if _get(d or {}, "preflight.checks.leaf_hash") is not None:
            src = (name, _get(d, "preflight.checks.leaf_hash"))
            break
    if src is None:
        return _gate("G-LEAF", False,
                     "RUN/RUN_MANIFEST_R5.json::preflight.checks.leaf_hash "
                     "(fallback RUN/SMOKE_R5.json::preflight.checks.leaf_hash)",
                     "G-LEAF row UNRESOLVED: neither manifest carries "
                     "preflight.checks.leaf_hash — ABSENT IS FAIL (READ_RULE "
                     "§1). Carried gate, address 'as carried' in §2.")
    name, lh = src
    ok = bool(lh.get("ok")) and lh.get("harness_leaf_hash") == lh.get("expected")
    return _gate("G-LEAF", ok,
                 f"RUN/{name}::preflight.checks.leaf_hash",
                 None if ok else
                 f"G-LEAF row FAILED: harness_leaf_hash "
                 f"{lh.get('harness_leaf_hash')!r} != expected "
                 f"{lh.get('expected')!r}",
                 source=name, leaf_hash=lh)


def gate_prefix(uncapped) -> dict:
    """`G-PREFIX` (carried) — the per-rid EXACT prefix+append identity between
    `arms` and `arms_full`.

    ⚠️ A naive `arms == arms_full` fails ~16% of rids BY DESIGN: the champion
    pick is APPENDED when its transposition rep is absent from the tie set. The
    conjunct is the exact prefix+append identity, which `AW.build_rows` already
    counts per rid — this gate READS those counters rather than recomputing."""
    n = (uncapped or {}).get("n_rids", 0)
    ok = bool(n) and (uncapped or {}).get("n_prefix_ok") == n
    return _gate("G-PREFIX", ok,
                 "analyze_widening.build_rows uncapped counters "
                 "(n_rids / n_prefix_ok), over RUN/ARMS_R5.json::<rid>."
                 "{arms, arms_full}",
                 None if ok else
                 f"G-PREFIX row FAILED: {n - (uncapped or {}).get('n_prefix_ok', 0)}"
                 f" of {n} rid(s) break the prefix identity arms[:len(arms_full)]"
                 f" == arms_full",
                 n_rids=n, n_prefix_ok=(uncapped or {}).get("n_prefix_ok"),
                 violations=(uncapped or {}).get("violations", [])[:10])


def gate_uncapped(plan, uncapped) -> dict:
    """`G-UNCAPPED` (carried) — `uncapped == true`, `cap_j == null`, and the
    per-rid prefix+append identity. Delegated to `AW.uncapped_gate` VERBATIM."""
    blk = AW.uncapped_gate({STRATUM: plan or {}}, {STRATUM: uncapped or {}})
    ok = bool(blk.get("ok"))
    return _gate("G-UNCAPPED", ok, blk.get("resolved_at"),
                 None if ok else
                 "G-UNCAPPED row FAILED: the conjunct is uncapped == true AND "
                 "cap_j == null AND zero prefix+append violations "
                 "(analyze_widening.uncapped_gate)",
                 **{k: v for k, v in blk.items()
                    if k not in ("ok", "resolved_at")})


def gate_draw(draw) -> dict:
    """`G-DRAW` (carried) — the recorded `J = 4` subset is exactly this repo's
    own seeded draw at the run's git rev.

    ⚠️ Rider `I7-draw-scope`: it asserts NOTHING about the DEPLOYED rust draw."""
    if draw is None:
        return _gate("G-DRAW", False, "RUN/GATE_DRAW_R5.json::{ok, n_mismatch, "
                     "deployed_cap_j}",
                     "G-DRAW row UNRESOLVED: GATE_DRAW_R5.json absent or "
                     "unreadable — ABSENT IS FAIL (READ_RULE §1)")
    conj = {"ok": draw.get("ok") is True,
            "n_mismatch_is_0": draw.get("n_mismatch") == 0,
            "deployed_cap_j_is_4": draw.get("deployed_cap_j") == DEPLOYED_CAP_J}
    bad = sorted(k for k, v in conj.items() if not v)
    return _gate("G-DRAW", not bad,
                 "RUN/GATE_DRAW_R5.json::{ok, n_mismatch, deployed_cap_j}",
                 None if not bad else f"G-DRAW row FAILED on conjunct(s) {bad}",
                 conjuncts=conj, n_checked=draw.get("n_checked"),
                 scope="I7-draw-scope: asserts nothing about the DEPLOYED rust "
                       "draw")


def gate_crn(crn_by_stratum, smoke_paths) -> dict:
    """`G-CRN` (carried) — delegated to `AW.crn_gate` VERBATIM."""
    blk = AW.crn_gate(crn_by_stratum, list(smoke_paths or []))
    ok = bool(blk.get("ok"))
    return _gate("G-CRN", ok, blk.get("resolved_at"),
                 None if ok else
                 "G-CRN row FAILED: the conjuncts are per-judge smoke witness "
                 "true AND n_crn_verified == n_ok on every leg AND EXACTLY ONE "
                 "witness kind per judge (a leg set mixing witness kinds is a "
                 "harness error, not a CRN failure)",
                 **{k: v for k, v in blk.items()
                    if k not in ("ok", "resolved_at")})


def gate_arms(arms_by_stratum) -> dict:
    """`G-ARMS` (carried) — delegated to `AW.arms_gate_block` VERBATIM. Per ARM,
    not per ply: every full-set arm scored on ALL `M` worlds."""
    blk = AW.arms_gate_block(arms_by_stratum, include_partial=False)
    ok = bool(blk.get("ok"))
    return _gate("G-ARMS", ok, blk.get("resolved_at"),
                 None if ok else
                 f"G-ARMS row FAILED: n_arms_complete "
                 f"({blk.get('n_arms_complete')}) != n_arms "
                 f"({blk.get('n_arms')}) — an arm short of M worlds makes its "
                 f"rid non-analysable under include_partial == false",
                 **{k: v for k, v in blk.items()
                    if k not in ("ok", "resolved_at")})


def gate_bitexact(instrument) -> dict:
    """`G-BITEXACT@HEAD` (carried) — the rust ARB judge prices this run, so its
    identity gate carries."""
    if instrument is None:
        return _gate("G-BITEXACT@HEAD", False,
                     "RUN/GATE_BITEXACT_HEAD.json::{pass, digests_equal, "
                     "n_value_mismatch} · RUN/INSTRUMENT_IDENTITY_R5.json::"
                     "{committed_diff.empty, working_tree.by_box.<box>.clean}",
                     "G-BITEXACT@HEAD row UNRESOLVED: neither the bit-exactness "
                     "report nor the instrument-identity artifact is present — "
                     "ABSENT IS FAIL (READ_RULE §1)")
    conj = {}
    if "pass" in instrument or "digests_equal" in instrument:
        conj["pass"] = instrument.get("pass") is True
        conj["digests_equal"] = instrument.get("digests_equal") is True
        conj["n_value_mismatch_is_0"] = instrument.get("n_value_mismatch") == 0
    else:
        boxes = _get(instrument, "working_tree.by_box") or {}
        conj["committed_diff_empty"] = _get(instrument, "committed_diff.empty") is True
        conj["every_box_clean"] = bool(boxes) and all(
            (b or {}).get("clean") is True for b in boxes.values())
    bad = sorted(k for k, v in conj.items() if not v)
    return _gate("G-BITEXACT@HEAD", not bad,
                 "RUN/GATE_BITEXACT_HEAD.json::{pass, digests_equal, "
                 "n_value_mismatch} · RUN/INSTRUMENT_IDENTITY_R5.json::"
                 "{committed_diff.empty, working_tree.by_box.<box>.clean}",
                 None if not bad else
                 f"G-BITEXACT@HEAD row FAILED on conjunct(s) {bad}",
                 conjuncts=conj)


def gate_twobox(merge) -> dict:
    """`G-TWOBOX` — `../DEVIATIONS.md` §D1/§D3/§D4.13 as ruled, witnessed by the
    two-box merge report."""
    if merge is None:
        return _gate("G-TWOBOX", False, "RUN/MERGE_REPORT_s2.json",
                     "G-TWOBOX row UNRESOLVED: MERGE_REPORT_s2.json absent or "
                     "unreadable — ABSENT IS FAIL (READ_RULE §1)")
    problems = merge.get("problems") or []
    conj = {"merge_ok": merge.get("ok") is True,
            "no_problems": not problems,
            "not_dry_run": merge.get("dry_run") is not True}
    bad = sorted(k for k, v in conj.items() if not v)
    return _gate("G-TWOBOX", not bad, "RUN/MERGE_REPORT_s2.json::{ok, problems, "
                 "dry_run, legs}",
                 None if not bad else
                 f"G-TWOBOX row FAILED on conjunct(s) {bad}"
                 + (f"; first problem: {problems[0]!r}" if problems else ""),
                 conjuncts=conj, n_problems=len(problems),
                 problems=problems[:5],
                 n_records_present=merge.get("n_records_present"))


#: ⛔ `G-REPLICATE` is DROPPED in R5 — DELIBERATELY, and WITH THIS SENTENCE
#: rather than silently, because R2's objection was the silence, not the drop.
GATES_DROPPED = {
    "G-REPLICATE": "DROPPED deliberately (READ_RULE §0): its (B <= 16, E = 16) "
                   "corner is S1's, and S1 is not this run's stratum. Dropped "
                   "with this sentence rather than silently — R2's objection "
                   "was the silence, not the drop.",
}


# --------------------------------------------------------------------------- #
# record discovery                                                              #
# --------------------------------------------------------------------------- #
def discover_judge(legs_root: Path, judge: str, profile: str) -> tuple:
    """`{rid: {leg: record}}` for one judge, from
    `<legs_root>/<judge>/<profile>/leg<r>/records/<rid>.json`.

    `AT.discover_records` walks `<root>/<profile>/leg<r>/records/*.json`, so the
    root it wants is `<legs_root>/<judge>` — the SAME walker Stage 1 and W3 use,
    including its duplicate-record refusal."""
    root = Path(legs_root) / judge
    if not root.is_dir():
        raise SystemExit(
            f"REFUSING: the {judge!r} leg tree does not exist at {root}. The "
            f"merged layout is RUN/legs/{STRATUM}/<judge>/{profile}/leg<r>/"
            f"records/<rid>.json; without the ORACLE ({JUDGE_ORACLE}) side "
            f"there is no Delta_ora to adjudicate, and without the ARBITER "
            f"({JUDGE_ARBITER}) side the deploy rider has nothing to ride on.")
    by_rid, present, not_ok = AT.discover_records(root, only_profiles={profile})
    return by_rid, present, not_ok


def leg_rid_sets(by_rid: dict) -> dict:
    """`{leg: {rid, …}}` — the OBSERVED per-leg rid sets, for G-STAGED's exact
    predicate. Built from what is on disk, never from the plan."""
    out = {}
    for rid, legs in (by_rid or {}).items():
        for leg in legs:
            out.setdefault(int(leg), set()).add(rid)
    return out


# --------------------------------------------------------------------------- #
# assembly                                                                      #
# --------------------------------------------------------------------------- #
def assemble_readout(*, s2, branch, xfree, gates, gates_ok, s2_n, failed,
                     supply_chain, d_draw, provenance, config) -> dict:
    """The addressed machine surface. ⭐ `s2` is `AW.j_rider_block`'s output with
    the private working values stripped and `xfree_window` re-prosed."""
    fired = branch["fired"]
    j_s2 = {
        "delta_ora": s2.get("delta_ora"),
        "ci95_ora": AW.ci95_of(s2.get("ci95_ora")),
        "r_ora": s2.get("r_ora"),
        "ci95_r_ora": s2.get("ci95_r_ora"),
        "r_ora_reported": bool(s2.get("r_ora_reported")),
        "ora_j4_ci95": AW.ci95_of(s2.get("ora_j4_ci95")),
        "delta_arb": s2.get("delta_arb"),
        "ci95_arb": AW.ci95_of(s2.get("ci95_arb")),
        "n_capped": int(s2.get("n_capped") or 0),
        "xfree_window": xfree,
        # non-addressed context, reported because §6 asks for it
        "se_ora": s2.get("se_ora"), "z_ora": s2.get("z_ora"),
        "significant_ora": s2.get("significant_ora"),
        "ora_full": s2.get("ora_full"), "ora_j4": s2.get("ora_j4"),
        "n_roots": s2.get("n_roots"), "e_worlds": s2.get("e_worlds"),
        "adjudication": (
            f"{JUDGE_ORACLE} is the ORACLE and ADJUDICATES; {JUDGE_ARBITER} is "
            f"the ARBITER and RIDES — delta_arb / R_arb are DEPLOY RIDERS and "
            f"adjudicate nothing. Significance is ONE test, taken ONCE, on the "
            f"pre-committed percentile ROOT bootstrap "
            f"({BOOT_REPS} reps, seed {BOOT_SEED}, cluster = root_id)."),
    }
    widening = {
        "stratum": STRATUM,
        "j_rider": {
            "s2": j_s2,
            # ⛔ P1 — carried S1 addresses, present with their ABSENCE WITNESS
            # and NO value of any kind. See `s1_rider_absence_block`.
            "s1_replication": s1_rider_absence_block(
                "widening.j_rider.s1_replication"),
            "interaction": s1_rider_absence_block(
                "widening.j_rider.interaction"),
            "d_draw": d_draw,
        },
        "completion": {
            "s2_n": s2_n,
            "floor": gates["G-COMPLETE"]["detail"].get("floor"),
            "n2_committed": gates["G-COMPLETE"]["detail"].get("n2_committed"),
            "evaluated_after_exclusions": True,
        },
        "failed": failed,
        "gates": gates,
        "gates_ok": gates_ok,
        "gates_dropped": GATES_DROPPED,
        "supply_chain": supply_chain,
        "branch": branch,
        "markers": {
            "marker": MARKER,
            "addresses": list(SCHEMA_ADDRESSES),
            "n_addresses": len(SCHEMA_ADDRESSES),
            "rule": ("READ_RULE §1: every address carries EXACTLY ONE "
                     "existence-time marker, and every address THIS file writes "
                     f"is {MARKER} — it exists only after scoring. 'as carried' "
                     "is not a marker."),
            "audited_by": ("A3, before adjudication. ⭐ The A1 pass audits THIS "
                           "LIST against the committed fixture, so an address "
                           "added here without its fixture entry FAILS A1 "
                           "rather than passing silently."),
            "fixture_naming_conflict": FIXTURE_NAMING_CONFLICT,
        },
        "config": config,
    }
    return {"generated_utc": AT._now_utc(),
            "run": "tiearb_widening_20260817 rung3_r5",
            "read_rule": "measurement/tiearb_widening_20260817/rung3_r5/"
                         "READ_RULE.md rev R5.1",
            "provenance": provenance,
            "widening": widening,
            "_fired_branch": fired}


def build_branch_block(decision: dict, xfree: dict, gates_ok: bool,
                       failing_gates: list) -> dict:
    """`widening.branch` — the branch table's verdict, or `W-UNREADABLE`.

    ⚠️ P2 lives here. On the LICENSED path exactly ONE branch token is written:
    the fired one. On the UNREADABLE path NO branch token is written at all —
    §2's "Any FAIL ⇒ W-UNREADABLE; nothing licensed" plus §7's blindness rule,
    which together mean a fixing session must not be able to read the verdict
    off a read-out whose gates failed.

    ⛔ The non-fired rows are NEVER narrated. No "just missed", no "would have
    fired at", no enumeration "for context" — those are the shapes that put a
    second token on the page.
    """
    prints = mandatory_prints(xfree)
    if not gates_ok:
        return {
            "fired": "W-UNREADABLE",
            "licensed": False,
            "reasons": [
                "a READ_RULE §2 gate FAILED ⇒ W-UNREADABLE; NOTHING is "
                "licensed.",
                "the branch table's verdict is NOT printed on this path (§7 "
                "blindness): a fixing session reads the failing gate's inputs "
                "and stays blind to the outcome.",
                "failing gate(s): " + ", ".join(failing_gates),
            ],
            "mandatory_prints": prints,
            "failing_gates": failing_gates,
            "guard_fired": None,
            "r_ora_reported": None,
            "noise_rider": None,
        }
    reasons = [
        decision.get("reason"),
        "READ_RULE §5, read IN ORDER, FIRST MATCH WINS; the table is TOTAL by "
        "row 6, so exactly one row fires for every input.",
    ]
    if decision.get("guard_fired"):
        reasons.append(
            "PRE-BRANCH GUARD FIRED: lower(CI95(ora_J4)) <= 0, so R_ora is "
            "DEGENERATE and is NOT reported — r_ora and ci95_r_ora go to null "
            "TOGETHER, and adjudication runs on Delta_ora alone via the "
            "committed sub-table.")
    else:
        reasons.append(
            "the pre-branch guard did NOT fire: lower(CI95(ora_J4)) > 0, so "
            "R_ora is a ratio of like quantities and IS reported.")
    if decision.get("x_noise"):
        reasons.append(
            "ARBITER NOISE RIDER FIRES: upper(CI95(Delta_arb)) < 0 while "
            "lower(CI95(Delta_ora)) > 0. It is NON-ADJUDICATING and does not "
            "change which row fired — the oracle adjudicates, the arbiter "
            "rides.")
    return {
        "fired": decision["branch"],
        "licensed": True,
        "reasons": [r for r in reasons if r],
        "mandatory_prints": prints,
        "guard_fired": bool(decision.get("guard_fired")),
        "r_ora_reported": bool(decision.get("r_ora_reported")),
        "noise_rider": bool(decision.get("x_noise")),
        "table_source": "analyze_widening.decide_rung3 — READ_RULE §5's table "
                        "VERBATIM (carried unchanged from R3.3 §5: not one "
                        "threshold, sign or condition moves)",
        "non_fired_rows": "NOT NARRATED. The rows that did not fire are named "
                          "in the READ_RULE and nowhere in this read-out — a "
                          "near-miss narration is how a second branch token "
                          "ends up on a page that fired one.",
    }


def supply_chain_block(corpus, dupe, staging, floors, params=None) -> dict:
    """§6 — the supply chain from `CORPUS_R5.json`'s REALIZED integers, plus the
    dupe-group consistency result and §2.1's statement about what the two
    degeneracy gates DO and DO NOT establish."""
    c = corpus or {}
    return {
        "n_in": c.get("n_in"),
        "n_excluded_r5": c.get("n_excluded_r5"),
        "n_positions": c.get("n_positions"),
        "n_distinct_seeds": c.get("n_distinct_seeds"),
        "n_out_of_band": c.get("n_out_of_band"),
        "n_seeds_136e9": c.get("n_seeds_136e9"),
        "max_positions_per_seed": c.get("max_positions_per_seed"),
        "excluded_rids": sorted(c.get("excluded_rids") or []),
        "seed_ranges": c.get("seed_ranges"),
        "leg_path": c.get("leg_path"),
        "leg_sha256": c.get("leg_sha256"),
        "arms_r5_sha256": c.get("arms_r5_sha256"),
        "provenance": c.get("provenance"),
        "staged": {
            "n_leg_rids": (staging or {}).get("n_leg_rids"),
            "n_arms_rids": (staging or {}).get("n_arms_rids"),
            "n_total_pairs": (staging or {}).get("n_total_pairs"),
            "leg_ladder_expected": list(
                (params or {}).get("leg_ladder") or LEG_LADDER_EXPECTED),
            "n_chunks": (staging or {}).get("n_chunks"),
        },
        "committed_parameters": params,
        "internal_dupe": {
            "d_internal": (dupe or {}).get("d_internal"),
            "guard": 0.05,
            "n_dupe_groups": (dupe or {}).get("n_dupe_groups"),
            "n_dupe_positions": (dupe or {}).get("n_dupe_positions"),
            "ply_histogram": (dupe or {}).get("ply_histogram"),
            "band_pairs": (dupe or {}).get("band_pairs"),
            "what_it_establishes": (
                "READ_RULE §2.1: BOTH degeneracy gates are CORPUS-IDENTITY "
                "checks, NOT discovery gates. The collision quantity for this "
                "corpus was already known (3 groups / 6 positions) because the "
                "calibration measured the SAME PHYSICAL FILE. Their live "
                "content is 'the corpus is the one that was measured' — a real "
                "and falsifiable property (a different leg file, a re-mine, a "
                "truncated read all fail it) — and it is ALL they establish."),
        },
        "d_model_fit": {
            "form": "d_model(G) = a * G^b",
            "r_squared": 1.0,
            "status": "VACUOUS — reported because §6 requires it, and marked "
                      "vacuous because r^2 = 1.0 on a fit with as many "
                      "parameters as points says nothing. ⛔ It is NOT the "
                      "bound; the absolute 5% guard is.",
        },
        "floors_source": {
            "n2": (floors or {}).get("n2"),
            "gate_floor": (floors or {}).get("gate_floor"),
            "floor_fraction": (floors or {}).get("floor_fraction"),
            "failed_record_bound_frac": (floors or {}).get(
                "failed_record_bound_frac"),
        },
    }


# --------------------------------------------------------------------------- #
# fixture (A1) — key set == schema address set, TYPES ONLY                       #
# --------------------------------------------------------------------------- #
def build_fixture() -> dict:
    """The `A1` fixture: the schema's address tree with JSON-TYPE-NAME leaves.

    ⚠️ **NO VALUES.** `A1` runs `[pre-corpus]`, before the blind commit — key
    presence and JSON type only, no value computed, printed or stored. A leaf
    here is the NAME of a type, never an exemplar of one.
    """
    out: dict = {}
    for addr in SCHEMA_ADDRESSES:
        parts = addr.split(".")
        cur = out
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = SCHEMA_TYPES[addr]
    return out


def fixture_target(run_dir: Path, explicit=None) -> dict:
    """Which fixture filename to write, and the DISCLOSURE of the conflict."""
    fx_dir = Path(run_dir) / "fixtures"
    preferred = fx_dir / FIXTURE_PREFERRED
    accepted = fx_dir / FIXTURE_ACCEPTED
    path = Path(explicit) if explicit else preferred
    return {
        "path": str(path),
        "name_used": Path(path).name,
        "preferred": FIXTURE_PREFERRED,
        "accepted_alternative": FIXTURE_ACCEPTED,
        "preferred_exists": preferred.is_file(),
        "accepted_alternative_exists": accepted.is_file(),
        "conflict": FIXTURE_NAMING_CONFLICT,
    }


# --------------------------------------------------------------------------- #
# the human-readable report                                                     #
# --------------------------------------------------------------------------- #
def render_md(v: dict) -> str:
    w = v["widening"]
    br = w["branch"]
    L = [f"# RUNG 3 (`J > 4`) — READ-OUT, rev R5.1 (stratum `{STRATUM}`)", "",
         f"generated: {v['generated_utc']}",
         f"read rule: `{v['read_rule']}`", "",
         "> Significance is ONE test, taken ONCE: `lower(CI95) > 0` on the",
         f"> pre-committed percentile ROOT bootstrap ({BOOT_REPS} reps, seed",
         f"> {BOOT_SEED}, cluster = `root_id`).",
         f"> `{JUDGE_ORACLE}` is the ORACLE and ADJUDICATES; `{JUDGE_ARBITER}`",
         "> is the ARBITER and RIDES — it adjudicates nothing.", "",
         "## Gates (READ_RULE §2 — every row resolved, none short-circuited)",
         "", "| gate | verdict | resolved_at |", "|---|---|---|"]
    for name, g in sorted(w["gates"].items()):
        L.append(f"| `{name}` | {'PASS' if g['ok'] else 'FAIL'} | "
                 f"`{g.get('resolved_at') or 'UNRESOLVED'}` |")
    for name, why in sorted(w["gates_dropped"].items()):
        L.append(f"| `{name}` | DROPPED | — |")
    L += ["", f"gate set: **{'ALL PASS' if w['gates_ok'] else 'FAIL'}** "
              f"({len(w['gates'])} rows resolved)", ""]
    for name, g in sorted(w["gates"].items()):
        if not g["ok"] and g.get("why"):
            L += [f"- ⛔ `{name}`: {g['why']}"]
    if any(not g["ok"] for g in w["gates"].values()):
        L.append("")
    for name, why in sorted(w["gates_dropped"].items()):
        L += [f"- ⛔ `{name}`: {why}", ""]

    if not w["gates_ok"]:
        # READ_RULE §2 + §7: on any gate FAIL this report prints GATE INPUTS
        # ONLY — no ora, no Delta, no CI, no per-position statistic — so a
        # fixing session can read it and stay blind.
        L += ["## ⛔ W-UNREADABLE — GATE INPUTS ONLY", "",
              "A §2 gate FAILED. Nothing is licensed, the branch table's",
              "verdict is not printed, and this report carries gate inputs and",
              "nothing else (§7 blindness).", "", "```json",
              json.dumps({"gates": w["gates"],
                          "completion": w["completion"],
                          "failed": w["failed"],
                          "supply_chain": w["supply_chain"]},
                         indent=2, sort_keys=True, default=str),
              "```", ""]
        return "\n".join(L) + "\n"

    s2 = w["j_rider"]["s2"]
    L += ["## Rung 3 — the primary", "",
          "| quantity | value | CI95 |", "|---|---|---|",
          f"| `Delta_ora` (ora_full − ora_J4, capped plies) | "
          f"{AW._f(s2['delta_ora'])} | {AW._ci(s2['ci95_ora'])} |",
          f"| `ora_J4` (the ratio's denominator) | {AW._f(s2['ora_j4'])} | "
          f"{AW._ci(s2['ora_j4_ci95'])} |",
          f"| `R_ora` (ora_full / ora_J4) | "
          f"{AW._f(s2['r_ora']) if s2['r_ora_reported'] else 'NOT REPORTED'} | "
          f"{AW._ci(s2['ci95_r_ora']) if s2['r_ora_reported'] else 'DEGENERATE'} |",
          f"| `Delta_arb` (deploy RIDER — adjudicates nothing) | "
          f"{AW._f(s2['delta_arb'])} | {AW._ci(s2['ci95_arb'])} |", "",
          f"`n_capped` = {s2['n_capped']} over {s2['n_roots']} roots at "
          f"`E = {s2['e_worlds']}`.", "",
          f"## Branch: `{br['fired']}`", ""]
    for r in br["reasons"]:
        L.append(f"- {r}")
    L += ["", "### Mandatory prints (READ_RULE §5 — on every branch)", ""]
    mp = br["mandatory_prints"]
    L += [f"1. {mp['i_separability_1400_vs_1244']}", "",
          f"2. {mp['ii_0842_unresolved_at_bracket_top']}", "",
          f"3. {mp['iii_attainability_window_at_realized_se']}", "",
          f"   window (`xfree_window`): lo = {AW._f(mp['iii_window']['lo'])}, "
          f"hi = {AW._f(mp['iii_window']['hi'])}, "
          f"half_width = {AW._f(mp['iii_window']['half_width'])}, "
          f"empty = {mp['iii_window']['empty']}", "",
          f"⛔ {br['non_fired_rows']}", "",
          "## Riders", "",
          f"- `d_draw`: ran = {w['j_rider']['d_draw']['d_draw_ran']}, "
          f"n_checked = {w['j_rider']['d_draw']['n_checked']}, "
          f"agreement_rate = {AW._f(w['j_rider']['d_draw']['agreement_rate'])} "
          f"— reports the MAGNITUDE of rider I7's dedupe-partition conditional "
          f"and adjudicates nothing.",
          f"- `s1_replication` / `interaction`: {S1_ABSENCE_WITNESS}", "",
          "## Completion, failures, supply chain", "",
          f"- `completion.s2_n` = {w['completion']['s2_n']} against the "
          f"committed floor {w['completion']['floor']} "
          f"(= ceil(0.95 x {w['completion']['n2_committed']})), evaluated "
          f"AFTER exclusions and "
          f"AFTER the §3 whole-rid drop.",
          f"- `failed`: {w['failed']['n_failed_rids']} rid(s) of "
          f"{w['failed']['n_attempted']} attempted = "
          f"{AW._f(w['failed']['rate'], 5)} against the bound "
          f"{FAILED_BOUND_FRAC}; by class {w['failed']['by_class']}.",
          f"- {w['failed']['corrected_expectation_r5']}",
          f"- supply chain: n_in = {w['supply_chain']['n_in']}, "
          f"n_excluded_r5 = {w['supply_chain']['n_excluded_r5']}, "
          f"n_positions = {w['supply_chain']['n_positions']}, "
          f"n_distinct_seeds = {w['supply_chain']['n_distinct_seeds']}, "
          f"max_positions_per_seed = "
          f"{w['supply_chain']['max_positions_per_seed']}.",
          f"- `d_internal` = "
          f"{AW._f(w['supply_chain']['internal_dupe']['d_internal'], 6)} "
          f"against the absolute 0.05 guard. "
          f"{w['supply_chain']['internal_dupe']['what_it_establishes']}",
          f"- `d_model(G) = a*G^b`: "
          f"{w['supply_chain']['d_model_fit']['status']}", "",
          "## Existence-time markers", "",
          f"Every address this file writes is `{MARKER}`. "
          f"{w['markers']['rule']}", "",
          f"{w['markers']['audited_by']}", "",
          f"⚠️ {w['markers']['fixture_naming_conflict']}", ""]
    L += ["Addresses:", ""]
    for a in w["markers"]["addresses"]:
        L.append(f"- `{a}` `{MARKER}`")
    L.append("")
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------- #
# CLI                                                                           #
# --------------------------------------------------------------------------- #
def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", required=True,
                    help="the RUN dir (rung3_r5). Every other path defaults "
                         "inside it.")
    ap.add_argument("--legs-root", default=None,
                    help=f"default <RUN>/legs/{STRATUM}")
    ap.add_argument("--arms", default=None, help="default <RUN>/ARMS_R5.json")
    ap.add_argument("--corpus", default=None, help="default <RUN>/CORPUS_R5.json")
    ap.add_argument("--staging", default=None, help="default <RUN>/STAGING_R5.json")
    ap.add_argument("--internal-dupe", default=None,
                    help="default <RUN>/GATE_INTERNAL_DUPE.json")
    ap.add_argument("--disjoint", default=None,
                    help="default <RUN>/GATE_DISJOINT_R5.json")
    ap.add_argument("--draw", default=None, help="default <RUN>/GATE_DRAW_R5.json")
    ap.add_argument("--bitexact", default=None,
                    help="default <RUN>/GATE_BITEXACT_HEAD.json, then "
                         "<RUN>/INSTRUMENT_IDENTITY_R5.json")
    ap.add_argument("--floors", default=None, help="default <RUN>/FLOORS_R5.json")
    ap.add_argument("--smoke", default=None, help="default <RUN>/SMOKE_R5.json")
    ap.add_argument("--run-manifest", default=None,
                    help="default <RUN>/RUN_MANIFEST_R5.json")
    ap.add_argument("--positions-plan", default=None,
                    help=f"default <RUN>/corpus/positions_{STRATUM}/"
                         f"POSITIONS_PLAN.json")
    ap.add_argument("--merge-report", default=None,
                    help=f"default <RUN>/MERGE_REPORT_{STRATUM}.json")
    ap.add_argument("--d-draw", default=None, help="default <RUN>/D_DRAW.json")
    ap.add_argument("--out-json", default=None,
                    help="default <RUN>/verdicts/READOUT_R5.json")
    ap.add_argument("--out-md", default=None,
                    help="default <RUN>/verdicts/READOUT_R5.md")
    ap.add_argument("--emit-fixture", action="store_true",
                    help=f"also write the A1 fixture (fixtures/"
                         f"{FIXTURE_PREFERRED}); TYPES ONLY, no values")
    ap.add_argument("--fixture-out", default=None)
    ap.add_argument("--dry-run", action="store_true",
                    help="compute and print, write nothing")
    ap.add_argument("--judge-oracle", default=JUDGE_ORACLE)
    ap.add_argument("--judge-arbiter", default=JUDGE_ARBITER)
    ap.add_argument("--profile", default=PROFILE)
    ap.add_argument("--e-worlds", type=int, default=E_WORLDS)
    ap.add_argument("--m-expected", type=int, default=M_EXPECTED)
    ap.add_argument("--boot-reps", type=int, default=BOOT_REPS)
    ap.add_argument("--boot-seed", type=int, default=BOOT_SEED)
    ap.add_argument("--rnd-seed", type=int, default=AW.RND_SEED)
    ap.add_argument("--parity-base", type=int, choices=(0, 1),
                    default=AW.PARITY_BASE)
    return ap.parse_args(argv)


def refuse_to_overwrite(paths) -> None:
    """A superseded read-out is EVIDENCE and stays readable; what must be
    impossible is mistaking it for a verdict (§D4.18(d)). So this refuses to
    overwrite one, and the move-aside leaves a readable record of the gap."""
    existing = [str(p) for p in paths if Path(p).is_file()]
    if not existing:
        return
    raise SystemExit(
        "REFUSING to overwrite an existing read-out: " + ", ".join(existing)
        + f". §D4.18(d): a superseded artifact is EVIDENCE and stays readable "
        f"— what must be impossible is mistaking it for a verdict. Move it "
        f"aside with a suffix that makes invalidity obvious ON SIGHT "
        f"(`READOUT_R5.json{AW.INVALID_SUFFIX_CONVENTION}`), NAME THE MOVE in "
        f"the read-out's provenance, then re-run.")


def main(argv=None) -> int:
    a = parse_args(argv)
    run = Path(a.run)
    legs_root = Path(a.legs_root) if a.legs_root else run / "legs" / STRATUM
    arms_path = Path(a.arms) if a.arms else run / "ARMS_R5.json"
    out_json = Path(a.out_json) if a.out_json else run / "verdicts" / "READOUT_R5.json"
    out_md = Path(a.out_md) if a.out_md else run / "verdicts" / "READOUT_R5.md"

    def d(explicit, *rel):
        if explicit:
            return Path(explicit)
        for r in rel:
            p = run / r
            if p.is_file():
                return p
        return run / rel[0]

    p_corpus = d(a.corpus, "CORPUS_R5.json")
    p_staging = d(a.staging, "STAGING_R5.json")
    p_dupe = d(a.internal_dupe, "GATE_INTERNAL_DUPE.json")
    p_disjoint = d(a.disjoint, "GATE_DISJOINT_R5.json")
    p_draw = d(a.draw, "GATE_DRAW_R5.json")
    p_bitexact = d(a.bitexact, "GATE_BITEXACT_HEAD.json",
                   "INSTRUMENT_IDENTITY_R5.json")
    p_floors = d(a.floors, "FLOORS_R5.json")
    p_smoke = d(a.smoke, "SMOKE_R5.json")
    p_manifest = d(a.run_manifest, "RUN_MANIFEST_R5.json")
    p_plan = d(a.positions_plan, f"corpus/positions_{STRATUM}/POSITIONS_PLAN.json")
    p_merge = d(a.merge_report, f"MERGE_REPORT_{STRATUM}.json")
    p_ddraw = d(a.d_draw, "D_DRAW.json")

    if not a.dry_run:
        refuse_to_overwrite([out_json, out_md])

    # ---- the POPULATION AUTHORITY, READ (never re-derived by subtraction) ---- #
    arms_index = _load_json(arms_path)
    if not isinstance(arms_index, dict) or not arms_index:
        raise SystemExit(
            f"REFUSING: the population authority {arms_path} is absent, "
            f"unreadable or empty. DESIGN ruling 2026-08-19 shape (a): ONE "
            f"materialized authority that every consumer READS. Re-deriving "
            f"the population by subtraction here is shape (b) — D4 with the "
            f"operands swapped — and is not licensed.")

    # ---- records ------------------------------------------------------------ #
    if_by, if_present, if_notok = discover_judge(legs_root, a.judge_oracle,
                                                 a.profile)
    arb_by, arb_present, arb_notok = discover_judge(legs_root, a.judge_arbiter,
                                                    a.profile)
    observed_legs = leg_rid_sets(if_by)

    # ---- ⭐ THE ESTIMATOR IS AW's, WHOLE -------------------------------------- #
    rows, counts, arms_gate, crn, uncapped, failed_block = AW.build_rows(
        arms_index, if_by, arb_by, e_levels=(a.e_worlds,),
        m_expected=a.m_expected, parity_base=a.parity_base,
        rnd_seed=a.rnd_seed, stratum_tag=STRATUM)

    s2_raw = AW.j_rider_block(rows, a.e_worlds, a.boot_reps, a.boot_seed)
    decision = AW.decide_rung3(s2_raw.get("_d_ora") or {},
                               s2_raw.get("_r_ora") or {},
                               s2_raw.get("_ora_j4") or {},
                               s2_raw.get("_d_arb") or {})
    xfree = sanitized_xfree_window(
        s2_raw.get("xfree_window") or AW.xfree_window({}))
    s2 = AW._strip_private(s2_raw)

    # `s2_n` is AW's `completion_block` definition (capped rows among analysed),
    # lifted here because that function is S1+S2-shaped and R5 has ONE stratum:
    # calling it with an empty S1 would manufacture an S1 conjunct failure out
    # of a stratum that does not exist.
    s2_n = len([r for r in rows if r["capped_at_4"]])

    failed = {
        "n_failed_rids": failed_block.get("n_failed_rids", 0),
        "n_attempted": counts.get("planned", len(arms_index)),
        "rate": ((failed_block.get("n_failed_rids", 0)
                  / counts["planned"]) if counts.get("planned") else 0.0),
        "by_class": dict(Counter(
            c for r in failed_block.get("by_rid", [])
            for c in r.get("diagnostic_class", []))),
        "accounting": failed_block,
        "corrected_expectation_r5": (
            "READ_RULE §3, CORRECTED ON THE RECORD: R5's corpus sits slightly "
            "DEEPER than S1's (mean ply 69.15, median 68, max 142; 63.3% at "
            "ply >= 50; only 2.63% at ply <= 2, against S1's mean 66.50) — in "
            "exactly the region where the encoder-window limitation fires. The "
            "pre-registered expectation is therefore EQUAL-OR-HIGHER than S1's "
            "realized 0.30%, NOT lower. The inferential error, named so it is "
            "not repeated: the previous revision reasoned from the ply of the "
            "three COLLISIONS (forced early by the birthday argument) and "
            "generalised it to the ply of the CORPUS. Where collisions happen "
            "is not where the population lives."),
        "selection_effect_note": (
            "⚠️ AW.failed_record_block's `selection_effect` sentence is "
            "carried verbatim from S1 and quotes S1's realized 4 / 1,344 = "
            "0.30%. Those integers are S1's, NOT this run's; the DISCLOSURE it "
            "makes (the dropped set is correlated with board geometry) is what "
            "carries, and this run's own integers are the four fields above."),
    }

    # ---- artifacts ---------------------------------------------------------- #
    corpus = _load_json(p_corpus)
    staging = _load_json(p_staging)
    dupe = _load_json(p_dupe)
    dis = _load_json(p_disjoint)
    draw = _load_json(p_draw)
    bitexact = _load_json(p_bitexact)
    floors = _load_json(p_floors)
    smoke = _load_json(p_smoke)
    manifest = _load_json(p_manifest)
    plan = _load_json(p_plan)
    merge = _load_json(p_merge)

    leg_manifests = []
    for judge in (a.judge_oracle, a.judge_arbiter):
        for mp in sorted((legs_root / judge / a.profile).glob("leg*/manifest.json")):
            leg_manifests.append((str(mp), _load_json(mp)))

    dd = _load_json(p_ddraw) or {}
    d_draw = {
        "d_draw_ran": bool(dd),
        "n_checked": dd.get("n_checked"),
        "n_agree": dd.get("n_agree"),
        "agreement_rate": dd.get("agreement_rate"),
        "n_unreconstructible": dd.get("n_unreconstructible"),
        "source": str(p_ddraw) if dd else None,
        "adjudicates": "nothing — a reported magnitude, never a branch input. "
                       "It reports the MAGNITUDE of rider I7's unverified "
                       "dedupe-partition conditional.",
    }

    # ---- ⭐ EVERY §2 GATE, RESOLVED INDEPENDENTLY, NEVER SHORT-CIRCUITED ------ #
    # Each row is resolved in its own try/except: a row that raises becomes a
    # FAIL that names itself, and EVERY LATER ROW STILL RESOLVES AND REPORTS.
    # A gate set that stops at the first failure is a gate set whose later rows
    # were never checked — and "not checked" reads on the page as "passed".
    params = committed_parameters(floors, staging)
    resolvers = [
        ("G-CORPUS",
         lambda: gate_corpus(corpus, floors, arms_index, arms_path, params)),
        ("G-STAGED",
         lambda: gate_staged(staging, arms_index, observed_legs, params)),
        ("G-INTERNAL-DUPE", lambda: gate_internal_dupe(dupe, corpus)),
        ("G-DISJOINT", lambda: gate_disjoint(dis)),
        ("G-BAND", lambda: gate_band(corpus)),
        ("G-COMPLETE", lambda: gate_complete(s2_n, params)),
        ("G-FAILED", lambda: gate_failed(failed, failed["n_attempted"])),
        ("G-M", lambda: gate_m(manifest, smoke, leg_manifests)),
        ("G-SALT", lambda: gate_salt(manifest, plan, arms_index, leg_manifests)),
        ("G-BACKEND", lambda: gate_backend(manifest, leg_manifests)),
        ("G-DDRAW", lambda: gate_ddraw(d_draw)),
        ("G-LEAF", lambda: gate_leaf(manifest, smoke)),
        ("G-PREFIX", lambda: gate_prefix(uncapped)),
        ("G-CRN", lambda: gate_crn({STRATUM: crn},
                                   [p_smoke] if p_smoke.is_file() else [])),
        ("G-UNCAPPED", lambda: gate_uncapped(plan, uncapped)),
        ("G-DRAW", lambda: gate_draw(draw)),
        ("G-ARMS", lambda: gate_arms({STRATUM: arms_gate})),
        ("G-BITEXACT@HEAD", lambda: gate_bitexact(bitexact)),
        ("G-TWOBOX", lambda: gate_twobox(merge)),
    ]
    gates = {}
    for name, fn in resolvers:
        try:
            gates[name] = fn()
        except Exception as exc:                      # noqa: BLE001
            gates[name] = _gate(
                name, False, "UNRESOLVED",
                f"{name} row RAISED while resolving ({type(exc).__name__}: "
                f"{exc}). Recorded as a FAIL so the row is visible; every "
                f"later row was still resolved.",
                exception=f"{type(exc).__name__}: {exc}")
    gates_ok = all(g["ok"] for g in gates.values())
    failing = sorted(n for n, g in gates.items() if not g["ok"])

    branch = build_branch_block(decision, xfree, gates_ok, failing)

    fixture_info = fixture_target(run, a.fixture_out)
    verdict = assemble_readout(
        s2=s2, branch=branch, xfree=xfree, gates=gates, gates_ok=gates_ok,
        s2_n=s2_n, failed=failed,
        supply_chain=supply_chain_block(corpus, dupe, staging, floors, params),
        d_draw=d_draw,
        provenance={
            "population_authority": str(arms_path),
            "population_authority_rule":
                "READ, never re-derived by subtraction (DESIGN ruling "
                "2026-08-19, shape (a))",
            "legs_root": str(legs_root),
            "artifacts": {
                "corpus": str(p_corpus), "staging": str(p_staging),
                "internal_dupe": str(p_dupe), "disjoint": str(p_disjoint),
                "draw": str(p_draw), "bitexact": str(p_bitexact),
                "floors": str(p_floors), "smoke": str(p_smoke),
                "run_manifest": str(p_manifest), "positions_plan": str(p_plan),
                "merge_report": str(p_merge), "d_draw": str(p_ddraw),
            },
            "fixture": fixture_info,
            "estimator": "analyze_widening (build_rows / RootBoot / "
                         "j_rider_block / decide_rung3 / xfree_window) — this "
                         "module is a DRIVER and EMITTER only",
        },
        config={
            "stratum": STRATUM, "profile": a.profile,
            "judge_oracle": a.judge_oracle, "judge_arbiter": a.judge_arbiter,
            "e_worlds": a.e_worlds, "m_expected": a.m_expected,
            "boot_reps": a.boot_reps, "boot_seed": a.boot_seed,
            "rnd_seed": a.rnd_seed, "parity_base": a.parity_base,
            "counts": counts,
            "records_present": {"oracle": if_present, "arbiter": arb_present},
            "n_records_not_ok": {"oracle": len(if_notok),
                                 "arbiter": len(arb_notok)},
            "n_leg_manifests": len(leg_manifests),
            "significance": "lower(CI95) > 0 on the percentile root bootstrap",
        })
    fired = verdict.pop("_fired_branch")

    text_json = json.dumps(verdict, indent=2, sort_keys=True, default=str)
    text_md = render_md(verdict)

    # ---- ⛔ P2, ENFORCED AT THE EMITTER, not merely intended ------------------ #
    for label, text in (("READOUT_R5.json", text_json), ("READOUT_R5.md", text_md)):
        v = token_bar_violations(text, fired if gates_ok else None)
        if v["extra_tokens"] or v["void_token_present"]:
            raise SystemExit(
                f"REFUSING to emit {label}: the rung-3 token bar is broken. "
                f"Exactly ONE branch token may appear — the one that fired "
                f"({fired!r}) — and the R4 void token may appear NOWHERE (R5 "
                f"is the SUCCESSOR to that void, not a continuation of it). "
                f"Extra token(s): {v['extra_tokens']}; void token present: "
                f"{v['void_token_present']}. The non-fired rows must not be "
                f"narrated as near-misses.")

    if a.dry_run:
        print(text_md)
        print(f"[rung3_r5] DRY RUN — nothing written. branch = {branch['fired']} "
              f"| gates_ok = {gates_ok} | s2_n = {s2_n}")
        return 0

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(text_json)
    out_md.write_text(text_md)
    if a.emit_fixture:
        fp = Path(fixture_info["path"])
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(json.dumps(build_fixture(), indent=2, sort_keys=True))
        print(f"[rung3_r5] A1 fixture -> {fp} "
              f"(name used: {fixture_info['name_used']}; "
              f"conflict disclosed in the read-out)")
    print(f"[rung3_r5] READOUT -> {out_json}")
    print(f"[rung3_r5] report  -> {out_md}")
    print(f"[rung3_r5] gates_ok = {gates_ok} | branch = {branch['fired']} | "
          f"s2_n = {s2_n} | n_capped = {s2.get('n_capped')}")

    # ⚠️ The §2 CONSISTENCY raise is DEFERRED to here, AFTER every gate has been
    # resolved and the read-out written — so the refusal never costs the reader
    # the rest of the gate set.
    raisers = sorted(n for n, g in gates.items()
                     if g.get("detail", {}).get("raises"))
    if raisers:
        print(f"[rung3_r5] ⛔ RAISING ROW(S): {raisers} — READ_RULE §2 says a "
              f"mismatch on this conjunct RAISES. The read-out above is "
              f"complete; escalate rather than re-running.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
