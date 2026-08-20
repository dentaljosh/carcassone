#!/usr/bin/env python3
"""**A1 / A2 / A3** — the acceptance passes of the RUNG-3 `R5` preregistration.

Licensed by `measurement/tiearb_widening_20260817/rung3_r5/READ_RULE.md` §1,
which defines three passes and their mandatory completeness assertion — and then
**names no tool for them**. That silence is why the `A2` checkpoint was skipped
before the first scoring leg (recorded as deviation **D6**). This module is the
missing actor; `READ_RULE.md` §2 is its ONLY address authority.

  `--pass A1`  `[pre-corpus]`   STATIC SCHEMA AUDIT against the committed
                                fixtures in `<run>/fixtures/`, for every
                                `[post-corpus]` and `[post-scoring]` address.
                                Key presence and JSON type ONLY.
  `--pass A2`  `[post-corpus]`  resolve every `[pre-corpus]` and
                                `[post-corpus]` address **LIVE** — primary and
                                fallback independently — and **VERIFY THE
                                FREEZE** (the three pinned shas, §D6).
  `--pass A3`  `[post-scoring]` resolve the `[post-scoring]` addresses live.

⭐ **THE CARDINAL PROPERTY: NO VALUE IS EVER PRINTED OR STORED.** Per address
this tool emits the ADDRESS, its GATE, its MARKER, `resolved`/`UNRESOLVED`, and
the JSON TYPE NAME (`object` / `array` / `string` / `number` / `boolean` /
`null`). Never the value, never a truncation of it, never a length that is
itself the value, never a sha. The pair is read BLIND — an auditor that leaks a
value is a read-out, and running it would spend the single-use rule.

⭐ **PRIMARY AND FALLBACK ARE RESOLVED INDEPENDENTLY, ALWAYS.** Every address in
the table is a first-class row; nothing short-circuits on a primary. A fallback
that has quietly become unresolvable is the fail-always/pass-always defect this
campaign keeps finding (`READ_RULE` §2.2 exists because a review nearly *created*
one), so an UNRESOLVED fallback FAILS the pass and is listed under
`unaudited_fallbacks` — it is never downgraded to a warning because its primary
happened to resolve.

⭐ **THE COMPLETENESS ASSERTION IS OVER THE FILE, NOT OVER THE TABLE.**
`parsed_addresses()` re-derives the address set from `READ_RULE.md` §2 at every
pass and compares it to this module's table:

    named in the file, in no pass  ⇒ FAIL (uncovered)
    in the table, not in the file  ⇒ FAIL (invented — §1.4's prohibition)

⚠️ **REPORTED, NEVER RESOLVED.** §2's carried-gate row (`G-LEAF`, `G-PREFIX`,
`G-CRN`, `G-ARMS`, `G-UNCAPPED`, `G-DRAW`, `G-BITEXACT@HEAD`) has the literal
address column *"as carried"* — it names NO address, so it can be audited at no
pass. Those gates are emitted in `carried_without_address`. A row that cannot be
evaluated must NEVER silently count as covered, and this tool does not invent an
address to make one countable.

⛔ **NULL IS ABSENT.** `READ_RULE` §0 reasons under `ABSENT IS FAIL`; a key
present with `null` is reported `UNRESOLVED` with type `null`. R5's §2 address
set contains no sanctioned null (the `cap_j` row of R4's CLOSED `allow_null`
table is not an R5 address), so no exception list exists here — and adding one
later is how a fail-closed rule becomes fail-open.

Exit codes
    0   the pass resolved every address it is positioned to resolve
    2   at least one address is UNRESOLVED, or the completeness assertion failed
    3   ⛔ **D6 RAISE** — a pinned sha does not match, or cannot be recomputed.
        A2 VERIFIES the freeze; it does not assume it. Nothing is edited,
        re-pinned or re-derived: the pass stops and escalates to the owner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

TOOL = "[acceptance-r5]"

# ⚠️ Placeholders as the pair spells them. `<name>` / `<rid>` are WILDCARDS over
# one key; `leg<N>` is a wildcard over one directory. They are translated to a
# resolution spelling in the table below, never by pattern-guessing at run time.
WILDCARD = "*"


# --------------------------------------------------------------------------- #
# the address language — presence + TYPE, and nothing else                      #
# --------------------------------------------------------------------------- #
def json_type(v) -> str:
    """The JSON TYPE NAME, which is the ONLY thing this tool is allowed to say
    about a value. Note `int` and `float` collapse to `number`: the distinction
    is a property of the value, and this tool reports properties of the SCHEMA."""
    if v is None:
        return "null"
    if isinstance(v, bool):          # ⚠️ before int — bool IS an int in Python
        return "boolean"
    if isinstance(v, (int, float)):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object"
    return "unknown"


def dig(obj, dotted: str):
    """Every value reachable by `dotted` (`.`-separated; `*` matches any one key
    of a dict / any one element of a list). `[]` when nothing matches."""
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


# --------------------------------------------------------------------------- #
# the READ_RULE parser — auditable, and deliberately narrow                      #
# --------------------------------------------------------------------------- #
#: A backticked token in the `address` column is an ADDRESS iff it carries `::`
#: (`PATH::keypath`) or is a bare PATH (`RUN/ARMS_R5.json`). Everything else in
#: that column is prose — §2's `G-CORPUS` cell alone backticks `excluded_rids`,
#: `arms_r5_sha256`, `R4_ARMS.rids`, `|rids| == 1060` and a rid literal, none of
#: which is an address. ⚠️ The bare-path form REQUIRES a `/`: that is what keeps
#: the prose mention of `ARMS_R5.json` from being counted a second time next to
#: the real `RUN/ARMS_R5.json`, and keeps `tier1_rust_leg.py:401` out entirely.
_BARE_PATH = re.compile(r"^[\w./<>*\-]+/[\w./<>*\-]+\.(?:json|jsonl|md)$")
_GATE_NAME = re.compile(r"^G-[A-Z0-9@\-]+$")
_TICKED = re.compile(r"`([^`]+)`")


def _split_top(body: str) -> list:
    """Split on commas at brace-depth 0 (nested groups stay whole)."""
    out, depth, cur = [], 0, []
    for ch in body:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return out


def expand_braces(spec: str) -> list:
    """`a.{b,c}.d` → `a.b.d`, `a.c.d`; NESTED groups expand too, which §2's
    `G-DISJOINT` address needs (`{passed, comparisons.<name>.layers.{a_root_id,
    b_rid}.n_intersection}`). An unbalanced brace is returned literally rather
    than guessed at — a parser that repairs its input cannot be audited."""
    i = spec.find("{")
    if i < 0:
        return [spec.strip()]
    depth, j = 0, -1
    for k in range(i, len(spec)):
        if spec[k] == "{":
            depth += 1
        elif spec[k] == "}":
            depth -= 1
            if depth == 0:
                j = k
                break
    if j < 0:
        return [spec.strip()]
    head, body, tail = spec[:i], spec[i + 1:j], spec[j + 1:]
    out = []
    for alt in _split_top(body):
        for done in expand_braces(head + alt.strip() + tail):
            if done not in out:
                out.append(done)
    return out


def _markdown_tables(text: str) -> list:
    """Contiguous blocks of `|`-delimited lines, header row first."""
    tables, cur = [], []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("|") and s.endswith("|"):
            cur.append(s)
        elif cur:
            tables.append(cur)
            cur = []
    if cur:
        tables.append(cur)
    return tables


def _cells(row: str) -> list:
    return [c.strip() for c in row.strip().strip("|").split("|")]


def _clean_header(cell: str) -> str:
    return cell.replace("`", "").replace("*", "").strip().lower()


def parsed_addresses(text: str) -> dict:
    """The addresses `READ_RULE.md` NAMES, re-derived from the file itself.

    ⭐ SCOPE: the ONE §2 table — the table whose header carries BOTH a `gate` and
    an `address` column. That selection rule is mechanical and it matters:

      · §0's carried-gate reconciliation has a `gate` column and NO address one.
      · §2.2's rulings table has an `address` column and NO gate one — and one of
        its rows is `SMOKE_R5.json::resolved_config.m`, a spelling the pair
        **REJECTS** ("⛔ wrong — fixed to top-level `m_worlds`"). Parsing it as
        "named" would oblige this tool to audit an address the pair killed, i.e.
        to build the fail-always fallback §2.2 exists to prevent. It is surfaced
        under `rulings_not_addresses` instead of being counted.
      · §4's power table has neither.

    Returns `addresses` (sorted, brace-expanded, one per key),
    `by_gate`, `carried_without_address` (rows whose address column names none),
    and `rulings_not_addresses`.
    """
    addresses, by_gate, carried = [], {}, []
    table = None
    for tbl in _markdown_tables(text):
        head = [_clean_header(c) for c in _cells(tbl[0])]
        if "gate" in head and "address" in head:
            table = (tbl, head.index("gate"), head.index("address"))
            break
    if table is None:
        raise SystemExit(f"{TOOL} REFUSING: no §2 gate/address table found in the "
                         f"READ_RULE — the address authority is missing, and an "
                         f"acceptance pass with no authority audits nothing.")
    rows, gi, ai = table
    for row in rows[1:]:
        cells = _cells(row)
        if len(cells) <= max(gi, ai):
            continue
        if set(cells[0].replace(" ", "")) <= {"-", ":"}:   # the |---|---| rule
            continue
        gates = [t for t in _TICKED.findall(cells[gi]) if _GATE_NAME.match(t)]
        found = []
        for tok in _TICKED.findall(cells[ai]):
            tok = tok.strip().strip("*").strip()
            if "::" in tok:
                path, keyspec = tok.split("::", 1)
                for key in expand_braces(keyspec):
                    found.append(f"{path.strip()}::{key.strip()}")
            elif _BARE_PATH.match(tok):
                found.append(tok)
        if not found:
            # ⚠️ "as carried" is not an address. The row is REPORTED, never
            # resolved — see the module docstring.
            carried.append({"gate_cell": cells[gi], "gates": gates,
                            "address_cell": cells[ai]})
            continue
        for a in found:
            if a not in addresses:
                addresses.append(a)
            by_gate.setdefault(gates[0] if gates else "?", []).append(a)

    # §2.2's rulings table, surfaced so the REJECTED spelling is visible rather
    # than silently absent from both the covered set and the report.
    rulings = []
    for tbl in _markdown_tables(text):
        head = [_clean_header(c) for c in _cells(tbl[0])]
        if "address" in head and "gate" not in head and "verdict" in head:
            ai2 = head.index("address")
            for row in tbl[1:]:
                cells = _cells(row)
                if len(cells) <= ai2 or set(cells[0].replace(" ", "")) <= {"-", ":"}:
                    continue
                for tok in _TICKED.findall(cells[ai2]):
                    if "::" in tok:
                        rulings.append(tok.strip())
    return {"addresses": sorted(addresses), "by_gate": by_gate,
            "carried_without_address": carried,
            "rulings_not_addresses": sorted(set(rulings))}


# --------------------------------------------------------------------------- #
# the address table — CODE-RESIDENT, one row per address named in §2            #
# --------------------------------------------------------------------------- #
class Addr:
    """ONE address of `READ_RULE.md` §2.

    `address`   the spelling AS THE FILE WRITES IT (placeholders and all). This
                string is what the completeness assertion compares — so a table
                row whose spelling drifts from the file reads as `invented`,
                which is the intended alarm.
    `marker`    the §1 existence-time marker, which decides WHICH passes may
                demand it. A pass never demands an address its own position
                makes impossible.
    `role`      `primary` | `fallback` — resolved independently, always.
    `glob`      resolution spelling under the RUN dir (`leg<N>` → `leg*`).
    `key`       resolution spelling of the key path (`<name>`/`<rid>` → `*`).
    `fixture`   candidate fixture filenames for A1, in preference order.
    """

    def __init__(self, address, gate, marker, glob, key=None, kind="json",
                 fixture=(), role="primary", note=""):
        self.address = address
        self.gate = gate
        self.marker = marker
        self.glob = glob
        # ⚠️ `<name>` / `<rid>` are the PAIR's placeholder spelling; `*` is the
        # resolution spelling. The translation happens HERE, once, so the
        # `address` string can stay byte-faithful to §2 (which is what the
        # completeness assertion compares) while `key` stays resolvable.
        self.key = re.sub(r"<[^>]+>", WILDCARD, key) if key else key
        self.kind = kind
        self.fixture = tuple(fixture)
        self.role = role
        self.note = note

    #: A1 audits every `[post-corpus]` and `[post-scoring]` address on fixtures;
    #: A2 every `[pre-corpus]` and `[post-corpus]` address live; A3 the
    #: `[post-scoring]` ones. Union == the whole table, asserted at every pass.
    def in_pass(self, which: str) -> bool:
        if which == "A1":
            return self.marker in ("[post-corpus]", "[post-scoring]")
        if which == "A2":
            return self.marker in ("[pre-corpus]", "[post-corpus]")
        return self.marker == "[post-scoring]"


# ---- artifact → (RUN-relative glob, A1 fixture candidates) ----------------- #
CORPUS = ("CORPUS_R5.json", ("CORPUS_R5.fixture.json",))
STAGING = ("STAGING_R5.json", ("STAGING_R5.fixture.json",))
DUPE = ("GATE_INTERNAL_DUPE.json", ("GATE_INTERNAL_DUPE.fixture.json",))
DISJOINT = ("GATE_DISJOINT_R5.json", ("GATE_DISJOINT_R5.fixture.json",))
SMOKE = ("SMOKE_R5.json", ("SMOKE_R5.fixture.json",))
MANIFEST = ("RUN_MANIFEST_R5.json", ("RUN_MANIFEST_R5.fixture.json",))
#: ⚠️ `leg<N>` is a DIRECTORY wildcard. §2.2 verified this manifest's
#: `resolved_config` block AT SOURCE (`tier1_rust_leg.py:396-406`) and RETAINED
#: it against a review that would have rewritten it — do not "fix" the spelling.
LEG = ("legs/s2/tier1-greedy/walled/leg*/manifest.json",
       ("leg_manifest.fixture.json",))
#: the SPELLING §2 uses for the same artifact — `leg<N>`, not the glob. The
#: address string must match the file byte for byte or the completeness
#: assertion reads the row as `invented`, which is the intended alarm.
LEG_SPELLED = "RUN/legs/s2/tier1-greedy/walled/leg<N>/manifest.json"
#: ⭐ RULE 7 — the pair contradicts itself on this fixture's NAME: DESIGN's
#: fixture list says `READOUT.fixture.json`, its execution-layer ruling says
#: `READOUT_R5.fixture.json`, and the RUN dir carries the former. HANDLED AND
#: REPORTED, not resolved: either name is accepted, the one actually found is
#: recorded under `readout_fixture_ambiguity`, and the pair is NOT edited.
READOUT = ("verdicts/READOUT*.json",
           ("READOUT_R5.fixture.json", "READOUT.fixture.json"))
#: ⚠️ `…/ARMS.json` and `…/manifest.json` in §2 are ELLIPSIS spellings that
#: inherit the directory of the address printed immediately before them in the
#: same cell — `RUN/corpus/positions_s2/` for G-SALT's ARMS, the leg-manifest
#: path for G-BACKEND's fallback. That inheritance is recorded HERE, in code,
#: rather than re-guessed by each reader.
PLAN = ("corpus/positions_s2/POSITIONS_PLAN.json", ("POSITIONS_PLAN.fixture.json",))
ARMS_STAGED = ("corpus/positions_s2/ARMS.json", ("ARMS.fixture.json",))


def _rows(artifact, gate, marker, keys, kind="json", role="primary",
          prefix="RUN/", spelled=None, note=""):
    glob, fixture = artifact
    path = spelled if spelled is not None else prefix + glob
    return [Addr(f"{path}::{k}", gate, marker, glob, k, kind, fixture, role, note)
            for k in keys]


#: ⭐ THE TABLE. Every row's `address` is copied from `READ_RULE.md` §2's address
#: column; every `marker` from its marker column. Both are re-checked against the
#: file at every pass by the completeness assertion, so a silent drift here is
#: caught rather than trusted.
ADDRESS_TABLE = tuple(
    # ---- G-CORPUS `[post-corpus]` — corpus IDENTITY, not discovery (§2.1) --- #
    _rows(CORPUS, "G-CORPUS", "[post-corpus]",
          ["leg_path", "leg_sha256", "r4_exclusion_list_sha256", "n_in",
           "n_excluded_r5", "n_positions", "excluded_rids", "arms_r5_sha256"],
          note="the three shas in this row are the ones A2 RECOMPUTES (§D6)")
    # ⭐ ARMS_R5.json is the MATERIALIZED POPULATION AUTHORITY (DESIGN ruling
    # 2026-08-19). It is addressed as a bare PATH — the pair names no key path
    # on it — so presence is all this tool may check, and it must not invent
    # `::rids` to check more (§1.4).
    + [Addr("RUN/ARMS_R5.json", "G-CORPUS", "[post-corpus]", "ARMS_R5.json",
            None, "exists", ("ARMS_R5.fixture.json",),
            note="population authority; addressed as a bare path")]

    # ---- G-STAGED `[post-corpus]` — the staging WITNESS ---------------------- #
    # ⚠️ CORPUS_R5's identity does NOT cover this layer: it is written before
    # staging exists (DESIGN staging recipe, ruling (c)), which is why the pair
    # addresses a separate artifact rather than re-reading the corpus stamp.
    + _rows(STAGING, "G-STAGED", "[post-corpus]",
            ["arms_r5_sha256", "staged_arms_sha256", "arms_copy_identical",
             "n_leg_rids", "n_arms_rids", "rid_sets_equal", "missing_in_leg",
             "missing_in_arms", "stage_chunks_rid_set_agrees", "n_chunks"],
            note="both directions of the rid-set equality are ADDRESSED "
                 "(missing_in_leg AND missing_in_arms) — D4's missing invariant")

    # ---- G-INTERNAL-DUPE `[post-corpus]` ------------------------------------ #
    # ⚠️ §2.1: this gate is a CORPUS-IDENTITY check, not a discovery gate —
    # `d_internal` is a deterministic function of a sha-pinned leg. Its
    # falsifiable content is the CONSISTENCY block, which is why every one of
    # those keys is addressed rather than just the ratio.
    + _rows(DUPE, "G-INTERNAL-DUPE", "[post-corpus]",
            ["n_positions", "n_dupe_groups", "n_dupe_positions", "d_internal",
             "ply_histogram", "band_pairs", "leg_sha256"])

    # ---- G-DISJOINT `[post-corpus]` — rid/root layers ONLY ------------------ #
    # ⛔ the digest layer is NOT carried (§0). ⚠️ `<name>` is a wildcard over the
    # comparisons, and one of them (`s2_vs_exclude_rids`) legitimately declares
    # `a_root_id` ABSENT — a JSON reference list has no root identity, and the
    # emitter records it in `layers_absent` rather than fabricating a zero. So
    # this address resolves when the layer resolves on the comparisons that HAVE
    # it; demanding it on every comparison would fail a healthy run.
    + _rows(DISJOINT, "G-DISJOINT", "[post-corpus]",
            ["passed",
             "comparisons.<name>.layers.a_root_id.n_intersection",
             "comparisons.<name>.layers.b_rid.n_intersection"])

    # ---- G-BAND `[post-corpus]` — RESTORED (§0, R9) ------------------------- #
    # ⛔ `n_duplicate_seeds` is DELETED (§2.2 N1) and is deliberately NOT here:
    # at the seed level it is vacuous by construction. `max_positions_per_seed`
    # is the mining-ceiling invariant it was standing in for.
    + _rows(CORPUS, "G-BAND", "[post-corpus]",
            ["seed_ranges", "n_distinct_seeds", "n_out_of_band",
             "n_seeds_136e9", "max_positions_per_seed"])

    # ---- G-COMPLETE / G-FAILED `[post-scoring]` ----------------------------- #
    + _rows(READOUT, "G-COMPLETE", "[post-scoring]",
            ["widening.completion.s2_n"], spelled="READOUT")
    # ⚠️ `n_attempted` is ADDRESSED in R5 (it is the denominator of the bound;
    # an unaddressed denominator is an unauditable rate).
    + _rows(READOUT, "G-FAILED", "[post-scoring]",
            ["widening.failed.n_failed_rids", "widening.failed.n_attempted",
             "widening.failed.rate", "widening.failed.by_class"],
            spelled="READOUT")

    # ---- G-M — the ONE gate the file gives TWO markers ----------------------- #
    # ⭐ REQUIREMENT-6 SPLIT, with the reason: §2 marks G-M
    # "`[post-scoring]` + `[post-corpus]`" and then says why a `[post-corpus]`
    # address is REQUIRED (R1) — "so the constant this revision exists to
    # correct halts the run BEFORE ~300 wh is spent". The pre-leg address is
    # therefore `[post-corpus]` (A2, before the first scoring leg); the post
    # addresses and the leg-manifest fallback are `[post-scoring]` (A3), because
    # neither emitter has run before a leg does. Marking them all
    # `[post-scoring]` would postpone the halt past the spend; marking them all
    # `[post-corpus]` would fail every healthy run at A2.
    + _rows(SMOKE, "G-M", "[post-corpus]", ["m_worlds"],
            note="⭐ N2: TOP-LEVEL. `run_tiletie`'s smoke manifest has NO "
                 "`resolved_config` key — the rejected spelling is §2.2's")
    + _rows(MANIFEST, "G-M", "[post-scoring]", ["m_worlds", "b_ceiling_from_m"])
    + _rows(LEG, "G-M", "[post-scoring]", ["resolved_config.m"], role="fallback",
            spelled=LEG_SPELLED,
            note="✅ verified to EXIST at source (§2.2) — retained, not rewritten")

    # ---- G-SALT `[post-scoring]` -------------------------------------------- #
    + _rows(MANIFEST, "G-SALT", "[post-scoring]", ["world_seed_salt"])
    + _rows(PLAN, "G-SALT", "[post-scoring]", ["deployed_cap_j"],
            note="`deployed_cap_j == 4` is now ADDRESSED (R6)")
    # `<rid>` is a wildcard over the top-level rid keys: `cap_seed` must be
    # present for EVERY rid, so the address is checked per entry.
    + [Addr("…/ARMS.json::<rid>.cap_seed", "G-SALT", "[post-scoring]",
            ARMS_STAGED[0], "cap_seed", "json_per_entry", ARMS_STAGED[1],
            note="ellipsis inherits `RUN/corpus/positions_s2/` from the address "
                 "printed before it in the same cell")]
    + _rows(LEG, "G-SALT", "[post-scoring]", ["resolved_config.world_seed_salt"],
            role="fallback", spelled=LEG_SPELLED)

    # ---- G-BACKEND `[post-scoring]` ----------------------------------------- #
    + _rows(MANIFEST, "G-BACKEND", "[post-scoring]",
            ["arb_backend", "resolved_backend_by_leg", "arb_legal_mask_cache"])
    + [Addr("…/manifest.json::resolved_config.legal_mask_cache", "G-BACKEND",
            "[post-scoring]", LEG[0], "resolved_config.legal_mask_cache",
            "json", LEG[1], role="fallback",
            note="ellipsis inherits the leg-manifest path from G-M/G-SALT")]

    # ---- G-DDRAW `[post-scoring]` — the conjunct EXISTS (§2) ---------------- #
    + _rows(READOUT, "G-DDRAW", "[post-scoring]",
            ["widening.j_rider.d_draw.d_draw_ran"], spelled="READOUT")
    + [Addr("RUN/D_DRAW.json", "G-DDRAW", "[post-scoring]", "D_DRAW.json",
            None, "exists", ("D_DRAW.fixture.json",))]

    # ---- G-TWOBOX `[post-scoring]` ------------------------------------------ #
    + [Addr("RUN/MERGE_REPORT_s2.json", "G-TWOBOX", "[post-scoring]",
            "MERGE_REPORT_s2.json", None, "exists",
            ("MERGE_REPORT_s2.fixture.json",))]
)


def address_table() -> list:
    """The live table. Indirection is deliberate: a test that DELETES a row must
    be able to prove the completeness assertion catches the hole."""
    return list(ADDRESS_TABLE)


# --------------------------------------------------------------------------- #
# resolution — presence + TYPE, on fixtures (A1) or live (A2/A3)                 #
# --------------------------------------------------------------------------- #
def _resolve_doc(row: Addr, doc, label: str) -> tuple:
    """`(ok, types, why)` for ONE document. Nothing here may return a value."""
    if row.kind == "exists":
        return True, [], None
    types, missing = set(), []
    if row.kind == "json_per_entry":
        if not isinstance(doc, dict) or not doc:
            return False, [], f"{label}: not a non-empty rid-keyed object"
        for entry in doc.values():
            vals = dig(entry, row.key)
            for v in vals:
                types.add(json_type(v))
            if not vals:
                missing.append(f"{label}::<rid>.{row.key} ABSENT")
            elif any(v is None for v in vals):
                missing.append(f"{label}::<rid>.{row.key} null (ABSENT IS FAIL)")
    else:
        vals = dig(doc, row.key)
        for v in vals:
            types.add(json_type(v))
        if not vals:
            missing.append(f"{label}::{row.key} ABSENT")
        elif any(v is None for v in vals):
            missing.append(f"{label}::{row.key} null (ABSENT IS FAIL)")
    # dedup: a per-entry miss on 1,060 rids is ONE defect, not 1,060 lines
    seen = []
    for m in missing:
        if m not in seen:
            seen.append(m)
    return (not seen), sorted(types), ("; ".join(seen[:4]) if seen else None)


def resolve_live(row: Addr, run: Path) -> dict:
    """A2/A3 — resolve `row` against the RUN tree."""
    out = {"address": row.address, "gate": row.gate, "marker": row.marker,
           "role": row.role, "mode": "live", "state": "UNRESOLVED",
           "types": [], "why": None, "n_files": 0}
    files = sorted(run.glob(row.glob)) if run.is_dir() else []
    out["n_files"] = len(files)
    if not files:
        out["why"] = (f"no file matches {row.glob} under the RUN dir "
                      f"(ABSENT IS FAIL)")
        return out
    ok, types, whys = True, set(), []
    for f in files:
        if row.kind == "exists":
            continue
        try:
            doc = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            ok = False
            whys.append(f"{f.name}: unreadable ({exc.__class__.__name__})")
            continue
        fok, ftypes, why = _resolve_doc(row, doc, f.name)
        ok = ok and fok
        types.update(ftypes)
        if why:
            whys.append(why)
    out["types"] = sorted(types)
    out["state"] = "resolved" if ok else "UNRESOLVED"
    out["why"] = "; ".join(whys[:4]) or None
    return out


def resolve_fixture(row: Addr, fixtures: Path) -> dict:
    """A1 — the STATIC SCHEMA AUDIT, against the committed fixtures.

    ⚠️ An address with NO committed fixture is NOT waived: it is reported
    UNRESOLVED with the fixture name it wanted, and listed under
    `no_fixture_committed`. A1 exists to catch a mis-spelled address BEFORE the
    blind commit; an address whose spelling is first exercised on read-out day is
    the silent hole the campaign keeps re-finding, and calling it a pass here
    would manufacture exactly that hole.
    """
    out = {"address": row.address, "gate": row.gate, "marker": row.marker,
           "role": row.role, "mode": "fixture", "state": "UNRESOLVED",
           "types": [], "why": None, "fixture": None,
           "fixture_candidates": list(row.fixture)}
    hit = next((n for n in row.fixture if (fixtures / n).is_file()), None)
    if hit is None:
        out["why"] = ("NO COMMITTED FIXTURE (looked for "
                      f"{' | '.join(row.fixture) or '<none declared>'}) — A1 "
                      "cannot audit this spelling; it stays unaudited until it "
                      "is read live")
        out["no_fixture"] = True
        return out
    out["fixture"] = hit
    if row.kind == "exists":
        out["state"] = "resolved"
        return out
    try:
        doc = json.loads((fixtures / hit).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        out["why"] = f"{hit}: unreadable ({exc.__class__.__name__})"
        return out
    ok, types, why = _resolve_doc(row, doc, hit)
    out["types"] = types
    out["state"] = "resolved" if ok else "UNRESOLVED"
    out["why"] = why
    return out


# --------------------------------------------------------------------------- #
# ⛔ D6 — A2 VERIFIES THE FREEZE, it does not assume it                          #
# --------------------------------------------------------------------------- #
class FreezeRaise(Exception):
    """A pinned sha drifted, or could not be recomputed. Exit 3, nothing else."""


#: ⚠️ THE R4 EXCLUSION LIST'S REFERENT, pinned by `FLOORS_R5.json`
#: (`r4_exclusion_list_sha256_referent`): the sha is over
#: `json.dumps(sorted(GATE_DISJOINT.json::digest_exclusions.S2.rids))` — default
#: separators, NO `sort_keys`, UTF-8, no trailing newline — of
#: `shared_run_r4/GATE_DISJOINT.json`. ⛔ It is **NOT** any `EXCLUDE_RIDS_*.txt`
#: file (N4); a verifier that reaches for those CANNOT reproduce it and would
#: convict a healthy freeze.
R4_GATE_DISJOINT = "../shared_run_r4/GATE_DISJOINT.json"


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _raise(what: str) -> None:
    raise FreezeRaise(
        f"⛔ RAISE TO THE OWNER — D6 FREEZE VERIFICATION FAILED.\n"
        f"{TOOL} {what}\n"
        f"{TOOL} A2 verifies the freeze; it does not assume it. This tool does "
        f"NOT edit, re-pin or re-derive any pinned value, and it does not "
        f"continue: the corpus a gate sha-pins is the corpus that was measured, "
        f"so drift is an owner decision, never a harness one.\n"
        f"{TOOL} No sha is printed (the pair is read blind) — the comparison "
        f"result is the whole output.")


def verify_freeze(run: Path) -> dict:
    """The three pinned shas of `READ_RULE` §2, RECOMPUTED.

    ⭐ Reported as `match` / `MISMATCH` ONLY. No sha is printed — not the pinned
    one, not the recomputed one — because a sha is a value and rule 1 governs
    every emission of this tool. Likewise no PATH read out of an artifact is
    printed: `CORPUS_R5.json::leg_path` is itself a value.
    """
    checks = []
    cpath = run / "CORPUS_R5.json"
    if not cpath.is_file():
        _raise("CORPUS_R5.json is absent — the three pinned shas cannot be "
               "recomputed, so the freeze is UNVERIFIED (which is exactly the "
               "state D6 recorded).")
    try:
        corpus = json.loads(cpath.read_text())
    except (OSError, json.JSONDecodeError):
        _raise("CORPUS_R5.json is unreadable — the freeze cannot be verified.")

    # (a) the physical leg file ------------------------------------------------
    leg_path, leg_sha = corpus.get("leg_path"), corpus.get("leg_sha256")
    if not isinstance(leg_path, str) or not isinstance(leg_sha, str):
        _raise("CORPUS_R5.json::{leg_path, leg_sha256} do not both resolve to "
               "strings — the leg pin cannot be checked.")
    lp = Path(leg_path)
    if not lp.is_absolute():
        lp = run / lp
    if not lp.is_file():
        _raise("the file named by CORPUS_R5.json::leg_path is not present — the "
               "sha-pinned leg cannot be re-hashed. (The path is a VALUE and is "
               "not printed.)")
    ok_a = _sha256_file(lp) == leg_sha
    checks.append({"check": "leg file vs CORPUS_R5.json::leg_sha256",
                   "result": "match" if ok_a else "MISMATCH"})
    if not ok_a:
        _raise("CORPUS_R5.json::leg_sha256 does NOT match the sha256 of the file "
               "at CORPUS_R5.json::leg_path — the corpus on disk is not the "
               "corpus the calibration measured (§2.1: both degeneracy gates are "
               "corpus-IDENTITY checks, and this is the identity failing).")

    # (b) the materialized population authority --------------------------------
    arms_sha = corpus.get("arms_r5_sha256")
    ap = run / "ARMS_R5.json"
    if not isinstance(arms_sha, str) or not ap.is_file():
        _raise("RUN/ARMS_R5.json or CORPUS_R5.json::arms_r5_sha256 is absent — "
               "the MATERIALIZED POPULATION AUTHORITY cannot be verified, and "
               "every consumer READS it (DESIGN ruling 2026-08-19).")
    ok_b = _sha256_file(ap) == arms_sha
    checks.append({"check": "RUN/ARMS_R5.json vs CORPUS_R5.json::arms_r5_sha256",
                   "result": "match" if ok_b else "MISMATCH"})
    if not ok_b:
        _raise("RUN/ARMS_R5.json does NOT hash to CORPUS_R5.json::arms_r5_sha256 "
               "— the population authority on disk is not the one the corpus "
               "stamp pins.")
    # FLOORS_R5.json carries its own copy of the same sha; when it does, the two
    # copies must agree. A second copy that has drifted is a second authority,
    # which is the shape the DESIGN ruling exists to forbid.
    fp = run / "FLOORS_R5.json"
    floors_copy = None
    if fp.is_file():
        try:
            floors = json.loads(fp.read_text())
        except (OSError, json.JSONDecodeError):
            _raise("FLOORS_R5.json is unreadable — its copy of arms_r5_sha256 "
                   "cannot be compared.")
        vals = dig(floors, "population_authority.arms_r5_sha256")
        if vals:
            floors_copy = "match" if vals[0] == arms_sha else "MISMATCH"
            checks.append({"check": "FLOORS_R5.json::population_authority."
                                    "arms_r5_sha256 vs CORPUS_R5.json::"
                                    "arms_r5_sha256",
                           "result": floors_copy})
            if floors_copy == "MISMATCH":
                _raise("FLOORS_R5.json's copy of arms_r5_sha256 disagrees with "
                       "CORPUS_R5.json's — two copies of one pin have drifted "
                       "apart, i.e. a SECOND population authority exists.")
    if floors_copy is None:
        checks.append({"check": "FLOORS_R5.json::population_authority."
                                "arms_r5_sha256 vs CORPUS_R5.json::"
                                "arms_r5_sha256",
                       "result": "not published — FLOORS_R5.json carries no copy"})

    # (c) the R4 exclusion list, recomputed by its PINNED recipe ---------------
    pinned = corpus.get("r4_exclusion_list_sha256")
    gd = (run / R4_GATE_DISJOINT).resolve()
    if not isinstance(pinned, str):
        _raise("CORPUS_R5.json::r4_exclusion_list_sha256 is absent — R5's corpus "
               "is R4's post-exclusion leg PLUS this list; an unpinned exclusion "
               "list is an unbounded corpus.")
    if not gd.is_file():
        _raise("shared_run_r4/GATE_DISJOINT.json is not reachable beside the RUN "
               "dir, so r4_exclusion_list_sha256 cannot be recomputed by its "
               "PINNED recipe. ⛔ Do not substitute an EXCLUDE_RIDS_*.txt file "
               "(N4): it cannot reproduce this sha, and a verifier that reaches "
               "for it convicts a healthy freeze.")
    try:
        gdoc = json.loads(gd.read_text())
    except (OSError, json.JSONDecodeError):
        _raise("shared_run_r4/GATE_DISJOINT.json is unreadable — the exclusion "
               "list cannot be recomputed.")
    rids = dig(gdoc, "digest_exclusions.S2.rids")
    if not rids or not isinstance(rids[0], list):
        _raise("shared_run_r4/GATE_DISJOINT.json::digest_exclusions.S2.rids does "
               "not resolve to an array — the pinned recipe has no input.")
    recomputed = hashlib.sha256(
        json.dumps(sorted(rids[0])).encode("utf-8")).hexdigest()
    ok_c = recomputed == pinned
    checks.append({"check": "sha256(json.dumps(sorted(GATE_DISJOINT.json::"
                            "digest_exclusions.S2.rids))) vs CORPUS_R5.json::"
                            "r4_exclusion_list_sha256",
                   "result": "match" if ok_c else "MISMATCH"})
    if not ok_c:
        _raise("the R4 exclusion list does NOT reproduce CORPUS_R5.json::"
               "r4_exclusion_list_sha256 under its pinned serialization "
               "(json.dumps default separators, no sort_keys, UTF-8, no trailing "
               "newline) — either the list moved or the recipe is not the one "
               "that was pinned.")
    return {"verified": True, "checks": checks,
            "disclosure": "match/MISMATCH only — no sha and no artifact-supplied "
                          "path is printed or stored"}


# --------------------------------------------------------------------------- #
# the completeness assertion — over the FILE                                     #
# --------------------------------------------------------------------------- #
def completeness(table: list, parsed: dict) -> dict:
    """§1's mandatory assertion, run at EVERY pass.

    Two directions, both fatal, because they are different diseases:
      · UNCOVERED — the file names an address no pass audits (§1's "no address
        may be audited at neither pass").
      · INVENTED  — the table carries an address the file does not name (§1.4's
        prohibition on inventing an address at read time).
    """
    named = set(parsed["addresses"])
    in_table = {r.address for r in table}
    by_pass = {p: sorted(r.address for r in table if r.in_pass(p))
               for p in ("A1", "A2", "A3")}
    union = set().union(*by_pass.values()) if by_pass else set()
    carried = [{"gates": c["gates"], "address_cell": c["address_cell"],
                "why": "the address column names NO address ('as carried') — "
                       "this row cannot be evaluated at any pass and is REPORTED "
                       "rather than counted as covered"}
               for c in parsed["carried_without_address"]]
    return {
        "n_named_in_read_rule": len(named),
        "n_in_address_table": len(in_table),
        "uncovered": sorted(named - in_table),
        "invented": sorted(in_table - named),
        "audited_at_no_pass": sorted(in_table - union),
        "union_equals_table": union == in_table,
        "by_pass_counts": {p: len(v) for p, v in by_pass.items()},
        "carried_without_address": carried,
        "rulings_not_addresses": parsed["rulings_not_addresses"],
        "ok": not (named - in_table) and not (in_table - named)
              and union == in_table,
    }


# --------------------------------------------------------------------------- #
def run_pass(which: str, run: Path, read_rule: Path) -> tuple:
    """`(report, exit_code)`. Raises `FreezeRaise` for the D6 escalation."""
    table = address_table()
    parsed = parsed_addresses(read_rule.read_text())
    comp = completeness(table, parsed)

    rows = [r for r in table if r.in_pass(which)]
    fixtures = run / "fixtures"
    if which == "A1":
        results = [resolve_fixture(r, fixtures) for r in rows]
    else:
        results = [resolve_live(r, run) for r in rows]

    # ⭐ RULE 7 — record WHICH of the two contradictory fixture names was found,
    # under a key that makes the ambiguity visible instead of quietly picking one.
    found = next((n for n in READOUT[1] if (fixtures / n).is_file()), None)
    ambiguity = {
        "design_fixture_list_names": "fixtures/READOUT.fixture.json",
        "execution_layer_ruling_names": "fixtures/READOUT_R5.fixture.json",
        "accepted": list(READOUT[1]),
        "found": found,
        "handling": "EITHER name is accepted, READOUT_R5 preferred. The pair "
                    "contradicts itself here; this tool REPORTS the conflict and "
                    "does not edit the pair to settle it.",
    }

    unresolved = [r for r in results if r["state"] == "UNRESOLVED"]
    no_fixture = [r["address"] for r in results if r.get("no_fixture")]
    # ⚠️ an UNRESOLVED FALLBACK is a FAIL, not a footnote — see the docstring.
    unaudited_fb = [r["address"] for r in results
                    if r["role"] == "fallback" and r["state"] == "UNRESOLVED"]

    freeze = None
    if which == "A2":
        # ⛔ D6: the freeze is VERIFIED here, before the first scoring leg.
        freeze = verify_freeze(run)

    report = {
        "pass": which,
        "run": str(run),
        "read_rule": str(read_rule),
        "mechanism": "address + gate + marker + resolved/UNRESOLVED + JSON type "
                     "name. NO VALUE is printed or stored — not the value, not a "
                     "truncation of it, not a length, not a sha.",
        "completeness": comp,
        "readout_fixture_ambiguity": ambiguity,
        "freeze_verification": freeze,
        "addresses": results,
        "n_addresses_this_pass": len(results),
        "n_unresolved": len(unresolved),
        "unaudited_fallbacks": unaudited_fb,
        "no_fixture_committed": no_fixture,
        "passed": comp["ok"] and not unresolved,
    }
    return report, (0 if report["passed"] else 2)


def _print(report: dict) -> None:
    which = report["pass"]
    comp = report["completeness"]
    print(f"{TOOL} pass  = {which}")
    print(f"{TOOL} RUN   = {report['run']}")
    print(f"{TOOL} rule  = {report['read_rule']}")
    print(f"{TOOL} MECHANISM: {report['mechanism']}")
    print(f"{TOOL} completeness: {comp['n_named_in_read_rule']} address(es) named "
          f"in READ_RULE §2, {comp['n_in_address_table']} in the table "
          f"(A1={comp['by_pass_counts']['A1']} A2={comp['by_pass_counts']['A2']} "
          f"A3={comp['by_pass_counts']['A3']}) -> "
          f"{'OK' if comp['ok'] else 'FAILED'}")
    for c in comp["carried_without_address"]:
        print(f"{TOOL} ⚠️  carried WITHOUT an address (reported, not resolved): "
              f"{', '.join(c['gates'])}  <- {c['why']}")
    for a in comp["uncovered"]:
        print(f"{TOOL} *** UNCOVERED  {a}  <- named in READ_RULE §2, audited at "
              f"NO pass", file=sys.stderr)
    for a in comp["invented"]:
        print(f"{TOOL} *** INVENTED   {a}  <- in the table, named NOWHERE in "
              f"READ_RULE §2 (§1.4)", file=sys.stderr)
    amb = report["readout_fixture_ambiguity"]
    print(f"{TOOL} ⚠️  READOUT fixture name conflict: DESIGN says "
          f"{amb['design_fixture_list_names']}, its execution-layer ruling says "
          f"{amb['execution_layer_ruling_names']}; found = {amb['found']}")
    if report["freeze_verification"]:
        for c in report["freeze_verification"]["checks"]:
            print(f"{TOOL} freeze  {c['result']:10s} {c['check']}")
    for r in report["addresses"]:
        mark = "OK " if r["state"] == "resolved" else "***"
        types = "/".join(r["types"]) if r["types"] else "-"
        print(f"{TOOL} {mark} {r['gate']:16s} {r['marker']:15s} "
              f"{r['role']:8s} {r['state']:10s} type={types:10s} {r['address']}"
              + (f"  <- {r['why']}" if r["why"] else ""))
    if report["unaudited_fallbacks"]:
        print(f"{TOOL} ⚠️ {len(report['unaudited_fallbacks'])} pre-registered "
              f"FALLBACK(s) UNRESOLVED — a fallback first exercised on the day it "
              f"is needed is an unaudited address, which is the fail-always/"
              f"pass-always defect this campaign keeps finding.", file=sys.stderr)
    if report["no_fixture_committed"]:
        print(f"{TOOL} ⚠️ {len(report['no_fixture_committed'])} address(es) have "
              f"NO committed fixture, so A1 could not audit their spelling.",
              file=sys.stderr)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pass", dest="which", required=True,
                    choices=("A1", "A2", "A3"),
                    help="A1 = static schema audit on the committed fixtures; "
                         "A2 = live [pre-corpus]+[post-corpus] + the D6 freeze "
                         "verification; A3 = live [post-scoring]")
    ap.add_argument("--run", required=True, help="the R5 RUN dir")
    ap.add_argument("--read-rule", default=None,
                    help="default: <run>/READ_RULE.md — the ADDRESS AUTHORITY")
    ap.add_argument("--json-out", default=None,
                    help="write the report here. ⚠️ This is the ONLY path this "
                         "tool ever writes.")
    a = ap.parse_args(argv)

    run = Path(a.run)
    read_rule = Path(a.read_rule) if a.read_rule else run / "READ_RULE.md"
    if not run.is_dir():
        print(f"{TOOL} RUN dir does not exist: {run}", file=sys.stderr)
        return 2
    if not read_rule.is_file():
        print(f"{TOOL} READ_RULE not found: {read_rule} — there is no address "
              f"authority, and an acceptance pass without one audits nothing.",
              file=sys.stderr)
        return 2

    try:
        report, code = run_pass(a.which, run, read_rule)
    except FreezeRaise as exc:
        print(f"{TOOL} {exc}", file=sys.stderr)
        return 3

    _print(report)
    if a.json_out:
        out = Path(a.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=True))
        print(f"{TOOL} -> {out}")

    if code:
        bad = [r for r in report["addresses"] if r["state"] == "UNRESOLVED"]
        print(f"\n{'=' * 72}\n"
              f"{TOOL} ***** ACCEPTANCE PASS {a.which} FAILED *****\n"
              f"{TOOL} {len(bad)} address(es) UNRESOLVED; completeness "
              f"{'OK' if report['completeness']['ok'] else 'FAILED'}.\n"
              + "".join(f"{TOOL}   {r['gate']} / {r['role']} / {r['address']}\n"
                        for r in bad[:12])
              + f"{TOOL} The row named above is the failing row — fix the EMITTER "
                f"or the ADDRESS, and fix the one that is actually wrong: a log "
                f"that convicts the wrong gate is how a wrong cause survives into "
                f"a close-out.\n{'=' * 72}", file=sys.stderr)
        return code
    print(f"{TOOL} PASS — {report['n_addresses_this_pass']} address(es) resolved "
          f"at {a.which}; completeness assertion OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
