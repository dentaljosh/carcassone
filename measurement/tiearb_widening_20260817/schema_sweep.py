#!/usr/bin/env python3
"""THE CLASSIFICATION SWEEP — commissioned by §D4.14b (`942e228d`).

Three merge-layer refusals in a row (`execution` → D3, `git_rev`/`code_rev` →
D4.11, `preflight.checks` → D4.14) said the same thing: **the classification was
being built by crashing into it.** This closes the schema BY ENUMERATION instead,
so the fail-closed default changes meaning — after this, an unclassified-key
raise means *a SCHEMA CHANGE, a new emitter field*, not *a field nobody thought
about*.

WHAT IT DOES, per the commission:

  1. ENUMERATES FROM THE REAL ARTIFACTS, never from reading code — the
     `RUN_MANIFEST_*` files AND the per-leg manifests of **both emitters**
     (`oracle_score_pilot` writes `execution`; `tier1_rust_leg` writes
     `preflight.wheel` — exactly the schema difference that reading one emitter
     would have missed).
  2. CLASSIFIES every key against the tables wired into `merge_legs.py` — it
     imports them, so the sweep and the merge cannot drift.
  3. MEASURES the OBSERVED DIVERGENCE AXIS per key (none / leg / chunk / judge /
     box / tranche / invocation) from the artifacts, so a classification is a
     measurement rather than an opinion.
  4. FLAGS every gate-addressed dotted path AND ASSERTS THE CONVERSE — that every
     gate-addressed path named in the READ_RULEs EXISTS in the enumerated schema.
     That converse is the check that would have caught `G-SALT`'s primary being
     audited at neither pass.
  5. IS RE-RUNNABLE: `SCHEMA_SWEEP.md` + `SCHEMA_SWEEP.json`, so the next schema
     change DIFFS mechanically instead of refusing at merge time.

⚠️ It reads artifacts and writes only its own two output files. It opens no
record, computes no statistic, and touches nothing under the prereg dir.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import merge_legs as ML  # noqa: E402  (the classification tables live there, ONCE)

REPO = ML.REPO
CAMPAIGN = ML.CAMPAIGN
SCHEMA = "carcassonne-tiearb-widening-schema-sweep/v1"

#: Blocks `merge_legs` dives INTO. A key under one of these is classified at
#: `<prefix>.<key>`; everything below that is the value.
DIVE_PREFIXES = ("resolved_config", "execution", "champion_manifest",
                 "preflight", "preflight.checks", "preflight.wheel")

#: The axes a value may legitimately be a function of, in the order a reader
#: should prefer them (coarsest/most benign first).
AXES = ("leg", "chunk", "judge", "box", "tranche", "kind")

CLASSES = ("IDENTITY_REQUIRED", "AGGREGATE_SUM", "AGGREGATE_UNION", "PER_CHUNK",
           "JUDGE_SCOPED_IDENTITY", "LICENCE_GOVERNED", "TELEMETRY",
           "RECOMPUTED", "NESTED", "UNCLASSIFIED")

#: `merge_run_manifest` recomputes these four as a union/superset across the
#: (judge, chunk) invocations, so their per-invocation difference is expected
#: rather than a defect. Named here so the sweep does not mis-report them as
#: identity-required keys that would refuse.
RUN_MANIFEST_RECOMPUTED = frozenset({"judges", "judge_backend", "r9_by_profile",
                                     "resolved_backend_by_leg"})

#: A class that TOLERATES divergence. Anything else refuses when it differs, so
#: the sweep can tell the reader which rows would refuse on today's artifacts.
TOLERANT = {"PER_CHUNK", "AGGREGATE_SUM", "AGGREGATE_UNION", "TELEMETRY",
            "LICENCE_GOVERNED", "RECOMPUTED", "NESTED"}


# --------------------------------------------------------------------------- #
# 1. enumerate the real artifacts                                              #
# --------------------------------------------------------------------------- #
def load_sources(run_manifests, legs_roots) -> list:
    """[{kind, judge, chunk, leg, box, tranche, path, doc}] from REAL files."""
    lic = ML.RevLicense()
    out = []

    d = Path(run_manifests)
    for p in sorted(d.glob("RUN_MANIFEST_*_chunk*.json")) if d.is_dir() else ():
        m = re.match(r"RUN_MANIFEST_(S\d)_(.+)_chunk(\d+)\.json$", p.name)
        if not m:
            continue
        doc = json.loads(p.read_text())
        out.append({"kind": "RUN_MANIFEST", "stratum": m.group(1),
                    "judge": m.group(2), "chunk": int(m.group(3)), "leg": None,
                    "path": str(p), "doc": doc})

    # ⚠️ The MERGED artifact is what the gates actually address
    # (`RUN/RUN_MANIFEST_{S1,S2}.json`), and it is NOT written by `merge_legs`
    # alone: `c_remeasure.py` merges its own gate-addressed block into the same
    # file. Enumerating it separately is what makes the converse check honest —
    # otherwise `c_remeasure.*` reads as a missing address when in truth it is a
    # key contributed by another tool.
    for p in sorted(Path(ML.RUN_DIR).glob("RUN_MANIFEST_*.json")):
        if "_chunk" in p.name:
            continue
        try:
            doc = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        out.append({"kind": "RUN_MANIFEST_MERGED", "stratum": p.stem[-2:],
                    "judge": None, "chunk": None, "leg": None,
                    "path": str(p), "doc": doc})

    for root in legs_roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for p in sorted(root.glob("chunk*/*/*/leg*/manifest.json")):
            rel = p.relative_to(root).parts       # chunk<k>/<judge>/<prof>/leg<N>
            try:
                chunk = int(rel[0][len("chunk"):])
                leg = int(rel[3][len("leg"):])
            except (ValueError, IndexError):
                continue
            doc = json.loads(p.read_text())
            out.append({"kind": "leg", "stratum": None, "judge": rel[1],
                        "chunk": chunk, "leg": leg, "path": str(p), "doc": doc})

    for s in out:
        s["box"] = ML._box_key(s["doc"])[0]
        s["tranche"] = None
        for dotted in ("git_rev", "code_rev", "execution.code_rev",
                       "preflight.checks.git_clean.git_rev"):
            v = ML._get(s["doc"], dotted)
            if v is not ML._MISSING:
                t = lic.tranche_of(v)
                if t:
                    s["tranche"] = t
                    break
    return out


def enumerate_paths(doc: dict) -> dict:
    """{dotted path at the CLASSIFICATION GRAIN: value} for one artifact."""
    out = {}
    for key, val in (doc or {}).items():
        if key in DIVE_PREFIXES and isinstance(val, dict):
            for k2, v2 in val.items():
                sub = f"{key}.{k2}"
                if sub in DIVE_PREFIXES and isinstance(v2, dict):
                    for k3, v3 in v2.items():
                        out[f"{sub}.{k3}"] = v3
                else:
                    out[sub] = v2
        else:
            out[key] = val
    return out


# --------------------------------------------------------------------------- #
# 2. the OBSERVED divergence axis — a measurement, not an opinion              #
# --------------------------------------------------------------------------- #
def observed_axis(rows: list) -> dict:
    """rows = [{axis values…, "value": canon}] for ONE (kind, path).

    Returns the minimal axis (or axis pair) the value is a FUNCTION of. If no
    axis explains it, the value differs per invocation — that is TELEMETRY, and
    saying so is the whole point of measuring rather than assuming.
    """
    values = {r["value"] for r in rows}
    if len(values) <= 1:
        return {"axis": "none", "n_distinct": len(values)}

    def is_function_of(axes):
        seen = {}
        for r in rows:
            k = tuple(r.get(a) for a in axes)
            if k in seen and seen[k] != r["value"]:
                return False
            seen[k] = r["value"]
        return True

    for a in AXES:
        if len({r.get(a) for r in rows}) > 1 and is_function_of((a,)):
            return {"axis": a, "n_distinct": len(values)}
    for i, a in enumerate(AXES):
        for b in AXES[i + 1:]:
            if is_function_of((a, b)):
                return {"axis": f"{a}+{b}", "n_distinct": len(values)}
    return {"axis": "invocation", "n_distinct": len(values)}


# --------------------------------------------------------------------------- #
# 3. classify — reading merge_legs' OWN tables, so the two cannot drift        #
# --------------------------------------------------------------------------- #
def classify(path: str, kind: str) -> dict:
    """(class, why) for a dotted path, mirroring `merge_manifests` exactly."""
    identity = (ML.RUN_MANIFEST_IDENTITY if kind.startswith("RUN_MANIFEST")
                else ML.IDENTITY_REQUIRED)

    def R(cls, why, rule=""):
        return {"class": cls, "why": why, "rule": rule}

    if path in ML.REV_LICENSED_PATHS:
        return R("LICENCE_GOVERNED", "the run's rev under one of its four "
                                     "spellings", "D4.11/D4.12 enumerated pair")
    if kind.startswith("RUN_MANIFEST") and path in RUN_MANIFEST_RECOMPUTED:
        return R("RECOMPUTED", "union / superset across the (judge, chunk) "
                               "invocations — no single invocation carries them "
                               "all, and G-BACKEND quantifies over all of them",
                 "merge_run_manifest")
    if path in identity:
        return R("IDENTITY_REQUIRED", "identity-required path", "IDENTITY_REQUIRED")

    if "." not in path:
        if path in ML.AGGREGATE_SUM:
            return R("AGGREGATE_SUM", "pure counter", "AGGREGATE_SUM")
        if path in ML.AGGREGATE_UNION:
            return R("AGGREGATE_UNION", "set-unioned", "AGGREGATE_UNION")
        if path in ML.PER_CHUNK:
            return R("PER_CHUNK", "legitimately per chunk", "PER_CHUNK")
        if path in DIVE_PREFIXES:
            return R("NESTED", "merged key by key; see its sub-keys", "")
        return R("IDENTITY_REQUIRED", "no merge rule: equal across chunks or "
                                      "RAISE (fail-closed default)", "default")

    head, _, tail = path.rpartition(".")
    if head == "resolved_config":
        if tail in ML.RESOLVED_CONFIG_PER_CHUNK:
            return R("PER_CHUNK", "chunk-scoped run config",
                     "RESOLVED_CONFIG_PER_CHUNK")
        return R("IDENTITY_REQUIRED", "must agree across chunks or RAISE",
                 "_merge_resolved_config default")
    if head == "execution":
        if tail in ML.EXECUTION_PER_CHUNK:
            return R("PER_CHUNK", "BOX-LOCAL — recorded, never compared across "
                                  "hosts (JCZ §0.F.2c)", "EXECUTION_PER_CHUNK")
        if tail in ML.EXECUTION_IDENTITY_REQUIRED:
            return R("LICENCE_GOVERNED", "cross-host source-rev witness; a "
                                         "cross-tranche divergence is licensed "
                                         "only under D4.13's four conjuncts",
                     "EXECUTION_IDENTITY_REQUIRED + D4.13")
        return R("IDENTITY_REQUIRED", "unclassified inside `execution` ⇒ RAISE",
                 "D3 §D3.2 default")
    if head == "champion_manifest":
        return R("IDENTITY_REQUIRED", "a different champion is a different run",
                 "_merge_champion_manifest default")
    if head == "preflight.checks":
        if tail in ML.PREFLIGHT_CHECKS_IDENTITY_REQUIRED:
            return R("IDENTITY_REQUIRED", "design constant / gate-addressed",
                     "D4.14 7/7")
        if tail in ML.PREFLIGHT_CHECKS_JUDGE_SCOPED:
            return R("JUDGE_SCOPED_IDENTITY", "equal WITHIN a judge, ACTIVELY "
                                              "checked; cross-judge not compared",
                     "D4.14 7/7")
        if tail in ML.PREFLIGHT_CHECKS_LICENCE_GOVERNED:
            return R("LICENCE_GOVERNED", "carried per chunk; ASSERTED by the "
                                         "D4.12 licence (ruled once, not twice)",
                     "D4.14 7/7")
        if tail == "process_census":
            return R("TELEMETRY", "timestamped ps+loadavg — differs by "
                                  "construction; the emitter itself excludes it "
                                  "from `ok`", "D4.14 7/7 (PER_CHUNK)")
        if tail in ML.PREFLIGHT_CHECKS_PER_CHUNK:
            return R("PER_CHUNK", "chunk-scoped path/flag", "D4.14 7/7")
        return R("UNCLASSIFIED", "outside the CLOSED SET D4.14 enumerated ⇒ a "
                                 "SCHEMA CHANGE", "raise")
    if head == "preflight.wheel":
        if tail == "carc_rs_build":
            return R("LICENCE_GOVERNED", "the tier1 emitter's spelling of the "
                                         "build stamp", "D4.13")
        if tail == "carc_rs_binary_sha":
            return R("PER_CHUNK", "box-local; WITHIN-BOX constancy is a standing "
                                  "assertion", "D4.13 conjunct (ii)")
        return R("IDENTITY_REQUIRED", "unclassified inside `preflight.wheel` ⇒ "
                                      "RAISE", "D4.13 default")
    if head == "preflight":
        if tail in ("checks", "wheel"):
            return R("NESTED", "merged key by key; see its sub-keys", "")
        return R("IDENTITY_REQUIRED", "unclassified inside `preflight` ⇒ RAISE",
                 "_merge_preflight default")
    return R("IDENTITY_REQUIRED", "no merge rule ⇒ RAISE", "default")


# --------------------------------------------------------------------------- #
# 4. gate-addressed paths, and THE CONVERSE                                    #
# --------------------------------------------------------------------------- #
#: `RUN/RUN_MANIFEST_{S1,S2}.json::preflight.checks.leaf_hash.ok` and friends.
#: The tail keeps its braces — `_expand_braces` handles them, including the
#: NESTED form the c-remeasure address uses
#: (`c_remeasure.{legs.{arb,if}.{committed,realized},ok}`), which a naive
#: `\{[^}]*\}` would mis-split and turn into phantom paths.
_ADDR = re.compile(r"([A-Za-z0-9_/{},.<>*-]*\.json)::([A-Za-z0-9_.{},\s]+)")


def _expand_braces(s: str) -> list:
    """`a.{b,c.{d,e}}` -> [a.b, a.c.d, a.c.e]. Depth-aware, so nested groups and
    the commas inside them are not confused with the outer ones."""
    i = s.find("{")
    if i < 0:
        return [s.strip()]
    depth, j = 0, None
    for k in range(i, len(s)):
        if s[k] == "{":
            depth += 1
        elif s[k] == "}":
            depth -= 1
            if depth == 0:
                j = k
                break
    if j is None:                       # unterminated (line-truncated address)
        return [s[:i].strip()]
    alts, buf, depth = [], "", 0
    for ch in s[i + 1:j]:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if ch == "," and depth == 0:
            alts.append(buf)
            buf = ""
        else:
            buf += ch
    alts.append(buf)
    out = []
    for alt in alts:
        out += _expand_braces(s[:i] + alt.strip() + s[j + 1:])
    return out


def read_rule_addresses(read_rules) -> dict:
    """{artifact_kind: {dotted path: [source docs]}} scraped from the READ_RULEs.

    Both pairs are scanned: R4's §2 CARRIES the R3 gate table by reference, so
    the gate addresses of record live in the older file.
    """
    out: dict = {}
    for rr in read_rules:
        rr = Path(rr)
        if not rr.is_file():
            continue
        text = rr.read_text()
        for artifact, tail in _ADDR.findall(text):
            base = Path(artifact).name
            if base.startswith("RUN_MANIFEST"):
                kind = "RUN_MANIFEST"
            elif base == "manifest.json":
                kind = "leg"
            else:
                continue
            for tail_expanded in _expand_braces(tail):
                for path in tail_expanded.split(","):
                    path = path.strip().rstrip(".")
                    if not path or " " in path:
                        continue
                    out.setdefault(kind, {}).setdefault(path, []).append(rr.name)
    return out


def gate_converse(addresses: dict, schema: dict) -> list:
    """⭐ THE CONVERSE: every gate-addressed path must EXIST in the enumerated
    schema. A gate whose address does not exist reads as ABSENT, and absent is
    how `G-SALT`'s primary came to be audited at neither pass."""
    missing = []
    for kind, paths in sorted(addresses.items()):
        present = set(schema.get(kind, set()))
        if kind == "RUN_MANIFEST":
            # the address names the MERGED artifact, whose schema is the
            # per-chunk schema PLUS whatever other tools contribute to it
            present |= set(schema.get("RUN_MANIFEST_MERGED", set()))
        for path in sorted(paths):
            # a gate may address a LEAF below the classification grain
            # (`preflight.checks.leaf_hash.ok`); its prefix must exist
            if any(p == path or path.startswith(p + ".") for p in present):
                continue
            missing.append({"kind": kind, "path": path,
                            "named_in": sorted(set(paths[path]))})
    return missing


