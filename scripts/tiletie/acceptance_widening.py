#!/usr/bin/env python3
"""**W8** — the pre-run ACCEPTANCE TEST (DESIGN §9 steps 4a / 4b; rev R2).

Walks a committed address list and, for each address, reports **`resolved` /
`UNRESOLVED` plus the JSON TYPE of the value — and prints no value, ever.**
Primary and fallback are resolved **independently** (a fallback that is only
exercised the day it is needed is unaudited), across **both strata**, over every
address named in `READ_RULE.md` §2 (gates), §4/§5 (branch inputs) and
`DESIGN.md` §7 (the `c`-remeasure obligation, incl. `GEN_SMOKE.json` and the
realized-vs-committed block).

Why it exists: `READ_RULE` §1.2 makes ABSENT a FAIL and §1.4 forbids inventing
an address at read time. Five gates across the two review rounds named addresses
no emitter writes — each would have voided a HEALTHY run. This is the mechanical
form of §1.5's structural test (*would this gate fail on a healthy run?*).

THREE phases, because the artifacts appear at three different times (§0.G
re-split what R2 called 4a, after the executor found the judge smokes are NOT
corpus-free — see `book_4b_pre`):

  `--mode 4a`      PRE-BLIND-COMMIT, and now GENUINELY corpus-free:
                   (a) `live`    — `GATE_BITEXACT_HEAD.json`, nothing else.
                   (b) `fixture` — a STATIC SCHEMA AUDIT: W5 and W3 are run over
                                   committed synthetic fixtures in a scratch dir,
                                   and the `GATE_DISJOINT` / `GATE_DRAW` /
                                   `POSITIONS_PLAN` / `ARMS` /
                                   `READOUT::widening.*` / `per_position_*.jsonl`
                                   spellings — PLUS the two fixtures §0.G adds,
                                   a LEG-MANIFEST (`resolved_config.*`,
                                   `preflight.seeds.*`) and a SMOKE-MANIFEST
                                   (`c_worker_secs_per_playout`,
                                   `crn_cross_leg_identical`) — are resolved
                                   THERE. The run's own
                                   `verdicts/SEALED_G_REPLICATE.json` is NOT
                                   brought into existence and W3 never touches a
                                   real corpus position (REVIEW_R2 §N3).

  `--mode 4b-pre`  POST-CORPUS, PRE-SCORING — the four judge smokes on the FRESH
                   corpus, their per-judge manifests, `G-CRN`'s smoke half and
                   §7's judge-leg `c`-remeasure, plus the `RUN_MANIFEST_*`
                   preflight keys and the copied-back leg manifests.

  `--mode 4b`      POST-CORPUS, PRE-SCORING — the corpus artifacts, which carry
                   NO outcome statistic: `CHAMP_GAMES_VERIFY.json`,
                   `GATE_DISJOINT.json` (all five comparisons +
                   `strata_root_overlap`), `POSITIONS_PLAN.json` / `ARMS.json` on
                   both strata, `GATE_DRAW.json`, `GEN_SMOKE.json` and
                   `RUN_MANIFEST_S1::c_remeasure`.

  `--mode all`     all three.

MECHANISM: key presence + JSON type ONLY. No value is computed, printed or
stored — so running this does not spend the read rule and does not make the
session non-blind.

NULLS: `ABSENT IS FAIL`, and `null` is absent — except at the four addresses of
`READ_RULE` §1.2's **CLOSED** `allow_null` table (`ALLOW_NULL` below), each of
which is accepted only when its **discriminating witness** is in the stated
state. That list is closed at the blind commit and must not grow afterwards.

Exit codes
    0   every address resolved (or its gate resolved at a pre-registered fallback)
    1   at least one address is UNRESOLVED
    2   the run dir is missing / the fixture pass could not be built
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

WILDCARD = "*"
JUDGE = "tier1-greedy"   # every per-leg address is bound to the ARB leg (§N7)

# --------------------------------------------------------------------------- #
# READ_RULE §1.2 — the CLOSED `allow_null` table (four addresses, rev R3.1)      #
# --------------------------------------------------------------------------- #
#: `ABSENT IS FAIL`, and `null` is absent — EXCEPT at these four addresses,
#: where `null` is the CORRECT value. Each is paired with the WITNESS that
#: distinguishes "legitimately null" from "broken": a null here WITHOUT its
#: witness in the stated state is a FAIL, exactly as anywhere else.
#:
#: ⚠️ **THIS LIST IS CLOSED AT THE BLIND COMMIT.** No address may be added to it
#: afterwards — "this null is fine too" is how a fail-closed rule becomes
#: fail-open. An unforeseen legitimate null is a numbered §7 deviation in the
#: read-out, never a quiet extension of this table.
#:
#: Keyed by the address's LEAF (or by its parent, for the `d_draw.*` family);
#: the witness is resolved as a SIBLING of the address being checked, so one
#: row covers the address wherever it legitimately appears.
ALLOW_NULL = {
    "r_ora": {
        "address": "READOUT::widening.j_rider.s2.r_ora",
        "legitimate_iff": "the §5 degenerate-denominator guard fired",
        "witness": {"r_ora_reported": False},
    },
    "ci95_r_ora": {
        "address": "READOUT::widening.j_rider.s2.ci95_r_ora",
        "legitimate_iff": "same event, same moment",
        "witness": {"r_ora_reported": False},
    },
    "d_draw.*": {
        "address": "READOUT::widening.j_rider.d_draw.*",
        "legitimate_iff": "W9 has not run",
        "witness": {"d_draw_ran": False},
    },
    "cap_j": {
        "address": "POSITIONS_PLAN.json::cap_j",
        "legitimate_iff": "the build was uncapped — G-UNCAPPED REQUIRES this null",
        "witness": {"uncapped": True, "cap_j_label": "inf"},
    },
}


def _allow_null_row(dotted: str):
    """The CLOSED table's row for a dotted address, or None. The `d_draw.*`
    family matches on the PARENT segment; every other row on the leaf."""
    parts = dotted.split(".")
    if len(parts) >= 2 and parts[-2] == "d_draw":
        return "d_draw.*", ALLOW_NULL["d_draw.*"]
    leaf = parts[-1]
    row = ALLOW_NULL.get(leaf)
    return (leaf, row) if row else None


def null_is_legitimate(doc, dotted: str):
    """`(ok, detail)` — is a `null` at `dotted` one of the four sanctioned ones,
    WITH its witness in the stated state?"""
    hit = _allow_null_row(dotted)
    if not hit:
        return False, None
    name, row = hit
    parent = dotted.rsplit(".", 1)[0] if "." in dotted else ""
    for wkey, want in row["witness"].items():
        path = f"{parent}.{wkey}" if parent else wkey
        vals = dig(doc, path)
        if not vals or any(v != want for v in vals):
            return False, {"row": name, "witness": path, "expected": want,
                           "state": "ABSENT" if not vals else "MISMATCH"}
    return True, {"row": name, "witness": sorted(row["witness"])}


# --------------------------------------------------------------------------- #
# the address language                                                          #
# --------------------------------------------------------------------------- #
def json_type(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "str"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object"
    return type(v).__name__


def dig(obj, dotted: str):
    """Every value reachable by `dotted` (`.`-separated; `*` matches any one key
    of a dict / any one element of a list). Returns [] when nothing matches."""
    cur = [obj]
    for part in dotted.split("."):
        nxt = []
        for c in cur:
            if part == WILDCARD:
                if isinstance(c, dict):
                    nxt.extend(c.values())
                elif isinstance(c, list):
                    nxt.extend(c)
            elif isinstance(c, dict) and part in c:
                nxt.append(c[part])
        cur = nxt
        if not cur:
            return []
    return cur


class Check:
    """ONE address: a file glob + the dotted keys that must resolve in it.

    `kind`
        `json`            every key resolves in every matched file
        `json_per_entry`  every key resolves under every TOP-LEVEL value
                          (the `ARMS.json::<rid>.<key>` shape)
        `json_any_of`     at least one of `keys` resolves (an OR address)
        `jsonl`           every key resolves on every line
        `exists`          the file merely has to exist

    A `null` FAILS (READ_RULE §1.2) unless the address is one of the four in the
    CLOSED `ALLOW_NULL` table AND its witness is in the stated state. That is
    checked here, against the same document, so a null can never be waved
    through by the checker's own configuration.
    """

    def __init__(self, root, glob, keys=(), kind="json", label=None,
                 min_files=1, max_lines=100, max_entries=100):
        self.root = Path(root)
        self.glob = glob
        self.keys = list(keys)
        self.kind = kind
        self.label = label or (f"{glob}::{{{','.join(self.keys)}}}"
                               if self.keys else glob)
        self.min_files = min_files
        self.max_lines = max_lines
        self.max_entries = max_entries
        self.sanctioned_nulls = []

    def _ok(self, key, vals, doc) -> bool:
        if not vals:
            return False
        if all(v is not None for v in vals):
            return True
        ok, detail = null_is_legitimate(doc, key)
        if ok:
            self.sanctioned_nulls.append({"key": key, **(detail or {})})
        return ok

    def resolve(self) -> dict:
        files = sorted(self.root.glob(self.glob)) if self.root.is_dir() else []
        base = {"address": f"{self.root}/{self.label}", "n_files": len(files)}
        if len(files) < self.min_files:
            return {**base, "resolved": False, "types": {},
                    "sanctioned_nulls": [],
                    "why": f"no file matches the glob (need >= {self.min_files})"}
        if self.kind == "exists":
            return {**base, "resolved": True, "types": {},
                    "sanctioned_nulls": [], "why": None}
        missing, types = [], {}
        self.sanctioned_nulls = []

        def note(key, vals):
            for v in vals:
                types.setdefault(key, set()).add(json_type(v))

        for f in files:
            try:
                if self.kind == "jsonl":
                    lines = [ln for ln in f.read_text().splitlines() if ln.strip()]
                    if not lines:
                        missing.append(f"{f.name}: empty jsonl")
                        continue
                    for ln in lines[:self.max_lines]:
                        rec = json.loads(ln)
                        for k in self.keys:
                            vals = dig(rec, k)
                            note(k, vals)
                            if not self._ok(k, vals, rec):
                                missing.append(f"{f.name}::<line>.{k}")
                    continue
                doc = json.loads(f.read_text())
                if self.kind == "json_per_entry":
                    if not isinstance(doc, dict) or not doc:
                        missing.append(f"{f.name}: not a non-empty rid-keyed object")
                        continue
                    for entry in list(doc.values())[:self.max_entries]:
                        for k in self.keys:
                            vals = dig(entry, k)
                            note(k, vals)
                            if not self._ok(k, vals, entry):
                                missing.append(f"{f.name}::<rid>.{k}")
                elif self.kind == "json_any_of":
                    hits = [k for k in self.keys if self._ok(k, dig(doc, k), doc)]
                    for k in self.keys:
                        note(k, dig(doc, k))
                    if not hits:
                        missing.append(f"{f.name}::{{{'|'.join(self.keys)}}}")
                else:
                    for k in self.keys:
                        vals = dig(doc, k)
                        note(k, vals)
                        if not self._ok(k, vals, doc):
                            missing.append(f"{f.name}::{k}")
            except (OSError, json.JSONDecodeError) as exc:
                missing.append(f"{f.name}: unreadable ({exc})")
        missing = sorted(set(missing))
        seen, sanctioned = set(), []
        for s in self.sanctioned_nulls:            # dedup across files/entries
            if s["key"] not in seen:
                seen.add(s["key"])
                sanctioned.append(s)
        return {**base, "resolved": not missing,
                "types": {k: sorted(v) for k, v in sorted(types.items())},
                "sanctioned_nulls": sanctioned,
                "why": None if not missing else "; ".join(missing[:6])}


class Gate:
    """A gate: PRIMARY checks (all must resolve) and an optional FALLBACK list.
    Both are ALWAYS resolved, independently, and both are reported."""

    def __init__(self, name, primary, fallback=(), note="", phase="4b",
                 optional=False):
        self.name = name
        self.primary = list(primary)
        self.fallback = list(fallback)
        self.note = note
        self.phase = phase
        #: an OPTIONAL address is reported but never fails the harness — it
        #: belongs to a rider whose emitter may legitimately not have run yet.
        self.optional = bool(optional)

    def resolve(self) -> dict:
        prim = [c.resolve() for c in self.primary]
        fall = [c.resolve() for c in self.fallback]
        ok_p = bool(prim) and all(r["resolved"] for r in prim)
        ok_f = bool(fall) and all(r["resolved"] for r in fall)
        at = "primary" if ok_p else ("fallback" if ok_f else
                                     ("OPTIONAL-ABSENT" if self.optional
                                      else "UNRESOLVED"))
        return {"gate": self.name, "phase": self.phase, "resolved_at": at,
                "optional": self.optional,
                "resolved": at != "UNRESOLVED",
                "primary_ok": ok_p, "fallback_ok": ok_f if fall else None,
                "primary": prim, "fallback": fall, "note": self.note,
                "has_fallback": bool(self.fallback)}


# --------------------------------------------------------------------------- #
# the address book — READ_RULE §2/§4/§5 + DESIGN §7, verbatim (rev R2)           #
# --------------------------------------------------------------------------- #
LEGS = f"legs/s*/{JUDGE}/walled/leg*/manifest.json"
RECORDS = f"s*/{JUDGE}/walled/leg*/records/*.json"
COMPARISONS_FULL = ("s1_vs_tiletie0812", "s1_vs_tiearb2_0816",
                    "s2_vs_tiletie0812", "s2_vs_tiearb2_0816")
COMPARISON_RID_ONLY = "s1s2_vs_exclude_rids"


def book_bitexact(R: Path) -> list:
    """4a(live) — the ONLY live address 4a can answer, now that §0.G moved the
    judge smokes to 4b-pre. `G-BITEXACT@HEAD` is produced at §9 step 3, before
    the blind commit, and needs no corpus."""
    return [Gate("G-BITEXACT@HEAD", [
        Check(R, "GATE_BITEXACT_HEAD.json",
              ["pass", "n_playouts_compared", "n_value_bit_identical",
               "n_value_mismatch", "legal_mask_cache", "git_rev"])],
        note="no fallback. Reached ONLY by verify_tier1_rust.py --out (W7); "
             "without --out it can write only into the CLOSED Stage-2 run dir",
        phase="4a-live")]


def book_4b_pre(R: Path, S: Path) -> list:
    """4b-pre (post-corpus, PRE-SCORING) — the four judge smokes on the FRESH
    corpus, their per-judge manifests, `G-CRN`'s smoke half and §7's judge-leg
    `c`-remeasure.

    ⚠️ §0.G moved these OFF 4a. They were labelled "corpus-free", but
    `run_tiletie.select_smoke_positions()` resolves its positions through
    `<positions-dir>/ARMS.json` and `POSITIONS_PLAN.json` — files W6 does not
    build until step 6 — and `--positions-dir` DEFAULTS TO
    `measurement/tiletie_pricing_20260812/positions`, the SPENT corpus §3
    requires disjointness FROM. Run as written, 4a would have quietly scored
    positions from a burned corpus. **`--positions-dir` must be named
    EXPLICITLY in every smoke invocation — never defaulted.**

    The `c`-HALT still fires BEFORE the expensive legs, which is its whole
    purpose. Their SPELLINGS are audited pre-commit by the two fixtures in
    `book_fixture`, so the move costs no pre-commit coverage."""
    g = []
    g.append(Gate("G-LEAF", [
        Check(R, "RUN_MANIFEST_S1.json", ["preflight.checks.leaf_hash.ok"]),
        Check(R, "RUN_MANIFEST_S2.json", ["preflight.checks.leaf_hash.ok"])],
        [Check(R, "RUN_MANIFEST_S*.json",
               ["preflight.checks.leaf_hash.harness_leaf_hash",
                "preflight.checks.leaf_hash.expected"])],
        phase="4b-pre"))

    g.append(Gate("G-M", [
        Check(R, "RUN_MANIFEST_S1.json", ["m_worlds", "b_ceiling_from_m"]),
        Check(R, "RUN_MANIFEST_S2.json", ["m_worlds", "b_ceiling_from_m"])],
        [Check(R, LEGS, ["resolved_config.m"])],
        note="fallback exists ONLY on the tier1-greedy leg", phase="4b-pre"))

    g.append(Gate("G-BACKEND", [
        Check(R, "RUN_MANIFEST_S1.json",
              ["arb_backend", "resolved_backend_by_leg", "arb_legal_mask_cache"]),
        Check(R, "RUN_MANIFEST_S2.json",
              ["arb_backend", "resolved_backend_by_leg", "arb_legal_mask_cache"])],
        [Check(R, LEGS, ["resolved_config.legal_mask_cache"])],
        phase="4b-pre"))

    g.append(Gate("G-PREFIX", [
        Check(R, LEGS, ["preflight.seeds.ok", "preflight.seeds.prefix_stable_at"])],
        [Check(R, LEGS, ["preflight.seeds.derivation",
                         "preflight.seeds.probe_world_seeds_head"])],
        note="witnessed ONCE on the ARB leg — prefix stability is a property of "
             "the shared seed derivation, not of a leg. `prefix_ok` exists "
             "nowhere in the repo", phase="4b-pre"))

    g.append(Gate("G-CRN (smoke half)", [
        Check(R, "SMOKE_MANIFEST_S1_*.json", ["crn_cross_leg_identical"],
              min_files=2),
        Check(R, "SMOKE_MANIFEST_S2_*.json", ["crn_cross_leg_identical"],
              min_files=2)],
        [Check(S, RECORDS, ["crn_verified"]),
         Check(S, RECORDS, ["world_deck_hash", "afterstate_deck_hash_a"],
               kind="json_any_of")],
        note="FOUR smokes: {S1 --m 128, S2 --m 32} x {clair-puct, tier1-greedy}; "
             "one shared --smoke-manifest path would overwrite. The per-record "
             "fallback is records/<rid>.json — there is no *.jsonl leg file",
        phase="4b-pre"))

    g.append(Gate("§7 c-remeasure (judge legs)", [
        Check(R, "SMOKE_MANIFEST_S1_*.json", ["c_worker_secs_per_playout"],
              min_files=2),
        Check(R, "SMOKE_MANIFEST_S2_*.json", ["c_worker_secs_per_playout"],
              min_files=2)],
        note="the figure of record is c_worker_secs_per_playout, NEVER "
             "worker_secs_per_playout (inflated ~1.9x); null/0 is a FAILED "
             "SMOKE, not a cheap leg and not a HALT",
        phase="4b-pre"))
    return g


def book_fixture(R: Path, S: Path) -> list:
    """4a(fixture) — the static schema audit of the W3/W5 output spellings."""
    V = "verdicts"
    g = []
    g.append(Gate("G-DISJOINT", [
        Check(R, "GATE_DISJOINT.json",
              ["passed", "strata_root_overlap", "comparisons"]
              + [f"comparisons.{c}.layers.{lay}.n_intersection"
                 for c in COMPARISONS_FULL
                 for lay in ("a_root_id", "b_rid", "c_position_digest")]
              + [f"comparisons.{COMPARISON_RID_ONLY}.layers.b_rid.n_intersection",
                 f"comparisons.{COMPARISON_RID_ONLY}.passed"])],
        note="FIVE comparisons; the fifth is RID LAYER ONLY (EXCLUDE_RIDS_all.txt "
             "is a rid text file). No fallback — a missing gate file is a FAIL",
        phase="4a-fixture"))

    g.append(Gate("G-DRAW", [
        Check(R, "GATE_DRAW.json", ["n_checked", "n_mismatch", "ok", "git_rev"])],
        [Check(R, "corpus/positions_s1/ARMS.json",
               ["arms_full", "subset_j4", "subset_j4_id"], kind="json_per_entry"),
         Check(R, "corpus/positions_s2/ARMS.json",
               ["arms_full", "subset_j4", "subset_j4_id"], kind="json_per_entry")],
        note="owned by W5 (DESIGN §8 builder delta 2)", phase="4a-fixture"))

    g.append(Gate("G-ARMS", [
        Check(R, f"{V}/READOUT.json",
              ["widening.gates.arms.n_arms", "widening.gates.arms.n_arms_complete",
               "widening.gates.arms.include_partial", "widening.gates.arms.ok"])],
        [Check(R, f"{V}/per_position_s1.jsonl",
               ["n_worlds_per_arm", "n_arms_planned"], kind="jsonl"),
         Check(R, f"{V}/per_position_s2.jsonl",
               ["n_worlds_per_arm", "n_arms_planned"], kind="jsonl")],
        phase="4a-fixture"))

    g.append(Gate("G-COMPLETE", [
        Check(R, f"{V}/READOUT.json",
              ["widening.completion.s1_n", "widening.completion.s2_n",
               "widening.completion.s1_max_per_root",
               "widening.completion.s2_max_per_root"])],
        [Check(R, f"{V}/per_position_s1.jsonl", ["root_id", "rid"], kind="jsonl"),
         Check(R, f"{V}/per_position_s2.jsonl", ["root_id", "rid"], kind="jsonl")],
        phase="4a-fixture"))

    g.append(Gate("G-REPLICATE", [
        Check(R, f"{V}/READOUT.json",
              ["widening.stage1_replication.pass",
               "widening.stage1_replication.per_rung_inside_envelope",
               "widening.stage1_replication.arb16_convicts",
               "widening.stage1_replication.envelope_inflation"])],
        note="NO FALLBACK — booleans only; a missing/null block is a FAIL. The "
             "sealed z-file is WRITE-ONLY and is not an address (READ_RULE §7)",
        phase="4a-fixture"))

    g.append(Gate("G-UNCAPPED", [
        Check(R, "corpus/positions_s1/POSITIONS_PLAN.json",
              ["uncapped", "cap_j", "cap_j_label"]),
        Check(R, "corpus/positions_s2/POSITIONS_PLAN.json",
              ["uncapped", "cap_j", "cap_j_label"]),
        Check(R, "corpus/positions_s*/ARMS.json",
              ["arms", "arms_full", "champ_arm_action", "champ_arm_index"],
              kind="json_per_entry", min_files=2)],
        [Check(R, f"{V}/READOUT.json", ["widening.gates.uncapped"])],
        note="`cap_j` is null on an uncapped build — G-UNCAPPED REQUIRES that "
             "null. It is row 4 of the CLOSED allow_null table and is accepted "
             "only with its witness: `uncapped == true` AND `cap_j_label == "
             "\"inf\"`",
        phase="4a-fixture"))

    ladder = [f"widening.b_ladder.E{e}.B{b}.{k}"
              for e in (64, 16) for b in (1, 2, 4, 8, 16, 32, 64)
              for k in ("arb", "ci95", "se")]
    g.append(Gate("READOUT §4 (rung 2 branch inputs)", [
        Check(R, f"{V}/READOUT.json",
              ["widening.delta.d_16_64.value", "widening.delta.d_16_64.ci95",
               "widening.delta.d_16_64.se_root", "widening.delta.d_16_32.value",
               "widening.delta.d_16_32.ci95", "widening.delta.d_16_32.se_root"]
              + ladder)],
        [Check(R, f"{V}/per_position_s1.jsonl",
               ["arb_j4_E64_B16", "arb_j4_E64_B64", "d_16_64_E64", "root_id"],
               kind="jsonl")],
        phase="4a-fixture"))

    g.append(Gate("READOUT §5 (rung 3 branch inputs)", [
        Check(R, f"{V}/READOUT.json",
              ["widening.j_rider.s2.delta_ora", "widening.j_rider.s2.ci95_ora",
               "widening.j_rider.s2.r_ora", "widening.j_rider.s2.ci95_r_ora",
               "widening.j_rider.s2.ora_j4_ci95", "widening.j_rider.s2.delta_arb",
               "widening.j_rider.s2.ci95_arb", "widening.j_rider.s2.n_capped",
               "widening.j_rider.s2.xfree_window",
               "widening.j_rider.s1_replication.delta_ora",
               "widening.j_rider.s1_replication.ci95_ora",
               "widening.j_rider.s1_replication.n_capped",
               "widening.j_rider.interaction.arb_full_64_minus_16",
               "widening.j_rider.interaction.arb_full_16_minus_j4_16",
               "widening.j_rider.s2.r_ora_reported",
               "widening.j_rider.d_draw.d_draw_ran",
               "widening.j_rider.d_draw.n_checked",
               "widening.j_rider.d_draw.agreement_rate"])],
        [Check(R, f"{V}/per_position_s2.jsonl",
               ["ora_full_E16", "ora_j4_E16", "d_ora_E16", "capped_at_4",
                "root_id"], kind="jsonl")],
        note="`r_ora` and `ci95_r_ora` go null TOGETHER when the §5 "
             "degenerate-denominator guard fires, and `d_draw.*` is null until "
             "W9 runs — rows 1-3 of the CLOSED allow_null table, accepted only "
             "with their witnesses (`r_ora_reported == false`, "
             "`d_draw_ran == false`)",
        phase="4a-fixture"))

    g.append(Gate("READOUT §7 (report surface)", [
        Check(R, f"{V}/READOUT.md", kind="exists"),
        Check(R, f"{V}/READOUT.json",
              ["widening.gates_summary.*.resolved_at",
               "widening.branch.rung2.branch", "widening.branch.rung3.branch",
               "widening.gates.crn.ok", "widening.gates.crn.witness_kinds"])],
        phase="4a-fixture"))

    # ---- the TWO fixtures §0.G adds, so moving the judge smokes to 4b-pre --- #
    # ---- costs NO pre-commit coverage of their spellings -------------------- #
    g.append(Gate("LEG-MANIFEST fixture (G-M / G-BACKEND / G-SALT / G-PREFIX "
                  "fallbacks)", [
        Check(R, LEGS,
              ["resolved_config.world_seed_salt", "resolved_config.m",
               "resolved_config.legal_mask_cache",
               "preflight.seeds.ok", "preflight.seeds.prefix_stable_at",
               "preflight.seeds.derivation",
               "preflight.seeds.probe_world_seeds_head"])],
        note="`resolved_config.*` and `preflight.seeds.*` exist ONLY on the "
             "tier1-greedy (tier1_rust_leg) manifests — the clair-puct legs are "
             "oracle_score_pilot manifests and carry neither. Auditing the "
             "spellings HERE is what lets §0.G move the live smokes to 4b-pre "
             "without losing pre-commit coverage",
        phase="4a-fixture"))

    g.append(Gate("SMOKE-MANIFEST fixture (G-CRN smoke half / §7 judge legs)", [
        Check(R, "SMOKE_MANIFEST_S1_*.json",
              ["c_worker_secs_per_playout", "crn_cross_leg_identical",
               "m_worlds", "arb_backend"], min_files=2),
        Check(R, "SMOKE_MANIFEST_S2_*.json",
              ["c_worker_secs_per_playout", "crn_cross_leg_identical",
               "m_worlds", "arb_backend"], min_files=2)],
        note="four manifests, one per {stratum x judge} — one shared "
             "--smoke-manifest path would have the second smoke overwrite the "
             "first. The cost figure of record is c_worker_secs_per_playout, "
             "NEVER worker_secs_per_playout",
        phase="4a-fixture"))
    return g


def book_corpus(R: Path, S: Path) -> list:
    """4b — the real corpus artifacts (no outcome statistic among them)."""
    g = [Gate("G-BAND", [
        Check(R, "corpus/CHAMP_GAMES_VERIFY.json",
              ["band_ok", "seed_band", "n_out_of_band", "n_duplicate_seeds",
               "n_games_realized", "sha256_of_sorted_seeds"])],
        note="no seed list exists anywhere BY DESIGN — the emitter publishes "
             "sha256_of_sorted_seeds. If the blind top-up was exercised, "
             "CHAMP_GAMES_VERIFY_TOPUP.json must satisfy the same conjuncts "
             "against its OWN seed_band",
        phase="4b")]

    g.append(Gate("G-SALT", [
        Check(R, "RUN_MANIFEST_S1.json", ["world_seed_salt"]),
        Check(R, "RUN_MANIFEST_S2.json", ["world_seed_salt"]),
        Check(R, "corpus/positions_s*/POSITIONS_PLAN.json", ["deployed_cap_j"],
              min_files=2),
        Check(R, "corpus/positions_s*/ARMS.json", ["cap_seed"],
              kind="json_per_entry", min_files=2)],
        [Check(R, LEGS, ["resolved_config.world_seed_salt"])],
        note="world_seed_salt is a MODULE CONSTANT, not a flag", phase="4b"))

    g.append(Gate("§7 c-remeasure (generation + realized-vs-committed)", [
        Check(R, "corpus/GEN_SMOKE.json", ["worker_secs_per_game"]),
        Check(R, "RUN_MANIFEST_S1.json",
              ["c_remeasure.legs.arb.committed", "c_remeasure.legs.arb.realized",
               "c_remeasure.legs.if.committed", "c_remeasure.legs.if.realized",
               "c_remeasure.legs.generation.committed",
               "c_remeasure.legs.generation.realized",
               "c_remeasure.halt_fired"])],
        note="the judge smoke cannot price the generation leg — §7.2 requires a "
             "separate timed 10-game generation smoke. HALT is ONE-SIDED",
        phase="4b"))

    g.append(Gate("W9 D-DRAW (rider, OPTIONAL)", [
        Check(R, "D_DRAW.json",
              ["n_checked", "n_agree", "agreement_rate", "n_unreconstructible",
               "git_rev"])],
        note="OPTIONAL: absent until W9's probe runs, and its absence never "
             "fails the harness — `D-DRAW` reports the MAGNITUDE of rider I7's "
             "unverified dedupe-partition conditional and ADJUDICATES NOTHING. "
             "When absent, every READOUT `d_draw.*` address is null under row 3 "
             "of the CLOSED allow_null table (witness `d_draw_ran == false`)",
        phase="4b", optional=True))

    # the corpus-side halves of the fixture-audited gates, on the REAL artifacts
    for gate in book_fixture(R, S):
        if gate.name in ("G-DISJOINT", "G-DRAW", "G-UNCAPPED"):
            g.append(Gate(gate.name, gate.primary, gate.fallback, gate.note,
                          phase="4b"))
    return g


def address_book(run_dir, share, mode="all") -> list:
    """The LIVE half of the book for `mode` (the fixture half is built
    separately, against a scratch tree, by `build_fixture_tree`)."""
    R, S = Path(run_dir), Path(share)
    out = []
    if mode in ("4a", "all"):
        out += book_bitexact(R)
    if mode in ("4b-pre", "all"):
        out += book_4b_pre(R, S)
    if mode in ("4b", "all"):
        out += book_corpus(R, S)
    return out


# --------------------------------------------------------------------------- #
# the 4a fixture pass — run W5 + W3 over committed synthetic fixtures            #
# --------------------------------------------------------------------------- #
def build_fixture_tree(scratch) -> Path:
    """Materialise a fixture RUN/ and run W5 (`gate_disjoint --merged`,
    `gate_draw`) and W3 (`analyze_widening`) over it. Returns the fixture RUN
    dir. NOTHING here touches the real run: the real
    `verdicts/SEALED_G_REPLICATE.json` is never brought into existence."""
    import widening_fixtures as WF                                 # noqa: E402

    fx = WF.build_full_fixture(scratch)
    run, share = fx["run"], fx["share"]
    py = sys.executable
    corpus = run / "corpus"

    # a banked-reference stand-in for each of the two ARMS.json comparisons
    refs = {}
    for name, seed in (("tiletie0812", 101), ("tiearb2_0816", 202)):
        d = Path(scratch) / f"ref_{name}"
        WF.make_corpus(d, n_positions=6, m=8, seed=seed, rid_prefix=name[:4],
                       band_lo=999000000000)
        refs[name] = d
    excl = Path(scratch) / "EXCLUDE_RIDS_all.txt"
    excl.write_text("# fixture exclusion list\nrefx:doesnotexist:p000\n")

    cmds = [
        [py, str(HERE / "gate_disjoint.py"), "--merged",
         "--s1-dir", str(corpus / "positions_s1"),
         "--s2-dir", str(corpus / "positions_s2"),
         "--ref", f"tiletie0812={refs['tiletie0812']}",
         "--ref", f"tiearb2_0816={refs['tiearb2_0816']}",
         "--exclude-rids", str(excl),
         "--out", str(run / "GATE_DISJOINT.json")],
        [py, str(HERE / "gate_draw.py"),
         "--arms", str(corpus / "positions_s1" / "ARMS.json"),
         "--arms", str(corpus / "positions_s2" / "ARMS.json"),
         "--out", str(run / "GATE_DRAW.json")],
        [py, str(HERE / "analyze_widening.py"),
         "--plan-dir-s1", str(corpus / "positions_s1"),
         "--plan-dir-s2", str(corpus / "positions_s2"),
         "--if-records-s1", str(share / "s1" / "clair-puct"),
         "--arb-records-s1", str(share / "s1" / "tier1-greedy"),
         "--if-records-s2", str(share / "s2" / "clair-puct"),
         "--arb-records-s2", str(share / "s2" / "tier1-greedy"),
         "--smoke-manifest", str(run / "SMOKE_MANIFEST_S1_tier1-greedy.json"),
         "--smoke-manifest", str(run / "SMOKE_MANIFEST_S1_clair-puct.json"),
         "--stage1b-ladder", str(fx["stage1b_ladder"]),
         # --d-draw is DELIBERATELY OMITTED: the fixture pass must exercise the
         # `d_draw_ran == false` state, so row 3 of the CLOSED allow_null table
         # is audited on the day it is written and not on the day it is needed.
         "--boot-reps", "200",
         "--out-dir", str(run / "verdicts")],
        [py, str(HERE / "c_remeasure.py"),
         "--smoke", str(run / "SMOKE_MANIFEST_S1_tier1-greedy.json"),
         "--smoke", str(run / "SMOKE_MANIFEST_S1_clair-puct.json"),
         "--smoke", str(run / "SMOKE_MANIFEST_S2_tier1-greedy.json"),
         "--smoke", str(run / "SMOKE_MANIFEST_S2_clair-puct.json"),
         "--gen-smoke", str(corpus / "GEN_SMOKE.json"),
         "--manifest", str(run / "RUN_MANIFEST_S1.json")],
    ]
    for cmd in cmds:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode not in (0,):
            raise RuntimeError(f"fixture emitter failed ({Path(cmd[1]).name}, "
                               f"rc={r.returncode}):\n{r.stderr[-2000:]}")
    return run


# --------------------------------------------------------------------------- #
def _print(results, verbose):
    marks = {"primary": "OK ", "fallback": "FB ", "UNRESOLVED": "***",
             "OPTIONAL-ABSENT": "-- "}
    for r in results:
        print(f"[acceptance] {marks[r['resolved_at']]} {r['phase']:11s} "
              f"{r['gate']:36s} {r['resolved_at']}")
        for section in ("primary", "fallback"):
            for c in r[section]:
                for s in c.get("sanctioned_nulls", []):
                    print(f"[acceptance]        allow_null  row {s['row']!r} "
                          f"sanctions {s['key']} (witness "
                          f"{','.join(s.get('witness', []))})")
                if verbose or (not c["resolved"] and not r["optional"]):
                    state = "resolved" if c["resolved"] else "UNRESOLVED"
                    types = ", ".join(f"{k}:{'/'.join(v)}"
                                      for k, v in list(c["types"].items())[:6])
                    print(f"[acceptance]        {section:8s} {state:10s} "
                          f"{c['address']}"
                          + (f"  [types {types}]" if verbose and types else "")
                          + (f"  <- {c['why']}" if c["why"] else ""))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run-dir", required=True, help="the RUN/ tree (shared_run/)")
    ap.add_argument("--share", default="/mnt/c/carc-shared/tiearb_widening_20260817",
                    help="SHARE root holding the per-record leg output")
    ap.add_argument("--mode", choices=("4a", "4b-pre", "4b", "all"),
                    default="all",
                    help="4a = fixture schema audit + G-BITEXACT@HEAD "
                         "(pre-blind-commit, genuinely corpus-free); "
                         "4b-pre = the four judge smokes on the FRESH corpus; "
                         "4b = the corpus artifacts")
    ap.add_argument("--no-fixture", action="store_true",
                    help="skip the 4a static schema audit (live addresses only)")
    ap.add_argument("--fixture-dir", default=None,
                    help="keep the fixture scratch tree here instead of a tmpdir")
    ap.add_argument("--out", default=None, help="write the report JSON here")
    ap.add_argument("--verbose", action="store_true",
                    help="print every address and its JSON type, not just the "
                         "unresolved ones (still never a VALUE)")
    a = ap.parse_args(argv)

    run_dir = Path(a.run_dir)
    if not run_dir.is_dir():
        print(f"[acceptance] RUN dir does not exist: {run_dir}", file=sys.stderr)
        return 2

    print(f"[acceptance] RUN   = {run_dir}")
    print(f"[acceptance] SHARE = {a.share}")
    print(f"[acceptance] mode  = {a.mode}  (presence + JSON type ONLY; no value "
          f"is computed, printed or stored)")

    results = [g.resolve() for g in address_book(run_dir, a.share, a.mode)]

    fixture_run = None
    if a.mode in ("4a", "all") and not a.no_fixture:
        tmp = a.fixture_dir or tempfile.mkdtemp(prefix="widening_fixture_")
        try:
            fixture_run = build_fixture_tree(tmp)
        except (RuntimeError, ImportError) as exc:
            print(f"[acceptance] FIXTURE PASS COULD NOT BE BUILT: {exc}",
                  file=sys.stderr)
            return 2
        results += [g.resolve()
                    for g in book_fixture(fixture_run, Path(tmp) / "share")]
        print(f"[acceptance] fixture schema audit under {fixture_run}")

    _print(results, a.verbose)

    n_bad = sum(1 for r in results if not r["resolved"])
    n_fb = sum(1 for r in results if r["resolved_at"] == "fallback")
    n_fb_broken = sum(1 for r in results
                      if r["has_fallback"] and r["fallback_ok"] is False)
    report = {"run_dir": str(run_dir), "share": str(a.share), "mode": a.mode,
              "fixture_run": str(fixture_run) if fixture_run else None,
              "n_gates": len(results), "n_unresolved": n_bad,
              "n_fallback_only": n_fb, "n_unaudited_fallbacks": n_fb_broken,
              "gates": results, "passed": n_bad == 0,
              "mechanism": "key presence + JSON type only; no value is computed, "
                           "printed or stored"}
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(report, indent=2, sort_keys=True,
                                          default=str))
        print(f"[acceptance] -> {a.out}")

    if n_fb_broken:
        print(f"[acceptance] ⚠️ {n_fb_broken} gate(s) have a pre-registered "
              f"FALLBACK that does not resolve — it would be unaudited on the "
              f"day it is needed.", file=sys.stderr)
    if n_bad:
        print(f"\n{'=' * 70}\n"
              f"[acceptance] ***** ACCEPTANCE TEST FAILED *****\n"
              f"[acceptance] {n_bad} gate(s) UNRESOLVED at EVERY pre-registered "
              f"address.\n"
              f"[acceptance] READ_RULE §1.2: ABSENT IS FAIL. §1.4: no address may "
              f"be invented at read time.\n"
              f"[acceptance] Fix the EMITTER now — 4a is before the blind commit; "
              f"4b is the last moment a fix is free.\n{'=' * 70}", file=sys.stderr)
        return 1
    print(f"[acceptance] PASS — {len(results)} gate(s) resolved "
          f"({n_fb} at a fallback only, {n_fb_broken} unaudited fallback(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
