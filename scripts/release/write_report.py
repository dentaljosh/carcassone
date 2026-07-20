#!/usr/bin/env python3
"""Generate measurement/release_audit_<date>/REPORT.md from the F1 audit artifacts
(pytest.xml + replay.json). Invoked by scripts/release_audit.sh; reads its env."""
from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(os.environ["CARC_REPORT_OUT"])
PYTEST_RC = int(os.environ.get("CARC_REPORT_PYTEST_RC", "1"))
REPLAY_RC = int(os.environ.get("CARC_REPORT_REPLAY_RC", "1"))

# Property -> the test module that guards it (for the per-property table).
PROPERTY_MODULES = {
    "dual-farm / same-city terminal scoring (P1-L5)": "test_farm_scoring",
    "crop boundary strict mode (P1-R1)": "test_crop_boundary",
    "legal-cache / state-key collisions (P1-R7/S6)": "test_key_collision",
    "rotation-alias canonicalization (P1-A3)": "test_rotation_alias",
    "deck canonicalization / no hidden-order leak (CL-056)": "test_deck_canonicalization",
    "current-tile / bag invariants": "test_bag_invariants",
    "result-sign semantics (won_by_champ/diff)": "test_sign_semantics",
    "factory manifest golden + hash dialects": "test_factory_manifest",
}


def _parse_pytest(xml_path: Path):
    """Return {module: (n_total, n_fail)} and (total, failed) from a junit xml."""
    per_mod: dict[str, list[int]] = {}
    total = failed = 0
    if not xml_path.is_file():
        return per_mod, (0, 0)
    root = ET.parse(xml_path).getroot()
    for tc in root.iter("testcase"):
        cls = tc.get("classname", "")
        mod = cls.split(".")[-1] if "." in cls else cls
        mod = mod.split("::")[0]
        bad = any(c.tag in ("failure", "error") for c in tc)
        per_mod.setdefault(mod, [0, 0])
        per_mod[mod][0] += 1
        per_mod[mod][1] += int(bad)
        total += 1
        failed += int(bad)
    return per_mod, (total, failed)


def main() -> int:
    per_mod, (total, failed) = _parse_pytest(OUT / "pytest.xml")
    replay = {}
    rp = OUT / "replay.json"
    if rp.is_file():
        replay = json.loads(rp.read_text())

    overall = "PASS" if (PYTEST_RC == 0 and REPLAY_RC == 0) else "FAIL"
    lines = [
        f"# F1 release-integrity audit — {overall}",
        "",
        f"Generated {datetime.now(timezone.utc).isoformat()} by `scripts/release_audit.sh`.",
        "Gate: **zero semantic/configuration divergences** before any headline claim. "
        "Re-run after any leaf/search/config change touching the champion.",
        "",
        "## Property suite (`tests/release/`)",
        "",
        "| Property | Module | Tests | Result |",
        "|---|---|---:|---|",
    ]
    for prop, mod in PROPERTY_MODULES.items():
        n, nf = per_mod.get(mod, [0, 0])
        res = "n/a" if n == 0 else ("PASS" if nf == 0 else f"**FAIL ({nf})**")
        lines.append(f"| {prop} | `{mod}` | {n} | {res} |")
    lines += [
        "",
        f"**Suite total: {total - failed}/{total} passed** (pytest rc={PYTEST_RC}). "
        f"Full log: `pytest.log` / `pytest.xml`.",
        "",
        "## Adversarial state replay (`scripts/release/replay_audit.py`)",
        "",
    ]
    if replay:
        lines += [
            f"- **Result: {'PASS' if replay.get('ok') else 'FAIL'}** (rc={REPLAY_RC})",
            f"- Corpus source: `{replay.get('corpus_source', '?')}`",
            f"- States replayed: **{replay.get('n_states', 0)}** "
            f"({replay.get('n_prod_games', 0)} production + "
            f"{replay.get('n_synthetic_games', 0)} synthetic games); "
            f"by source {replay.get('states_by_source', {})}",
            f"- Strict-window drops — **production (GATED): "
            f"{replay.get('strict_window_failures_production', 0)}** | "
            f"synthetic (adversarial probe): {replay.get('strict_window_failures_synthetic', 0)}",
            f"- **Dangerous key collisions (GATED, count-differing): "
            f"{replay.get('dangerous_key_collisions', 0)}**",
            f"- Rotation-alias label fragmentation (P1-A3, benign/measured): "
            f"{replay.get('rotation_alias_fragmentations_p1a3', 0)} "
            f"(built-in detector logs: {replay.get('key_collisions_builtin_detector', 0)})",
            f"- Champion manifest drift mid-run: **{replay.get('manifest_drift', True)}**",
            f"- Champion leaf hash (harness dialect): `{replay.get('leaf_hash_harness', '?')}`",
            f"- Wall: {replay.get('wall_secs', '?')}s. Scope note: {replay.get('note', '')}",
        ]
        if replay.get("failures"):
            lines += ["", "### Replay failures", "```",
                      json.dumps(replay["failures"], indent=1), "```"]
    else:
        lines.append("- replay.json not found (replay step did not complete).")

    lines += [
        "",
        "## Champion of record (governance/PRODUCTION.yaml)",
        "",
        "Verified at construction by `champion_factory.make_production_champion` — leaf proven "
        "on real boards (curve125 values + a leaf-output panel + three hash dialects). "
        "`champion_factory.LEAF_HASH_*` are the runtime-verified fingerprints:",
        "",
        "| Dialect | Hash |",
        "|---|---|",
        "| `_leaf_hash` (harness, meeple_k=2.0) | `a36d2e15a3b3d71d` |",
        "| `_frozen_config_hash` (champ_env, meeple_k=0.0) | `6dfffd57051690f2` |",
        "| `_frozen_config_hash` (meeple_k=2.0) | `158f17ff76adaa02` |",
        "",
        "## Artifacts",
        "",
        "- `pytest.log`, `pytest.xml` — property-suite output",
        "- `replay.json`, `replay.log` — adversarial replay",
        "- `collisions/` — built-in state-key collision detector output (empty on PASS)",
        "",
        "> STATUS wiring: paste the runner's `STATUS one-liner` into STATUS.md at merge-time "
        "close-out (this runner does not edit the live doc).",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n")
    print(f"[write_report] wrote {OUT/'REPORT.md'} ({overall})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