# --------------------------------------------------------------------------- #
# the sweep                                                                    #
# --------------------------------------------------------------------------- #
def sweep(run_manifests, legs_roots, read_rules) -> dict:
    sources = load_sources(run_manifests, legs_roots)
    if not sources:
        raise SystemExit("REFUSING: no artifacts found — the sweep enumerates "
                         "from the REAL artifacts, never from reading code")

    by_kind_path: dict = {}
    for s in sources:
        for path, value in enumerate_paths(s["doc"]).items():
            by_kind_path.setdefault((s["kind"], path), []).append({
                "leg": s["leg"], "chunk": s["chunk"], "judge": s["judge"],
                "box": s["box"], "tranche": s["tranche"], "kind": s["kind"],
                "value": ML._canon(value),
            })

    schema_by_kind: dict = {}
    for kind, path in by_kind_path:
        schema_by_kind.setdefault(kind, set()).add(path)

    rows = []
    for (kind, path), obs in sorted(by_kind_path.items()):
        cls = classify(path, kind)
        axis = observed_axis(obs)
        gate = [g for g in ML.GATE_ADDRESSED_PATHS
                if g == path or g.startswith(path + ".")]
        contributed = (kind == "RUN_MANIFEST_MERGED"
                       and path not in schema_by_kind.get("RUN_MANIFEST", set()))
        # ⭐ the column that turns the table into a PRE-FLIGHT: a key whose class
        # does not tolerate divergence, observed diverging, WOULD REFUSE today.
        # ⚠️ a `leg` value that varies ONLY by judge never meets itself in a
        # merge: `merge_stratum` merges one (judge, leg) at a time, so the judge
        # is fixed inside every `merge_manifests` call. Reporting it as a refusal
        # would be a false alarm — the axis is real, the collision is not.
        judge_only = (kind == "leg" and axis["axis"] == "judge")
        would_refuse = (axis["axis"] != "none"
                        and cls["class"] not in TOLERANT
                        and not judge_only
                        and not any(b == path or b.startswith(path + ".")
                                    for b in ML.BUILD_LICENSED_PATHS))
        rows.append({
            "kind": kind, "path": path, "class": cls["class"],
            "contributed_by_another_tool": contributed,
            "would_refuse_on_todays_artifacts": would_refuse,
            "why": cls["why"], "rule": cls["rule"],
            "observed_axis": axis["axis"], "n_distinct": axis["n_distinct"],
            "n_sources": len(obs),
            "judges": sorted({str(o["judge"]) for o in obs}),
            "gate_addressed": bool(gate), "gate_paths": gate,
        })

    addresses = read_rule_addresses(read_rules)
    missing = gate_converse(addresses, schema_by_kind)

    return {
        "schema": SCHEMA,
        "run_id": ML.RUN_ID,
        "deviation": "D4.14b (commissioned)",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "generator": "measurement/tiearb_widening_20260817/schema_sweep.py",
        "n_sources": len(sources),
        "sources_by_kind": {k: sum(1 for s in sources if s["kind"] == k)
                            for k in sorted({s["kind"] for s in sources})},
        "judges": sorted({str(s["judge"]) for s in sources}),
        "chunks": sorted({str(s["chunk"]) for s in sources}),
        "tranches": sorted({str(s["tranche"]) for s in sources}),
        "boxes": sorted({str(s["box"]) for s in sources}),
        "rows": rows,
        "unclassified": [r for r in rows if r["class"] == "UNCLASSIFIED"],
        "would_refuse": [r for r in rows if r["would_refuse_on_todays_artifacts"]],
        "gate_addressed_in_read_rule": {k: sorted(v) for k, v in addresses.items()},
        "gate_addresses_missing_from_schema": missing,
        "governance": "Measurement plumbing only. Opens no record, computes no "
                      "statistic, writes nothing under the prereg dir.",
    }


