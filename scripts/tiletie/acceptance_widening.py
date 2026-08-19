#!/usr/bin/env python3
"""**W8** — the ACCEPTANCE TEST (DESIGN §9 steps 4a / 4b-pre / 4b, + post).

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

FOUR phases, because the artifacts appear at four different times. §0.G re-split
what R2 called 4a (the judge smokes are NOT corpus-free — see `book_4b_pre`), and
`post` exists because an address whose emitter has not run yet is not one that
may be waived, only one that binds later (see `book_post_scoring`):

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

  `--mode post`    POST-SCORING — the addresses that cannot exist until a leg
                   and the analyzer have run: `G-SALT`'s `world_seed_salt`
                   (`RUN_MANIFEST_*`, written at leg launch; `resolved_config`
                   on the leg manifests) and the read-out-time gates `G-ARMS`,
                   `G-COMPLETE`, `G-REPLICATE` and the `READOUT` branch inputs.
                   ⚠️ An address whose emitter has not run is not one that may
                   be WAIVED — it is one that binds LATER. This mode is where.

  `--mode all`     all four.

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


#: §D4.16 BLOCKER 2 — the S2 VOID SCOPE.
#:
#: `G-SALT`'s S2 conjunct addresses `RUN_MANIFEST_S2.json::world_seed_salt`,
#: which CANNOT EXIST under Reading A. FAIL is false (nothing failed — a
#: pre-registered rule voided the stratum); PASS is a lie (nothing was checked);
#: silent absence violates §1.3's `resolved_at` duty. ⇒ **VOID (stratum) — not
#: evaluated**, citing the same positive witness the analyzer uses.
#:
#: ⚠️ IT MUST BE A HARNESS SCOPE, NOT A DOCUMENTED READING. A prose reading
#: would require a human to translate `UNRESOLVED` into "void, correctly" — a
#: CARVE-OUT BY INTERPRETATION, and R4.5 already ruled that carve-outs are how
#: this class recurs (it is why `STAGE1B_LADDER.json` was COPIED rather than
#: address-excepted).
#:
#: ⚠️ AND IT IS DERIVED FROM THE ARTIFACT, NEVER FROM A FLAG. There is no CLI
#: option that activates, widens or silences it — `ABSENT IS FAIL` may not
#: become silenceable, which is the same non-silenceable principle the two-rev
#: licence rests on. Scope: ONLY addresses bearing the S2 stratum marker, and
#: ONLY under the positive witness. S1 and every non-S2 address are untouched.
VOID_RESOLVED_AT = "VOID (stratum)"
VOID_WHY = "VOID (stratum) — not evaluated"
VOID_WITNESS_FILE = "GATE_DISJOINT.json"


def void_stratum_scope(run_dir) -> dict:
    """Which strata a POSITIVE artifact witness declares void.

    `digest_exclusions.<stratum>.void == true` and nothing else: a missing file,
    a missing block, a missing row and a `null` all yield an INACTIVE scope, so
    absence can never scope an address out of `ABSENT IS FAIL`.
    """
    p = Path(run_dir) / VOID_WITNESS_FILE
    out = {"active": False, "strata": (), "source": str(p), "present": False,
           "address": f"{VOID_WITNESS_FILE}::digest_exclusions.<stratum>.void",
           "voided_strata": None,
           "why": "no GATE_DISJOINT.json — absence is NOT a void witness"}
    if not p.is_file():
        return out
    try:
        d = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        out["why"] = f"GATE_DISJOINT.json unreadable ({exc})"
        return out
    strata = tuple(sorted(
        str(s).upper() for s, v in (d.get("digest_exclusions") or {}).items()
        if isinstance(v, dict) and v.get("void") is True))
    out.update({"present": True, "strata": strata, "active": bool(strata),
                "voided_strata": d.get("voided_strata"),
                "why": (f"positive witness: void is true for {list(strata)}"
                        if strata else
                        "no stratum carries void == true — scope INACTIVE")})
    return out


#: How an address declares which stratum it belongs to when it is not passed
#: explicitly. Structural, from the address itself — never a human judgement at
#: audit time.
_STRATUM_MARKERS = (("S2", ("_S2", "_s2", "/s2/", "positions_s2", "S2_")),
                    ("S1", ("_S1", "_s1", "/s1/", "positions_s1", "S1_")))


def stratum_of(glob: str, label: str = "") -> str:
    """The stratum an address is marked for, or None. `s*` globs span both and
    are deliberately NOT marked: they are not S2-addressed."""
    hay = f"/{glob}/{label}/"
    for tag, marks in _STRATUM_MARKERS:
        if any(m in hay for m in marks):
            return tag
    return None


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
                 min_files=1, max_lines=100, max_entries=100, stratum=None):
        self.root = Path(root)
        self.glob = glob
        self.keys = list(keys)
        self.kind = kind
        self.label = label or (f"{glob}::{{{','.join(self.keys)}}}"
                               if self.keys else glob)
        self.min_files = min_files
        self.max_lines = max_lines
        self.max_entries = max_entries
        #: which stratum this address is marked for — explicit wins, else the
        #: marker structurally present in the address itself
        self.stratum = stratum or stratum_of(self.glob, self.label)
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

    def resolve(self, void_scope=None) -> dict:
        files = sorted(self.root.glob(self.glob)) if self.root.is_dir() else []
        base = {"address": f"{self.root}/{self.label}", "n_files": len(files),
                "stratum": self.stratum}
        # ⭐ §D4.16's harness scope: an S2-marked address under a POSITIVE void
        # witness is NOT EVALUATED — never FAIL (nothing failed), never PASS
        # (nothing was checked), never silent (the resolved_at duty). Untouched
        # for S1 and for every non-S2 address, and unreachable from any flag.
        if (void_scope or {}).get("active") and self.stratum in (
                void_scope or {}).get("strata", ()):
            return {**base, "resolved": None, "void": True, "types": {},
                    "sanctioned_nulls": [], "why": VOID_WHY,
                    "void_witness": {k: (void_scope or {}).get(k) for k in
                                     ("address", "source", "voided_strata",
                                      "why")}}
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

    def resolve(self, void_scope=None) -> dict:
        prim = [c.resolve(void_scope) for c in self.primary]
        fall = [c.resolve(void_scope) for c in self.fallback]

        def _live(rs):
            return [r for r in rs if not r.get("void")]

        voided = [r["address"] for r in prim + fall if r.get("void")]
        live_p, live_f = _live(prim), _live(fall)
        # a VOID conjunct neither satisfies nor breaks its gate: the gate is
        # decided by the conjuncts that were actually evaluated, and a gate
        # whose every conjunct is void resolves at VOID (stratum).
        ok_p = bool(live_p) and all(r["resolved"] for r in live_p)
        ok_f = bool(live_f) and all(r["resolved"] for r in live_f)
        all_void = bool(prim) and not live_p and (not fall or not live_f)
        if all_void:
            at = VOID_RESOLVED_AT
        else:
            at = "primary" if ok_p else ("fallback" if ok_f else
                                         ("OPTIONAL-ABSENT" if self.optional
                                          else "UNRESOLVED"))
        return {"gate": self.name, "phase": self.phase, "resolved_at": at,
                "optional": self.optional,
                "resolved": at != "UNRESOLVED",
                "void": all_void, "void_addresses": voided,
                "primary_ok": ok_p, "fallback_ok": ok_f if fall else None,
                "primary": prim, "fallback": fall, "note": self.note,
                "has_fallback": bool(self.fallback)}


# --------------------------------------------------------------------------- #
# the address book — READ_RULE §2/§4/§5 + DESIGN §7, verbatim (rev R2)           #
# --------------------------------------------------------------------------- #
LEGS = f"legs/s*/{JUDGE}/walled/leg*/manifest.json"
RECORDS = f"s*/{JUDGE}/walled/leg*/records/*.json"
#: R4 §2b(vi) — all SEVEN comparisons must be present. Three layers on each of
#: the six; `b_rid` only on the rid-txt one.
COMPARISONS_FULL = ("s1_vs_tiletie0812", "s1_vs_tiearb2_0816",
                    "s2_vs_tiletie0812", "s2_vs_tiearb2_0816",
                    "base_vs_extension", "s1_vs_s2")
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
                 f"comparisons.{COMPARISON_RID_ONLY}.passed"]
              + ["digest_exclusions.*.carried", "digest_exclusions.*.residual",
                 "digest_exclusions.*.n_excluded", "digest_exclusions.*.rate",
                 "digest_exclusions.*.bound_n",
                 # ⚠️ an address G-DISJOINT READS — ABSENT IS FAIL
                 "digest_exclusions.*.denominator_source",
                 "digest_exclusions.*.rids", "digest_exclusions.*.void",
                 "total_order", "voided_strata"])],
        note="SEVEN comparisons (R4 §2b(vi)): three layers on the four "
             "ARMS-vs-ARMS, three on base_vs_extension (per stratum), three on "
             "s1_vs_s2, and b_rid ONLY on s1s2_vs_exclude_rids. Plus the "
             "exclusion block, whose `denominator_source` is itself a read "
             "address. No fallback — a missing gate file is a FAIL",
        phase="4a-fixture"))

    g.append(Gate("CORPUS_UNION.json (R4-0.5 §3 — the corpus's composition)", [
        Check(R, "corpus/CORPUS_UNION.json",
              ["by_stratum.*.origin_commit", "by_stratum.*.banked_dir",
               "by_stratum.*.sha256_by_file", "by_stratum.*.n_retained",
               "by_stratum.*.n_fresh", "by_stratum.*.copied_not_symlinked",
               "totals.n_retained", "totals.n_fresh", "totals.n_total"])],
        [Check(R, f"{V}/READOUT.json",
               ["widening.corpus_union.totals.n_retained",
                "widening.corpus_union.totals.n_fresh"])],
        note="R4's `n` is a MIXTURE — retained band-135e9 positions COPIED "
             "read-only out of the SPENT run, plus fresh 137e9 extension. The "
             "stamp is where its composition is stated, and the read-out prints "
             "the split. `origin_commit` is the sentinel string "
             "\"untracked\" — never null — when the banked artifacts are not "
             "in git: the CLOSED allow_null table stays at its four entries, "
             "which is a stronger guarantee than widening it for one field",
        phase="4a-fixture"))

    g.append(Gate("FLOORS.json (the frozen floors + exclusion denominator)", [
        Check(R, "FLOORS.json",
              ["n1", "n2", "option_label", "r_s1", "r_s2cap",
               "games_extension_s1", "games_extension_s2", "sub_ranges"])],
        note="R4-8b: written BEFORE the extension band is claimed and committed "
             "WITH the blind pair. It carries the G-COMPLETE floors, the "
             "extension sub-ranges AND the FROZEN exclusion denominator — a "
             "floor chosen after supply is known is a floor fitted to the data",
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
               "widening.gates.crn.ok", "widening.gates.crn.witness_kinds",
               # G-SALT's ADJUDICATION-TIME verdict: the gate left the
               # pre-scoring 4b list, so this is where it is picked up
               "widening.gates.salt.ok",
               "widening.gates.salt.expected_world_seed_salt",
               "widening.gates_summary.G-SALT.ok"])],
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

    g.append(Gate("RUN-MANIFEST fixture (G-SALT primary / G-M / G-BACKEND / "
                  "G-LEAF)", [
        Check(R, "RUN_MANIFEST_S1.json",
              ["world_seed_salt", "m_worlds", "b_ceiling_from_m", "arb_backend",
               "resolved_backend_by_leg", "arb_legal_mask_cache", "git_rev",
               "preflight.checks.leaf_hash.ok",
               "preflight.checks.leaf_hash.harness_leaf_hash",
               "preflight.checks.leaf_hash.expected"]),
        Check(R, "RUN_MANIFEST_S2.json",
              ["world_seed_salt", "m_worlds", "b_ceiling_from_m", "arb_backend",
               "resolved_backend_by_leg", "arb_legal_mask_cache"])],
        note="⚠️ ADDED because G-SALT's PRIMARY (`RUN_MANIFEST::world_seed_salt`) "
             "was audited at NEITHER pass once G-SALT left 4b: 4a carried only "
             "the LEG-manifest fallback and the smoke manifest. Scoping the "
             "false failure out of 4b without this would have traded it for a "
             "SILENT HOLE — the spelling of a gate's primary address unaudited "
             "until the day it is read",
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
    band_keys = ["band_ok", "seed_band", "n_out_of_band", "n_duplicate_seeds",
                 "n_games_realized", "sha256_of_sorted_seeds"]
    g = [Gate("G-BAND (N-file: base + extension [+ top-up])", [
        Check(R, "corpus/CHAMP_GAMES_VERIFY.json", band_keys),
        Check(R, "corpus/CHAMP_GAMES_VERIFY_EXT.json", band_keys)],
        note="R4 §2c generalises the two-file form to N: EACH generated range "
             "emits its OWN verify file, checked against ITS OWN range, with "
             "its own committed floor. The top-up file is required IFF the "
             "clause was exercised. 136e9 is RELEASED UNUSED and must appear in "
             "NO file. No seed list exists anywhere by design — the emitter "
             "publishes sha256_of_sorted_seeds",
        phase="4b")]

    # ⚠️ G-SALT IS DELIBERATELY NOT HERE — see `book_post_scoring`. Its
    # `world_seed_salt` addresses are SCORING-TIME emissions (`RUN_MANIFEST_*`
    # is written by `run_tiletie` at leg launch; `resolved_config` only exists on
    # a leg manifest), so demanding them at 4b would fail EVERY healthy run —
    # the same structural defect READ_RULE §1.5 exists to catch, committed by
    # the harness that enforces it. The pair's §9 step-7 enumeration of 4b names
    # `CHAMP_GAMES_VERIFY`, `GATE_DISJOINT`, `POSITIONS_PLAN`/`ARMS`,
    # `GATE_DRAW`, `GEN_SMOKE` and the `c` block — and no salt.
    #
    # Its CORPUS-TIME half (`deployed_cap_j`, `cap_seed`) does resolve now, and
    # lives in files the enumeration already names, so it is audited here under
    # its own name rather than smuggled into G-SALT's row.
    g.append(Gate("G-SALT (corpus-time half only)", [
        Check(R, "corpus/positions_s*/POSITIONS_PLAN.json", ["deployed_cap_j"],
              min_files=2),
        Check(R, "corpus/positions_s*/ARMS.json", ["cap_seed"],
              kind="json_per_entry", min_files=2)],
        note="the salt half of G-SALT binds POST-SCORING (`--mode post`): "
             "`world_seed_salt` is a MODULE CONSTANT emitted into RUN_MANIFEST "
             "at leg launch, so it cannot exist before a leg has run",
        phase="4b"))

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


#: Gates whose addresses are READ-OUT-TIME emissions: they exist only after a
#: scoring leg and the analyzer have run. They are audited on FIXTURES at 4a
#: (which is what makes their spellings safe before the pair freezes) and on the
#: REAL tree at `--mode post`.
READOUT_TIME_GATES = (
    "G-ARMS", "G-COMPLETE", "G-REPLICATE",
    "READOUT §4 (rung 2 branch inputs)", "READOUT §5 (rung 3 branch inputs)",
    "READOUT §7 (report surface)",
)


def book_post_scoring(R: Path, S: Path) -> list:
    """POST-SCORING — every address that cannot exist until a leg has run.

    ⚠️ This mode is why `G-SALT` is not "optional forever". An address whose
    emitter has not run yet is not an address that may be waived; it is one that
    binds LATER. Dropping it from 4b without a mode that binds it afterwards
    would trade a gate that fails every healthy run for a gate that never runs
    at all — the same hole, wearing the opposite sign.

    ⚠️ Nothing here is audited by the analyzer: `analyze_widening.py` reads no
    `world_seed_salt` at all (checked), so if this harness does not bind G-SALT
    post-scoring, NOTHING does before the read rule's own reader reaches it."""
    g = [Gate("G-SALT", [
        Check(R, "RUN_MANIFEST_S1.json", ["world_seed_salt"]),
        Check(R, "RUN_MANIFEST_S2.json", ["world_seed_salt"]),
        Check(R, "corpus/positions_s*/POSITIONS_PLAN.json", ["deployed_cap_j"],
              min_files=2),
        Check(R, "corpus/positions_s*/ARMS.json", ["cap_seed"],
              kind="json_per_entry", min_files=2)],
        [Check(R, LEGS, ["resolved_config.world_seed_salt"])],
        note="`world_seed_salt` is a MODULE CONSTANT, not a flag — which is "
             "exactly why it must be READ from what the run emitted rather than "
             "assumed. Binds here, where its emitters have run",
        phase="post")]

    # the read-out-time gates, on the REAL tree this time
    for gate in book_fixture(R, S):
        if gate.name in READOUT_TIME_GATES:
            g.append(Gate(gate.name, gate.primary, gate.fallback, gate.note,
                          phase="post"))
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
    if mode in ("post", "all"):
        out += book_post_scoring(R, S)
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

    # R4 shape: BOTH strata carry base-band AND extension-band positions (so
    # `base_vs_extension` is a real comparison), and one EXTENSION digest is
    # planted to collide with a banked corpus — so the exclusion path is
    # exercised on a fixture instead of first meeting it on a real corpus, which
    # is how the R3.3 pair died.
    banked_leg = (Path(refs["tiletie0812"]) /
                  f"positions_{WF.PROFILE}_leg1.jsonl")
    first = json.loads(banked_leg.read_text().splitlines()[0])
    # ⚠️ the two strata mine DISJOINT sub-ranges of BOTH bands — that split IS
    # the disjointness mechanism, and a fixture that shared a range would fail
    # `s1_vs_s2` on the rid layer exactly as a mis-split real corpus would.
    import union_positions as UP                                   # noqa: E402
    banked_corpus = Path(scratch) / "shared_run" / "corpus"
    for tag, base_lo, ext_lo, sd in (("s1", 135000000000, 137000000000, 41),
                                     ("s2", 135000000350, 137000000508, 43)):
        # the RETAINED side lives under the SPENT pair, read-only ...
        WF.make_r4_corpus(banked_corpus / f"positions_{tag}", stratum=tag,
                          seed=sd, n_base=8, n_ext=0, base_lo=base_lo,
                          collide_with=(first["rid"], first["checksum"])
                          if tag == "s1" else None)
        # ... the fresh side under the LIVE one ...
        WF.make_r4_corpus(corpus / f"positions_{tag}_ext", stratum=tag,
                          seed=sd + 100, n_base=0, n_ext=6, ext_lo=ext_lo)
        # ... and the UNION is assembled by the REAL emitter, so the 4a schema
        # audit resolves CORPUS_UNION.json's spellings against the real writer.
        UP.assemble(banked_corpus / f"positions_{tag}",
                    corpus / f"positions_{tag}_ext",
                    corpus / f"positions_{tag}", stratum=tag)
    WF.make_records(share, json.loads(
        (corpus / "positions_s1" / "ARMS.json").read_text()),
        m=128, seed=11, stratum_dir="s1")
    WF.make_records(share, json.loads(
        (corpus / "positions_s2" / "ARMS.json").read_text()),
        m=32, seed=13, stratum_dir="s2")

    cmds = [
        [py, str(HERE / "gate_disjoint.py"), "--r4",
         "--s1-dir", str(corpus / "positions_s1"),
         "--s2-dir", str(corpus / "positions_s2"),
         "--ref", f"tiletie0812={refs['tiletie0812']}",
         "--ref", f"tiearb2_0816={refs['tiearb2_0816']}",
         "--exclude-rids", str(excl),
         "--floors", str(run / "FLOORS.json"),
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
         "--floors", str(run / "FLOORS.json"),
         "--champ-games-verify", str(corpus / "CHAMP_GAMES_VERIFY.json"),
         "--champ-games-verify", str(corpus / "CHAMP_GAMES_VERIFY_EXT.json"),
         "--gate-disjoint", str(run / "GATE_DISJOINT.json"),
         "--corpus-union", str(corpus / "CORPUS_UNION.json"),
         "--run-manifest", str(run / "RUN_MANIFEST_S1.json"),
         "--run-manifest", str(run / "RUN_MANIFEST_S2.json"),
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
             "OPTIONAL-ABSENT": "-- ", VOID_RESOLVED_AT: "VOI"}
    for r in results:
        print(f"[acceptance] {marks[r['resolved_at']]} {r['phase']:11s} "
              f"{r['gate']:36s} {r['resolved_at']}")
        for section in ("primary", "fallback"):
            for c in r[section]:
                for s in c.get("sanctioned_nulls", []):
                    print(f"[acceptance]        allow_null  row {s['row']!r} "
                          f"sanctions {s['key']} (witness "
                          f"{','.join(s.get('witness', []))})")
                if c.get("void"):
                    print(f"[acceptance]        {section:8s} "
                          f"{'VOID':10s} {c['address']}  <- {c['why']} "
                          f"({c['void_witness']['address']})")
                    continue
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
    ap.add_argument("--run-dir", required=True, help="the RUN/ tree (shared_run_r4/ — the LIVE R4 pair; shared_run/ is the "
                         "SPENT R3.3 pair and is read-only)")
    ap.add_argument("--share", default="/mnt/c/carc-shared/tiearb_widening_20260817",
                    help="SHARE root holding the per-record leg output")
    ap.add_argument("--mode", choices=("4a", "4b-pre", "4b", "post", "all"),
                    default="all",
                    help="4a = fixture schema audit + G-BITEXACT@HEAD "
                         "(pre-blind-commit, genuinely corpus-free); "
                         "4b-pre = the four judge smokes on the FRESH corpus; "
                         "4b = the corpus artifacts; "
                         "post = POST-SCORING — G-SALT and the read-out-time "
                         "gates, whose emitters have not run before a leg does")
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

    # ⚠️ ARTIFACT-DERIVED, NEVER A FLAG (§D4.16). There is deliberately no CLI
    # option that activates, widens or silences this: `ABSENT IS FAIL` may not
    # become silenceable.
    scope = void_stratum_scope(run_dir)
    if scope["active"]:
        print(f"[acceptance] S2 VOID SCOPE ACTIVE — {scope['why']} "
              f"({scope['address']}, {scope['source']}). S2-marked addresses "
              f"report '{VOID_WHY}'; S1 and every non-S2 address are UNTOUCHED "
              f"and ABSENT IS FAIL still binds them.")

    results = [g.resolve(scope) for g in address_book(run_dir, a.share, a.mode)]

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
              "void_scope": scope,
              "n_void": sum(1 for r in results if r.get("void")),
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
