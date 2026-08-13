#!/usr/bin/env python3
"""O0 — the PER-BOX leaf gate for the J-rules dose-0.25 deploy cell.

    <venv python> o0_leaf_gate.py <report.json>

Reads its expectations from the environment (`CELLJSON`, `EXPECT_CAND_HASH`, `CHAMP_HASH`,
`EXPECT_DOSE`, `EXPECT_MASK`, `TRAP_HASH`) so the SAME file runs on every box, and must be
invoked under the launcher env canon (`scripts/classical_search/menu_fair_cell.sh`'s export
block). Exit 0 = all gates pass.

⚠️ THE POINT OF THIS FILE IS THAT "THE CANDIDATE HASH MOVED" IS NOT A GATE.
`_LEAF_HASH_EXCLUDE_IF_DEFAULT` drops a field from the hashed dict only while it holds its
DEFAULT value, so a `{"jrules_dose": 0.0, "jrules_mask": 27}` leaf hashes to
`92ac0da996e1b37b` — which is NOT the champion's `a36d2e15a3b3d71d` — while computing a
leaf that is bit-identical to the champion's. A cell wired that way would pass every
"cand_hash_moves" check ever written and run **champion-vs-champion**, producing a
beautiful, meaningless null that reads as *"the anchor's strategy is worth nothing"* rather
than *"it never ran"*. The gate that proves the term is live is **O0e: the RESOLVED
`jrules_dose` VALUE**. O0h reproduces the trap hash on this box so O0e is demonstrably
load-bearing rather than merely asserted.

Referenced by: DEPLOY_PREREG.md §3, §6 N0 · DESIGN.md §9 pre-flight item 4, §11 G4.
Contains no strength statistic and touches no governance file.
"""
from __future__ import annotations

import dataclasses as _dc
import json
import os
import sys

REPO = "/home/doctor/projects/carcassone"
CURVE125 = [-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    out_path = sys.argv[1]

    sys.path.insert(0, os.path.join(REPO, "scripts", "classical_search"))
    from c5_leaf_override import _leaf_hash, _load_cand_leaf_cfg          # noqa: E402
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG            # noqa: E402

    cellp = os.environ["CELLJSON"]
    expect_cand = os.environ["EXPECT_CAND_HASH"]
    champ_exp = os.environ["CHAMP_HASH"]
    expect_dose = float(os.environ["EXPECT_DOSE"])
    expect_mask = int(os.environ["EXPECT_MASK"])
    trap_exp = os.environ["TRAP_HASH"]

    with open(cellp) as fh:
        raw = json.load(fh)
    cfg = _load_cand_leaf_cfg(cellp)
    champ = _leaf_hash(DEFAULT_CONFIG)
    cand = _leaf_hash(cfg)
    trap = _leaf_hash(_dc.replace(DEFAULT_CONFIG, jrules_dose=0.0, jrules_mask=27))

    gates: list[dict] = []
    ok = True

    def chk(name: str, cond: bool, observed, why: str = "") -> None:
        nonlocal ok
        ok &= bool(cond)
        gates.append({"gate": name, "ok": bool(cond), "observed": observed, "why": why})

    chk("O0a_env_canon_is_champion", champ == champ_exp, champ,
        "DEFAULT_CONFIG must resolve to the champion IN THIS PROCESS. If it does not, the "
        "env canon was mangled and every other hash below is meaningless.")
    chk("O0b_cand_leaf_hash_is_preregistered", cand == expect_cand, cand,
        "DEPLOY_PREREG.md section 3 and branch N0 commit to this exact hash.")
    chk("O0c_cand_hash_moves_off_champion", cand != champ, cand,
        "NECESSARY BUT NOT SUFFICIENT — see O0e. Kept because a candidate that equals the "
        "champion is a different (and equally fatal) failure.")
    chk("O0d_cell_json_content_verbatim",
        raw == {"jrules_dose": 0.25, "v29_meeple_curve": CURVE125}, raw,
        "DEPLOY_PREREG.md section 3 registers the cell BY CONTENT: curve125 verbatim (a "
        "no-op, proved not assumed) and nothing else. Any other content is a different cell "
        "and voids the pre-registration.")
    chk("O0e_resolved_dose_is_LIVE", float(cfg.jrules_dose) == expect_dose, cfg.jrules_dose,
        "THE MOVED-HASH TRAP, AND THE GATE THAT DEFEATS IT. A {dose 0.0, mask 27} leaf "
        "hashes AWAY from the champion yet computes the champion's leaf, so it passes O0c "
        "while running champion-vs-champion. Only the RESOLVED DOSE VALUE proves the term "
        "is live.")
    chk("O0f_mask_holds_default_31", int(cfg.jrules_mask) == expect_mask, cfg.jrules_mask,
        "N0: the absent key must resolve to 31 (JR_ALL = J1|J2|J5|J6|J8).")
    chk("O0g_no_jrules_mask_key_in_cell_json", "jrules_mask" not in raw, sorted(raw),
        "N0 / DESIGN O4': the key is omitted so a mask typo cannot silently ablate rules.")
    chk("O0h_trap_hash_reproduces_on_this_box", trap == trap_exp, trap,
        "The trap is REPRODUCED, not assumed. This proves the {dose 0, mask 27} leaf really "
        "does hash away from the champion on THIS box — i.e. that O0e is load-bearing here.")

    report = {
        "gate": "O0 (per-box leaf gate)",
        "cell_json": cellp,
        "host": os.uname().nodename,
        "all_gates_pass": ok,
        "champion_leaf_hash": champ,
        "cand_leaf_hash": cand,
        "moved_hash_trap_hash": trap,
        "resolved_jrules_dose": cfg.jrules_dose,
        "resolved_jrules_mask": cfg.jrules_mask,
        "cell_json_content": raw,
        "gates": gates,
        "note": "WIRING ONLY — contains no strength statistic by design.",
    }
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w") as fh:
        fh.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in
                      ("all_gates_pass", "champion_leaf_hash", "cand_leaf_hash",
                       "moved_hash_trap_hash", "resolved_jrules_dose",
                       "resolved_jrules_mask")}))
    for g in gates:
        if not g["ok"]:
            print(f"[O0] FAIL {g['gate']}: observed {g['observed']!r} — {g['why']}",
                  file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