def to_markdown(doc: dict) -> str:
    L = []
    A = L.append
    A("# SCHEMA SWEEP — the merge layer's classification, closed by enumeration")
    A("")
    A(f"*Generated `{doc['generated_utc']}` by `{doc['generator']}` — "
      f"**re-runnable**: re-run it and diff, do not hand-edit.*")
    A("")
    A("**Commissioned by [`DEVIATIONS.md` §D4.14b](DEVIATIONS.md).** Three "
      "merge refusals in a row (`execution` → D3, `git_rev`/`code_rev` → D4.11, "
      "`preflight.checks` → D4.14) meant the classification was being built by "
      "crashing into it. Enumerating it closes the schema, and the fail-closed "
      "default changes meaning: an unclassified-key raise now means **a schema "
      "change — a new emitter field**, which is exactly what should raise.")
    A("")
    A(f"**Enumerated from {doc['n_sources']} REAL artifacts** "
      + ", ".join(f"{v} × {k}" for k, v in sorted(doc["sources_by_kind"].items()))
      + f" · judges {doc['judges']} · chunks {doc['chunks']} · boxes "
      f"{doc['boxes']} · tranches {doc['tranches']}.")
    A("")
    A("Both emitters are covered: `oracle_score_pilot` writes `execution`, "
      "`tier1_rust_leg` writes `preflight.wheel` — reading one would have "
      "missed the other, which is why the commission says *enumerate from the "
      "artifacts, not from the code*.")
    A("")
    A("**Observed axis** is a MEASUREMENT over those artifacts — the axis the "
      "value is a function of — not an opinion: `none` (never differs) · `leg` "
      "· `chunk` · `judge` · `box` · `tranche` (the two revs) · `invocation` "
      "(differs per run ⇒ telemetry).")
    A("")

    unclassified = doc["unclassified"]
    missing = doc["gate_addresses_missing_from_schema"]
    A(f"- **UNCLASSIFIED keys: {len(unclassified)}**"
      + ("" if unclassified else " — the schema is CLOSED."))
    A(f"- **Gate-addressed paths missing from the schema: {len(missing)}**"
      + ("" if missing else " — the converse HOLDS."))
    A(f"- **Keys that WOULD REFUSE on today's artifacts: "
      f"{len(doc['would_refuse'])}**"
      + ("" if doc["would_refuse"] else " — the merge is clear."))
    for r in doc["would_refuse"]:
        A(f"  - ⛔ `{r['kind']}::{r['path']}` — class {r['class']}, observed "
          f"axis `{r['observed_axis']}`")
    A("")

    for kind in sorted({r["kind"] for r in doc["rows"]}):
        A(f"## `{kind}` artifacts")
        A("")
        A("| path | class | observed axis | n | gate | why |")
        A("|---|---|---|---|---|---|")
        for r in sorted(doc["rows"], key=lambda x: (x["kind"], x["path"])):
            if r["kind"] != kind:
                continue
            gate = "⚠️ **YES**" if r["gate_addressed"] else ""
            why = r["why"]
            if r.get("contributed_by_another_tool"):
                why = ("⭐ **NOT produced by `merge_legs`** — contributed by "
                       "another tool into the same artifact; the merge carries "
                       "it forward rather than overwriting it. " + why)
            A(f"| `{r['path']}` | {r['class']} | {r['observed_axis']} "
              f"({r['n_distinct']}/{r['n_sources']}) | {r['n_sources']} | "
              f"{gate} | {why} |")
        A("")

    A("## Gate-addressed paths named in the READ_RULEs (the CONVERSE check)")
    A("")
    for kind, paths in sorted(doc["gate_addressed_in_read_rule"].items()):
        A(f"- **`{kind}`**: " + ", ".join(f"`{p}`" for p in paths))
    A("")
    if missing:
        A("⛔ **MISSING from the enumerated schema — a gate whose address does "
          "not exist reads as ABSENT, and absent is FAIL:**")
        A("")
        for m in missing:
            A(f"- `{m['kind']}::{m['path']}` (named in {m['named_in']})")
    else:
        A("✅ Every gate-addressed path named in the READ_RULEs EXISTS in the "
          "enumerated schema.")
    A("")
    A("---")
    A("")
    A("*Measurement plumbing only: this sweep opens no record, computes no "
      "statistic, and writes nothing under the prereg dir.*")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run-manifests", default=str(CAMPAIGN / "chunks" / "manifests"))
    ap.add_argument("--legs-root", action="append", default=None,
                    help="SHARE/<RUN_ID>/chunks/<stratum>; repeatable")
    ap.add_argument("--read-rule", action="append", default=None)
    ap.add_argument("--out", default=str(CAMPAIGN / "SCHEMA_SWEEP.md"))
    ap.add_argument("--json", default=str(CAMPAIGN / "SCHEMA_SWEEP.json"))
    a = ap.parse_args(argv)

    legs = a.legs_root or [f"/mnt/c/carc-shared/{ML.RUN_ID}/chunks/s1",
                           f"/mnt/c/carc-shared/{ML.RUN_ID}/chunks/s2"]
    rules = a.read_rule or [CAMPAIGN / "shared_run_r4" / "READ_RULE.md",
                            CAMPAIGN / "shared_run" / "READ_RULE.md"]

    doc = sweep(a.run_manifests, legs, rules)
    Path(a.json).write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    Path(a.out).write_text(to_markdown(doc))

    print(f"[sweep] {doc['n_sources']} artifacts "
          f"({doc['sources_by_kind']}) -> {len(doc['rows'])} (kind, path) rows")
    print(f"[sweep] UNCLASSIFIED: {len(doc['unclassified'])}"
          + ("" if doc["unclassified"] else "  (schema CLOSED)"))
    for r in doc["unclassified"]:
        print(f"[sweep]   ⛔ {r['kind']}::{r['path']} axis={r['observed_axis']}")
    print(f"[sweep] gate addresses missing from schema: "
          f"{len(doc['gate_addresses_missing_from_schema'])}")
    for m in doc["gate_addresses_missing_from_schema"]:
        print(f"[sweep]   ⛔ {m['kind']}::{m['path']} (named in {m['named_in']})")
    print(f"[sweep] -> {a.out}\n[sweep] -> {a.json}")
    return 1 if (doc["unclassified"]
                 or doc["gate_addresses_missing_from_schema"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
