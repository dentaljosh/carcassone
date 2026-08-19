#!/usr/bin/env python3
"""MERGE the per-chunk scoring output of the tie-arbiter WIDENING two-box run
back into the EXACT layout the frozen `READ_RULE.md` addresses.

    SHARE/<RUN_ID>/chunks/<stratum>/chunk<k>/<judge>/<profile>/leg<N>/records/<rid>.json
        ->  SHARE/<RUN_ID>/<stratum>/<judge>/<profile>/leg<N>/records/<rid>.json
    ... plus one merged per-leg `manifest.json`, and one merged
        `RUN/RUN_MANIFEST_{S1,S2}.json`.

`build_widening_corpus.sh` phase 6 then copies every `manifest.json` from
`SHARE/<RUN_ID>/<stratum>/` back to `RUN/legs/<stratum>/…` — the address
`G-SALT` / `G-M` / `G-BACKEND` / `G-PREFIX` read.  `G-CRN`'s per-record fallback
reads `SHARE/{s1,s2}/tier1-greedy/walled/leg<N>/records/<rid>.json` directly,
which is exactly what this script assembles.

──────────────────────────────────────────────────────────────────────────────
⚠️ BLINDNESS.  This script NEVER OPENS A RECORD.  A record's rid is taken from
its FILE NAME (`records/<rid>.json`) and its bytes are copied with `shutil.copy2`,
so no value, mean, sd, `arb`, `ora`, `Δ` or CI passes through this process.  The
per-leg `summary.json` that `oracle_score_pilot` writes DOES carry outcome
statistics; it is copied verbatim to `summary_chunk<k>.json` and is **never
parsed and never aggregated** — a merged summary would be a computed statistic,
which this layer has no licence to produce.

⚠️ COMPLETENESS IS THE POINT.  Every rid the corpus plan places on a leg must
appear on that leg EXACTLY ONCE, for BOTH judges.  A gap or a duplicate exits
non-zero and names the rids.  A duplicate whose bytes differ is a hard error
(two boxes produced different output for one rid — the neutrality claim would be
false); a duplicate whose bytes are IDENTICAL is still an error, because it means
a chunk was merged twice or the allocation double-assigned it.

⚠️ IDENTITY-REQUIRED MANIFEST FIELDS.  The gate-addressed fields of a per-leg
manifest (`resolved_config.world_seed_salt`, `.m`, `.legal_mask_cache`,
`preflight.seeds.{ok,prefix_stable_at,derivation}`, `git_rev`, …) are asserted
EQUAL across every contributing chunk before the merged manifest carries them.
They are properties of `(salt, m)` and of the code revision, never of the box, so
divergence means a mixed-rev or mis-configured run and MUST fail loudly rather
than be averaged away.  Counters are summed; per-chunk-varying fields
(`workers`, `host`, wall clocks, paths) move into the merged `merge` block.

⚠️ `execution` IS CLASSIFIED KEY BY KEY, NOT AS A BLOCK (deviation D3 §D3.2,
commit `355ceb65`).  Two box-local keys (`carc_rs_binary_sha`, `carc_rs_path`)
are PER_CHUNK; `carc_rs_build` is IDENTITY_REQUIRED — the cross-host witness;
every other key inside `execution` keeps the fail-closed RAISE.  `--allow-varying`
is REJECTED for that block by the same ruling and is not consulted there: it
silences rather than records, and provenance is this layer's whole job.

⚠️ THE TWO-REV TRANCHE SPLIT (deviation D4.11/D4.12, commit `93f83e26`).  The
committed tranche (chunks 1-8) scored at `58c2b539`; the completion tranche
(chunks 9-16) scores at `4b24f512`, the rev that exists *because* it carries the
D4 fixes — holding the tranche at the old rev was impossible, the staging code
did not exist there.  `git_rev`/`code_rev` stay **IDENTITY_REQUIRED by default**;
a **narrowly-enumerated licensed pair** is the only divergence this file will
accept, and it accepts it only when **two independent things agree**:

  1. the enumerated pair is hard-coded HERE (a CLI flag was rejected for the same
     reason `--allow-varying` was: a flag is invisible in the artifact and
     passable by anyone; an enumerated code-resident licence is reviewable,
     testable, diffable and refuses everything not enumerated); AND
  2. `RUN/INSTRUMENT_IDENTITY.json` exists and asserts an EMPTY instrument diff
     between the two revs — and this file **RE-DERIVES that diff itself** with
     `git diff` before believing it.  The file is the *why*; the re-derivation is
     the *proof*.  A file can be edited; a subprocess `git diff` cannot be.

Plus, per D4.12, the `-dirty` suffix is matched on the BASE rev and every
contributing chunk must carry `preflight.checks.git_clean.ok == true`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

RUN_ID = "tiearb_widening_20260817"
CAMPAIGN = REPO / "measurement" / RUN_ID
# rev R4.5 — the LIVE prereg pair is `shared_run_r4/` (see stage_chunks.py);
# the name lives once, in WORKERS.conf::PREREG_DIR_NAME.
sys.path.insert(0, str(REPO / "scripts" / "tiletie"))
import widening_paths as WP  # noqa: E402

RUN_DIR = WP.run_dir(CAMPAIGN)
SCHEMA = "carcassonne-tiearb-widening-merge/v1"

STRATA = ("s1", "s2")
JUDGES = ("tier1-greedy", "clair-puct")
PROFILE = "walled"

#: `RUN_MANIFEST_{S1,S2}.json` — the READ_RULE spells the stratum UPPERCASE.
RUN_MANIFEST_NAME = {"s1": "RUN_MANIFEST_S1.json", "s2": "RUN_MANIFEST_S2.json"}


# --------------------------------------------------------------------------- #
# manifest-merge policy                                                        #
# --------------------------------------------------------------------------- #
#: Summed across chunks. Pure counters — no statistic, no value.
AGGREGATE_SUM = frozenset({
    "n_rows_in", "n_scored", "n_ok", "n_failed", "n_crn_verified",
    "n_playouts", "elapsed_secs_sum", "wall_secs",
})

#: Set-unioned and sorted.
AGGREGATE_UNION = frozenset({"errors"})

#: Legitimately per-chunk. Recorded under `merge.by_chunk`, and the merged
#: manifest carries the LOWEST-INDEXED chunk's value so the key keeps its type.
PER_CHUNK = frozenset({
    "generated_utc", "started_utc", "finished_utc", "python", "host",
    "workers", "n", "out_root", "out_subdir", "sampling", "source",
    "positions_jsonl", "positions_plan_path", "arms_path",
    "positions_plan_sha256", "arms_sha256", "legs", "resume",
    "wall_cap_secs",
})

#: Nested paths inside `resolved_config` that legitimately vary per chunk.
RESOLVED_CONFIG_PER_CHUNK = frozenset({
    "positions_jsonl", "n", "workers", "out_root", "out_subdir", "resume",
})

# --------------------------------------------------------------------------- #
# `execution` — ruled by deviation D3 §D3.2 (commit 355ceb65)                   #
# --------------------------------------------------------------------------- #
# The S1 merge raised fail-closed on the whole `execution` block for all 11
# multi-chunk `clair-puct` legs, which is R4-7.5 working as pre-registered:
# *"an unclassified differing key raises rather than defaulting … it fails
# closed on fields nobody anticipated."*  The ruling classifies the block
# KEY BY KEY and declines blanket PER_CHUNK, because opening the block wholesale
# would let a FUTURE non-box-local divergence (a different rust version, a
# different build) be recorded silently — discarding exactly the property
# R4-7.5 calls the important one:
#
#   execution.carc_rs_binary_sha  PER_CHUNK          JCZ §0.F.2c — the .so is NOT
#                                                    machine-reproducible; the
#                                                    value is BOX-LOCAL and may
#                                                    never be compared across
#                                                    hosts.
#   execution.carc_rs_path        PER_CHUNK          site-packages path; same
#                                                    category as `workers`, which
#                                                    R4-7.5 nulls as box-specific.
#                                                    PER_CHUNK is strictly better:
#                                                    it RECORDS rather than
#                                                    discards.
#   execution.carc_rs_build       IDENTITY_REQUIRED  the cross-host witness the
#                                                    JCZ ruling names — the value
#                                                    that legitimately MAY be
#                                                    compared across hosts. If it
#                                                    ever differs, the merge MUST
#                                                    raise.
#   any other key in execution    RAISE (default)    preserves the fail-closed
#                                                    property.
#
# ⚠️ `--allow-varying` is REJECTED for this block by the same ruling: it silences
# rather than records, and provenance is the merge layer's entire job. It is not
# consulted anywhere in the `execution` path below.
EXECUTION_PER_CHUNK = frozenset({"carc_rs_binary_sha", "carc_rs_path"})
EXECUTION_IDENTITY_REQUIRED = frozenset({"carc_rs_build"})


# --------------------------------------------------------------------------- #
# the two-rev tranche licence — ruled by deviation D4.11/D4.12 (`93f83e26`)     #
# --------------------------------------------------------------------------- #
#: THE ENUMERATED LICENCE. Exactly two revs, full shas, hard-coded. Anything
#: else — a third value, a typo, a rev nobody ruled on — refuses exactly as it
#: does today. This is the whole point: the licence is a closed enumeration, not
#: a permission to differ.
LICENSED_TRANCHE_REVS = {
    # chunks 1-8, the committed tranche (D4.10)
    "committed_tranche": "58c2b539556916b0f6280d233b48d5dcbed7ca88",
    # chunks 9-16, the completion tranche — the rev that carries the D4 fixes
    "completion_tranche": "4b24f512a0833b3fe71a126b713c560b2c8c4db1",
}

#: ⚠️ ENUMERATED ADDRESSES, not a pattern. The run records its rev under FOUR
#: spellings and the licence must cover each or refuse the merge for the very
#: fact it licensed:
#:   git_rev                        full sha   (tier1-greedy leg + RUN_MANIFEST)
#:   code_rev                       short sha  (clair-puct leg)
#:   execution.code_rev             `<short>-dirty`  (clair-puct leg) — this is
#:                                  the field D4.12's `-dirty` rule is about
#:   champion_manifest.code_commit  full sha   (clair-puct leg)
#: Any OTHER key that differs still refuses, including one that happens to hold
#: a licensed sha.
REV_LICENSED_PATHS = ("git_rev", "code_rev", "execution.code_rev",
                      "champion_manifest.code_commit")

#: A rev value is matched as a sha PREFIX after the `-dirty` suffix is stripped
#: (D4.12): the run records the same rev as a full sha, a short sha, and a
#: short sha with the suffix. Below this length a "prefix" is not evidence.
MIN_SHA_PREFIX = 8

#: ⚠️ THE CORRECTED INSTRUMENT SET (D4.11 Amendment 2). The proposal spelled the
#: pilot `scripts/tiletie/oracle_score_pilot.py`, which DOES NOT EXIST — the
#: pilot is under `scripts/measurement_infra/`, and a witness asserting "empty
#: diff" over a non-existent path is VACUOUSLY TRUE. That path is the file that
#: executes the `clair-puct` leg: 93% of the run's cost, unwitnessed. So the
#: witness check below also asserts every path EXISTS at both revs, which is the
#: generalisable form of that lesson.
INSTRUMENT_PATHS = (
    "scripts/tiletie/run_tiletie.py",
    "scripts/measurement_infra/oracle_score_pilot.py",   # <-- corrected path
    "scripts/tiletie/tier1_rust_leg.py",
    "src/",
    "engine/",
    "rust/",
)

INSTRUMENT_IDENTITY_NAME = "INSTRUMENT_IDENTITY.json"
INSTRUMENT_IDENTITY_SCHEMA = "carcassonne-tiearb-widening-instrument-identity/v1"

#: Where the witness is looked for, in order. D4.11 names `RUN/`; the campaign
#: root is accepted as a fallback because that is where this campaign's other
#: cross-cutting witnesses landed (`d3_witness/D3_WITNESS.json`). Whichever is
#: found is RECORDED in the merged artifact, so the reader is never guessing.
def instrument_identity_candidates(campaign=CAMPAIGN):
    return (Path(RUN_DIR) / INSTRUMENT_IDENTITY_NAME,
            Path(campaign) / INSTRUMENT_IDENTITY_NAME)

#: Dotted paths that MUST agree across every chunk of a leg. A divergence here
#: is a mixed-rev / mis-configured run, never a throughput artefact.
IDENTITY_REQUIRED = (
    "schema", "driver", "harness", "design_doc", "git_rev", "code_rev",
    "judge", "profile", "leg", "m_worlds", "rules_profile", "max_plies",
    "resolved_config.world_seed_salt",
    "resolved_config.m",
    "resolved_config.legal_mask_cache",
    "resolved_config.rules_profile",
    "resolved_config.oracle_policy",
    "resolved_config.arb_backend",
    "preflight.seeds.ok",
    "preflight.seeds.prefix_stable_at",
    "preflight.seeds.derivation",
    "crn.seed_derivation",
    "oracle.policy",
)

#: The same discipline for the per-invocation `RUN_MANIFEST_*` files. These are
#: the exact scalars READ_RULE §2 addresses (G-SALT / G-M / G-BACKEND / G-LEAF).
RUN_MANIFEST_IDENTITY = (
    "schema", "driver", "design_doc", "git_rev",
    "world_seed_salt", "m_worlds", "m_max", "b_ceiling_from_m",
    "arb_backend", "arb_legal_mask_cache", "oracle_sims",
    "preflight.checks.leaf_hash.ok",
    "preflight.checks.leaf_hash.harness_leaf_hash",
    "preflight.checks.leaf_hash.expected",
)

_MISSING = object()


def _get(d: dict, dotted: str):
    cur = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return _MISSING
        cur = cur[part]
    return cur


def _sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _canon(v) -> str:
    return json.dumps(v, sort_keys=True, default=str)


class MergeError(RuntimeError):
    pass


def _git(repo, *args) -> tuple:
    """(rc, stdout, stderr) — plain `git`, no shell, absolute repo."""
    r = subprocess.run(["git", "-C", str(repo), *args],
                       capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def _strip_dirty(value: str) -> str:
    """D4.12: match the licence on the BASE rev.

    NOT exact-string matching including the suffix — a chunk that happened to
    record a clean `code_rev` would then be REFUSED while a healthy dirty one
    passed, a false refusal of the class this campaign keeps generating. And NOT
    bare suffix-stripping either: the suffix is only *gestured* at here; the
    assertion with semantics is `preflight.checks.git_clean.ok`, which
    `RevLicense.authorize` requires per chunk.
    """
    s = str(value).strip()
    for suffix in ("-dirty", ".dirty", "+dirty"):
        if s.endswith(suffix):
            return s[: -len(suffix)]
    return s


def _rev_fragment_of_build(build: str):
    """The `+<hex>+` rev fragment `carc_rs-0.1.0+<rev12>+rustcunpinned` stamps,
    and the string with it blanked — so "differs only by the rev" is decidable
    rather than eyeballed."""
    if not isinstance(build, str):
        return None, None
    parts = build.split("+")
    for i, p in enumerate(parts):
        q = p.strip().lower()
        if len(q) >= MIN_SHA_PREFIX and all(c in "0123456789abcdef" for c in q):
            blanked = list(parts)
            blanked[i] = "<REV>"
            return q, "+".join(blanked)
    return None, build


def _tranche_of_sha(value, revs=None):
    """Module-level tranche lookup — the same prefix rule `RevLicense` uses."""
    if not isinstance(value, str):
        return None
    base = _strip_dirty(value).lower()
    if len(base) < MIN_SHA_PREFIX or not all(c in "0123456789abcdef" for c in base):
        return None
    for name, sha in (revs or LICENSED_TRANCHE_REVS).items():
        if sha.lower().startswith(base) or base.startswith(sha.lower()):
            return name
    return None


def carc_rs_build_refusal(values: dict, *, where: str, revs=None) -> "MergeError":
    """⛔ UNRULED, and the merge says so precisely rather than merging or hiding.

    D3 §D3.2 makes `carc_rs_build` IDENTITY_REQUIRED — *"the cross-host witness
    … if it ever differs, the merge MUST raise"*. D4.11's completeness note then
    leans on it: *"D3's `execution.carc_rs_build` IDENTITY_REQUIRED already
    covers the compiled half (equal across all chunks)"*.

    **That premise does not survive a two-rev tranche.** The build string stamps
    the repo rev (`carc_rs-0.1.0+<rev12>+rustcunpinned`), so it differs between
    the tranches for the same reason `git_rev` does — while remaining EQUAL
    across boxes within a tranche, which is the cross-HOST property D3 actually
    bought. The rev half is licensed by D4.11; the host half must stay.

    Deciding which is a RULING, not a merge-layer choice, so this refuses and
    names the question instead of quietly extending the licence.
    """
    revs = dict(revs or LICENSED_TRANCHE_REVS)
    detail = "; ".join(f"chunk{k}={_canon(v)}" for k, v in sorted(values.items()))
    licensed = {t: sha[:12] for t, sha in revs.items()}

    frags = {k: _rev_fragment_of_build(v) for k, v in values.items()}
    blanked = {b for _f, b in frags.values()}
    tranches = {_tranche_of_sha(f, revs) for f, _b in frags.values()}
    rev_only = (len(blanked) == 1 and None not in tranches
                and len(tranches) == len(revs))
    if not rev_only:
        # the ORIGINAL D3 §D3.2 refusal — a genuinely different build, which is
        # a mixed-build run and was never in question.
        return MergeError(
            f"identity-required path {where!r} DIVERGES across chunks: {detail}"
            f" — D3 §D3.2 names this the CROSS-HOST WITNESS: it is the one value "
            f"inside `execution` that may legitimately be compared across boxes, "
            f"so a divergence is a mixed-build run and MUST raise. (The values "
            f"differ in more than the licensed rev fragment, so the D4.11 "
            f"two-rev question does not even arise here.)")

    return MergeError(
        f"carc_rs_build DIVERGES at {where}: {detail}. ⛔ UNRULED — D3 §D3.2 "
        f"rules this field IDENTITY_REQUIRED ('if it ever differs, the merge "
        f"MUST raise') while D4.11's completeness note assumes it is EQUAL "
        f"across all chunks, which cannot hold across two revs: the build "
        f"string embeds the repo rev ({licensed}). Within a tranche it is still "
        f"equal across boxes — the cross-HOST witness D3 bought is intact; it is "
        f"the cross-REV comparison that D4.11 did not foresee. This merge layer "
        f"does NOT extend the licence to it: escalate for a ruling.")


class RevLicense:
    """The D4.11 licence: an enumerated rev pair AND a re-derived instrument
    witness. Either alone is weaker than both — a file can be edited, and a
    hard-coded pair alone asserts nothing about WHY the pair is safe."""

    def __init__(self, *, repo=REPO, identity_path=None, campaign=CAMPAIGN,
                 git_clean_by_chunk=None, revs=None):
        self.repo = Path(repo)
        self.campaign = Path(campaign)
        self.revs = dict(revs if revs is not None else LICENSED_TRANCHE_REVS)
        self._explicit_path = Path(identity_path) if identity_path else None
        #: {(judge, chunk) | chunk: {"ok": bool, "source": str, …}} — the D4.12
        #: per-chunk evidence for artifacts that do not carry it themselves
        #: (per-leg manifests do NOT: only RUN_MANIFEST has preflight.checks).
        self.git_clean_by_chunk = dict(git_clean_by_chunk or {})
        self._witness = None
        self.used = []

    # ---- rev matching ---------------------------------------------------- #
    def tranche_of(self, value):
        """The tranche a recorded rev belongs to, or None. Matches a full sha, a
        short sha, and (D4.12) the `-dirty` form, as a PREFIX either way."""
        if not isinstance(value, str):
            return None
        base = _strip_dirty(value).lower()
        if len(base) < MIN_SHA_PREFIX or not all(c in "0123456789abcdef" for c in base):
            return None
        for name, sha in self.revs.items():
            sha = sha.lower()
            if sha.startswith(base) or base.startswith(sha):
                return name
        return None

    # ---- the witness ------------------------------------------------------ #
    def identity_path(self):
        if self._explicit_path is not None:
            return self._explicit_path
        for p in instrument_identity_candidates(self.campaign):
            if p.is_file():
                return p
        return instrument_identity_candidates(self.campaign)[0]

    def witness(self) -> dict:
        """Load AND re-derive. Cached: the git work happens once per merge."""
        if self._witness is not None:
            return self._witness
        p = self.identity_path()
        if not p.is_file():
            raise MergeError(
                f"the two-rev licence requires {INSTRUMENT_IDENTITY_NAME} and it "
                f"is ABSENT (looked at "
                f"{[str(c) for c in instrument_identity_candidates(self.campaign)]}). "
                f"D4.11 Amendment 1: the code holds the enumerated pair AND the "
                f"witness must assert the empty instrument diff — BOTH, or "
                f"refuse. Generate it with instrument_identity.py.")
        try:
            doc = json.loads(p.read_text())
        except json.JSONDecodeError as exc:
            raise MergeError(f"{p} is not valid JSON: {exc}")

        if doc.get("schema") != INSTRUMENT_IDENTITY_SCHEMA:
            raise MergeError(
                f"{p}: schema {doc.get('schema')!r} != {INSTRUMENT_IDENTITY_SCHEMA!r}")
        claimed = {str(v.get("sha", "")).lower()
                   for v in (doc.get("revs") or {}).values()}
        want = {s.lower() for s in self.revs.values()}
        if claimed != want:
            raise MergeError(
                f"{p}: the witness asserts revs {sorted(claimed)} but the "
                f"code-resident licence enumerates {sorted(want)}. Both must "
                f"name the SAME pair — that is the point of requiring two "
                f"independent things to agree.")
        paths = list(doc.get("instrument_paths") or [])
        if list(INSTRUMENT_PATHS) != paths:
            raise MergeError(
                f"{p}: instrument_paths {paths} != the corrected set "
                f"{list(INSTRUMENT_PATHS)} (D4.11 Amendment 2 — a witness over a "
                f"path that does not exist is VACUOUSLY TRUE)")
        if (doc.get("committed_diff") or {}).get("empty") is not True:
            raise MergeError(
                f"{p}: committed_diff.empty is not true — the witness itself "
                f"says the instrument moved between the two revs")
        boxes = (doc.get("working_tree") or {}).get("by_box") or {}
        if not boxes:
            raise MergeError(
                f"{p}: working_tree.by_box is empty. D4.11 Amendment 3: "
                f"`git diff A..B` is BLIND to uncommitted dirt in the instrument "
                f"scripts, so the witness must also carry `git status "
                f"--porcelain` scoped to the same paths, per box.")
        dirty = {b: v for b, v in boxes.items()
                 if v.get("clean") is not True or (v.get("porcelain") or "").strip()}
        if dirty:
            raise MergeError(
                f"{p}: working tree NOT clean over the instrument paths on "
                f"box(es) {sorted(dirty)} — {[(b, (v.get('porcelain') or '')[:120]) for b, v in sorted(dirty.items())]}")

        rederived = self.rederive()
        doc = dict(doc)
        doc["_rederived"] = rederived
        doc["_path"] = str(p)
        doc["_sha256"] = _sha256_file(p)
        self._witness = doc
        return doc

    def rederive(self) -> dict:
        """⭐ THE PROOF. The witness file is the *why*; this is the *that*.

        Re-runs the recipe — existence of every instrument path at BOTH revs,
        then `git diff` between them scoped to those paths — inside THIS repo,
        never trusting a path or a result recorded in the file.
        """
        shas = sorted(self.revs.values())
        a, b = shas[0], shas[1] if len(shas) > 1 else shas[0]
        for sha in (a, b):
            rc, _out, err = _git(self.repo, "cat-file", "-e", f"{sha}^{{commit}}")
            if rc != 0:
                raise MergeError(
                    f"licensed rev {sha[:12]} is not a commit in {self.repo} "
                    f"({err.strip()}) — the licence cannot be verified, so it "
                    f"does not apply")
        missing = []
        for path in INSTRUMENT_PATHS:
            for sha in (a, b):
                rc, out, _err = _git(self.repo, "ls-tree", "-r", "--name-only",
                                     sha, "--", path)
                if rc != 0 or not out.strip():
                    missing.append((path, sha[:12]))
        if missing:
            raise MergeError(
                f"instrument path(s) absent at a licensed rev: {missing[:5]} — "
                f"an 'empty diff' over a path that does not exist is VACUOUSLY "
                f"TRUE, which is exactly the defect D4.11 Amendment 2 caught")
        rc, stat, err = _git(self.repo, "diff", "--stat", a, b, "--", *INSTRUMENT_PATHS)
        if rc != 0:
            raise MergeError(f"git diff failed in {self.repo}: {err.strip()}")
        rc, names, err = _git(self.repo, "diff", "--name-only", a, b,
                              "--", *INSTRUMENT_PATHS)
        if rc != 0:
            raise MergeError(f"git diff failed in {self.repo}: {err.strip()}")
        changed = [ln for ln in names.splitlines() if ln.strip()]
        if changed:
            raise MergeError(
                f"RE-DERIVED INSTRUMENT DIFF IS NOT EMPTY between "
                f"{a[:12]}..{b[:12]}: {len(changed)} file(s) changed "
                f"(first: {changed[:5]}). The witness claims otherwise, so the "
                f"witness is stale or wrong. The licence does NOT apply.")
        return {
            "recipe": f"git -C <repo> diff --name-only {a} {b} -- "
                      + " ".join(INSTRUMENT_PATHS),
            "repo": str(self.repo), "rev_a": a, "rev_b": b,
            "paths": list(INSTRUMENT_PATHS),
            "n_files_changed": 0, "empty": True, "stat": stat.strip(),
            "verified_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    # ---- D4.12's per-chunk clean assertion --------------------------------- #
    def git_clean_ok(self, chunk, manifest: dict) -> dict:
        """`preflight.checks.git_clean.ok == true`, per chunk.

        Read from the artifact itself when it carries it (RUN_MANIFEST does);
        otherwise from the per-chunk RUN_MANIFEST map the caller supplied (the
        per-LEG manifests do not carry `preflight.checks` at all, and requiring
        it *there* would refuse every healthy leg — a false refusal).
        """
        local = _get(manifest or {}, "preflight.checks.git_clean")
        if local is not _MISSING and isinstance(local, dict):
            return {"ok": bool(local.get("ok")), "source": "manifest",
                    "dirty_paths": local.get("dirty_paths")}
        for key in (chunk, str(chunk)):
            if key in self.git_clean_by_chunk:
                v = dict(self.git_clean_by_chunk[key])
                v.setdefault("source", "RUN_MANIFEST")
                v["ok"] = bool(v.get("ok"))
                return v
        return {"ok": None, "source": None}

    # ---- the decision ------------------------------------------------------ #
    def authorize(self, dotted: str, present: dict, manifests: dict) -> dict:
        """Licence this divergence, or raise. `present` = {chunk: value}."""
        if dotted not in REV_LICENSED_PATHS:
            raise MergeError(
                f"{dotted!r} is not a licensed rev address. The D4.11 licence is "
                f"an ENUMERATED set of addresses ({list(REV_LICENSED_PATHS)}); "
                f"any other key that differs still refuses, including one "
                f"holding a licensed sha.")
        by_tranche, unlicensed = {}, {}
        for k, v in sorted(present.items()):
            t = self.tranche_of(v)
            if t is None:
                unlicensed[k] = v
            else:
                by_tranche.setdefault(t, []).append(k)
        if unlicensed:
            raise MergeError(
                f"identity-required path {dotted!r} DIVERGES across chunks and "
                f"chunk(s) {sorted(unlicensed)} carry rev(s) "
                f"{[str(v) for v in unlicensed.values()]} that are NOT in the "
                f"enumerated licence "
                f"{ {t: s[:12] for t, s in self.revs.items()} }. D4.11: any "
                f"other rev, or any third value, still refuses.")

        witness = self.witness()          # raises unless the licence is armed

        clean, missing = {}, []
        for k in sorted(present):
            ev = self.git_clean_ok(k, manifests.get(k) or {})
            clean[str(k)] = ev
            if ev["ok"] is not True:
                missing.append((k, ev))
        if missing:
            raise MergeError(
                f"{dotted!r}: the two-rev licence requires "
                f"preflight.checks.git_clean.ok == true for EVERY contributing "
                f"chunk (D4.12 — the `-dirty` suffix only gestures at what this "
                f"assertion checks). Not satisfied for: "
                + "; ".join(f"chunk{k}={v}" for k, v in missing))

        record = {
            "path": dotted,
            "by_chunk": {str(k): v for k, v in sorted(present.items())},
            "tranches": {t: sorted(ks) for t, ks in sorted(by_tranche.items())},
            "licensed_revs": {t: s for t, s in sorted(self.revs.items())},
            "git_clean_by_chunk": clean,
            "instrument_identity": {
                "path": witness["_path"], "sha256": witness["_sha256"],
                "rederived": witness["_rederived"],
            },
            "deviation": "D4.11/D4.12 (measurement/tiearb_widening_20260817/"
                         "DEVIATIONS.md, commit 93f83e26)",
            "note": "ENUMERATED two-rev licence. The tranche split is a "
                    "NECESSARY consequence of the D4.2 completion — the "
                    "completion tranche cannot run at the spent rev because the "
                    "staging code did not exist there. No gate constrains the "
                    "run's git_rev (D4.10). The instrument diff between the two "
                    "revs was RE-DERIVED here, not read from the witness.",
        }
        self.used.append(record)
        return record


def merge_manifests(by_chunk: dict, *, identity_required=IDENTITY_REQUIRED,
                    allow_varying=(), license=None) -> dict:
    """Merge {chunk_index: manifest dict} into one.

    Fail-closed: an unclassified key whose value differs across chunks raises.
    """
    if not by_chunk:
        raise MergeError("merge_manifests called with zero manifests")
    order = sorted(by_chunk)
    first = by_chunk[order[0]]
    allow = set(allow_varying)
    rev_records = []

    # 1) identity-required paths
    for dotted in identity_required:
        vals = {k: _get(m, dotted) for k, m in by_chunk.items()}
        present = {k: v for k, v in vals.items() if v is not _MISSING}
        if not present:
            continue
        if len(present) != len(vals):
            missing = sorted(k for k, v in vals.items() if v is _MISSING)
            raise MergeError(
                f"identity-required path {dotted!r} is present on some chunks but "
                f"absent on {missing} — a leg cannot be half-configured")
        distinct = {_canon(v) for v in present.values()}
        if len(distinct) != 1:
            # ⭐ the ONLY divergence this file accepts: the enumerated two-rev
            # licence (D4.11). Everything else raises exactly as it always did.
            if license is not None and dotted in REV_LICENSED_PATHS:
                rev_records.append(license.authorize(dotted, present, by_chunk))
                continue
            raise MergeError(
                f"identity-required path {dotted!r} DIVERGES across chunks: "
                + "; ".join(f"chunk{k}={_canon(v)}" for k, v in sorted(present.items())))

    merged = json.loads(json.dumps(first))
    keys = sorted({k for m in by_chunk.values() for k in m})
    per_chunk_block: dict = {str(k): {} for k in order}
    divergent = []

    for key in keys:
        vals = {k: m.get(key, _MISSING) for k, m in by_chunk.items()}
        present = {k: v for k, v in vals.items() if v is not _MISSING}
        if key in AGGREGATE_SUM:
            nums = [v for v in present.values() if isinstance(v, (int, float))]
            merged[key] = round(sum(nums), 3) if any(
                isinstance(v, float) for v in nums) else sum(nums)
            for k, v in present.items():
                per_chunk_block[str(k)][key] = v
            continue
        if key in AGGREGATE_UNION:
            acc = set()
            for v in present.values():
                acc.update(v or [])
            merged[key] = sorted(acc)
            continue
        if key in PER_CHUNK:
            for k, v in present.items():
                per_chunk_block[str(k)][key] = v
            merged[key] = present[min(present)]
            continue
        if key == "resolved_config":
            merged[key] = _merge_resolved_config(present, per_chunk_block)
            continue
        if key == "execution":
            merged[key] = _merge_execution(present, per_chunk_block,
                                           license=license, manifests=by_chunk,
                                           rev_records=rev_records)
            continue
        if key == "champion_manifest":
            merged[key] = _merge_champion_manifest(
                present, per_chunk_block, license=license, manifests=by_chunk,
                rev_records=rev_records)
            continue
        if key == "preflight":
            merged[key] = _merge_preflight(present, per_chunk_block,
                                           license=license)
            continue
        distinct = {_canon(v) for v in present.values()}
        if len(distinct) == 1 and len(present) == len(vals):
            merged[key] = present[min(present)]
            continue
        # the two-rev licence, at the TOP level (`git_rev` on the tier1-greedy
        # leg, `code_rev` on the clair-puct leg). Licensed => RECORDED per chunk,
        # never averaged, never silently carried.
        if (license is not None and key in REV_LICENSED_PATHS
                and len(present) == len(vals)):
            # `git_rev`/`code_rev` are ALSO identity-required paths, so they may
            # already have been authorized above — authorize once, record once.
            if key not in {r["path"] for r in rev_records}:
                rev_records.append(license.authorize(key, present, by_chunk))
            for k, v in present.items():
                per_chunk_block[str(k)][key] = v
            merged[key] = present[min(present)]
            continue
        if key in allow:
            for k, v in present.items():
                per_chunk_block[str(k)][key] = v
            merged[key] = present[min(present)]
            divergent.append(key)
            continue
        raise MergeError(
            f"key {key!r} differs across chunks and has no merge rule "
            f"(classify it in AGGREGATE_SUM / PER_CHUNK / IDENTITY_REQUIRED, or "
            f"pass --allow-varying {key}). "
            + "; ".join(f"chunk{k}={_canon(v)[:120]}" for k, v in sorted(present.items())))

    merged["merge"] = {
        "schema": SCHEMA,
        "run_id": RUN_ID,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "chunks": order,
        "note": ("A TWO-BOX merge of per-chunk legs. Counters are summed; "
                 "gate-addressed fields were asserted IDENTICAL across chunks "
                 "before being carried. Per-chunk values are below. "
                 "wall_secs is a SUM across chunks that ran on different boxes "
                 "and possibly concurrently — it is NOT a wall clock and is not "
                 "the cost currency of record (DESIGN §7 costs from "
                 "elapsed_secs)."),
        "by_chunk": per_chunk_block,
        "wall_secs_max": max(
            [float(m.get("wall_secs") or 0.0) for m in by_chunk.values()] or [0.0]),
        "divergent_keys_allowed": sorted(divergent),
    }
    if rev_records:
        merged["merge"]["rev_license"] = {
            "schema": "carcassonne-tiearb-widening-rev-license/v1",
            "deviation": "D4.11/D4.12",
            "paths": sorted({r["path"] for r in rev_records}),
            "records": rev_records,
            "note": "⚠️ THIS LEG SPANS TWO REVS. The merged manifest carries the "
                    "LOWEST-indexed chunk's value for each rev field so the key "
                    "keeps its type and never reads null; the per-chunk truth is "
                    "here and in merge.by_chunk. The pair is enumerated in "
                    "merge_legs.LICENSED_TRANCHE_REVS and the instrument diff "
                    "between the two revs was RE-DERIVED at merge time.",
        }
    return merged


def _merge_execution(present: dict, per_chunk_block: dict, *, license=None,
                     manifests=None, rev_records=None) -> dict:
    """Merge the `execution` block KEY BY KEY, per deviation D3 §D3.2.

    Three classes and no fourth: two BOX-LOCAL keys are recorded per chunk, the
    cross-host build witness must be IDENTICAL, and every other key keeps the
    fail-closed raise. `allow_varying` is deliberately NOT threaded in here —
    D3 rejects it for this block by name.
    """
    order = sorted(present)
    non_dict = {k: v for k, v in present.items() if not isinstance(v, dict)}
    if non_dict:
        distinct = {_canon(v) for v in present.values()}
        if len(distinct) != 1:
            raise MergeError(
                "`execution` is not a dict on every chunk and the values differ: "
                + "; ".join(f"chunk{k}={_canon(v)[:120]}"
                            for k, v in sorted(present.items())))
        return json.loads(json.dumps(present[order[0]]))

    merged = json.loads(json.dumps(present[order[0]]))
    keys = sorted({k for v in present.values() for k in v})
    for key in keys:
        vals = {k: v.get(key, _MISSING) for k, v in present.items()}
        have = {k: v for k, v in vals.items() if v is not _MISSING}
        distinct = {_canon(v) for v in have.values()}
        if key in EXECUTION_PER_CHUNK:
            # BOX-LOCAL: recorded per chunk rather than discarded or asserted
            for k, v in have.items():
                per_chunk_block[str(k)].setdefault("execution", {})[key] = v
            merged[key] = have[min(have)]
            continue
        if key in EXECUTION_IDENTITY_REQUIRED:
            if len(have) != len(vals):
                missing = sorted(k for k, v in vals.items() if v is _MISSING)
                raise MergeError(
                    f"identity-required path 'execution.{key}' is present on some "
                    f"chunks but absent on {missing} — a leg cannot be "
                    f"half-configured")
            if len(distinct) != 1:
                if key == "carc_rs_build":
                    raise carc_rs_build_refusal(
                        have, where="execution.carc_rs_build",
                        revs=(license.revs if license is not None else None))
                raise MergeError(
                    f"identity-required path 'execution.{key}' DIVERGES across "
                    f"chunks: "
                    + "; ".join(f"chunk{k}={_canon(v)}"
                                for k, v in sorted(have.items()))
                    + " — D3 §D3.2 names this the CROSS-HOST WITNESS: it is the "
                      "one value inside `execution` that may legitimately be "
                      "compared across boxes, so a divergence is a mixed-build "
                      "run and MUST raise.")
            merged[key] = have[min(have)]
            continue
        # ⭐ `execution.code_rev` — the `<short>-dirty` field D4.12 is about.
        if (license is not None and key == "code_rev" and len(distinct) != 1
                and len(have) == len(vals)):
            rec = license.authorize("execution.code_rev", have, manifests or {})
            if rev_records is not None:
                rev_records.append(rec)
            for k, v in have.items():
                per_chunk_block[str(k)].setdefault("execution", {})[key] = v
            merged[key] = have[min(have)]
            continue
        if len(distinct) != 1 or len(have) != len(vals):
            raise MergeError(
                f"execution.{key} differs across chunks and is UNCLASSIFIED. D3 "
                f"§D3.2 classifies only carc_rs_binary_sha / carc_rs_path "
                f"(PER_CHUNK, box-local) and carc_rs_build (IDENTITY_REQUIRED); "
                f"every other key inside `execution` keeps the fail-closed "
                f"RAISE, and --allow-varying is rejected for this block: "
                + "; ".join(f"chunk{k}={_canon(v)[:120]}"
                            for k, v in sorted(have.items())))
        merged[key] = have[min(have)]
    return merged


def _merge_champion_manifest(present: dict, per_chunk_block: dict, *,
                             license=None, manifests=None,
                             rev_records=None) -> dict:
    """`champion_manifest` — identical across chunks EXCEPT `code_commit`, which
    is the run's rev under a third spelling (full sha, `clair-puct` legs).

    Licensed by the same enumerated pair; every other key keeps the fail-closed
    raise, because a champion that differed in anything else would be a
    different champion.
    """
    order = sorted(present)
    if not all(isinstance(v, dict) for v in present.values()):
        distinct = {_canon(v) for v in present.values()}
        if len(distinct) != 1:
            raise MergeError(
                "`champion_manifest` is not a dict on every chunk and differs: "
                + "; ".join(f"chunk{k}={_canon(v)[:120]}"
                            for k, v in sorted(present.items())))
        return json.loads(json.dumps(present[order[0]]))

    merged = json.loads(json.dumps(present[order[0]]))
    keys = sorted({k for v in present.values() for k in v})
    for key in keys:
        vals = {k: v.get(key, _MISSING) for k, v in present.items()}
        have = {k: v for k, v in vals.items() if v is not _MISSING}
        distinct = {_canon(v) for v in have.values()}
        if len(distinct) == 1 and len(have) == len(vals):
            merged[key] = have[min(have)]
            continue
        if license is not None and key == "code_commit":
            rec = license.authorize("champion_manifest.code_commit", have,
                                    manifests or {})
            if rev_records is not None:
                rev_records.append(rec)
            for k, v in have.items():
                per_chunk_block[str(k)].setdefault("champion_manifest", {})[key] = v
            merged[key] = have[min(have)]
            continue
        raise MergeError(
            f"champion_manifest.{key} differs across chunks and is NOT licensed "
            f"(only `code_commit` is, under the D4.11 two-rev pair): "
            + "; ".join(f"chunk{k}={_canon(v)[:120]}" for k, v in sorted(have.items())))
    return merged


def _merge_preflight(present: dict, per_chunk_block: dict, *, license=None) -> dict:
    """`preflight` on the `tier1-greedy` leg carries `wheel.carc_rs_build`.

    Nested rather than compared whole, so a divergence localises to the field
    that actually moved instead of dumping the whole block into the error — the
    difference between a reader who can act and one who cannot. `preflight.seeds.*`
    is already IDENTITY_REQUIRED above; everything here keeps the raise.
    """
    order = sorted(present)
    if not all(isinstance(v, dict) for v in present.values()):
        distinct = {_canon(v) for v in present.values()}
        if len(distinct) != 1:
            raise MergeError(
                "`preflight` is not a dict on every chunk and differs: "
                + "; ".join(f"chunk{k}={_canon(v)[:120]}"
                            for k, v in sorted(present.items())))
        return json.loads(json.dumps(present[order[0]]))

    merged = json.loads(json.dumps(present[order[0]]))
    keys = sorted({k for v in present.values() for k in v})
    for key in keys:
        vals = {k: v.get(key, _MISSING) for k, v in present.items()}
        have = {k: v for k, v in vals.items() if v is not _MISSING}
        distinct = {_canon(v) for v in have.values()}
        if len(distinct) == 1 and len(have) == len(vals):
            merged[key] = have[min(have)]
            continue
        if key == "wheel" and all(isinstance(v, dict) for v in have.values()):
            builds = {k: v.get("carc_rs_build") for k, v in have.items()}
            if len({_canon(v) for v in builds.values()}) != 1:
                raise carc_rs_build_refusal(
                    builds, where="preflight.wheel.carc_rs_build",
                    revs=(license.revs if license is not None else None))
        raise MergeError(
            f"preflight.{key} differs across chunks and has no merge rule: "
            + "; ".join(f"chunk{k}={_canon(v)[:120]}" for k, v in sorted(have.items())))
    return merged


def _merge_resolved_config(present: dict, per_chunk_block: dict) -> dict:
    order = sorted(present)
    merged = json.loads(json.dumps(present[order[0]]))
    keys = sorted({k for v in present.values() for k in v})
    for key in keys:
        vals = {k: v.get(key, _MISSING) for k, v in present.items()}
        have = {k: v for k, v in vals.items() if v is not _MISSING}
        if key in RESOLVED_CONFIG_PER_CHUNK:
            for k, v in have.items():
                per_chunk_block[str(k)].setdefault("resolved_config", {})[key] = v
            if key == "n":
                merged[key] = sum(v for v in have.values() if isinstance(v, int))
            elif key == "resume":
                merged[key] = any(bool(v) for v in have.values())
            else:
                merged[key] = None       # explicitly NOT one chunk's value
            continue
        distinct = {_canon(v) for v in have.values()}
        if len(distinct) != 1:
            raise MergeError(
                f"resolved_config.{key} diverges across chunks and is not in "
                f"RESOLVED_CONFIG_PER_CHUNK: "
                + "; ".join(f"chunk{k}={_canon(v)}" for k, v in sorted(have.items())))
        merged[key] = have[min(have)]
    return merged


# --------------------------------------------------------------------------- #
# expected rid sets — read from the CORPUS plan, not from what happened to run  #
# --------------------------------------------------------------------------- #
def expected_leg_rids(positions_dir: Path) -> dict:
    """{"<profile>/leg<r>": {rid, ...}} from the CORPUS positions dir.

    This is the denominator of the completeness check: what the run was
    SUPPOSED to produce, independent of which chunks reported.
    """
    plan = json.loads((Path(positions_dir) / "POSITIONS_PLAN.json").read_text())
    out = {}
    for key, info in sorted((plan.get("files") or {}).items()):
        p = Path(info["path"])
        if not p.is_file():
            p = Path(positions_dir) / Path(info["path"]).name
        if not p.is_file():
            raise MergeError(f"missing corpus leg file for {key}: {info['path']}")
        rids = set()
        for ln in p.read_text().splitlines():
            if ln.strip():
                rids.add(json.loads(ln)["rid"])
        if len(rids) != int(info["n"]):
            raise MergeError(f"{p}: {len(rids)} distinct rids but plan says {info['n']}")
        out[key] = rids
    return out


def chunk_dirs(chunks_root: Path) -> dict:
    """{chunk_index: dir} for every `chunk<k>` under `chunks_root`."""
    out = {}
    root = Path(chunks_root)
    if not root.is_dir():
        return out
    for d in sorted(root.iterdir()):
        if d.is_dir() and d.name.startswith("chunk"):
            try:
                out[int(d.name[len("chunk"):])] = d
            except ValueError:
                continue
    return out


# --------------------------------------------------------------------------- #
# the merge                                                                    #
# --------------------------------------------------------------------------- #
def git_clean_by_chunk_from_manifests(manifests_dir, stratum: str) -> dict:
    """{chunk: {"ok", "dirty_paths", "sources"}} from the per-chunk
    `RUN_MANIFEST_*` files — the ONLY artifacts that carry
    `preflight.checks.git_clean` (per-leg manifests do not).

    ANDed across judges for the same chunk: a chunk is clean only if every
    invocation that touched it said so.
    """
    out: dict = {}
    d = Path(manifests_dir)
    if not d.is_dir():
        return out
    S = str(stratum).upper()
    for p in sorted(d.glob(f"RUN_MANIFEST_{S}_*_chunk*.json")):
        try:
            doc = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        tag = p.name.split("_chunk")[-1][: -len(".json")]
        try:
            k = int(tag)
        except ValueError:
            continue
        gc = _get(doc, "preflight.checks.git_clean")
        if gc is _MISSING or not isinstance(gc, dict):
            continue
        row = out.setdefault(k, {"ok": True, "dirty_paths": [], "sources": []})
        row["ok"] = bool(row["ok"]) and bool(gc.get("ok"))
        row["dirty_paths"] = sorted(set(row["dirty_paths"])
                                    | set(gc.get("dirty_paths") or []))
        row["sources"].append(str(p))
    return out


def merge_stratum(*, stratum: str, chunks_root: Path, out_dir: Path,
                  positions_dir: Path, judges=JUDGES, dry_run: bool = False,
                  allow_varying=(), license=None, manifests_dir=None) -> dict:
    chunks_root, out_dir = Path(chunks_root), Path(out_dir)
    expected = expected_leg_rids(positions_dir)
    cdirs = chunk_dirs(chunks_root)
    if license is None:
        # the licence is ARMED BY DEFAULT but INERT unless a rev actually
        # diverges: it is consulted only on divergence, and it refuses unless
        # the witness is present and its diff re-derives empty.
        license = RevLicense(git_clean_by_chunk=git_clean_by_chunk_from_manifests(
            manifests_dir if manifests_dir is not None
            else CAMPAIGN / "chunks" / "manifests", stratum))
    report = {
        "schema": SCHEMA, "run_id": RUN_ID, "stratum": stratum,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "chunks_root": str(chunks_root), "out_dir": str(out_dir),
        "positions_dir": str(positions_dir),
        "chunks_found": sorted(cdirs),
        "expected_legs": {k: len(v) for k, v in sorted(expected.items())},
        "judges": list(judges), "dry_run": bool(dry_run),
        "legs": {}, "problems": [], "ok": False,
        "n_records_copied": 0, "n_records_present": 0,
    }
    if not cdirs:
        report["problems"].append(f"no chunk dirs under {chunks_root}")
        return report

    for judge in judges:
        for leg_key, want in sorted(expected.items()):
            profile, leg_tag = leg_key.split("/leg")
            dst_leg = out_dir / judge / profile / f"leg{leg_tag}"
            dst_records = dst_leg / "records"
            owner: dict = {}
            dupes, mismatched = [], []
            copied = 0

            for k in sorted(cdirs):
                src_records = cdirs[k] / judge / profile / f"leg{leg_tag}" / "records"
                if not src_records.is_dir():
                    continue
                for f in sorted(src_records.glob("*.json")):
                    rid = f.stem                       # ⚠️ NEVER opened for values
                    if rid in owner:
                        dupes.append({"rid": rid, "chunks": [owner[rid][0], k]})
                        if _sha256_file(owner[rid][1]) != _sha256_file(f):
                            mismatched.append(rid)
                        continue
                    owner[rid] = (k, f)
                    if not dry_run:
                        dst_records.mkdir(parents=True, exist_ok=True)
                        target = dst_records / f.name
                        if target.exists() and _sha256_file(target) == _sha256_file(f):
                            pass                       # idempotent re-merge
                        else:
                            shutil.copy2(f, target)
                            copied += 1

            got = set(owner)
            missing = sorted(want - got)
            extra = sorted(got - want)
            leg_report = {
                "n_expected": len(want), "n_present": len(got),
                "n_copied": copied,
                "n_missing": len(missing), "missing": missing[:20],
                "n_extra": len(extra), "extra": extra[:20],
                "n_duplicate": len(dupes), "duplicates": dupes[:20],
                "n_duplicate_bytes_differ": len(mismatched),
                "duplicates_bytes_differ": mismatched[:20],
                "by_chunk": {str(k): sum(1 for v in owner.values() if v[0] == k)
                             for k in sorted(cdirs)},
                "ok": not missing and not extra and not dupes,
            }
            report["legs"][f"{judge}/{leg_key}"] = leg_report
            report["n_records_copied"] += copied
            report["n_records_present"] += len(got)
            if missing:
                report["problems"].append(
                    f"{judge}/{leg_key}: {len(missing)} rid(s) MISSING "
                    f"(first: {missing[:3]})")
            if extra:
                report["problems"].append(
                    f"{judge}/{leg_key}: {len(extra)} rid(s) NOT in the corpus plan "
                    f"(first: {extra[:3]})")
            if dupes:
                report["problems"].append(
                    f"{judge}/{leg_key}: {len(dupes)} DUPLICATE rid(s) across chunks "
                    f"({len(mismatched)} with differing bytes) — a chunk was merged "
                    f"twice or the allocation double-assigned it")

            # ---- per-leg manifest merge ------------------------------------ #
            mans, man_paths = {}, {}
            for k in sorted(cdirs):
                mp = cdirs[k] / judge / profile / f"leg{leg_tag}" / "manifest.json"
                if mp.is_file():
                    mans[k] = json.loads(mp.read_text())
                    man_paths[k] = mp
            if mans:
                try:
                    merged = merge_manifests(mans, allow_varying=allow_varying,
                                             license=license)
                except MergeError as exc:
                    report["problems"].append(f"{judge}/{leg_key}: manifest merge: {exc}")
                    leg_report["manifest_ok"] = False
                    leg_report["manifest_error"] = str(exc)
                else:
                    merged["merge"]["sources"] = {
                        str(k): {"path": str(p), "sha256": _sha256_file(p)}
                        for k, p in sorted(man_paths.items())}
                    merged["merge"]["records_by_chunk"] = leg_report["by_chunk"]
                    leg_report["manifest_ok"] = True
                    if not dry_run:
                        dst_leg.mkdir(parents=True, exist_ok=True)
                        (dst_leg / "manifest.json").write_text(
                            json.dumps(merged, indent=2, sort_keys=True))
            else:
                leg_report["manifest_ok"] = None

            # ---- summary.json: copied VERBATIM, never parsed ---------------- #
            if not dry_run:
                for k in sorted(cdirs):
                    sp = cdirs[k] / judge / profile / f"leg{leg_tag}" / "summary.json"
                    if sp.is_file():
                        dst_leg.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(sp, dst_leg / f"summary_chunk{k}.json")

    if license is not None and license.used:
        report["rev_license"] = {
            "active": True,
            "paths": sorted({r["path"] for r in license.used}),
            "licensed_revs": dict(license.revs),
            "instrument_identity": license.used[0]["instrument_identity"],
            "note": "this stratum's merge SPANS TWO REVS under the enumerated "
                    "D4.11 licence; the instrument diff was re-derived here",
        }
    report["ok"] = not report["problems"]
    return report


def merge_run_manifest(*, stratum: str, manifests_dir: Path, out_path: Path,
                       judges=JUDGES, dry_run: bool = False,
                       allow_varying=(), license=None) -> dict:
    """Merge the per-(judge, chunk) `RUN_MANIFEST_*` files into the single
    `RUN/RUN_MANIFEST_{S1,S2}.json` the READ_RULE addresses."""
    manifests_dir = Path(manifests_dir)
    S = stratum.upper()
    found = {}
    for judge in judges:
        for p in sorted(manifests_dir.glob(f"RUN_MANIFEST_{S}_{judge}_chunk*.json")):
            k = p.name.split("_chunk")[-1][: -len(".json")]
            found[f"{judge}#{k}"] = (p, json.loads(p.read_text()))
    out = {"schema": SCHEMA, "stratum": S, "out_path": str(out_path),
           "n_sources": len(found), "sources": sorted(str(p) for p, _ in found.values()),
           "ok": False, "problems": []}
    if not found:
        out["problems"].append(f"no RUN_MANIFEST_{S}_*_chunk*.json under {manifests_dir}")
        return out
    try:
        merged = merge_manifests(
            {i: m for i, (_, m) in enumerate(
                (v for _, v in sorted(found.items())), start=1)},
            identity_required=RUN_MANIFEST_IDENTITY,
            # these four are recomputed below (union / superset), so a
            # per-invocation difference is expected rather than a defect
            allow_varying=set(allow_varying) | {"judges", "judge_backend",
                                                "r9_by_profile",
                                                "resolved_backend_by_leg"},
            license=license)
    except MergeError as exc:
        out["problems"].append(f"RUN_MANIFEST merge: {exc}")
        return out

    # resolved_backend_by_leg is a UNION across (judge, chunk) invocations —
    # G-BACKEND requires every `tier1-greedy/walled` entry to read `rust`, and no
    # single invocation carries them all.
    union, conflicts = {}, []
    for _, (_p, m) in sorted(found.items()):
        for k, v in (m.get("resolved_backend_by_leg") or {}).items():
            if k in union and union[k] != v:
                conflicts.append({"leg": k, "values": sorted({union[k], v})})
            union[k] = v
    if conflicts:
        out["problems"].append(f"resolved_backend_by_leg CONFLICTS: {conflicts[:5]}")
        return out
    merged["resolved_backend_by_leg"] = dict(sorted(union.items()))
    merged["judges"] = sorted({j for _p, m in found.values()
                               for j in (m.get("judges") or [])})
    merged["judge_backend"] = {}
    for _, (_p, m) in sorted(found.items()):
        merged["judge_backend"].update(m.get("judge_backend") or {})
    merged["merge"]["sources"] = {
        key: {"path": str(p), "sha256": _sha256_file(p)}
        for key, (p, _) in sorted(found.items())}
    merged["merge"]["note"] += (
        " RUN_MANIFEST flavour: resolved_backend_by_leg is the UNION over every "
        "(judge, chunk) invocation — no single invocation carries every leg, and "
        "G-BACKEND quantifies over all of them.")

    if not dry_run:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(json.dumps(merged, indent=2, sort_keys=True))
    out["ok"] = True
    return out


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--stratum", required=True, choices=list(STRATA))
    ap.add_argument("--chunks-root", required=True,
                    help="SHARE/<RUN_ID>/chunks/<stratum>")
    ap.add_argument("--out-dir", required=True, help="SHARE/<RUN_ID>/<stratum>")
    ap.add_argument("--positions-dir", default=None,
                    help="the CORPUS positions dir (default: "
                         "shared_run_r4/corpus/positions_<stratum>) — the "
                         "completeness DENOMINATOR")
    ap.add_argument("--manifests-dir", default=str(CAMPAIGN / "chunks" / "manifests"),
                    help="where run_scoring.sh wrote the per-chunk RUN_MANIFEST_*")
    ap.add_argument("--run-manifest-out", default=None,
                    help="default: shared_run_r4/RUN_MANIFEST_{S1,S2}.json")
    ap.add_argument("--report", default=None,
                    help="default: <campaign>/MERGE_REPORT_<stratum>.json")
    ap.add_argument("--judges", nargs="+", default=list(JUDGES))
    ap.add_argument("--allow-varying", nargs="*", default=[],
                    help="manifest keys allowed to differ across chunks "
                         "(recorded in merge.by_chunk instead of failing)")
    ap.add_argument("--instrument-identity", default=None,
                    help=f"path to {INSTRUMENT_IDENTITY_NAME} (default: "
                         f"RUN/ then the campaign root). ⚠️ NOT a licence: it "
                         f"only says WHERE the witness is. The rev pair is "
                         f"hard-coded and the instrument diff is re-derived.")
    ap.add_argument("--repo", default=str(REPO),
                    help="repo the instrument diff is re-derived in")
    ap.add_argument("--dry-run", action="store_true",
                    help="report only: copy nothing, write nothing")
    ap.add_argument("--no-run-manifest", action="store_true",
                    help="skip the RUN_MANIFEST merge (leg merge only)")
    return ap


def main(argv=None) -> int:
    a = build_arg_parser().parse_args(argv)
    stratum = a.stratum
    positions_dir = Path(a.positions_dir or (RUN_DIR / "corpus" / f"positions_{stratum}"))
    report_path = Path(a.report or (CAMPAIGN / f"MERGE_REPORT_{stratum}.json"))

    license = RevLicense(
        repo=Path(a.repo), identity_path=a.instrument_identity,
        git_clean_by_chunk=git_clean_by_chunk_from_manifests(a.manifests_dir,
                                                             stratum))

    rep = merge_stratum(stratum=stratum, chunks_root=Path(a.chunks_root),
                        out_dir=Path(a.out_dir), positions_dir=positions_dir,
                        judges=tuple(a.judges), dry_run=a.dry_run,
                        allow_varying=a.allow_varying, license=license,
                        manifests_dir=Path(a.manifests_dir))

    if not a.no_run_manifest and not rep["problems"]:
        out_path = Path(a.run_manifest_out or (RUN_DIR / RUN_MANIFEST_NAME[stratum]))
        rm = merge_run_manifest(stratum=stratum, manifests_dir=Path(a.manifests_dir),
                                out_path=out_path, judges=tuple(a.judges),
                                dry_run=a.dry_run, allow_varying=a.allow_varying,
                                license=license)
        rep["run_manifest"] = rm
        rep["problems"].extend(rm["problems"])
        rep["ok"] = not rep["problems"]

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(rep, indent=1) + "\n")

    print(json.dumps({k: v for k, v in rep.items() if k != "legs"}, indent=1))
    for name, leg in sorted(rep["legs"].items()):
        flag = "ok" if leg["ok"] else "FAIL"
        print(f"[merge] {flag:4s} {name}: present={leg['n_present']}/"
              f"{leg['n_expected']} copied={leg['n_copied']} "
              f"missing={leg['n_missing']} extra={leg['n_extra']} "
              f"dupes={leg['n_duplicate']} by_chunk={leg['by_chunk']}")
    print(f"[merge] report -> {report_path}")

    if not rep["ok"]:
        print(f"\n[merge] FATAL: {len(rep['problems'])} problem(s) — "
              f"the merged tree is NOT complete. DO NOT ANALYSE.", file=sys.stderr)
        for p in rep["problems"]:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"[merge] COMPLETE — every rid present exactly once on every leg, "
          f"both judges.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
